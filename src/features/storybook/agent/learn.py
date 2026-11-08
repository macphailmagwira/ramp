"""LEARN subgraph for the Storybook agent.

Codebase orientation + knowledge discovery, organised into four areas that the
frontend renders as separate tabs:

    1. overview      - what the project is, modules + how they connect, entry points
    2. flows         - zoomable execution graph (feature -> component -> function/...)
    3. apis          - API reference grouped by module/feature, with rich per-endpoint docs
    4. codebase      - module/file/symbol tree, dependencies, where business logic lives

Pipeline:
    collect -> map_architecture -> discover_flows -> enrich_flows -> build_flow_graph
            -> api_explore -> codebase -> validate

Deterministic extraction (parsers) runs first; the LLM only narrates and
enriches on top of that, so the factual structure stays ground-truth-accurate.
All names here are prefixed ``learn_`` / ``LEARN_`` so other subgraphs (SET UP,
BUILD, ...) can live alongside without clashing.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from src.features.ai.bedrock import invoke_qwen, parse_json
from src.features.github.services import (
    call_graph_extractor,
    dependency_parser,
    symbol_extractor,
)

LEARN_NAME = "learn"  # key of this section in the final book

LEARN_PARSEABLE = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}

LEARN_SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "target", ".next", "vendor", ".tox", ".mypy_cache", ".pytest_cache",
    ".gradle", ".idea", "site-packages", ".terraform", "coverage",
}

# Node kinds used in the flows graph.
LEARN_NODE_KINDS = ("feature", "component", "function", "service", "database", "external")
# Edge kinds used in the flows graph.
LEARN_EDGE_KINDS = ("contains", "call", "branch", "error", "alt")

# APIs are grouped by top-level module; cap the number of groups richly documented.
LEARN_MAX_API_GROUPS = 12
LEARN_MAX_ENDPOINTS_PER_GROUP = 40
# Endpoints sent to the LLM per call. Kept small so the rich per-endpoint JSON
# fits inside max_tokens (a single call over all 36 endpoints truncated mid-JSON
# and dropped every detail field).
LEARN_API_BATCH = 6
LEARN_API_MAX_TOKENS = 4000


class LearnState(TypedDict, total=False):  # PRIVATE to this subgraph
    project_root: str
    files: Optional[list]                       # stored RepositoryFile rows (DB source)
    file_map: dict                              # path -> {content, ext, name}
    file_deps: list                             # internal import edges
    symbols: list                               # functions / classes
    func_edges: list                            # call edges
    manifest_deps: list                         # third-party packages
    routes: list                                # API surface
    framework: list                             # detected tech / languages
    modules: list                               # folder grouping + cross-module edges
    api_groups: dict                           # module -> [route]
    overview: dict                             # LLM narration (area 1)
    flows: list                                # enriched flows (area 2 narrative)
    flow_graph: dict                           # built graph per flow (area 2 graph)
    apis: list                                 # enriched API groups (area 3)
    codebase: dict                             # tree + symbols + deps (area 4)
    output: dict


# =============================================================================
# COLLECT: build the deterministic code graph from the project files
# =============================================================================
def learn_load_files(state: LearnState) -> dict:
    """Return {path: {"content", "ext", "name"}} from DB rows or disk."""
    files: dict = {}
    if state.get("files"):
        for row in state["files"]:
            content = getattr(row, "content", None)
            if content is None:
                continue
            files[row.path] = {
                "content": content,
                "ext": (Path(row.path).suffix.lower() or ""),
                "name": row.name,
            }
        return files

    root = Path(state["project_root"])
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in LEARN_SKIP_DIRS]
        for name in names:
            full = Path(dirpath) / name
            try:
                if full.stat().st_size > 1_000_000:
                    continue
                content = full.read_text(errors="replace")
            except Exception:
                continue
            rel = full.relative_to(root).as_posix()
            files[rel] = {
                "content": content,
                "ext": full.suffix.lower(),
                "name": name,
            }
    return files


def learn_collect_node(state: LearnState):
    files = learn_load_files(state)
    all_paths = list(files.keys())

    file_deps = []
    for path, f in files.items():
        for raw, itype in dependency_parser.parse_dependencies(path, f["content"]):
            tgt = dependency_parser.resolve_import_to_path(path, raw, itype, all_paths)
            if tgt and tgt != path:
                file_deps.append({"source": path, "target": tgt, "import_type": itype})

    symbols = []
    for path, f in files.items():
        if f["ext"] in LEARN_PARSEABLE:
            for s in symbol_extractor.extract_symbols(path, f["content"]):
                s = dict(s)
                s["file_path"] = path
                symbols.append(s)

    known_names = {s["name"] for s in symbols}
    func_edges = []
    for path, f in files.items():
        if f["ext"] in LEARN_PARSEABLE:
            for caller, callee, line in call_graph_extractor.extract_calls(
                path, f["content"], known_names
            ):
                func_edges.append(
                    {"source": caller, "target": callee, "line": line, "file": path}
                )

    manifest_deps = _learn_scan_manifest_deps(files)
    framework = _learn_detect_framework(files)
    routes = _learn_scan_routes(files, framework)
    modules = _learn_build_modules(files, file_deps)
    api_groups = _learn_group_routes(routes)

    return {
        "file_map": files,
        "file_deps": file_deps,
        "symbols": symbols,
        "func_edges": func_edges,
        "manifest_deps": manifest_deps,
        "routes": routes,
        "framework": framework,
        "modules": modules,
        "api_groups": api_groups,
    }


# =============================================================================
# Deterministic extraction helpers (no LLM)
# =============================================================================
def _learn_detect_framework(files: dict) -> list:
    """Best-effort framework / language detection (mirrors the scanner)."""
    tech: set = set()
    names = {f["name"].lower(): path for path, f in files.items()}

    pj = names.get("package.json")
    if pj:
        try:
            data = json.loads(files[pj]["content"])
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        except Exception:
            deps = {}
        d = set(deps)
        if "next" in d:
            tech.add("Next.js")
        if "react" in d:
            tech.add("React")
        if "vue" in d:
            tech.add("Vue")
        if "svelte" in d:
            tech.add("Svelte")
        if "vite" in d:
            tech.add("Vite")
        if "express" in d:
            tech.add("Express")
        if "nestjs" in d or "@nestjs/core" in d:
            tech.add("NestJS")
        if "angular" in d or "@angular/core" in d:
            tech.add("Angular")
        if "typescript" in d:
            tech.add("TypeScript")
        if not tech:
            tech.add("Node.js")

    py = next((p for n, p in names.items() if n in ("pyproject.toml", "requirements.txt", "setup.py")), None)
    if py:
        t = files[py]["content"].lower()
        if "fastapi" in t:
            tech.add("FastAPI")
        elif "django" in t:
            tech.add("Django")
        elif "flask" in t:
            tech.add("Flask")
        else:
            tech.add("Python")

    if "go.mod" in names:
        tech.add("Go")
    if "cargo.toml" in names:
        tech.add("Rust")
    if "pom.xml" in names or "build.gradle" in names or "build.gradle.kts" in names:
        tech.add("Java")
    if next((n for n in names if n.endswith(".csproj")), None):
        tech.add("C#")
    return sorted(tech)


def _learn_scan_manifest_deps(files: dict) -> list:
    """Extract third-party dependencies from each ecosystem's manifest."""
    out: list = []
    names = {f["name"].lower(): path for path, f in files.items()}

    pj = names.get("package.json")
    if pj:
        try:
            data = json.loads(files[pj]["content"])
            for sect in ("dependencies", "devDependencies"):
                for name, ver in data.get(sect, {}).items():
                    out.append({"name": name, "version": str(ver), "manager": "npm"})
        except Exception:
            pass

    req = names.get("requirements.txt")
    if req:
        for m in re.finditer(
            r"^([A-Za-z0-9_.\-]+)\s*(?:[=<>!~]=?|===)\s*([^\s;#]+)",
            files[req]["content"], re.MULTILINE,
        ):
            out.append({"name": m.group(1), "version": m.group(2), "manager": "pip"})

    pt = names.get("pyproject.toml")
    if pt:
        txt = files[pt]["content"]
        for m in re.finditer(
            r'^\s*["\']?([A-Za-z0-9_.\-]+)["\']?\s*(?:[<>=!~]=?|===)\s*["\']?([^\s"\']+)',
            txt, re.MULTILINE,
        ):
            out.append({"name": m.group(1), "version": m.group(2), "manager": "pyproject"})
        for m in re.finditer(
            r'^\s*([A-Za-z0-9_.\-]+)\s*=\s*["\']\^?[\d]', txt, re.MULTILINE,
        ):
            out.append({"name": m.group(1), "version": "", "manager": "pyproject"})

    gm = names.get("go.mod")
    if gm:
        for m in re.finditer(r'^\s*([A-Za-z0-9_./\-]+)\s+v[\d]', files[gm]["content"], re.MULTILINE):
            out.append({"name": m.group(1), "version": "", "manager": "go"})

    ct = names.get("cargo.toml")
    if ct:
        for m in re.finditer(r'^\s*([A-Za-z0-9_.\-]+)\s*=\s*"([^"]+)"', files[ct]["content"], re.MULTILINE):
            out.append({"name": m.group(1), "version": m.group(2), "manager": "cargo"})

    pom = names.get("pom.xml")
    if pom:
        for m in re.finditer(r"<artifactId>([^<]+)</artifactId>", files[pom]["content"]):
            out.append({"name": m.group(1).strip(), "version": "", "manager": "maven"})

    return out


