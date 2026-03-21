"""
Given a file's content and the list of known symbol names in the repository,
detects function call relationships.

Returns a list of (caller_qualified_name, callee_name, call_line) tuples.
The service layer is responsible for resolving names → DB ids.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Any

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.call_graph_extractor")

CallEdge = tuple[str, str, int | None]  # (caller_qualified_name, callee_name, line)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_calls(
    file_path: str,
    content: str,
    known_names: set[str],
) -> list[CallEdge]:
    """
    Parse *content* and return call edges whose callee is in *known_names*.

    known_names — set of all function/method names across the entire repo
                  (used to filter out stdlib / third-party calls).
    """
    ext = Path(file_path).suffix.lower()
    try:
        if ext == ".py":
            return _extract_python_calls(content, known_names)
        if ext in (".ts", ".tsx", ".js", ".jsx"):
            return _extract_js_ts_calls(content, known_names)
    except Exception:
        logger.debug("Call extraction failed | file=%s", file_path, exc_info=True)
    return []


# ---------------------------------------------------------------------------
# Python — AST walk
# ---------------------------------------------------------------------------


def _extract_python_calls(content: str, known_names: set[str]) -> list[CallEdge]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    edges: list[CallEdge] = []
    _walk_py_scope(tree, caller_qname=None, edges=edges, known_names=known_names)
    return edges


def _walk_py_scope(
    node: ast.AST,
    caller_qname: str | None,
    edges: list[CallEdge],
    known_names: set[str],
    class_prefix: str | None = None,
) -> None:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            _walk_py_scope(
                child,
                caller_qname=caller_qname,
                edges=edges,
                known_names=known_names,
                class_prefix=child.name,
            )
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qname = f"{class_prefix}.{child.name}" if class_prefix else child.name
            # Walk the body of this function to find its call sites
            for sub in ast.walk(child):
                if isinstance(sub, ast.Call):
                    callee = _py_call_name(sub)
                    if callee and callee in known_names and callee != qname:
                        line = getattr(sub, "lineno", None)
                        edges.append((qname, callee, line))
            # Recurse into nested functions
            _walk_py_scope(
                child,
                caller_qname=qname,
                edges=edges,
                known_names=known_names,
                class_prefix=class_prefix,
            )
        else:
            _walk_py_scope(
                child,
                caller_qname=caller_qname,
                edges=edges,
                known_names=known_names,
                class_prefix=class_prefix,
            )


def _py_call_name(node: ast.Call) -> str | None:
    """Extract the simple name being called, ignoring attribute chains."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr  # e.g. self.foo() → "foo"
    return None


# ---------------------------------------------------------------------------
# TypeScript / JavaScript — regex-based
# ---------------------------------------------------------------------------

_TS_FUNC_DEF = re.compile(
    r"""
    (?:export\s+)?(?:default\s+)?(?:async\s+)?
    (?:function\s*\*?\s*)
    (?P<n>[A-Za-z_$][\w$]*)
    \s*[<(]
    |
    (?:export\s+)?(?:const|let|var)\s+
    (?P<n2>[A-Za-z_$][\w$]*)
    \s*=\s*(?:async\s+)?(?:\([^)]*\)|\w+)\s*=>
    """,
    re.VERBOSE | re.MULTILINE,
)

_TS_CALL = re.compile(
    r"""
    (?<![.\w])       # not a method call from an object literal
    (?P<n>[A-Za-z_$][\w$]*)
    \s*\(
    """,
    re.VERBOSE | re.MULTILINE,
)

_KEYWORDS = frozenset(
    {
        "if", "for", "while", "switch", "catch", "return", "typeof", "instanceof",
        "new", "delete", "void", "throw", "await", "yield", "async", "function",
        "class", "import", "export", "from", "const", "let", "var", "of", "in",
        "super", "this", "true", "false", "null", "undefined",
    }
)

_SINGLE_LINE_COMMENT = re.compile(r"//.*$", re.MULTILINE)
_MULTI_LINE_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(s: str) -> str:
    s = _MULTI_LINE_COMMENT.sub("", s)
    return _SINGLE_LINE_COMMENT.sub("", s)


def _line_of(content: str, pos: int) -> int:
    return content.count("\n", 0, pos) + 1


def _extract_js_ts_calls(content: str, known_names: set[str]) -> list[CallEdge]:
    stripped = _strip_comments(content)
    edges: list[CallEdge] = []

    # Collect all function definition ranges with their names
    func_ranges: list[tuple[str, int]] = []  # (qname, start_pos)
    for m in _TS_FUNC_DEF.finditer(stripped):
        name = m.group("n") or m.group("n2")
        if name:
            func_ranges.append((name, m.start()))

    # For each call site, attribute it to the nearest enclosing function
    # (simple heuristic: the last function def that starts before the call)
    for m in _TS_CALL.finditer(stripped):
        callee = m.group("n")
        if callee in _KEYWORDS or callee not in known_names:
            continue
        call_pos = m.start()
        line = _line_of(stripped, call_pos)

        # Find the enclosing function (last def before this call)
        caller: str | None = None
        for fname, fstart in reversed(func_ranges):
            if fstart < call_pos:
                caller = fname
                break

        if caller and caller != callee:
            edges.append((caller, callee, line))

    return edges