"""SET UP subgraph for the Storybook agent.

Reads the actual project files from ``project_root`` and turns them into a
getting-started guide via Qwen on AWS Bedrock:

    collect -> compress -> llm -> validate -> check -> END

All names here are prefixed ``setup_`` / ``SETUP_`` so other subgraphs
(LEARN, BUILD, ...) can live alongside without clashing. The parent graph in
``src.features.ai.story_book_agent`` imports :func:`build_setup` and
:data:`SETUP_NAME` from here.
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

SETUP_NAME = "set_up"  # key of this section in the final book


class SetupState(TypedDict, total=False):      # PRIVATE to this subgraph
    project_root: str
    files: Optional[list]                       # stored RepositoryFile rows (DB source)
    tree: dict
    lockfiles: list
    files: dict
    data: dict
    guide: dict
    errors: list
    output: dict


# =============================================================================
# COLLECT: which files matter for setup? (grouped by kind)
# =============================================================================
SETUP_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
                   "target", ".next", "vendor", ".tox", ".mypy_cache", ".pytest_cache",
                   ".gradle", ".idea", "site-packages", ".terraform", "coverage"}

SETUP_LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock",
                   "pipfile.lock", "cargo.lock", "go.sum", "gemfile.lock", "composer.lock", "bun.lockb"}

# kind: manifest  (what to install + language versions + monorepo layout)
SETUP_MANIFESTS = {
    "package.json", "pnpm-workspace.yaml", "turbo.json", "nx.json", "lerna.json", "deno.json",
    "pyproject.toml", "setup.py", "setup.cfg", "pipfile", "environment.yml", "environment.yaml",
    "poetry.toml", "uv.toml",
    "go.mod", "go.work", "cargo.toml", "rust-toolchain", "rust-toolchain.toml",
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "gemfile", "composer.json", "mix.exs", "pubspec.yaml", "package.swift", "cmakelists.txt",
    "meson.build", "build.sbt", "podfile", "global.json",
    ".nvmrc", ".node-version", ".python-version", ".ruby-version", ".java-version",
    ".tool-versions", ".sdkmanrc", "runtime.txt", "mise.toml", ".mise.toml", "devbox.json",
    "flake.nix", "shell.nix",
}
# kind: tasks  (task runners and process definitions)
SETUP_TASK_FILES = {"makefile", "justfile", "taskfile.yml", "taskfile.yaml", "rakefile",
                    "tox.ini", "noxfile.py", "procfile"}
# kind: ci
SETUP_CI_FILES = {".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml", "bitbucket-pipelines.yml",
                  "jenkinsfile", ".drone.yml", "cloudbuild.yaml", "cloudbuild.yml",
                  "buildspec.yml", "appveyor.yml"}
# kind: deploy  (hosting configs: low priority)
SETUP_DEPLOY_FILES = {"vercel.json", "netlify.toml", "fly.toml", "render.yaml", "serverless.yml",
                      "serverless.yaml", "app.yaml", "heroku.yml", "railway.json", "railway.toml",
                      "skaffold.yaml", "tiltfile", "chart.yaml", "kustomization.yaml",
                      "wrangler.toml", "firebase.json"}
# kind: config  (things that decide ports, migrations, servers, databases)
SETUP_CONFIG_FILES = {"alembic.ini", "gunicorn.conf.py", "uwsgi.ini", "supervisord.conf",
                      "nginx.conf", "default.conf", "schema.prisma", "knexfile.js", "knexfile.ts",
                      "drizzle.config.ts", "drizzle.config.js", ".sequelizerc", "ormconfig.json",
                      "init.sql", "schema.sql", "seed.sql", "manage.py", ".pre-commit-config.yaml"}
# kind: script  (helper scripts)
SETUP_WORDS = ("setup", "install", "bootstrap", "init", "entrypoint", "start", "serve",
               "migrate", "seed", "wait-for", "run", "dev")
SETUP_SCRIPT_NAMES = {"setup", "bootstrap", "install", "dev", "start", "server", "serve", "run",
                      "test", "console", "update", "build", "entrypoint", "migrate", "seed"}
SETUP_SCRIPT_DIRS = ("scripts", "script", "bin")

# Order = importance. The LLM sees these first; later kinds get dropped if space runs out.
SETUP_PRIORITY = ["compose", "dockerfile", "devcontainer", "tasks", "manifest",
                  "env", "script", "config", "ci", "deploy"]
SETUP_LIMITS = {"compose": 8000, "dockerfile": 4000, "devcontainer": 4000, "tasks": 8000,
                "manifest": 3000, "env": 3000, "script": 2000, "config": 2000, "ci": 2000,
                "deploy": 1500}                                  # max characters per file
SETUP_MAX_PER_KIND = {"compose": 12, "dockerfile": 15, "devcontainer": 3, "tasks": 5,
                      "manifest": 15, "env": 8, "script": 12, "config": 8, "ci": 6, "deploy": 6}
SETUP_TOTAL_CHARS = 60_000                                       # overall cap on the prompt


def setup_collect_from_db(rows):
    """Build the same (tree, lockfiles, files) tuple as setup_collect, but from
    stored RepositoryFile rows instead of a disk folder. Each ``row`` exposes
    ``path`` and ``content`` (and optionally ``size_bytes``).
    """
    tree, lockfiles, files = {}, [], {}
    for row in rows:
        path = row.path
        low = path.split("/")[-1].lower()
        size = getattr(row, "size_bytes", None) or 0
        if low in SETUP_LOCKFILES:
            lockfiles.append(path)
        elif setup_kind(path, low) and row.content is not None and size < 200_000:
            files[path] = row.content

    # Shallow folder tree (top two levels), mirroring setup_collect's shape so
    # the LLM sees the same structure.
    for path in files:
        low = path.split("/")[-1].lower()
        parts = path.split("/")
        if len(parts) <= 2:
            folder = "/".join(parts[:-1]) or "."
            name_ok = (not low.startswith("readme")) and (
                not low.startswith(".env") or setup_kind(path, low) == "env"
            )
            if name_ok and low not in tree.setdefault(folder, []):
                tree[folder].append(low)
    for folder in tree:
        tree[folder] = sorted(tree[folder])[:15]
    return tree, lockfiles, files


def setup_name(path):
    return path.split("/")[-1].lower()


def setup_clean(p):
    """Remove a leading './' from a path (lstrip would also eat the dot of '.env')."""
    return p[2:] if p.startswith("./") else p


def setup_kind(path, name):
    """What kind of setup file is this? None = not interesting (docs and secrets are never kept)."""
    parts = path.split("/")[:-1]                                 # folder names
    ext = name.rsplit(".", 1)[1] if "." in name else ""

    if name.startswith("readme") or ext in ("md", "rst", "adoc"):
        return None                                              # no docs

    if ext in ("yml", "yaml") and name.startswith(("docker-compose", "compose")):
        return "compose"                                         # docker-compose.yml, .dev.yml, compose.yaml
    if name in ("dockerfile", "containerfile") or name.startswith(("dockerfile.", "containerfile.")) \
            or ext == "dockerfile":
        return "dockerfile"                                      # every Dockerfile, any folder
    if name in ("devcontainer.json", ".devcontainer.json", ".gitpod.yml") or \
            (".devcontainer" in parts and ext == "json"):
        return "devcontainer"

    if name in SETUP_TASK_FILES:
        return "tasks"
    if name in SETUP_MANIFESTS or ext in ("csproj", "fsproj", "sln") or \
            (name.startswith(("requirements", "constraints")) and ext == "txt"):
        return "manifest"

    # Env TEMPLATES only. Real .env files hold secrets and are never matched here.
    if name.startswith((".env", "env.")) and any(w in name for w in ("example", "sample", "template", "dist")):
        return "env"
    if name.endswith((".env.example", ".env.sample", ".env.template")):
        return "env"

    if (path.startswith(".github/workflows/") and ext in ("yml", "yaml")) or name in SETUP_CI_FILES \
            or (path.startswith(".circleci/") and name == "config.yml"):
        return "ci"

    if name in SETUP_CONFIG_FILES:
        return "config"
    if name in SETUP_DEPLOY_FILES:
        return "deploy"

    in_scripts_dir = any(p in SETUP_SCRIPT_DIRS for p in parts)
    if ext in ("sh", "bash", "ps1", "bat", "cmd") and (in_scripts_dir or any(w in name for w in SETUP_WORDS)):
        return "script"
    if not ext and in_scripts_dir and name in SETUP_SCRIPT_NAMES:
        return "script"                                          # bin/setup, script/bootstrap
    return None


def setup_collect(root, max_depth=3):
    """Return (tree, lockfiles, files) for the project at `root`."""
    root = Path(root)
    tree, lockfiles, files = {}, [], {}
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SETUP_SKIP_DIRS]
        rel = Path(dirpath).relative_to(root)
        if len(rel.parts) > max_depth:
            dirs[:] = []
            continue
        if len(rel.parts) <= 2:
            tree[rel.as_posix()] = [n for n in sorted(names)
                                    if not n.lower().startswith("readme")
                                    and not n.lower().startswith(".env")
                                    or setup_kind(n, n.lower()) == "env"][:15]
        for name in names:
            path = (rel / name).as_posix()
            low = name.lower()
            full = Path(dirpath) / name
            if low in SETUP_LOCKFILES:
                lockfiles.append(path)
            elif setup_kind(path, low) and full.stat().st_size < 200_000:
                files[path] = full.read_text(errors="ignore")
    return tree, lockfiles, files


# =============================================================================
# COMPRESS: most important kinds first, shallow paths first, capped overall
# =============================================================================
def setup_compress_package_json(text):
    try:
        pkg = json.loads(text)
    except ValueError:
        return text[:3000]
    keep = {k: pkg[k] for k in ("name", "scripts", "engines", "packageManager", "workspaces") if k in pkg}
    keep["dependencies"] = list(pkg.get("dependencies", {}))[:15]
    return json.dumps(keep, indent=1)


def setup_compress(tree, lockfiles, files):
    by_kind = {}
    for path, text in files.items():
        by_kind.setdefault(setup_kind(path, setup_name(path)), []).append((path, text))

    small, used, left_out = {}, 0, []
    for kind in SETUP_PRIORITY:
        # Shallow paths first: in a monorepo the root files matter most.
        items = sorted(by_kind.get(kind, []), key=lambda it: (it[0].count("/"), it[0]))
        for i, (path, text) in enumerate(items):
            body = setup_compress_package_json(text) if path.endswith("package.json") \
                else text[:SETUP_LIMITS[kind]]
            if i >= SETUP_MAX_PER_KIND[kind] or used + len(body) > SETUP_TOTAL_CHARS:
                left_out.append(path)                            # no room: just list the name
                continue
            small[path] = body
            used += len(body)
    return {"folders": tree, "lockfiles": lockfiles, "files": small, "not_included": left_out[:40]}


# =============================================================================
# LLM: ALL the ways to run it, most reliable first
# =============================================================================
SETUP_SYSTEM = ("You are a senior engineer writing a getting-started guide. "
                "Respond with valid JSON only, no markdown.")


def setup_ask_llm(data):
    prompt = f"""Below are the key setup and config files from a repository (compose files,
Dockerfiles, devcontainer, task runners, manifests, env templates, scripts, config, CI).
Do not assume any README exists.

