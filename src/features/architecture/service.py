"""Architecture graph generation.

Code builds the structure (layers -> folders -> files, edges from real imports).
The LLM writes descriptions, and optionally resolves the layer of folders the keyword
rules could not place. It can never change the graph structure.

Tree: root (system) -> layers ("feature") -> folders ("component") -> ... -> files ("file")
Every node has `children` and `edges` between those children.
"""
import asyncio
import json
import logging
import os
import re
from collections import Counter, defaultdict
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.features.ai.bedrock import invoke_qwen
from src.features.architecture.repository import ArchitectureResultRepository
from src.features.architecture.schema import (
    ArchNode,
    ArchitectureGraphResponse,
)
from src.features.github.repository import (
    ConnectedRepositoryRepository,
    FileDependencyRepository,
    RepositoryFileRepository,
)

logger = logging.getLogger("api-main.ai.service")

MAX_GROUPS = 24          # max sibling folders on one level; extra folders are nested under "N more folders"
BUNDLE_MIN = 4           # this many loose files next to folders are bundled into one "<dir> files" node
CONCURRENCY = 8          # parallel LLM calls
MAX_DESCRIBED = 60       # describe the largest N non-file nodes; others keep a fallback
MAX_FILES_IN_PROMPT = 25
MAX_DIRS_PER_PLACEMENT_CALL = 40
MAX_FILES_PER_DIR_IN_PLACEMENT = 8
PLACEMENT_DEADLINE = 40  # seconds; on timeout the heuristic placement is kept
# Kept under the gunicorn worker timeout. Structure is built before this clock
# matters, so a timeout only costs some descriptions.
DESCRIBE_DEADLINE = 200

SYSTEM_PROMPT = """You are a senior software engineer explaining a codebase to a new developer.
Describe only what the file names, folder names and dependencies you are given support. Never name
frameworks, services or technologies that do not appear in them, and never guess at coupling or quality.
Folder and feature names (for example "storybook" or "architecture") are this project's own domain terms,
not the well-known tools of the same name. Be specific and concrete; reference real file names.
Respond with valid JSON only, no markdown."""

# ---------------------------------------------------------------------------
# 1. Layer classification (deterministic, with an optional LLM pass for unknowns)
# ---------------------------------------------------------------------------

# (id, label, default description). Order = order in the system map.
LAYERS = [
    ("ui", "UI / Frontend", "User-facing screens and components."),
    ("api", "API", "HTTP entry points: routes, controllers and request/response schemas."),
    ("services", "Business Logic", "Core application logic, workflows and agents."),
    ("data", "Data & Storage", "Models, database access and persistence."),
    ("external", "External Services", "Clients and integrations with third-party systems."),
    ("infra", "Infrastructure & Tooling", "Terraform, Docker, Nginx, scripts and project-level configuration."),
    ("shared", "Shared & Config", "Utilities, configuration and cross-cutting helpers."),
    ("tests", "Tests", "Automated tests."),
]
_ORDER = {lid: i for i, (lid, _, _) in enumerate(LAYERS)}
_LAYER_IDS = set(_ORDER)

_KEYWORDS = {
    "tests": "test tests testing spec specs conftest e2e",
    "ui": "ui frontend components component pages page screens views templates static styles css hooks",
    "api": "api router routers route routes controller controllers endpoint endpoints "
           "handler handlers schema schemas dto main server wsgi asgi",
    "data": "model models db database repository repositories repo dao orm entity entities "
            "migration migrations store sql",
    "external": "client clients integration integrations sdk gateway adapter adapters "
                "bedrock s3 aws stripe sentry email smtp sms",
    "services": "service services usecase usecases domain core logic business "
                "worker workers task tasks job jobs engine "
                "agent agents learn learning pipeline pipelines workflow workflows orchestrator",
    "shared": "util utils helper helpers common config settings constants lib logging middleware auth",
}
_TOKEN_LAYER = {tok: layer for layer, words in _KEYWORDS.items() for tok in words.split()}
_UI_EXT = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".html"}


def _split_tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


