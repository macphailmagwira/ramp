"""
Dependency Parser
==================

WHAT THIS FILE DOES (in plain English):
This file contains the low-level logic for reading a single source code
file's text and figuring out two things:
    1. What does this file import? (using regular expressions to spot
       `import`, `from ... import`, and `require(...)` statements)
    2. Where does that import actually point to on disk? (turning a name
       like "./utils" or "myapp.models" into a real file path like
       "src/utils.ts" or "myapp/models.py")

This is the "engine" used by DependencyGraphService - that service loops
over every file in a repo and calls the functions in this file to do the
actual parsing/resolving work.

KEY TERMS FOR BEGINNERS:
- "regular expression" (aka "regex"): a pattern used to search text for
  matches. For example, the pattern `import\\s+([\\w\\.]+)` looks for the
  word "import" followed by some whitespace, then captures a dotted name
  like "os.path". If regex syntax looks unfamiliar, that's normal - think
  of it as a very precise "find" operation.
- "relative import": an import that points to another file *within the
  same project*, as opposed to an external library. In Python, relative
  imports often start with a dot (e.g. `from . import utils`). In
  JavaScript/TypeScript, they start with "./" or "../".
- "resolving" an import: converting the raw text of an import statement
  (e.g. "./helpers") into an actual file that exists in the repository
  (e.g. "src/helpers.ts").
- "logger.info": writes a normal, human-readable status update to our logs.
- "logger.debug": writes MORE detailed information (only really needed when
  troubleshooting). Per team convention, debug logs also include the actual
  data/values involved (e.g. the specific imports found), not just a
  description of what happened.
"""

import re
import logging
from pathlib import Path
from typing import List, Tuple

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX

# The logger is how this module writes messages to our centralized logging
# system. Using a hierarchical name (prefix + ".dependency_parser") lets us
# filter/search logs specifically from this file later on.
logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.dependency_parser")

# --- Regular expressions used to find import statements in source code ---
#
# Each pattern below is compiled once (at module load time) so it can be
# reused efficiently every time we scan a new file, rather than
# recompiling the pattern on every single call.

# Python: "from x import y"
# Example match: "from myapp.models import User" -> captures "myapp.models"
PY_FROM_IMPORT = re.compile(r"^\s*from\s+([\w\.]+)\s+import\s+", re.MULTILINE)

# Python: "import x"
# Example match: "import os.path" -> captures "os.path"
PY_IMPORT = re.compile(r"^\s*import\s+([\w\.]+)", re.MULTILINE)

# JS/TS: "import ... from '...'" or "export ... from '...'"
# Example match: "import { foo } from './utils'" -> captures "./utils"
JS_IMPORT = re.compile(r"""(?:import|export)\s+.*?from\s+['"]([^'"]+)['"]""", re.MULTILINE)