{json.dumps(data, indent=1)}

Write ALL the ways to get this project running, ordered from MOST reliable to least.
Usually: (1) Docker Compose that starts everything, (2) project scripts / Makefile / task runner,
(3) manual local setup.

RULES:
- Include every distinct way you can find. Do not stop at one.
- If there are several compose files (dev, local, staging, ...), say what each is for
  and use the right `-f` flags in the commands.
- Say which Dockerfile builds which service.
- Use ONLY commands, files, services and make/just/task targets that exist in the files above.
- For each step set "source_file" to the file the command came from.

Return JSON:
{{"summary": "one sentence",
  "env_vars": [{{"name": "...", "purpose": "..."}}],
  "services": ["postgres", "redis"],
  "files_guide": [{{"file": "path", "purpose": "what this compose file / Dockerfile is for"}}],
  "run_options": [
    {{"name": "Docker Compose (all services)",
      "reliability": "high|medium|low",
      "best_for": "when to use this",
      "requires": ["docker"],
      "steps": [{{"title": "...", "description": "...", "command": "...",
                 "phase": "dependencies|env|services|run|verify",
                 "source_file": "path"}}]}}
  ]}}"""
    return parse_json(invoke_qwen(prompt, SETUP_SYSTEM, 4000))


# =============================================================================
# VALIDATE: force the LLM answer into ONE fixed shape (so the frontend never breaks)
# =============================================================================
# Output shape of this subgraph (schema_version 1):
# {
#   "schema_version": 1,
#   "summary": str,
#   "env_vars":    [{"name": str, "purpose": str}],
#   "services":    [str],
#   "files_guide": [{"file": str, "purpose": str}],
#   "run_options": [{"name": str, "reliability": "high|medium|low", "best_for": str,
#                    "requires": [str],
#                    "steps": [{"title": str, "description": str, "command": str,
#                               "phase": "dependencies|env|services|run|verify",
#                               "source_file": str,
#                               "verified": bool}]}],      # "verified" is added by CHECK
#   "warnings": [str]
# }
# Every key is always present, with the right type. Bad or extra data is repaired or dropped.
SETUP_SCHEMA_VERSION = 1
SETUP_PHASES = ("dependencies", "env", "services", "run", "verify")
SETUP_RELIABILITY = ("high", "medium", "low")


def setup_str(x):
    """Any value -> a clean string ('' for None)."""
    return "" if x is None else str(x).strip()


def setup_list(x):
    """Anything that isn't a list becomes an empty list."""
    return x if isinstance(x, list) else []