# Infrastructure & tooling: decided from the path alone, before any keyword matching,
# so e.g. terraform/**/main.tf or nginx/test-config.sh can never be mistaken for app code.
_INFRA_DIRS = {
    "terraform", "docker", "nginx", "workers", "scripts", "infra", "infrastructure",
    "deploy", "deployment", "k8s", "helm", ".github", ".circleci", "notebooks", "docs", "outputs",
}
_INFRA_EXT = {".tf", ".tfvars", ".hcl", ".tmpl", ".ipynb"}
_INFRA_NAMES = {
    "dockerfile", "makefile", "gunicorn.conf.py", ".gitignore", ".dockerignore",
    ".env.example", "tfplan", "procfile",
}
_ROOT_CONFIG_EXT = {".yml", ".yaml", ".toml", ".ini", ".cfg", ".lock", ".md", ".json", ".sh", ".txt"}


def _is_infra(path: str) -> bool:
    parts = path.split("/")
    name = parts[-1].lower()
    ext = os.path.splitext(name)[1]
    if len(parts) > 1 and parts[0].lower() in _INFRA_DIRS:
        return True
    if name in _INFRA_NAMES or ext in _INFRA_EXT or name.startswith("docker-compose"):
        return True
    return len(parts) == 1 and ext in _ROOT_CONFIG_EXT  # root-level config such as pyproject.toml


def _layer_by_path(path: str) -> str | None:
    if _is_infra(path):
        return "infra"
    parts = path.split("/")
    stem, ext = os.path.splitext(parts[-1])
    if ext.lower() in _UI_EXT:
        return "ui"
    # filename is the most specific signal, then folders deepest to shallowest
    tokens = _split_tokens(stem)
    for d in reversed(parts[:-1]):
        tokens += _split_tokens(d)
    for tok in tokens:
        if tok in _TOKEN_LAYER:
            return _TOKEN_LAYER[tok]
    return None


def _classify_files(files: list[str], pairs: list[tuple[str, str]]) -> tuple[dict[str, str], set[str]]:
    """Return (layer per file, files whose layer was only guessed).

    A file is "guessed" when no keyword matched its path and its layer came from
    neighbour voting or the final default. Those are the ones worth a second opinion.
    """
    layer: dict[str, str | None] = {f: _layer_by_path(f) for f in files}
    guessed: set[str] = {f for f in files if layer[f] is None}

    importers: dict[str, list[str]] = defaultdict(list)  # who imports f
    imported: dict[str, list[str]] = defaultdict(list)   # what f imports
    for s, t in pairs:
        imported[s].append(t)
        importers[t].append(s)
    by_dir: dict[str, list[str]] = defaultdict(list)
    for f in files:
        by_dir[os.path.dirname(f)].append(f)

    # Unknown files take the majority layer of their import neighbours and folder siblings.
    # - "shared" votes are ignored everywhere, because everything imports utils.
    # - "external" is never inherited through imports: a file that *calls* an AI/S3/email
    #   client is not itself an external service. Only folder siblings may vote external.
    for _ in range(3):
        changed = False
        for f in files:
            if layer[f]:
                continue
            votes: Counter[str] = Counter()
            for n in importers[f] + imported[f]:
                vote = layer[n]
                if n != f and vote and vote not in ("shared", "external"):
                    votes[vote] += 1
            for n in by_dir[os.path.dirname(f)]:
                vote = layer[n]
                if n != f and vote and vote != "shared":
                    votes[vote] += 1
            if votes:
                layer[f] = min(votes, key=lambda x: (-votes[x], _ORDER[x]))
                changed = True
        if not changed:
            break

    return {f: layer[f] or "services" for f in files}, guessed


def _placement_prompt(chunk: list[tuple[str, list[str], str]]) -> str:
    layers = "\n".join(f"  {lid}: {label} - {desc}" for lid, label, desc in LAYERS)
    lines = []
    for d, names, guess in chunk:
        shown = ", ".join(names[:MAX_FILES_PER_DIR_IN_PLACEMENT])
        extra = f" (+{len(names) - MAX_FILES_PER_DIR_IN_PLACEMENT} more)" if len(names) > MAX_FILES_PER_DIR_IN_PLACEMENT else ""
        lines.append(f"  {d or '(root)'}: {shown}{extra}  [current guess: {guess}]")
    folders = "\n".join(lines)
    return f"""Assign each folder to exactly one architecture layer.

Layers (use the id):
{layers}

Rules:
- Code that calls an AI model, database, queue or third-party API is still Business Logic;
  only the thin client/wrapper itself is External Services.
- Agents, pipelines, workflows and orchestration are Business Logic.
- Judge by folder and file names only.

Folders:
{folders}

Respond with exactly this JSON, using the folder paths above as keys:
{{"placements": {{"<folder path>": "<layer id>"}}}}"""