_PY_DECORATOR_ROUTE = re.compile(
    r'@(?P<obj>[\w\.]+)\.(?P<m>get|post|put|patch|delete|route)\(\s*[\'"](?P<p>[^\'"]+)[\'"]'
)
_PY_DJANGO_ROUTE = re.compile(r'\b(?:path|re_path|url)\(\s*[\'"]([^\'"]+)[\'"]')
_JS_ROUTE = re.compile(r'(?:app|router)\.(get|post|put|patch|delete)\(\s*[\'"]([^\'"]+)[\'"]')
_NEST_DECORATOR = re.compile(r'@(Get|Post|Put|Patch|Delete)\(\s*[\'"]([^\'"]*)[\'"]')
_GO_ROUTE = re.compile(r'(?:[\w.]+)\.(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\(\s*"([^"]+)"')
_GO_HANDLE = re.compile(r'\.HandleFunc\(\s*"([^"]+)"')
_RUST_ROUTE = re.compile(r'\.(?:route|get|post|put|patch|delete)\(\s*"([^"]+)"')
_ROCKET_DECORATOR = re.compile(r'#\[(get|post|put|patch|delete)\("?([^"\)]+)"?\)')
_JAVA_ROUTE = re.compile(r'@(Get|Post|Put|Patch|Delete|Request)Mapping')
_JAVA_PATH = re.compile(r'(?:value\s*=\s*)?["\']([^"\']+)["\']')


