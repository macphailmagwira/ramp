"""Architecture graph generation.

Code builds the structure (layers -> folders -> files, edges from real imports).
The LLM only writes descriptions, so it can't break the graph.

Tree: root (system) -> layers ("feature") -> folders ("component") -> ... -> files ("file")
Every node has `children` and `edges` between those children.
"""
import asyncio
import json
import logging
import os
import re
from collections import Counter, defaultdict

from src.features.ai.bedrock import invoke_qwen
from src.features.architecture.schema import (
    ArchNode,
    ArchitectureGraphResponse,
)

logger = logging.getLogger("api-main.ai.service")

LEAF_MAX = 12            # a group with <= this many files shows files directly
MAX_GROUPS = 12          # max sibling groups on one level; the rest go into "other"
CONCURRENCY = 8          # parallel LLM calls
MAX_DESCRIBED = 60       # describe the largest N non-file nodes; others keep a fallback
MAX_FILES_IN_PROMPT = 25
# Kept under the gunicorn worker timeout. Structure is built before this clock
# matters, so a timeout only costs some descriptions.
DESCRIBE_DEADLINE = 200

SYSTEM_PROMPT = """You are a senior software engineer explaining a codebase to a new developer.
Be specific and concrete; reference real file names. Respond with valid JSON only, no markdown."""

# ---------------------------------------------------------------------------
# 1. Layer classification (deterministic)
# ---------------------------------------------------------------------------

# (id, label, default description). Order = order in the system map.
LAYERS = [
    ("ui", "UI / Frontend", "User-facing screens and components."),
    ("api", "API", "HTTP entry points: routes, controllers and request/response schemas."),
    ("services", "Business Logic", "Core application logic and workflows."),
    ("data", "Data & Storage", "Models, database access and persistence."),
    ("external", "External Services", "Clients and integrations with third-party systems."),
    ("shared", "Shared & Config", "Utilities, configuration and cross-cutting helpers."),
    ("tests", "Tests", "Automated tests."),
]
_ORDER = {lid: i for i, (lid, _, _) in enumerate(LAYERS)}

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
                "worker workers task tasks job jobs engine",
    "shared": "util utils helper helpers common config settings constants lib logging middleware",
}
_TOKEN_LAYER = {tok: layer for layer, words in _KEYWORDS.items() for tok in words.split()}
_UI_EXT = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".html"}


def _split_tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


def _layer_by_path(path: str) -> str | None:
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


def _classify_files(files: list[str], pairs: list[tuple[str, str]]) -> dict[str, str]:
    layer: dict[str, str | None] = {f: _layer_by_path(f) for f in files}

    neighbors: dict[str, list[str]] = defaultdict(list)
    for s, t in pairs:
        neighbors[s].append(t)
        neighbors[t].append(s)
    by_dir: dict[str, list[str]] = defaultdict(list)
    for f in files:
        by_dir[os.path.dirname(f)].append(f)

    # Unknown files take the majority layer of their import neighbours and folder
    # siblings. "shared" votes are ignored because everything imports utils.
    for _ in range(3):
        changed = False
        for f in files:
            if layer[f]:
                continue
            votes: Counter[str] = Counter()
            for n in neighbors[f] + by_dir[os.path.dirname(f)]:
                l = layer[n]
                if n != f and l and l != "shared":
                    votes[l] += 1
            if votes:
                layer[f] = min(votes, key=lambda x: (-votes[x], _ORDER[x]))
                changed = True
        if not changed:
            break

    return {f: layer[f] or "services" for f in files}


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


def _file_node(f: str) -> dict:
    return {"id": f, "label": f.split("/")[-1], "type": "file", "file_path": f,
            "files": [f], "children": [], "edges": []}


def _group_node(scope: str, path: str, label: str, files: list[str], pairs, force_leaf=False) -> dict:
    fset = set(files)
    inner = [(s, t) for s, t in pairs if s in fset and t in fset]
    kids, kid_edges = _build_level(files, inner, scope, force_leaf)
    return {"id": f"{scope}:{path}", "label": label, "type": "component",
            "files": files, "children": kids, "edges": kid_edges}


