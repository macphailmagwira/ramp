import re
import logging
from pathlib import Path
from typing import List, Tuple

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.dependency_parser")

# Python: from x import y / import x
PY_FROM_IMPORT = re.compile(r"^\s*from\s+([\w\.]+)\s+import\s+", re.MULTILINE)
PY_IMPORT = re.compile(r"^\s*import\s+([\w\.]+)", re.MULTILINE)

# JS/TS: import ... from '...' / require('...')
JS_IMPORT = re.compile(r"""(?:import|export)\s+.*?from\s+['"]([^'"]+)['"]""", re.MULTILINE)
JS_REQUIRE = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", re.MULTILINE)


def parse_dependencies(file_path: str, content: str) -> List[Tuple[str, str]]:
    """
    Parse import statements from a file and return list of (raw_import, import_type).
    Only returns relative/local imports (not stdlib or node_modules).
    """
    ext = Path(file_path).suffix.lower()
    results = []

    if ext == ".py":
        for match in PY_FROM_IMPORT.finditer(content):
            module = match.group(1)
            if _is_relative_python(module):
                results.append((module, "from_import"))
        for match in PY_IMPORT.finditer(content):
            module = match.group(1)
            if _is_relative_python(module):
                results.append((module, "import"))

    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        for match in JS_IMPORT.finditer(content):
            path = match.group(1)
            if _is_relative_js(path):
                results.append((path, "esm_import"))
        for match in JS_REQUIRE.finditer(content):
            path = match.group(1)
            if _is_relative_js(path):
                results.append((path, "require"))

    return results


def resolve_import_to_path(
    source_file: str,
    raw_import: str,
    import_type: str,
    all_paths: List[str],
) -> str | None:
    """
    Try to resolve a raw import string to an actual file path in all_paths.
    Returns the matching path or None if unresolvable.
    """
    source_dir = str(Path(source_file).parent)

    if import_type in ("esm_import", "require"):
        return _resolve_js_import(source_dir, raw_import, all_paths)
    else:
        return _resolve_python_import(raw_import, all_paths)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_relative_python(module: str) -> bool:
    """Only keep intra-project imports (not stdlib, not third-party)."""
    # Relative imports start with dot, or contain dots suggesting local package
    if module.startswith("."):
        return True
    # Heuristic: if it doesn't look like a known stdlib/third-party root, include it
    # We keep it simple — exclude single-word all-lowercase (likely stdlib)
    parts = module.split(".")
    return len(parts) > 1 or (len(parts) == 1 and parts[0][0].isupper())


def _is_relative_js(path: str) -> bool:
    return path.startswith("./") or path.startswith("../")


def _resolve_js_import(source_dir: str, raw: str, all_paths: List[str]) -> str | None:
    import os
    # Resolve relative path properly using normpath
    base = os.path.normpath(os.path.join(source_dir, raw))
    # Convert backslashes on Windows
    base = base.replace('\\', '/')
    
    candidates = [
        base,
        base + '.ts',
        base + '.tsx', 
        base + '.js',
        base + '.jsx',
        base + '/index.ts',
        base + '/index.tsx',
        base + '/index.js',
    ]
    
    for candidate in candidates:
        normalized = candidate.lstrip('/')
        for p in all_paths:
            if p.replace('\\', '/') == normalized:
                return p
    return None


def _resolve_python_import(module: str, all_paths: List[str]) -> str | None:
    # Convert module.path -> module/path.py
    as_path = module.replace(".", "/")
    candidates = [
        as_path + ".py",
        as_path + "/__init__.py",
    ]
    for candidate in candidates:
        for p in all_paths:
            if _normalize(p).endswith(_normalize(candidate)):
                return p
    return None


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")