def _scan_python_routes(path: str, content: str) -> list:
    out = []
    for m in _PY_DECORATOR_ROUTE.finditer(content):
        method = m.group("m").upper()
        if method == "ROUTE":
            method = "GET"
        out.append({"method": method, "path": m.group("p"), "file": path})
    for m in _PY_DJANGO_ROUTE.finditer(content):
        out.append({"method": "ALL", "path": m.group(1), "file": path})
    return out


def _scan_js_routes(path: str, content: str) -> list:
    out = []
    for m in _JS_ROUTE.finditer(content):
        out.append({"method": m.group(1).upper(), "path": m.group(2), "file": path})
    for m in _NEST_DECORATOR.finditer(content):
        out.append({"method": m.group(1).upper(), "path": m.group(2) or "/", "file": path})
    return out


def _scan_go_routes(path: str, content: str) -> list:
    out = []
    for m in _GO_ROUTE.finditer(content):
        out.append({"method": m.group(1), "path": m.group(2), "file": path})
    for m in _GO_HANDLE.finditer(content):
        out.append({"method": "ALL", "path": m.group(1), "file": path})
    return out


def _scan_rust_routes(path: str, content: str) -> list:
    out = []
    for m in _RUST_ROUTE.finditer(content):
        kw = re.search(r'\.(\w+)\(\s*"', m.group(0))
        method = kw.group(1).upper() if kw else "ALL"
        if method == "ROUTE":
            method = "ALL"
        out.append({"method": method, "path": m.group(1), "file": path})
    for m in _ROCKET_DECORATOR.finditer(content):
        out.append({"method": m.group(1).upper(), "path": "/" + m.group(2).lstrip("/"), "file": path})
    return out


def _scan_java_routes(path: str, content: str) -> list:
    out = []
    for m in _JAVA_ROUTE.finditer(content):
        kind = m.group(1)
        rest = content[m.end(): m.end() + 120]
        pm = _JAVA_PATH.search(rest)
        path_ = pm.group(1) if pm else "/"
        method = "ALL" if kind == "Request" else kind.upper()
        out.append({"method": method, "path": path_, "file": path})
    return out


def _learn_scan_routes(files: dict, framework: list) -> list:
    routes: list = []
    for path, f in files.items():
        e = f["ext"]
        if e == ".py":
            routes += _scan_python_routes(path, f["content"])
        elif e in (".ts", ".tsx", ".js", ".jsx"):
            routes += _scan_js_routes(path, f["content"])
        elif e == ".go":
            routes += _scan_go_routes(path, f["content"])
        elif e == ".rs":
            routes += _scan_rust_routes(path, f["content"])
        elif e == ".java":
            routes += _scan_java_routes(path, f["content"])
    return routes


def _learn_build_modules(files: dict, file_deps: list) -> list:
    """Group files by top-level folder and count cross-module edges."""
    mod_files: dict = {}
    for path in files:
        parts = path.split("/")
        mod = parts[0] if len(parts) > 1 else "__root__"
        mod_files.setdefault(mod, []).append(path)
    mod_of = {p: (p.split("/")[0] if "/" in p else "__root__") for p in files}
    cross: dict = {}
    for e in file_deps:
        sm = mod_of.get(e["source"])
        tm = mod_of.get(e["target"])
        if sm and tm and sm != tm:
            cross.setdefault(sm, set()).add(tm)
    return sorted(
        (
            {"module": mod, "file_count": len(fps), "depends_on": sorted(cross.get(mod, set()))}
            for mod, fps in mod_files.items()
        ),
        key=lambda m: -m["file_count"],
    )


def _learn_group_routes(routes: list) -> dict:
    """Group routes by top-level module so the API explorer is organised, not flat."""
    groups: dict = {}
    for r in routes:
        parts = r["file"].split("/")
        mod = parts[0] if len(parts) > 1 else "__root__"
        groups.setdefault(mod, []).append(r)
    return groups