async def _refine_guessed(
    files: list[str],
    layer_of: dict[str, str],
    guessed: set[str],
) -> dict[str, str]:
    """Ask the LLM to place folders whose layer was only guessed. Unknown/invalid answers are ignored."""
    by_dir: dict[str, list[str]] = defaultdict(list)
    for f in files:
        by_dir[os.path.dirname(f)].append(f)

    todo: list[tuple[str, list[str], str]] = []
    for d, dfiles in by_dir.items():
        if any(f in guessed for f in dfiles):
            guess = Counter(layer_of[f] for f in dfiles if f in guessed).most_common(1)[0][0]
            todo.append((d, [os.path.basename(f) for f in sorted(dfiles)], guess))
    if not todo:
        return layer_of

    sem = asyncio.Semaphore(CONCURRENCY)
    refined = dict(layer_of)

    async def run(chunk: list[tuple[str, list[str], str]]) -> None:
        async with sem:
            try:
                raw = await asyncio.to_thread(
                    invoke_qwen, prompt=_placement_prompt(chunk), system=SYSTEM_PROMPT, max_tokens=1500
                )
            except Exception as e:
                logger.warning("LLM placement call failed | error=%s", e)
                return
        placements = _parse_obj(raw).get("placements")
        if not isinstance(placements, dict):
            return
        known_dirs = {d for d, _, _ in chunk}
        for d, lid in placements.items():
            if d not in known_dirs and d == "(root)":
                d = ""
            if d not in known_dirs or lid not in _LAYER_IDS:
                continue
            for f in by_dir[d]:
                if f in guessed:  # keyword-matched files are never overridden
                    refined[f] = lid

    chunks = [todo[i:i + MAX_DIRS_PER_PLACEMENT_CALL] for i in range(0, len(todo), MAX_DIRS_PER_PLACEMENT_CALL)]
    await asyncio.gather(*[run(c) for c in chunks])
    return refined


# ---------------------------------------------------------------------------
# 2. Graph building (deterministic)
# ---------------------------------------------------------------------------

def _common_prefix(dirs: list[list[str]]) -> list[str]:
    if not dirs:
        return []
    lo, hi = min(dirs), max(dirs)  # lexicographic min/max bound every other list
    n = 0
    for a, b in zip(lo, hi):
        if a != b:
            break
        n += 1
    return lo[:n]


def _aggregate(pairs, owner: dict[str, str]) -> list[list[str]]:
    """If any file in A imports any file in B, then A -> B."""
    seen: dict[tuple[str, str], None] = {}
    for s, t in pairs:
        a, b = owner.get(s), owner.get(t)
        if a and b and a != b:
            seen[(a, b)] = None
    return [list(k) for k in seen]


def _ensure_connected(ids: list[str], edges: list[list[str]]) -> list[list[str]]:
    """Link disconnected components so the top-level map is one connected graph."""
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        if a in parent and b in parent:
            parent[find(a)] = find(b)

    reps, seen = [], set()
    for i in ids:
        r = find(i)
        if r not in seen:
            seen.add(r)
            reps.append(i)
    return edges + [[a, b] for a, b in zip(reps, reps[1:])]


def _file_node(f: str, label: str | None = None) -> dict:
    return {"id": f, "label": label or f.split("/")[-1], "type": "file", "file_path": f,
            "files": [f], "children": [], "edges": []}


def _group_node(scope: str, path: str, label: str, files: list[str], pairs, force_leaf=False) -> dict:
    fset = set(files)
    inner = [(s, t) for s, t in pairs if s in fset and t in fset]
    kids, kid_edges = _build_level(files, inner, scope, force_leaf)
    return {"id": f"{scope}:{path}", "label": label, "type": "component",
            "files": files, "children": kids, "edges": kid_edges}