def setup_normalize(guide):
    """Turn whatever the LLM returned into the fixed shape above. Never raises."""
    guide = guide if isinstance(guide, dict) else {}

    env_vars = []
    for v in setup_list(guide.get("env_vars")):
        v = {"name": v} if isinstance(v, str) else v            # accept ["API_KEY", ...]
        if isinstance(v, dict) and setup_str(v.get("name")):
            env_vars.append({"name": setup_str(v["name"]), "purpose": setup_str(v.get("purpose"))})

    services = []
    for sv in setup_list(guide.get("services")):
        name = setup_str(sv.get("name")) if isinstance(sv, dict) else setup_str(sv)   # accept objects too
        if name:
            services.append(name)

    files_guide = []
    for f in setup_list(guide.get("files_guide")):
        if isinstance(f, dict) and setup_str(f.get("file")):
            files_guide.append({"file": setup_str(f["file"]), "purpose": setup_str(f.get("purpose"))})

    run_options = []
    for opt in setup_list(guide.get("run_options")):
        if not isinstance(opt, dict):
            continue
        steps = []
        for st in setup_list(opt.get("steps")):
            if not isinstance(st, dict):
                continue
            title, cmd = setup_str(st.get("title")), setup_str(st.get("command"))
            if not title and not cmd:
                continue                                         # empty step: drop it
            phase = setup_str(st.get("phase")).lower()
            steps.append({
                "title": title or cmd,
                "description": setup_str(st.get("description")),
                "command": cmd,
                "phase": phase if phase in SETUP_PHASES else "run",
                "source_file": setup_str(st.get("source_file")),
            })
        if not steps:
            continue                                             # option with no steps: drop it
        rel = setup_str(opt.get("reliability")).lower()
        run_options.append({
            "name": setup_str(opt.get("name")) or f"Option {len(run_options) + 1}",
            "reliability": rel if rel in SETUP_RELIABILITY else "medium",
            "best_for": setup_str(opt.get("best_for")),
            "requires": [setup_str(r) for r in setup_list(opt.get("requires")) if setup_str(r)],
            "steps": steps,
        })

    warnings = [] if run_options else ["No usable run options were produced."]
    return {"schema_version": SETUP_SCHEMA_VERSION, "summary": setup_str(guide.get("summary")),
            "env_vars": env_vars, "services": services, "files_guide": files_guide,
            "run_options": run_options, "warnings": warnings}