# =============================================================================
# LLM: area 1 - project overview
# =============================================================================
LEARN_SYSTEM = (
    "You are a senior engineer onboarding a developer to a codebase. "
    "Respond with valid JSON only, no markdown."
)


def _learn_symbol_signature(s: dict) -> str:
    try:
        params = json.loads(s.get("parameters") or "[]")
    except Exception:
        params = []
    if not isinstance(params, list):
        params = [str(params)]
    param_str = ", ".join(str(p) for p in params)
    prefix = "async " if s.get("is_async") else ""
    cls = f"{s['class_name']}." if s.get("class_name") else ""
    ret = s.get("return_type") or "None"
    return f"{prefix}{cls}{s['name']}({param_str}) -> {ret}"


async def learn_map_architecture_node(state: LearnState):
    modules = state["modules"]
    file_deps = state["file_deps"]
    incoming: dict = {}
    for e in file_deps:
        incoming[e["target"]] = incoming.get(e["target"], 0) + 1
    hubs = sorted(incoming.items(), key=lambda kv: kv[1], reverse=True)[:10]

    data = {
        "framework": state["framework"],
        "modules": modules,
        "hub_files": [{"file": f, "imported_by": c} for f, c in hubs],
        "external_dependencies_count": len(state["manifest_deps"]),
        "routes_count": len(state["routes"]),
        "symbols_count": len(state["symbols"]),
    }
    prompt = f"""Below is a deterministic summary of a repository's structure.

{json.dumps(data, indent=1)}

Write a guided onboarding overview for a new developer. Cover:
- a 2-3 sentence summary of what this codebase is and how it is structured
- each module's responsibility and its key files (use real module names above)
- how different parts of the system connect (cross-module dependencies)
- the most important entry points and where to start exploring
- the major areas of business logic and which modules implement them

Return JSON:
{{"summary": str,
  "modules": [{{"name": str, "responsibility": str, "connects_to": [str], "key_files": [str]}}],
  "entry_points": [str],
  "connections": [{{"from": str, "to": str, "note": str}}],
  "business_logic": [{{"topic": str, "locations": [str]}}],
  "warnings": [str]}}"""
    try:
        arch = await asyncio.to_thread(invoke_qwen, prompt, LEARN_SYSTEM, 4000)
        arch = parse_json(arch)
    except Exception as e:
        arch = {"summary": "", "modules": [], "entry_points": [], "connections": [],
                "business_logic": [], "warnings": [f"{LEARN_NAME}: {e}"]}
    return {"overview": arch}


# =============================================================================
# LLM: area 2 - execution flows (discover -> enrich -> build graph)
# =============================================================================
def _learn_call_graph_text(state: LearnState) -> str:
    lines = []
    for n in state["symbols"][:400]:
        lines.append(f"  [{n['file_path']}] {n['name']} ({n['symbol_type']})")
    edge_lines = [
        f"  {e['source']} -> {e['target']}" for e in state["func_edges"][:400]
    ]
    return (
        f"FUNCTIONS ({len(state['symbols'])} total, showing {len(lines)}):\n"
        + "\n".join(lines)
        + f"\n\nCALLS ({len(state['func_edges'])} total, showing {len(edge_lines)}):\n"
        + "\n".join(edge_lines)
    )


async def learn_discover_flows_node(state: LearnState):
    graph = _learn_call_graph_text(state)
    prompt = f"""Here is the function call graph for a codebase.

{graph}

Identify the distinct logical flows (user-facing features or system behaviours)
a developer should understand. Name each clearly (2-5 words).

Return JSON: {{"flows": [{{"id": "flow-1", "name": str, "description": str}}]}}"""
    try:
        raw = await asyncio.to_thread(invoke_qwen, prompt, LEARN_SYSTEM, 2000)
        data = parse_json(raw)
        flows = [f for f in data.get("flows", [])][:8]
    except Exception as e:
        flows = []
        state.setdefault("overview", {})
        state["overview"].setdefault("warnings", []).append(f"{LEARN_NAME}: {e}")
    return {"flows": flows}


async def learn_enrich_flows_node(state: LearnState):
    flows = state.get("flows", [])
    if not flows:
        return {"flows": []}
    graph = _learn_call_graph_text(state)
    enriched = []
    for flow in flows:
        prompt = f"""Feature being traced: "{flow.get('name')}"
{flow.get('description', '')}

{graph}

Write a step-by-step execution narrative for this flow for a developer new to the
code. Follow execution order. Reference real function names from the graph above.
Classify each step as function | service | database | external.

Return JSON:
{{"name": str, "description": str,
  "risks": [str],
  "steps": [{{"name": str, "description": str, "type": "function|service|database|external",
              "file": str, "line": null, "insight": str}}]}}"""
        try:
            raw = await asyncio.to_thread(invoke_qwen, prompt, LEARN_SYSTEM, 4000)
            data = parse_json(raw)
        except Exception:
            data = {"name": flow.get("name"), "description": flow.get("description", ""),
                    "risks": [], "steps": []}
        data["id"] = flow.get("id")
        enriched.append(data)
    return {"flows": enriched}