def _build_level(files: list[str], pairs, scope: str, force_leaf=False):
    """Return (child nodes, edges between those children) for a set of files.

    Files are grouped by sub-folder whenever they span more than one folder, so identically
    named files from different folders (router.py, schema.py, main.tf ...) are never shown
    side by side in one flat list. Files are only listed directly when they share one folder."""
    dirs = {f: f.split("/")[:-1] for f in files}
    common = _common_prefix(list(dirs.values()))

    groups: dict[tuple, list[str]] = defaultdict(list)
    loose: list[str] = []
    if not force_leaf:
        for f in files:
            d = dirs[f]
            if len(d) > len(common):
                groups[tuple(d[: len(common) + 1])].append(f)
            else:
                loose.append(f)

    if not groups:  # every file is in the same folder: list them
        return [_file_node(f) for f in files], _aggregate(pairs, {f: f for f in files})

    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    if len(ordered) > MAX_GROUPS:
        big, rest = ordered[: MAX_GROUPS - 1], ordered[MAX_GROUPS - 1:]
    else:
        big, rest = ordered, []

    nodes: list[dict] = []
    for key, gfiles in sorted(big, key=lambda kv: kv[0]):
        if len(gfiles) == 1:
            f = gfiles[0]  # keep the folder in the label: "user/service.py", not just "service.py"
            nodes.append(_file_node(f, "/".join(f.split("/")[len(common):])))
        else:
            nodes.append(_group_node(scope, "/".join(key), key[-1], gfiles, pairs))
    if rest:
        more = [f for _, fs in rest for f in fs]
        nodes.append(_group_node(scope, "/".join(common + [f"__more_{len(rest)}__"]), f"{len(rest)} more folders", more, pairs))
    if len(loose) >= BUNDLE_MIN:
        where = common[-1] if common else "root"
        nodes.append(_group_node(scope, "/".join(common + ["__files__"]), f"{where} files", loose, pairs, force_leaf=True))
    else:
        nodes += [_file_node(f) for f in loose]

    owner = {f: n["id"] for n in nodes for f in n["files"]}
    return nodes, _aggregate(pairs, owner)


# --- insights: facts computed from the real import graph, never written by the LLM ---------