def _build_level(files: list[str], pairs, scope: str, force_leaf=False):
    """Return (child nodes, edges between those children) for a set of files."""
    dirs = {f: f.split("/")[:-1] for f in files}
    common = _common_prefix(list(dirs.values()))

    groups: dict[tuple, list[str]] = defaultdict(list)
    loose: list[str] = []
    if not force_leaf and len(files) > LEAF_MAX:
        for f in files:
            d = dirs[f]
            if len(d) > len(common):
                groups[tuple(d[: len(common) + 1])].append(f)
            else:
                loose.append(f)

    if not groups:  # leaf level: show the files themselves
        return [_file_node(f) for f in files], _aggregate(pairs, {f: f for f in files})

    ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    if len(ordered) > MAX_GROUPS:
        big, rest = ordered[: MAX_GROUPS - 1], ordered[MAX_GROUPS - 1:]
    else:
        big, rest = ordered, []

    nodes: list[dict] = []
    for key, gfiles in big:
        if len(gfiles) == 1:
            loose.append(gfiles[0])
        else:
            nodes.append(_group_node(scope, "/".join(key), key[-1], gfiles, pairs))
    if rest:
        other = [f for _, fs in rest for f in fs]
        nodes.append(_group_node(scope, "/".join(common + ["__other__"]), "other", other, pairs, force_leaf=True))
    nodes += [_file_node(f) for f in loose]

    owner = {f: n["id"] for n in nodes for f in n["files"]}
    return nodes, _aggregate(pairs, owner)


def _build_architecture(files: list[str], edges: list[dict]) -> dict:
    files = list(dict.fromkeys(files))
    fset = set(files)
    pairs = list(dict.fromkeys(
        (e["source"], e["target"]) for e in edges
        if e["source"] in fset and e["target"] in fset and e["source"] != e["target"]
    ))

    layer_of = _classify_files(files, pairs)
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

    return {"id": "root", "label": "Architecture", "type": "system", "description": "",
            "files": files, "children": layer_nodes, "edges": top_edges}


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


def _node_prompt(n: dict) -> str:
    files = n["files"][:MAX_FILES_IN_PROMPT]
    more = len(n["files"]) - len(files)
    file_lines = "\n".join(f"  {f}" for f in files) + (f"\n  ... and {more} more" if more else "")
    return f"""Component: {n['label']}  (inside: {n['parent']})
Files ({len(n['files'])}):
{file_lines}
Depends on: {', '.join(dict.fromkeys(n['uses'])) or 'nothing at this level'}
Used by: {', '.join(dict.fromkeys(n['used_by'])) or 'nothing at this level'}

Respond with exactly this JSON:
{{"description": "1-2 sentences: what this component does and its role",
  "insight": "one short sharp observation (entry point, god file, clean separation, tight coupling) or empty string"}}"""


def _summary_prompt(root: dict) -> str:
    labels = {n["id"]: n["label"] for n in root["children"]}
    layers = "\n".join(f"  {n['label']} ({len(n['files'])} files): {n['description']}" for n in root["children"])
    edges = "\n".join(f"  {labels[a]} -> {labels[b]}" for a, b in root["edges"] if a in labels and b in labels)
    return f"""Layers of a codebase:
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


async def _describe_tree(root: dict) -> None:
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
        data = await _ask(_node_prompt(n), sem)
        if _text(data.get("description")):
            n["description"] = _text(data["description"])
        if _text(data.get("insight")):
            n["insight"] = _text(data["insight"])

    async def summarise() -> None:
        data = await _ask(_summary_prompt(root), sem)
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
) -> ArchitectureGraphResponse:
    tree = _build_architecture(files, edges)
    logger.info(
        "Architecture built | files=%d edges=%d layers=%d",
        len(files), len(edges), len(tree["children"]),
    )

    try:
        async with asyncio.timeout(DESCRIBE_DEADLINE):
            await _describe_tree(tree)
    except asyncio.TimeoutError:
        logger.warning("Description pass hit %ds deadline; returning partial descriptions", DESCRIBE_DEADLINE)

    return ArchitectureGraphResponse(summary=tree["description"], root=_to_arch(tree))