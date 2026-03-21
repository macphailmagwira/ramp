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
from src.features.github.schema import (
    FlowEdgeSchema,
    FlowGraphSchema,
    FlowNodeSchema,
)

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.flow_service")

MAX_DEPTH = 10          # maximum BFS hops to prevent runaway graphs
MAX_NODES = 100         # cap node count for large repos


class FlowService:
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
        all_funcs = await self.func_repo.get_by_repo(connected_repo_id)
        all_calls = await self.call_repo.get_by_repo(connected_repo_id)
        all_files = await self.file_repo.get_by_repo(connected_repo_id)
        all_deps  = await self.dep_repo.get_by_repo(connected_repo_id)

        # ---- Build in-memory indexes ----------------------------------
        func_by_id   = {f.id: f for f in all_funcs}
        file_by_id   = {f.id: f for f in all_files}

        # call graph: source_id → [target_id, ...]
        call_graph: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for c in all_calls:
            call_graph[c.source_function_id].append(c.target_function_id)

        # file dep graph: source_file_id → [target_file_id, ...]
        file_dep_graph: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for d in all_deps:
            file_dep_graph[d.source_file_id].append(d.target_file_id)

        # ---- Resolve entry point -------------------------------------
        entry_fn_id = self._resolve_entry(
            all_funcs, all_files,
            entry_function, entry_file, feature_name,
        )

        # ---- BFS from entry point ------------------------------------
        if entry_fn_id:
            fn_nodes, fn_edges = self._bfs_call_graph(
                entry_fn_id, call_graph, func_by_id, file_by_id,
                max_depth=max_depth,
            )
        else:
            # No entry point — return highest out-degree functions overview
            fn_nodes, fn_edges = self._top_level_overview(
                call_graph, func_by_id, file_by_id
            )

        # ---- Enrich with file-level cross-file edges -----------------
        # Find unique files touched by the function nodes
        touched_file_ids: set[uuid.UUID] = {n.file_id for n in fn_nodes if n.file_id}

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

        return FlowGraphSchema(
            entry_point=entry_function or entry_file or feature_name,
            function_nodes=[
                {"id": n.id, "label": n.label, "node_type": n.node_type,
                "file_path": n.file_path, "file_id": str(n.file_id) if n.file_id else None,
                "is_async": n.is_async, "line_start": n.line_start}
                for n in fn_nodes
            ],
            function_edges=[
                {"source": e.source, "target": e.target, "edge_type": e.edge_type}
                for e in fn_edges
            ],
            file_nodes=[
                {"id": n.id, "label": n.label, "node_type": n.node_type,
                "file_path": n.file_path, "file_id": None, "is_async": False, "line_start": None}
                for n in file_nodes
            ],
            file_edges=[
                {"source": e.source, "target": e.target, "edge_type": e.edge_type}
                for e in file_edges
            ],
        )

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
        """Return the id of the best matching starting function."""

        # 1. Direct function name match
        if entry_function:
            exact = [f for f in all_funcs if f.name == entry_function]
            if exact:
                return exact[0].id
            # partial match
            partial = [f for f in all_funcs if entry_function.lower() in f.name.lower()]
            if partial:
                return partial[0].id

        # 2. File path match — return the first function in that file
        if entry_file:
            file_match = next(
                (f for f in all_files if entry_file in f.path), None
            )
            if file_match:
                in_file = [fn for fn in all_funcs if fn.file_id == file_match.id]
                if in_file:
                    return in_file[0].id

        # 3. Feature name — fuzzy search across function names + file paths
        if feature_name:
            needle = feature_name.lower().replace(" ", "_")
            for fn in all_funcs:
                if needle in fn.name.lower():
                    return fn.id
            # try file path
            for f in all_files:
                if needle in f.path.lower():
                    funcs_in = [fn for fn in all_funcs if fn.file_id == f.id]
                    if funcs_in:
                        return funcs_in[0].id

        return None

    def _bfs_call_graph(
        self,
        start_id: uuid.UUID,
        call_graph: dict,
        func_by_id: dict,
        file_by_id: dict,
        max_depth: int,
    ) -> tuple[list[_FnNode], list[_FnEdge]]:
        visited: set[uuid.UUID] = set()
        queue: deque[tuple[uuid.UUID, int]] = deque([(start_id, 0)])
        nodes: list[_FnNode] = []
        edges: list[_FnEdge] = []

        while queue and len(nodes) < MAX_NODES:
            fn_id, depth = queue.popleft()
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

        return nodes, edges

    def _top_level_overview(
        self,
        call_graph: dict,
        func_by_id: dict,
        file_by_id: dict,
    ) -> tuple[list[_FnNode], list[_FnEdge]]:
        """Return the 20 highest out-degree functions as an overview."""
        ranked = sorted(
            func_by_id.keys(),
            key=lambda fid: len(call_graph.get(fid, [])),
            reverse=True,
        )[:20]

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

        return nodes, edges


# ---------------------------------------------------------------------------
# Lightweight dataclasses (avoid Pydantic overhead in inner loops)
# ---------------------------------------------------------------------------


class _FnNode:
    __slots__ = ("id", "label", "node_type", "file_path", "file_id", "is_async", "line_start")

    def __init__(self, *, id, label, node_type, file_path, file_id, is_async, line_start):
        self.id = id
        self.label = label
        self.node_type = node_type
        self.file_path = file_path
        self.file_id = file_id
        self.is_async = is_async
        self.line_start = line_start


class _FnEdge:
    __slots__ = ("source", "target", "edge_type")

    def __init__(self, *, source, target, edge_type):
        self.source = source
        self.target = target
        self.edge_type = edge_type