def _cycles(ids: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Strongly connected components with more than one member (= circular imports)."""
    out: dict[str, list[str]] = defaultdict(list)
    inn: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        out[a].append(b)
        inn[b].append(a)

    order: list[str] = []
    seen: set[str] = set()
    for s0 in ids:
        if s0 in seen:
            continue
        seen.add(s0)
        stack = [(s0, iter(out[s0]))]
        while stack:
            n, it = stack[-1]
            for m in it:
                if m not in seen:
                    seen.add(m)
                    stack.append((m, iter(out[m])))
                    break
            else:
                order.append(n)
                stack.pop()

    comp: set[str] = set()
    result: list[list[str]] = []
    for s0 in reversed(order):
        if s0 in comp:
            continue
        group, todo = [s0], [s0]
        comp.add(s0)
        while todo:
            n = todo.pop()
            for m in inn[n]:
                if m not in comp:
                    comp.add(m)
                    group.append(m)
                    todo.append(m)
        if len(group) > 1:
            result.append(group)
    return result


def _name_list(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) <= 3:
        return ", ".join(names[:-1]) + (" and " if len(names) > 1 else "") + names[-1]
    return f"{', '.join(names[:3])} and {len(names) - 3} more"


def _add_insights(node: dict) -> None:
    kids = node["children"]
    if node["type"] == "file" or not kids:
        return
    by_id = {k["id"]: k for k in kids}
    pairs = [(a, b) for a, b in node["edges"] if a in by_id and b in by_id and a != b]

    cyc = _cycles([k["id"] for k in kids], pairs)
    if cyc:
        members = set(max(cyc, key=len))
        names = [k["label"] for k in kids if k["id"] in members]
        node["insight"] = f"Circular dependency: {_name_list(names)} import each other."
    else:
        indeg: Counter[str] = Counter(b for _, b in pairs)
        if indeg:
            top, n = indeg.most_common(1)[0]
            if n >= 3 and n >= 0.4 * (len(kids) - 1):
                node["insight"] = f"{by_id[top]['label']} is imported by {n} of its {len(kids) - 1} neighbours."

    for k in kids:
        _add_insights(k)


def _build_architecture(files: list[str], edges: list[dict], layer_of: dict[str, str] | None = None) -> dict:
    files = list(dict.fromkeys(files))
    fset = set(files)
    pairs = list(dict.fromkeys(
        (e["source"], e["target"]) for e in edges
        if e["source"] in fset and e["target"] in fset and e["source"] != e["target"]
    ))

    if layer_of is None:
        layer_of, _ = _classify_files(files, pairs)
    by_layer: dict[str, list[str]] = defaultdict(list)
    for f in files:
        by_layer[layer_of[f]].append(f)

    layer_nodes = []
    for lid, label, desc in LAYERS:
        lfiles = by_layer.get(lid)
        if not lfiles:
            continue
        lset = set(lfiles)
        inner = [(s, t) for s, t in pairs if s in lset and t in lset]
        kids, kid_edges = _build_level(lfiles, inner, lid)
        layer_nodes.append({"id": lid, "label": label, "type": "feature", "description": desc,
                            "files": lfiles, "children": kids, "edges": kid_edges})

    top_edges = _aggregate(pairs, layer_of)
    top_edges = _ensure_connected([n["id"] for n in layer_nodes], top_edges)

    root = {"id": "root", "label": "Architecture", "type": "system", "description": "",
            "files": files, "children": layer_nodes, "edges": top_edges}
    _add_insights(root)
    return root


# ---------------------------------------------------------------------------
# 3. LLM descriptions (labels only; never structure)
# ---------------------------------------------------------------------------

def _parse_obj(raw: str) -> dict:
    try:
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _text(v) -> str:
    return v.strip() if isinstance(v, str) else ""


def _annotate(node: dict) -> None:
    """Attach parent/uses/used_by labels to each child from the real sibling edges."""
    kids = node["children"]
    by_id = {k["id"]: k for k in kids}
    for k in kids:
        k["parent"] = node["label"]
        k["uses"], k["used_by"] = [], []
    for a, b in node["edges"]:
        if a in by_id and b in by_id:
            by_id[a]["uses"].append(by_id[b]["label"])
            by_id[b]["used_by"].append(by_id[a]["label"])
    for k in kids:
        _annotate(k)


def _node_prompt(n: dict, project_context: str) -> str:
    files = n["files"][:MAX_FILES_IN_PROMPT]
    more = len(n["files"]) - len(files)
    file_lines = "\n".join(f"  {f}" for f in files) + (f"\n  ... and {more} more" if more else "")
    context = f"Project context:\n{project_context}\n\n" if project_context else ""
    return f"""{context}Component: {n['label']}  (inside: {n['parent']})
Files ({len(n['files'])}):
{file_lines}
Depends on: {', '.join(dict.fromkeys(n['uses'])) or 'nothing at this level'}
Used by: {', '.join(dict.fromkeys(n['used_by'])) or 'nothing at this level'}

Respond with exactly this JSON:
{{"description": "1-2 plain sentences: what this component is for and where it sits in the system"}}"""


def _summary_prompt(root: dict, project_context: str) -> str:
    labels = {n["id"]: n["label"] for n in root["children"]}
    layers = "\n".join(f"  {n['label']} ({len(n['files'])} files): {n['description']}" for n in root["children"])
    edges = "\n".join(f"  {labels[a]} -> {labels[b]}" for a, b in root["edges"] if a in labels and b in labels)
    context = f"Project context:\n{project_context}\n\n" if project_context else ""
    return f"""{context}Layers of a codebase:
{layers}

Dependencies between layers:
{edges}

Respond with exactly this JSON:
{{"summary": "2-3 sentence plain English overview of what this codebase is and how the layers fit together"}}"""


async def _ask(prompt: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        try:
            raw = await asyncio.to_thread(invoke_qwen, prompt=prompt, system=SYSTEM_PROMPT, max_tokens=300)
        except Exception as e:
            logger.warning("LLM description call failed | error=%s", e)
            return {}
    return _parse_obj(raw)


async def _describe_tree(root: dict, project_context: str = "") -> None:
    """Mutates root in place. Safe to cancel: finished descriptions are kept, the rest have fallbacks."""
    _annotate(root)

    nodes: list[dict] = []

    def walk(n: dict) -> None:
        for c in n["children"]:
            if c["type"] != "file":
                c.setdefault("description", f"{len(c['files'])} files under {c['label']}.")
                nodes.append(c)
                walk(c)

    walk(root)
    nodes.sort(key=lambda n: -len(n["files"]))

    layer_names = ", ".join(n["label"] for n in root["children"])
    root["description"] = f"{len(root['files'])} files organised into these layers: {layer_names}."

    sem = asyncio.Semaphore(CONCURRENCY)

    async def describe_node(n: dict) -> None:
        data = await _ask(_node_prompt(n, project_context), sem)
        if _text(data.get("description")):
            n["description"] = _text(data["description"])

    async def summarise() -> None:
        data = await _ask(_summary_prompt(root, project_context), sem)
        if _text(data.get("summary")):
            root["description"] = _text(data["summary"])

    await asyncio.gather(summarise(), *[describe_node(n) for n in nodes[:MAX_DESCRIBED]])


# ---------------------------------------------------------------------------
# 4. Public entry point (same signature the router already uses)
# ---------------------------------------------------------------------------

def _to_arch(n: dict) -> ArchNode:
    return ArchNode(
        id=n["id"],
        label=n["label"],
        type=n["type"],
        description=n.get("description", ""),
        insight=n.get("insight"),
        file_path=n.get("file_path"),
        children=[_to_arch(c) for c in n.get("children", [])],
        edges=n.get("edges", []),
    )


async def generate_architecture_story(
    files: list[str],
    edges: list[dict],
    max_retries: int = 2,  # unused; kept so existing callers don't break
    project_context: str = "",  # optional: short README excerpt to ground the descriptions
) -> ArchitectureGraphResponse:
    files = list(dict.fromkeys(files))
    fset = set(files)
    pairs = list(dict.fromkeys(
        (e["source"], e["target"]) for e in edges
        if e["source"] in fset and e["target"] in fset and e["source"] != e["target"]
    ))

    layer_of, guessed = _classify_files(files, pairs)
    if guessed:
        try:
            async with asyncio.timeout(PLACEMENT_DEADLINE):
                layer_of = await _refine_guessed(files, layer_of, guessed)
        except asyncio.TimeoutError:
            logger.warning("Placement pass hit %ds deadline; keeping heuristic layers", PLACEMENT_DEADLINE)

    tree = _build_architecture(files, edges, layer_of)
    logger.info(
        "Architecture built | files=%d edges=%d layers=%d guessed=%d",
        len(files), len(edges), len(tree["children"]), len(guessed),
    )

    try:
        async with asyncio.timeout(DESCRIBE_DEADLINE):
            await _describe_tree(tree, project_context[:1500])
    except asyncio.TimeoutError:
        logger.warning("Description pass hit %ds deadline; returning partial descriptions", DESCRIBE_DEADLINE)

    return ArchitectureGraphResponse(summary=tree["description"], root=_to_arch(tree))


# ---------------------------------------------------------------------------
# 5. Repo entry point (used by the API router)
# ---------------------------------------------------------------------------

async def generate_architecture_for_repo(
    db: AsyncSession,
    connected_repo_id: UUID,
    regenerate: bool = False,
) -> ArchitectureGraphResponse:
    """Build (and cache) the architecture story for a connected repo.

    When ``regenerate`` is False an already stored result is returned as-is.
    Otherwise the graph is rebuilt from the repo's indexed files and import
    edges, persisted, and returned."""
    result_repo = ArchitectureResultRepository(db)

    if not regenerate:
        existing = await result_repo.get_latest(connected_repo_id)
        if existing:
            return ArchitectureGraphResponse(**json.loads(existing.graph))

    repo = await ConnectedRepositoryRepository(db).get_by_id(repo_id=connected_repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Connected repository not found.")

    files = [
        f for f in await RepositoryFileRepository(db).get_by_repo(connected_repo_id)
        if not f.is_binary
    ]
    if not files:
        raise HTTPException(status_code=404, detail="No files found for this repository.")

    deps = await FileDependencyRepository(db).get_by_repo(connected_repo_id)
    file_by_id = {f.id: f for f in files}
    edges = [
        {"source": file_by_id[d.source_file_id].path,
         "target": file_by_id[d.target_file_id].path}
        for d in deps
        if d.source_file_id in file_by_id and d.target_file_id in file_by_id
    ]

    context_parts = [p for p in (repo.description, repo.framework, repo.tech_stack) if p]
    project_context = "\n".join(context_parts)

    graph = await generate_architecture_story(
        files=[f.path for f in files],
        edges=edges,
        project_context=project_context,
    )

    await result_repo.upsert_by_repo(
        connected_repo_id=connected_repo_id,
        user_id=repo.user_id,
        graph=graph.model_dump(),
    )
    return graph