# =============================================================================
# CHECK: is every command backed by real files?
# =============================================================================
SETUP_STANDARD = ("npm install", "npm ci", "yarn install", "pnpm install", "bun install",
                  "pip install -r", "pip install -e", "python -m venv", "poetry install",
                  "uv sync", "pipenv install", "go mod download", "cargo build",
                  "bundle install", "composer install", "mvn install", "pre-commit install")


def setup_compose_ok(part, paths, all_text):
    """Check a `docker compose ...` command: -f files exist, service names exist."""
    tokens = part.split()
    used = [tokens[i + 1] for i, t in enumerate(tokens[:-1]) if t in ("-f", "--file")]
    for f in used:                                          # every -f file must exist
        if setup_clean(f) not in paths:
            return False
    if not used and not any(setup_kind(p, setup_name(p)) == "compose" for p in paths):
        return False                                        # no compose file at all
    if "up" in tokens or "build" in tokens:                 # service names must exist
        start = tokens.index("up") if "up" in tokens else tokens.index("build")
        skip_next = False
        for t in tokens[start + 1:]:
            if skip_next:
                skip_next = False
            elif t in ("--profile", "--scale", "-p"):
                skip_next = True
            elif not t.startswith("-") and f"{t}:" not in all_text:
                return False
    return True