# JS/TS: "require('...')"
# Example match: "const x = require('./config')" -> captures "./config"
JS_REQUIRE = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""", re.MULTILINE)


def parse_dependencies(file_path: str, content: str) -> List[Tuple[str, str]]:
    """
    Scan a single file's source code text and extract its "local" import
    statements - i.e., imports that likely point to another file within
    this same project, as opposed to a standard-library or third-party
    package.

    HOW THIS WORKS:
    We look at the file's extension to decide which set of regex patterns
    to use (Python-style vs JavaScript/TypeScript-style), then run those
    patterns over the file's text to find every import statement. For each
    one found, we apply a quick heuristic filter (`_is_relative_python` or
    `_is_relative_js`) to throw out imports that are almost certainly NOT
    part of this project (e.g. `import os` or `import react`).

    Args:
        file_path: The file's path (used only to determine its extension,
            e.g. "src/app.py" -> ".py"). This does NOT need to be an
            absolute path.
        content: The full text content of the file to scan.

    Returns:
        A list of (raw_import, import_type) tuples. For example:
            [("./utils", "esm_import"), ("../config", "require")]
        or for Python:
            [("myapp.models", "from_import")]
        `import_type` will be one of: "from_import", "import" (Python),
        or "esm_import", "require" (JavaScript/TypeScript). If the file
        type isn't recognized, or no local imports are found, an empty
        list is returned.
    """
    ext = Path(file_path).suffix.lower()
    results = []

    logger.debug(
        "Parsing dependencies for file | path=%s extension=%s content_length=%d",
        file_path, ext, len(content),
    )

    if ext == ".py":
        # Look for "from x import y" style statements.
        for match in PY_FROM_IMPORT.finditer(content):
            module = match.group(1)
            if _is_relative_python(module):
                results.append((module, "from_import"))
        # Look for plain "import x" style statements.
        for match in PY_IMPORT.finditer(content):
            module = match.group(1)
            if _is_relative_python(module):
                results.append((module, "import"))

    elif ext in (".js", ".jsx", ".ts", ".tsx"):
        # Look for ES module style: import ... from '...'
        for match in JS_IMPORT.finditer(content):
            path = match.group(1)
            if _is_relative_js(path):
                results.append((path, "esm_import"))
        # Look for CommonJS style: require('...')
        for match in JS_REQUIRE.finditer(content):
            path = match.group(1)
            if _is_relative_js(path):
                results.append((path, "require"))

    else:
        # We don't have a parser for this file type (e.g. .md, .json,
        # .go, .rs, etc.), so there's nothing to extract.
        logger.debug(
            "No parser available for extension, skipping | path=%s extension=%s",
            file_path, ext,
        )

    logger.info(
        "Dependency parsing complete for file | path=%s local_imports_found=%d",
        file_path, len(results),
    )
    logger.debug(
        "Dependency parsing output | path=%s results=%s",
        file_path, results,
    )

    return results


def resolve_import_to_path(
    source_file: str,
    raw_import: str,
    import_type: str,
    all_paths: List[str],
) -> str | None:
    """
    Take a raw import string (e.g. "./utils" or "myapp.models") found in
    `source_file`, and try to match it up with an actual file path that
    exists in the repository.

    WHY WE NEED `source_file`:
    Relative imports (like "./utils" in JavaScript) are relative to the
    *importing* file's own folder, not the project root. So to resolve
    "./utils" imported from "src/pages/home.js", we need to know that
    "home.js" lives in "src/pages/", so "./utils" actually means
    "src/pages/utils".

    HOW THIS WORKS:
    Based on the `import_type` (which tells us whether this came from a
    JS/TS-style import or a Python-style import), we delegate to one of two
    specialized resolver functions:
        - `_resolve_js_import` for "esm_import" / "require"
        - `_resolve_python_import` for anything else (Python's
          "from_import" / "import")

    Args:
        source_file: The path of the file that contains this import
            statement (e.g. "src/pages/home.js"). Used to resolve
            relative paths correctly.
        raw_import: The exact text of the import target as written in the
            source code (e.g. "./utils", "myapp.models").
        import_type: One of "esm_import", "require", "from_import",
            "import" - tells us which resolution strategy to use.
        all_paths: The full list of every known file path in the
            repository, used as the set of possible "answers" when trying
            to match the import to a real file.

    Returns:
        The matching file path (as it appears in `all_paths`) if one could
        be found, or `None` if the import doesn't resolve to any known
        file in this repository (e.g. it's a third-party library import).
    """
    source_dir = str(Path(source_file).parent)

    logger.debug(
        "Resolving import | source_file=%s source_dir=%s raw_import=%s import_type=%s",
        source_file, source_dir, raw_import, import_type,
    )

    if import_type in ("esm_import", "require"):
        resolved = _resolve_js_import(source_dir, raw_import, all_paths)
    else:
        resolved = _resolve_python_import(raw_import, all_paths)

    if resolved:
        logger.debug(
            "Import resolved successfully | source_file=%s raw_import=%s resolved_path=%s",
            source_file, raw_import, resolved,
        )
    else:
        logger.debug(
            "Import could not be resolved (likely external/third-party) | "
            "source_file=%s raw_import=%s",
            source_file, raw_import,
        )

    return resolved


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
#
# Everything below is used internally by the two public functions above.
# Functions prefixed with an underscore (e.g. `_is_relative_python`) are a
# Python convention meaning "this is an implementation detail, not meant to
# be used directly from outside this file."

def _is_relative_python(module: str) -> bool:
    """
    Decide whether a Python module name is likely a "local" (intra-project)
    import, as opposed to a standard-library or third-party package import.

    THE HEURISTIC (a "heuristic" is an educated-guess rule, not a perfectly
    precise one):
        - If the module name starts with a dot (e.g. ".utils" or
          "..models"), it's definitely a relative import - Python only
          allows that syntax for imports within the same package.
        - Otherwise, we guess based on shape:
            * If the name has multiple dot-separated parts (e.g.
              "myapp.models"), we assume it's a local project import,
              since most third-party packages are imported as a single
              top-level name (e.g. "requests", "numpy").
            * If it's a single word AND starts with an uppercase letter
              (unusual for real package names, which are conventionally
              all-lowercase), we also treat it as likely local/custom code.

    NOTE: This is intentionally a simple, approximate rule - it will
    occasionally misclassify some imports, but works well enough in
    practice to filter out the vast majority of standard-library and
    third-party imports.

    Args:
        module: The raw module name captured from a Python import
            statement (e.g. "os.path", ".utils", "MyLocalModule").

    Returns:
        True if this looks like a local/intra-project import, False if it
        looks like a standard-library or third-party import.
    """
    # Relative imports start with dot, or contain dots suggesting local package
    if module.startswith("."):
        return True
    # Heuristic: if it doesn't look like a known stdlib/third-party root, include it
    # We keep it simple — exclude single-word all-lowercase (likely stdlib)
    parts = module.split(".")
    return len(parts) > 1 or (len(parts) == 1 and parts[0][0].isupper())


def _is_relative_js(path: str) -> bool:
    """
    Decide whether a JavaScript/TypeScript import path is a "local"
    (intra-project) import.

    In JS/TS, local imports are conventionally written starting with "./"
    (same folder) or "../" (parent folder) - e.g. "./utils" or
    "../config/settings". Anything else (like "react" or "lodash") is
    assumed to be a package installed via npm, not part of this project.

    Args:
        path: The raw import path (e.g. "./utils", "react").

    Returns:
        True if the path starts with "./" or "../", False otherwise.
    """
    return path.startswith("./") or path.startswith("../")


def _resolve_js_import(source_dir: str, raw: str, all_paths: List[str]) -> str | None:
    """
    Resolve a relative JavaScript/TypeScript import (e.g. "./utils") to an
    actual file path within the repository.

    WHY THIS IS TRICKY:
    JS/TS imports usually omit the file extension, and sometimes even omit
    the filename entirely (pointing at a folder that has an "index" file
    inside it, e.g. "./components" might really mean
    "./components/index.tsx"). So we can't just look for an exact string
    match - we have to try several *candidate* paths and see if any of
    them exist in the repo's file list.

    HOW THIS WORKS, STEP BY STEP:
        1. Combine the importing file's folder (`source_dir`) with the raw
           import string (`raw`) to get a normalized base path. For
           example, if `source_dir` is "src/pages" and `raw` is
           "./utils", the base becomes "src/pages/utils".
        2. Build a list of "candidate" paths by trying common file
           extensions and the "index" file convention (e.g.
           "src/pages/utils.ts", "src/pages/utils/index.ts", etc.).
        3. Check each candidate against the real list of files in the
           repo (`all_paths`). The first one that matches is returned.
        4. If none match, return None (the import couldn't be resolved -
           it might point to a file type we don't track, or the import
           might actually be broken/dead code).

    Args:
        source_dir: The folder containing the file that has this import
            (e.g. "src/pages").
        raw: The raw relative import path as written in the source code
            (e.g. "./utils", "../config/settings").
        all_paths: The full list of known file paths in the repository.

    Returns:
        The matching file path from `all_paths`, or None if no match was
        found.
    """
    import os
    # Resolve relative path properly using normpath
    # os.path.normpath cleans up things like "src/pages/../utils" into
    # simply "src/utils", collapsing ".." and "." segments correctly.
    base = os.path.normpath(os.path.join(source_dir, raw))
    # Convert backslashes on Windows
    # (normpath uses OS-specific separators; on Windows that's "\", but we
    # want to work consistently with "/" since that's how paths are stored)
    base = base.replace('\\', '/')

    # Try the bare path first, then try appending common extensions and
    # the "index" file convention used by JS/TS tooling.
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
    """
    Resolve a Python module name (e.g. "myapp.models") to an actual file
    path within the repository.

    HOW PYTHON MODULE NAMES MAP TO FILES:
    Python module names use dots to represent folder structure - e.g. the
    module "myapp.models" corresponds to either:
        - a file at "myapp/models.py", or
        - a package folder "myapp/models/" with an "__init__.py" inside it
    So we convert the dots to slashes and try both possibilities.

    Args:
        module: The raw module name (e.g. "myapp.models", ".utils").
        all_paths: The full list of known file paths in the repository.

    Returns:
        The matching file path from `all_paths` (matched by checking if
        any known path *ends with* one of our candidate suffixes - this
        allows matching even if the module is nested inside other parent
        folders we didn't fully account for), or None if no match is
        found.
    """
    # Convert module.path -> module/path.py
    as_path = module.replace(".", "/")
    candidates = [
        as_path + ".py",
        as_path + "/__init__.py",
    ]
    for candidate in candidates:
        for p in all_paths:
            # We compare normalized, slash-based versions of both strings,
            # and check for a suffix match rather than an exact match, so
            # that e.g. candidate "models/user.py" can match a real path
            # like "src/myapp/models/user.py".
            if _normalize(p).endswith(_normalize(candidate)):
                return p
    return None


def _normalize(path: str) -> str:
    """
    Normalize a file path string so it can be safely compared to another
    path string, regardless of minor formatting differences.

    Specifically, this:
        - Converts Windows-style backslashes ("\\") to forward slashes
          ("/"), so paths are consistent across operating systems.
        - Strips any leading "./" so that "./src/app.py" and "src/app.py"
          are treated as equivalent.

    Args:
        path: The path string to normalize.

    Returns:
        The normalized path string.
    """
    return path.replace("\\", "/").lstrip("./")