def _learn_mod_of(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return path.split("/")[0] if "/" in path else "__root__"


def learn_build_flow_graph_node(state: LearnState):
    """Build a zoomable graph per flow from deterministic data + enriched steps."""
    symbols = state.get("symbols", [])
    func_edges = state.get("func_edges", [])
    sig_by_file_name: dict = {}
    for s in symbols:
        sig_by_file_name.setdefault(s["file_path"], {})[s["name"]] = s

    graphs = []
    for fl in state.get("flows", []):
        nodes: dict = {}
        edges: list = []

        fid = fl.get("id") or f"flow-{len(graphs) + 1}"
        nodes[fid] = {
            "id": fid, "kind": "feature", "label": fl.get("name", "Unnamed flow"),
            "parent": None,
            "detail": {"summary": fl.get("description", ""), "source_file": None,
                       "code_ref": None, "line": None},
        }

        comps: set = set()
        func_nodes: dict = {}
        for st in fl.get("steps", []):
            fpath = st.get("file")
            fname = st.get("name")
            mod = _learn_mod_of(fpath)
            if mod:
                comps.add(mod)
            if fpath and fname:
                nid = f"{fpath}::{fname}"
                if nid not in func_nodes:
                    detail = sig_by_file_name.get(fpath, {}).get(fname, {})
                    func_nodes[nid] = {
                        "id": nid,
                        "kind": st.get("type") or "function",
                        "label": fname,
                        "parent": mod,
                        "detail": {
                            "summary": st.get("insight") or st.get("description", ""),
                            "source_file": fpath,
                            "code_ref": _learn_symbol_signature(detail) if detail else fname,
                            "line": detail.get("line_start") if detail else None,
                        },
                    }

        for m in comps:
            nid = f"mod::{m}"
            nodes[nid] = {"id": nid, "kind": "component", "label": m, "parent": fid,
                          "detail": {"summary": "", "source_file": None,
                                     "code_ref": None, "line": None}}
            edges.append({"from": fid, "to": nid, "kind": "contains", "label": ""})

        for nid, n in func_nodes.items():
            nodes[nid] = n
            if n["parent"]:
                edges.append({"from": f"mod::{n['parent']}", "to": nid,
                              "kind": "contains", "label": ""})

        known_func_ids = set(func_nodes)
        for e in func_edges:
            cs = f"{e['file']}::{e['source']}"
            ct = f"{e['file']}::{e['target']}"
            if cs in known_func_ids and ct in known_func_ids:
                edges.append({"from": cs, "to": ct, "kind": "call", "label": ""})

        graphs.append({
            "id": fid,
            "name": fl.get("name", "Unnamed flow"),
            "description": fl.get("description", ""),
            "risks": fl.get("risks", []),
            "graph": {"nodes": list(nodes.values()), "edges": edges},
        })
    return {"flow_graph": {"flows": graphs}}


# =============================================================================
# LLM: area 3 - API explorer (grouped, rich per-endpoint docs)
# =============================================================================
def _learn_norm_path(p: str) -> str:
    return (p or "").strip().rstrip("/")


def _learn_find_handler_name(content: Optional[str], method: str, path: str) -> Optional[str]:
    """Best-effort: return the handler function name for a route decorator."""
    if not content:
        return None
    target = _learn_norm_path(path)
    m_upper = method.upper()
    for m in _PY_DECORATOR_ROUTE.finditer(content):
        mm = m.group("m").upper()
        if mm == "ROUTE":
            mm = "GET"
        if mm != m_upper:
            continue
        if _learn_norm_path(m.group("p")) == target:
            tail = content[m.end():]
            fm = re.search(r"(?:async\s+def|def)\s+([A-Za-z_]\w*)\s*\(", tail)
            if fm:
                return fm.group(1)
    return None


def _learn_handler_symbol(state: LearnState, route: dict):
    """Resolve the handler symbol (with source_code + params) for a route, or None."""
    name = _learn_find_handler_name(
        state.get("file_map", {}).get(route["file"], {}).get("content"),
        route["method"], route["path"],
    )
    if not name:
        return None
    for s in state.get("symbols", []):
        if s.get("file_path") == route["file"] and s.get("name") == name:
            return s
    return None


_LEARN_PRIMITIVES = {
    "int", "float", "bool", "str", "bytes", "complex", "none", "any", "object",
    "list", "dict", "set", "tuple", "type", "date", "datetime", "time", "uuid",
    "decimal", "timedelta", "union", "optional",
}


def _learn_looks_like_model(typ: str) -> bool:
    """Heuristic: does this annotation refer to a request/response model (body)?"""
    if not typ:
        return False
    t = typ.strip()
    for wrapper in ("Optional", "Annotated", "Union", "List", "Sequence",
                    "Tuple", "Dict", "Set"):
        pref = f"{wrapper}["
        if t.startswith(pref):
            inner = t[len(pref):-1]
            parts = [p.strip() for p in inner.split(",")]
            return any(_learn_looks_like_model(p) for p in parts)
    base = re.split(r"[\[\], \.]", t)[0].strip()
    if not base or base in _LEARN_PRIMITIVES:
        return False
    return base[:1].isupper()


def _learn_params_from_symbol(symbol: dict, path: str) -> list:
    """Deterministic extraction of endpoint params from a handler signature."""
    try:
        raw = json.loads(symbol.get("parameters") or "[]")
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    path_params = set(re.findall(r"\{(\w+)\}", path or ""))
    out = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        name = p.get("name", "")
        if not name or name.startswith("*"):
            continue
        typ = p.get("type") or ""
        if name in path_params:
            pin, req = "path", True
        elif _learn_looks_like_model(typ):
            pin, req = "body", True
        else:
            pin, req = "query", (p.get("default") is None)
        out.append({
            "name": name, "in": pin, "type": typ,
            "required": bool(req), "description": "",
        })
    return out


def _learn_api_batch_context(state: LearnState, mod: str, routes: list) -> str:
    lines = [f"MODULE: {mod}", f"ROUTES ({len(routes)}):"]
    for r in routes:
        lines.append(f"  {r['method']} {r['path']}  ({r['file']})")
    lines.append("")
    lines.append("HANDLER SIGNATURES + SOURCE (use these to derive params, body, "
                 "response, errors and examples):")
    for r in routes:
        sym = _learn_handler_symbol(state, r)
        if not sym:
            continue
        lines.append(f"\n  # {r['method']} {r['path']} -> {sym['name']}")
        lines.append(f"  {_learn_symbol_signature(sym)}")
        src = sym.get("source_code")
        if src:
            indented = "\n".join("    " + ln for ln in src.splitlines())
            lines.append(f"  source:")
            lines.append(indented)
    return "\n".join(lines)


async def learn_api_explore_node(state: LearnState):
    groups = state.get("api_groups", {})
    if not groups:
        return {"apis": []}

    enriched = []
    for mod, routes in list(groups.items())[:LEARN_MAX_API_GROUPS]:
        endpoints: list = []
        for i in range(0, len(routes), LEARN_API_BATCH):
            endpoints += await _learn_api_batch(
                state, mod, routes[i:i + LEARN_API_BATCH]
            )
        if endpoints:
            enriched.append({"group": mod, "endpoints": endpoints})
    return {"apis": enriched}


async def _learn_api_batch(state: LearnState, mod: str, routes: list) -> list:
    """Document one small batch of routes. Falls back to deterministic extraction
    (params from the handler signature) if the LLM call or parsing fails, so a
    single bad batch never blanks the whole module's API reference."""
    ctx = _learn_api_batch_context(state, mod, routes)
    prompt = f"""{ctx}

These are the API routes for the "{mod}" module (a batch of {len(routes)}).
Write a structured reference for EACH endpoint listed under ROUTES, keeping the
exact "method" and "path" values from that list. Document accurately from the
handler signatures and source above:
- params: take from the handler signature. Path params appear in the URL; a
  Pydantic-model argument is the request body (in:"body"); the rest are query
  params. Include each param's name, type, required, and a short description.
- body_schema / response / errors / example: derive from the handler source and
  any models it references.
Return ONLY valid compact JSON (no markdown, no commentary).

Return JSON:
{{"group": str,
  "endpoints": [
    {{"method": str, "path": str,
      "summary": str,
      "behavior": str,
      "params": [{{"name": str, "in": "query|path|header|body", "type": str, "required": bool, "description": str}}],
      "headers": [str],
      "body_schema": str,
      "response": str,
      "errors": [str],
      "example": str,
      "source_files": [str],
      "related": [str]}}
  ]}}"""
    try:
        raw = await asyncio.to_thread(invoke_qwen, prompt, LEARN_SYSTEM, LEARN_API_MAX_TOKENS)
        data = parse_json(raw)
        returned = {
            (e.get("method"), e.get("path")): e
            for e in data.get("endpoints", [])
            if isinstance(e, dict) and e.get("method") and e.get("path")
        }
    except Exception as e:
        returned = {}
        state.setdefault("overview", {})
        state["overview"].setdefault("warnings", []).append(
            f"{LEARN_NAME}: api batch for {mod} failed ({e}); used extracted params"
        )

    out = []
    for r in routes:
        key = (r["method"], r["path"])
        src_files = [r["file"]]
        if key in returned:
            ep = dict(returned[key])
            ep["method"] = r["method"]
            ep["path"] = r["path"]
            ep["source_files"] = ep.get("source_files") or src_files
            out.append(ep)
            continue
        # Deterministic fallback: recover params/signature from the handler symbol.
        sym = _learn_handler_symbol(state, r)
        params = _learn_params_from_symbol(sym, r["path"]) if sym else []
        summary = ""
        if sym and sym.get("docstring"):
            summary = sym["docstring"].strip().splitlines()[0]
        out.append({
            "method": r["method"], "path": r["path"],
            "summary": summary,
            "behavior": "",
            "params": params,
            "headers": [],
            "body_schema": (sym.get("return_type") or "") if sym else "",
            "response": "",
            "errors": [],
            "example": "",
            "source_files": src_files,
            "related": [],
        })
    return out


# =============================================================================
# Deterministic: area 4 - codebase explorer
# =============================================================================
def learn_codebase_node(state: LearnState):
    files = state.get("file_map", {})
    modules = state.get("modules", [])
    symbols = state.get("symbols", [])
    file_deps = state.get("file_deps", [])

    module_files: dict = {}
    for path in files:
        parts = path.split("/")
        mod = parts[0] if len(parts) > 1 else "__root__"
        module_files.setdefault(mod, []).append(path)

    symbols_by_file: dict = {}
    for s in symbols:
        symbols_by_file.setdefault(s["file_path"], []).append(s)

    out_modules = []
    for m in modules:
        mod = m["module"]
        file_entries = []
        for fpath in sorted(module_files.get(mod, [])):
            syms = [
                {"name": s["name"], "kind": s.get("symbol_type", "function"),
                 "signature": _learn_symbol_signature(s),
                 "line": s.get("line_start")}
                for s in symbols_by_file.get(fpath, [])
            ]
            file_entries.append({
                "path": fpath,
                "symbol_count": len(syms),
                "symbols": syms[:60],
            })
        out_modules.append({
            "module": mod,
            "file_count": m["file_count"],
            "depends_on": m["depends_on"],
            "files": file_entries[:80],
        })

    dependencies = [
        {"from": e["source"], "to": e["target"], "kind": e.get("import_type", "import")}
        for e in file_deps[:400]
    ]

    return {
        "codebase": {
            "modules": out_modules,
            "dependencies": dependencies,
            "symbols_total": len(symbols),
            "routes_total": len(state.get("routes", [])),
        }
    }


# =============================================================================
# VALIDATE: force everything into one fixed shape (frontend never breaks)
# =============================================================================
def _learn_str(x):
    return "" if x is None else str(x).strip()


def _learn_list(x):
    return x if isinstance(x, list) else []


def _learn_api_param(p):
    if not isinstance(p, dict):
        return {"name": _learn_str(p), "in": "query", "type": "", "required": False, "description": ""}
    return {
        "name": _learn_str(p.get("name")),
        "in": _learn_str(p.get("in")) or "query",
        "type": _learn_str(p.get("type")),
        "required": bool(p.get("required", False)),
        "description": _learn_str(p.get("description")),
    }


def learn_normalize(state: LearnState) -> dict:
    overview_in = state.get("overview", {}) if isinstance(state.get("overview"), dict) else {}
    flows_in = state.get("flows", [])
    flow_graph = state.get("flow_graph", {}).get("flows", []) if isinstance(state.get("flow_graph"), dict) else []
    apis_in = state.get("apis", [])
    codebase_in = state.get("codebase", {}) if isinstance(state.get("codebase"), dict) else {}

    # --- area 1: overview ---
    ov_modules = []
    for m in _learn_list(overview_in.get("modules")):
        if isinstance(m, dict) and _learn_str(m.get("name")):
            ov_modules.append({
                "name": _learn_str(m.get("name")),
                "responsibility": _learn_str(m.get("responsibility")),
                "connects_to": [_learn_str(c) for c in _learn_list(m.get("connects_to")) if _learn_str(c)],
                "key_files": [_learn_str(f) for f in _learn_list(m.get("key_files")) if _learn_str(f)],
            })
    connections = []
    for c in _learn_list(overview_in.get("connections")):
        if isinstance(c, dict) and _learn_str(c.get("from")) and _learn_str(c.get("to")):
            connections.append({
                "from": _learn_str(c.get("from")),
                "to": _learn_str(c.get("to")),
                "note": _learn_str(c.get("note")),
            })
    business_logic = []
    for b in _learn_list(overview_in.get("business_logic")):
        if isinstance(b, dict) and _learn_str(b.get("topic")):
            business_logic.append({
                "topic": _learn_str(b.get("topic")),
                "locations": [_learn_str(loc) for loc in _learn_list(b.get("locations")) if _learn_str(loc)],
            })
    overview = {
        "summary": _learn_str(overview_in.get("summary")),
        "modules": ov_modules,
        "entry_points": [_learn_str(x) for x in _learn_list(overview_in.get("entry_points")) if _learn_str(x)],
        "connections": connections,
        "framework": _learn_list(state.get("framework")),
    }

    # --- area 2: flows (graph + narrative) ---
    flow_out = []
    flow_by_id = {f.get("id"): f for f in flow_graph}
    for fl in _learn_list(flows_in):
        if not isinstance(fl, dict):
            continue
        fid = fl.get("id")
        g = flow_by_id.get(fid, {}).get("graph", {"nodes": [], "edges": []})
        steps = []
        for s in _learn_list(fl.get("steps")):
            if not isinstance(s, dict):
                continue
            name = _learn_str(s.get("name"))
            if not name:
                continue
            steps.append({
                "name": name,
                "description": _learn_str(s.get("description")),
                "type": _learn_str(s.get("type")) or "function",
                "file": _learn_str(s.get("file")) or None,
                "line": s.get("line"),
                "insight": _learn_str(s.get("insight")) or None,
            })
        flow_out.append({
            "id": _learn_str(fid) or f"flow-{len(flow_out) + 1}",
            "name": _learn_str(fl.get("name")) or "Unnamed flow",
            "description": _learn_str(fl.get("description")),
            "risks": [_learn_str(r) for r in _learn_list(fl.get("risks")) if _learn_str(r)],
            "graph": {"nodes": g.get("nodes", []), "edges": g.get("edges", [])},
            "steps": steps,
        })

    # --- area 3: apis (grouped) ---
    apis_out = []
    for grp in _learn_list(apis_in):
        if not isinstance(grp, dict):
            continue
        endpoints = []
        for e in _learn_list(grp.get("endpoints")):
            if not isinstance(e, dict):
                continue
            endpoints.append({
                "method": _learn_str(e.get("method")),
                "path": _learn_str(e.get("path")),
                "summary": _learn_str(e.get("summary")),
                "behavior": _learn_str(e.get("behavior")),
                "params": [_learn_api_param(p) for p in _learn_list(e.get("params"))],
                "headers": [_learn_str(h) for h in _learn_list(e.get("headers")) if _learn_str(h)],
                "body_schema": _learn_str(e.get("body_schema")),
                "response": _learn_str(e.get("response")),
                "errors": [_learn_str(x) for x in _learn_list(e.get("errors")) if _learn_str(x)],
                "example": _learn_str(e.get("example")),
                "source_files": [_learn_str(f) for f in _learn_list(e.get("source_files")) if _learn_str(f)],
                "related": [_learn_str(r) for r in _learn_list(e.get("related")) if _learn_str(r)],
            })
        if not endpoints:
            continue
        apis_out.append({"group": _learn_str(grp.get("group")) or "api", "endpoints": endpoints})

    # --- area 4: codebase ---
    cb_modules = []
    resp_by_name = {m["name"]: m.get("responsibility", "") for m in ov_modules}
    for m in _learn_list(codebase_in.get("modules")):
        if not isinstance(m, dict):
            continue
        files = []
        for f in _learn_list(m.get("files")):
            if not isinstance(f, dict):
                continue
            files.append({
                "path": _learn_str(f.get("path")),
                "symbol_count": f.get("symbol_count", 0),
                "symbols": _learn_list(f.get("symbols")),
            })
        cb_modules.append({
            "module": _learn_str(m.get("module")),
            "responsibility": resp_by_name.get(_learn_str(m.get("module")), ""),
            "file_count": m.get("file_count", 0),
            "depends_on": _learn_list(m.get("depends_on")),
            "files": files,
        })
    codebase = {
        "modules": cb_modules,
        "dependencies": _learn_list(codebase_in.get("dependencies")),
        "symbols_total": codebase_in.get("symbols_total", 0),
        "routes_total": codebase_in.get("routes_total", 0),
        "business_logic": business_logic,
    }

    warnings = [_learn_str(w) for w in _learn_list(overview_in.get("warnings")) if _learn_str(w)]
    if not ov_modules and not flow_out and not apis_out and not cb_modules:
        warnings.append("No usable learn information was produced.")

    return {
        "schema_version": 2,
        "overview": overview,
        "flows": flow_out,
        "apis": apis_out,
        "codebase": codebase,
        "warnings": warnings,
    }


def learn_validate_node(state: LearnState):
    return {"output": learn_normalize(state)}


# =============================================================================
# NODES wiring
# =============================================================================
def build_learn():
    g = StateGraph(LearnState)
    g.add_node("collect", learn_collect_node)
    g.add_node("map_architecture", learn_map_architecture_node)
    g.add_node("discover_flows", learn_discover_flows_node)
    g.add_node("enrich_flows", learn_enrich_flows_node)
    g.add_node("build_flow_graph", learn_build_flow_graph_node)
    g.add_node("api_explore", learn_api_explore_node)
    g.add_node("codebase_explore", learn_codebase_node)
    g.add_node("validate", learn_validate_node)
    g.add_edge(START, "collect")
    g.add_edge("collect", "map_architecture")
    g.add_edge("map_architecture", "discover_flows")
    g.add_edge("discover_flows", "enrich_flows")
    g.add_edge("enrich_flows", "build_flow_graph")
    g.add_edge("build_flow_graph", "api_explore")
    g.add_edge("api_explore", "codebase_explore")
    g.add_edge("codebase_explore", "validate")
    g.add_edge("validate", END)
    return g.compile()