def setup_part_is_real(part, paths, all_text):
    """Check ONE command (no '&&') against the collected files."""
    part = " ".join(part.split())
    if part.startswith("docker-compose"):                   # treat old and new spelling the same
        part = "docker compose" + part[len("docker-compose"):]
    tokens = part.split()
    if part.startswith("docker compose"):
        return setup_compose_ok(part, paths, all_text)
    if part.startswith(("cd ", "echo ", "export ", "source ")):
        return True
    if tokens[0] == "cp" and len(tokens) >= 3:              # source file must exist
        return setup_clean(tokens[1]) in paths
    if tokens[0] in ("bash", "sh") and len(tokens) >= 2:    # script must exist
        return setup_clean(tokens[1]) in paths
    if setup_clean(tokens[0]) in paths:                     # ./scripts/start.sh, bin/setup
        return True
    if part.startswith(SETUP_STANDARD) or part == "yarn":
        return True
    m = re.match(r"(?:npm|pnpm|yarn)(?: run)? ([\w:.-]+)", part)
    if m:                                                   # script must exist in package.json
        return f'"{m.group(1)}"' in all_text
    m = re.match(r"(?:make|just|task) ([\w.:-]+)", part)
    if m:                                                   # target must exist
        return f"{m.group(1)}:" in all_text
    return part in all_text


def setup_check(guide, data):
    all_text = "\n".join(data["files"].values())
    paths = set(data["files"])
    warnings = []
    for opt in guide.get("run_options", []):
        for step in opt.get("steps", []):
            cmd = (step.get("command") or "").strip()
            step["verified"] = (not cmd) or all(
                setup_part_is_real(p.strip(), paths, all_text) for p in cmd.split("&&"))
            if not step["verified"]:
                warnings.append(f"[{opt.get('name')}] Unverified command: {cmd}")
    guide["warnings"] = guide.get("warnings", []) + warnings
    return guide


# =============================================================================
# NODES
# =============================================================================
def setup_collect_node(state):
    if state.get("files"):
        tree, lockfiles, files = setup_collect_from_db(state["files"])
    else:
        tree, lockfiles, files = setup_collect(state["project_root"])
    return {"tree": tree, "lockfiles": lockfiles, "files": files}


def setup_compress_node(state):
    return {"data": setup_compress(state["tree"], state["lockfiles"], state["files"])}


async def setup_llm_node(state):
    try:
        guide = await asyncio.to_thread(setup_ask_llm, state["data"])
        return {"guide": guide, "errors": []}
    except Exception as e:
        empty = {"summary": "", "env_vars": [], "services": [], "files_guide": [], "run_options": []}
        return {"guide": empty, "errors": [f"{SETUP_NAME}: {e}"]}


def setup_validate_node(state):
    return {"guide": setup_normalize(state["guide"])}


def setup_check_node(state):
    return {"output": setup_check(state["guide"], state["data"])}


def build_setup():
    g = StateGraph(SetupState)
    g.add_node("collect", setup_collect_node)
    g.add_node("compress", setup_compress_node)
    g.add_node("llm", setup_llm_node)
    g.add_node("validate", setup_validate_node)
    g.add_node("check", setup_check_node)
    g.add_edge(START, "collect")
    g.add_edge("collect", "compress")
    g.add_edge("compress", "llm")
    g.add_edge("llm", "validate")
    g.add_edge("validate", "check")
    g.add_edge("check", END)
    return g.compile()
