"""
Generates code-flow traces for a repository.

Given optional entry-point hints (file path, function name, feature name),
it walks:
  1. The function call graph  →  execution path within a file
  2. The file dependency graph  →  cross-file propagation

Returns a FlowGraphSchema ready to be serialised by FastAPI.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict, deque
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX
from src.features.github.repository import (
    FileDependencyRepository,
    FunctionCallRepository,
    RepositoryFileRepository,
    RepositoryFunctionRepository,
)
import json
from src.features.github.schema import FlowEdgeSchema, FlowGraphSchema, FlowNodeSchema


logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.flow_service")

MAX_DEPTH = 10          # maximum BFS hops to prevent runaway graphs
MAX_NODES = 100         # cap node count for large repos


class FlowService:
    """Service that creates a call‑graph/flow representation for a repository.

    The public method ``get_flow`` accepts optional hints (function name,
    file path, or free‑text feature name) that allow callers – typically the
    frontend – to focus the graph on a specific entry point.  If no hint matches,
    a high‑level overview is returned.

    Throughout the implementation a ``logging.Logger`` named
    ``{API_MAIN_LOGGER_NAME_PREFIX}.flow_service`` is used.  The added ``debug``
    statements emit step‑by‑step information that can be observed in the
    terminal when the logger level is set to ``DEBUG`` (e.g. by configuring the
    ``LOG_LEVEL`` environment variable or the ``logging`` configuration in the
    project).  The messages are intentionally concise but include the key data
    that a beginner might want to inspect – counts of loaded records, entry
    resolution results, BFS progression, and the final node/edge totals.
    """
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.file_repo = RepositoryFileRepository(db)
        self.func_repo = RepositoryFunctionRepository(db)
        self.call_repo = FunctionCallRepository(db)
        self.dep_repo = FileDependencyRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_flow(
        self,
        connected_repo_id: uuid.UUID,
        entry_function: Optional[str] = None,   # function name to start from
        entry_file: Optional[str] = None,        # file path to start from
        feature_name: Optional[str] = None,      # free-text hint (best-effort match)
        max_depth: int = MAX_DEPTH,
    ) -> FlowGraphSchema:
        """
        Build and return a flow graph rooted at the best matching entry point.
        Falls back to a top-level overview (highest out-degree nodes) if no
        entry point is specified or matched.
        """
        # ---- Load data ------------------------------------------------
        logger.info("Loading repository data for repo %s", connected_repo_id)
        all_funcs = await self.func_repo.get_by_repo(connected_repo_id)
        logger.debug("Loaded %d functions", len(all_funcs))
        all_calls = await self.call_repo.get_by_repo(connected_repo_id)
        logger.debug("Loaded %d function calls", len(all_calls))
        all_files = await self.file_repo.get_by_repo(connected_repo_id)
        logger.debug("Loaded %d files", len(all_files))
        all_deps  = await self.dep_repo.get_by_repo(connected_repo_id)
        logger.debug("Loaded %d file dependencies", len(all_deps))

        # ---- Build in-memory indexes ----------------------------------
        func_by_id   = {f.id: f for f in all_funcs}
        file_by_id   = {f.id: f for f in all_files}
        logger.info("Indexed %d functions and %d files", len(func_by_id), len(file_by_id))

        # call graph: source_id → [target_id, ...]
        call_graph: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for c in all_calls:
            call_graph[c.source_function_id].append(c.target_function_id)
        logger.debug("Constructed call graph with %d source nodes", len(call_graph))

        # file dep graph: source_file_id → [target_file_id, ...]
        file_dep_graph: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for d in all_deps:
            file_dep_graph[d.source_file_id].append(d.target_file_id)
        logger.debug("Constructed file dependency graph with %d source files", len(file_dep_graph))

        # ---- Resolve entry point -------------------------------------
        entry_fn_id = self._resolve_entry(
            all_funcs, all_files,
            entry_function, entry_file, feature_name,
        )
        logger.info(
            "Resolved entry point: function=%s, file=%s, feature=%s -> id=%s",
            entry_function, entry_file, feature_name, entry_fn_id,
        )


        # ---- BFS from entry point ------------------------------------
        if entry_fn_id:
            logger.info("Starting BFS from function %s (depth limit %d)", entry_fn_id, max_depth)
            fn_nodes, fn_edges = self._bfs_call_graph(
                entry_fn_id, call_graph, func_by_id, file_by_id,
                max_depth=max_depth,
            )
            logger.info("BFS completed: %d function nodes, %d edges", len(fn_nodes), len(fn_edges))
        else:
            # No entry point — return highest out-degree functions overview
            logger.info("No entry point resolved; generating top‑level overview")
            fn_nodes, fn_edges = self._top_level_overview(
                call_graph, func_by_id, file_by_id
            )
            logger.info("Overview generated: %d function nodes, %d edges", len(fn_nodes), len(fn_edges))


        # ---- Enrich with file-level cross-file edges -----------------
        # Find unique files touched by the function nodes
        touched_file_ids: set[uuid.UUID] = {n.file_id for n in fn_nodes if n.file_id}
        logger.info("Touched files count: %d", len(touched_file_ids))

        file_nodes: list[FlowNodeSchema] = []
        file_edges: list[FlowEdgeSchema] = []

        for fid in touched_file_ids:
            f = file_by_id.get(fid)
            if f:
                file_nodes.append(
                    FlowNodeSchema(
                        id=str(fid),
                        label=f.path,
                        node_type="file",
                        file_path=f.path,
                    )
                )
        logger.info("Created %d file nodes", len(file_nodes))

        for src_fid in touched_file_ids:
            for tgt_fid in file_dep_graph.get(src_fid, []):
                if tgt_fid in touched_file_ids:
                    file_edges.append(
                        FlowEdgeSchema(
                            source=str(src_fid),
                            target=str(tgt_fid),
                            edge_type="file_import",
                        )
                    )
        logger.info("Created %d file edges", len(file_edges))

        logger.debug(
            "Returning FlowGraphSchema: %d function nodes, %d function edges, %d file nodes, %d file edges",
            len(fn_nodes), len(fn_edges), len(file_nodes), len(file_edges),
        )

        # Build the FlowGraphSchema object
        graph = FlowGraphSchema(
            entry_point=entry_function or entry_file or feature_name,
            function_nodes=[
                {
                    "id": n.id,
                    "label": n.label,
                    "node_type": n.node_type,
                    "file_path": n.file_path,
                    "file_id": str(n.file_id) if n.file_id else None,
                    "is_async": n.is_async,
                    "line_start": n.line_start,
                    "source_code": func_by_id[uuid.UUID(n.id)].source_code   # ← NEW
                    if n.id and uuid.UUID(n.id) in func_by_id else None,
                }
                for n in fn_nodes
            ],
            function_edges=[
                {"source": e.source, "target": e.target, "edge_type": e.edge_type}
                for e in fn_edges
            ],
            file_nodes=[
                {"id": n.id, "label": n.label, "node_type": n.node_type,
                "file_path": n.file_path, "file_id": None, "is_async": False,
                "line_start": None, "source_code": None}
                for n in file_nodes
            ],
            file_edges=[
                {"source": e.source, "target": e.target, "edge_type": e.edge_type}
                for e in file_edges
            ],
        )
        # Log the full graph when debug logging is enabled
        if logger.isEnabledFor(logging.DEBUG):
            try:
                logger.debug("Full FlowGraph result: %s", json.dumps(graph.dict(), indent=2))
            except Exception as e:
                logger.debug("Failed to serialize FlowGraph for debug logging: %s", e)
        return graph


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_entry(
        self,
        all_funcs,
        all_files,
        entry_function: Optional[str],
        entry_file: Optional[str],
        feature_name: Optional[str],
    ) -> Optional[uuid.UUID]:
        """Pick the *best* function to start the flow graph.

        The method implements a three‑step heuristic:

        1. **Exact/partial function name** – If ``entry_function`` is supplied we
           first look for an exact match on ``Function.name``.  Failing that we
           perform a case‑insensitive ``in`` check to allow partial matches.
        2. **File path** – When a file hint is given we locate the first file
           whose ``path`` contains the supplied string and then choose the first
           function defined in that file.
        3. **Feature name** – As a fallback we treat the free‑text ``feature_name``
           as a loose search term: it is normalised to lower‑case and underscores,
           then compared against function names and file paths.

        The returned ``UUID`` is the id of the selected ``RepositoryFunction``
        record, or ``None`` if nothing matches.  Logging is performed at each
        stage so a beginner can follow the decision process.
        """
        # 1. Direct function name match
        if entry_function:
            logger.debug("Resolving entry by function name: %s", entry_function)
            exact = [f for f in all_funcs if f.name == entry_function]
            if exact:
                logger.debug("Exact function match found: %s", exact[0].id)
                return exact[0].id
            # partial match
            partial = [f for f in all_funcs if entry_function.lower() in f.name.lower()]
            if partial:
                logger.debug("Partial function match found: %s", partial[0].id)
                return partial[0].id

        # 2. File path match — return the first function in that file
        if entry_file:
            logger.debug("Resolving entry by file path: %s", entry_file)
            file_match = next((f for f in all_files if entry_file in f.path), None)
            if file_match:
                in_file = [fn for fn in all_funcs if fn.file_id == file_match.id]
                if in_file:
                    logger.debug("Function %s found in file %s", in_file[0].id, file_match.id)
                    return in_file[0].id

        # 3. Feature name — fuzzy search across function names + file paths
        if feature_name:
            logger.debug("Resolving entry by feature name: %s", feature_name)
            needle = feature_name.lower().replace(" ", "_")
            for fn in all_funcs:
                if needle in fn.name.lower():
                    logger.debug("Feature fuzzy match on function %s", fn.id)
                    return fn.id
            # try file path
            for f in all_files:
                if needle in f.path.lower():
                    funcs_in = [fn for fn in all_funcs if fn.file_id == f.id]
                    if funcs_in:
                        logger.debug("Feature fuzzy match on file %s, picking function %s", f.id, funcs_in[0].id)
                        return funcs_in[0].id

        logger.debug("No entry point resolved for hints: function=%s, file=%s, feature=%s",
                     entry_function, entry_file, feature_name)
        return None

    def _bfs_call_graph(
        self,
        start_id: uuid.UUID,
        call_graph: dict,
        func_by_id: dict,
        file_by_id: dict,
        max_depth: int,
    ) -> tuple[list[_FnNode], list[_FnEdge]]:
        """Depth‑limited Breadth‑First Search over the function call graph.

        * ``start_id`` – UUID of the entry function resolved earlier.
        * ``max_depth`` – Prevents runaway traversals; nodes deeper than this are
          ignored.
        * Returns two lists: ``_FnNode`` objects (function metadata) and
          ``_FnEdge`` objects (call relationships).

        The algorithm tracks visited functions to avoid cycles and respects the
        global ``MAX_NODES`` limit.  Debug logs emit the size of the queue and the
        current depth at each iteration, which is helpful for beginners watching
        the traversal progress.
        """
        visited: set[uuid.UUID] = set()
        queue: deque[tuple[uuid.UUID, int]] = deque([(start_id, 0)])
        nodes: list[_FnNode] = []
        edges: list[_FnEdge] = []

        while queue and len(nodes) < MAX_NODES:
            fn_id, depth = queue.popleft()
            logger.debug("BFS pop: fn_id=%s depth=%d queue_len=%d", fn_id, depth, len(queue))
            if fn_id in visited or depth > max_depth:
                continue
            visited.add(fn_id)

            fn = func_by_id.get(fn_id)
            if not fn:
                continue

            file = file_by_id.get(fn.file_id)
            nodes.append(
                _FnNode(
                    id=str(fn_id),
                    label=fn.qualified_name or fn.name,
                    node_type=fn.symbol_type,
                    file_path=file.path if file else None,
                    file_id=fn.file_id,
                    is_async=fn.is_async,
                    line_start=fn.line_start,
                    source_code=fn.source_code,
                )
            )

            for target_id in call_graph.get(fn_id, []):
                if target_id not in visited:
                    edges.append(
                        _FnEdge(
                            source=str(fn_id),
                            target=str(target_id),
                            edge_type="calls",
                        )
                    )
                    queue.append((target_id, depth + 1))
        logger.debug("BFS finished: visited %d functions, produced %d nodes and %d edges",
                     len(visited), len(nodes), len(edges))
        return nodes, edges


    def _top_level_overview(
        self,
        call_graph: dict,
        func_by_id: dict,
        file_by_id: dict,
    ) -> tuple[list[_FnNode], list[_FnEdge]]:
        """Generate a fallback graph showing the most *influential* functions.

        The method ranks all functions by their out‑degree (number of calls they
        make) and selects the top 20.  It then builds ``_FnNode`` and ``_FnEdge``
        objects for those functions, mirroring the structure produced by the BFS
        path.  Debug logging reports the ranking size and how many edges were
        retained after the filter.
        """
        ranked = sorted(
            func_by_id.keys(),
            key=lambda fid: len(call_graph.get(fid, [])),
            reverse=True,
        )[:20]
        logger.debug("Top‑level overview: selected %d functions by out‑degree", len(ranked))

        nodes = []
        edges = []
        included = set(ranked)

        for fn_id in ranked:
            fn = func_by_id[fn_id]
            file = file_by_id.get(fn.file_id)
            nodes.append(
                _FnNode(
                    id=str(fn_id),
                    label=fn.qualified_name or fn.name,
                    node_type=fn.symbol_type,
                    file_path=file.path if file else None,
                    file_id=fn.file_id,
                    is_async=fn.is_async,
                    line_start=fn.line_start,
                    source_code=fn.source_code,
                )
            )

            for target_id in call_graph.get(fn_id, []):
                if target_id in included:
                    edges.append(
                        _FnEdge(
                            source=str(fn_id),
                            target=str(target_id),
                            edge_type="calls",
                        )
                    )
        logger.debug("Overview generated %d nodes and %d edges", len(nodes), len(edges))
        return nodes, edges



# ---------------------------------------------------------------------------
# Lightweight dataclasses (avoid Pydantic overhead in inner loops)
# ---------------------------------------------------------------------------


class _FnNode:
    __slots__ = ("id", "label", "node_type", "file_path", "file_id", "is_async", "line_start", "source_code")
 
    def __init__(self, *, id, label, node_type, file_path, file_id, is_async, line_start, source_code=None):
        self.id = id
        self.label = label
        self.node_type = node_type
        self.file_path = file_path
        self.file_id = file_id
        self.is_async = is_async
        self.line_start = line_start
        self.source_code = source_code

class _FnEdge:
    __slots__ = ("source", "target", "edge_type")

    def __init__(self, *, source, target, edge_type):
        self.source = source
        self.target = target
        self.edge_type = edge_type