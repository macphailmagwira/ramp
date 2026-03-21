"""
Extracts functions, methods, and classes from Python and TypeScript/JavaScript
source files.  Returns plain dicts ready to be bulk-inserted into
repository_functions.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path
from typing import Any

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.symbol_extractor")

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_symbols(file_path: str, content: str) -> list[dict[str, Any]]:
    """
    Parse *content* and return a list of symbol dicts.

    Each dict has the keys expected by RepositoryFunctionRepository.replace_for_repo:
        name, qualified_name, symbol_type, parameters (JSON str), return_type,
        docstring, line_start, line_end, class_name, is_async
    """
    ext = Path(file_path).suffix.lower()
    try:
        if ext == ".py":
            return _extract_python(content)
        if ext in (".ts", ".tsx", ".js", ".jsx"):
            return _extract_js_ts(content)
    except Exception:
        logger.debug("Symbol extraction failed | file=%s", file_path, exc_info=True)
    return []


# ---------------------------------------------------------------------------
# Python extraction — uses stdlib `ast`
# ---------------------------------------------------------------------------


def _extract_python(content: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    symbols: list[dict[str, Any]] = []
    _visit_python_node(tree, symbols, class_name=None)
    return symbols


def _visit_python_node(
    node: ast.AST,
    symbols: list[dict[str, Any]],
    class_name: str | None,
) -> None:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            qualified = f"{class_name}.{child.name}" if class_name else child.name
            symbols.append(
                _make_symbol(
                    name=child.name,
                    qualified_name=qualified,
                    symbol_type="class",
                    parameters=None,
                    return_type=None,
                    docstring=_py_docstring(child),
                    line_start=child.lineno,
                    line_end=child.end_lineno,
                    class_name=class_name,
                    is_async=False,
                )
            )
            _visit_python_node(child, symbols, class_name=child.name)

        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_async = isinstance(child, ast.AsyncFunctionDef)
            stype = "method" if class_name else "function"
            qualified = f"{class_name}.{child.name}" if class_name else child.name
            params = _py_params(child)
            ret = _py_return_type(child)
            symbols.append(
                _make_symbol(
                    name=child.name,
                    qualified_name=qualified,
                    symbol_type=stype,
                    parameters=json.dumps(params),
                    return_type=ret,
                    docstring=_py_docstring(child),
                    line_start=child.lineno,
                    line_end=child.end_lineno,
                    class_name=class_name,
                    is_async=is_async,
                )
            )
            # Nested functions (closures) — recurse without changing class_name
            _visit_python_node(child, symbols, class_name=class_name)

        else:
            _visit_python_node(child, symbols, class_name=class_name)


def _py_docstring(node: ast.AST) -> str | None:
    return ast.get_docstring(node)  # type: ignore[arg-type]


def _py_params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
    params = []
    args = node.args
    # Build default offset: last N positional args may have defaults
    n_defaults = len(args.defaults)
    all_args = args.posonlyargs + args.args
    default_offset = len(all_args) - n_defaults

    for i, arg in enumerate(all_args):
        default_val = None
        if i >= default_offset:
            d = args.defaults[i - default_offset]
            try:
                default_val = ast.unparse(d)
            except Exception:
                default_val = "..."

        annotation = None
        if arg.annotation:
            try:
                annotation = ast.unparse(arg.annotation)
            except Exception:
                pass

        params.append({"name": arg.arg, "type": annotation, "default": default_val})

    # *args
    if args.vararg:
        annotation = None
        if args.vararg.annotation:
            try:
                annotation = ast.unparse(args.vararg.annotation)
            except Exception:
                pass
        params.append({"name": f"*{args.vararg.arg}", "type": annotation, "default": None})

    # **kwargs
    if args.kwarg:
        annotation = None
        if args.kwarg.annotation:
            try:
                annotation = ast.unparse(args.kwarg.annotation)
            except Exception:
                pass
        params.append({"name": f"**{args.kwarg.arg}", "type": annotation, "default": None})

    return params


def _py_return_type(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    if node.returns:
        try:
            return ast.unparse(node.returns)
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# TypeScript / JavaScript extraction — regex-based (no full AST)
# ---------------------------------------------------------------------------

# Matches: (export) (default) (async) function name(  OR  const/let/var name = (async) (
# Group 1: async keyword presence
# Group 2: function name
_TS_FUNC = re.compile(
    r"""
    (?:export\s+)?(?:default\s+)?
    (?P<async>async\s+)?
    (?:function\s*\*?\s*)
    (?P<name>[A-Za-z_$][\w$]*)
    \s*[<(]
    """,
    re.VERBOSE | re.MULTILINE,
)

# Arrow / const functions: const foo = async (...) =>  or  export const foo = (
_TS_ARROW = re.compile(
    r"""
    (?:export\s+)?
    (?:const|let|var)\s+
    (?P<name>[A-Za-z_$][\w$]*)
    \s*=\s*
    (?P<async>async\s+)?
    (?:\([^)]*\)|\w+)\s*=>
    """,
    re.VERBOSE | re.MULTILINE,
)

# class Foo  /  class Foo extends Bar
_TS_CLASS = re.compile(
    r"""
    (?:export\s+)?(?:abstract\s+)?
    class\s+
    (?P<name>[A-Za-z_$][\w$]*)
    """,
    re.VERBOSE | re.MULTILINE,
)

# method inside class:  methodName(  or  async methodName(
_TS_METHOD = re.compile(
    r"""
    ^\s+
    (?:(?:public|private|protected|static|readonly|override|abstract)\s+)*
    (?P<async>async\s+)?
    (?P<name>[A-Za-z_$][\w$]*)
    \s*[<(]
    """,
    re.VERBOSE | re.MULTILINE,
)

_SINGLE_LINE_COMMENT = re.compile(r"//.*$", re.MULTILINE)
_MULTI_LINE_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_ts_comments(content: str) -> str:
    content = _MULTI_LINE_COMMENT.sub("", content)
    content = _SINGLE_LINE_COMMENT.sub("", content)
    return content


def _line_of(content: str, pos: int) -> int:
    return content.count("\n", 0, pos) + 1


def _extract_js_ts(content: str) -> list[dict[str, Any]]:
    symbols: list[dict[str, Any]] = []
    stripped = _strip_ts_comments(content)

    # Classes
    for m in _TS_CLASS.finditer(stripped):
        line = _line_of(stripped, m.start())
        symbols.append(
            _make_symbol(
                name=m.group("name"),
                qualified_name=m.group("name"),
                symbol_type="class",
                parameters=None,
                return_type=None,
                docstring=None,
                line_start=line,
                line_end=None,
                class_name=None,
                is_async=False,
            )
        )

    # Named functions
    for m in _TS_FUNC.finditer(stripped):
        name = m.group("name")
        is_async = bool(m.group("async"))
        line = _line_of(stripped, m.start())
        symbols.append(
            _make_symbol(
                name=name,
                qualified_name=name,
                symbol_type="function",
                parameters=None,
                return_type=None,
                docstring=None,
                line_start=line,
                line_end=None,
                class_name=None,
                is_async=is_async,
            )
        )

    # Arrow functions assigned to const/let/var
    for m in _TS_ARROW.finditer(stripped):
        name = m.group("name")
        is_async = bool(m.group("async"))
        line = _line_of(stripped, m.start())
        symbols.append(
            _make_symbol(
                name=name,
                qualified_name=name,
                symbol_type="function",
                parameters=None,
                return_type=None,
                docstring=None,
                line_start=line,
                line_end=None,
                class_name=None,
                is_async=is_async,
            )
        )

    # Deduplicate by (name, line_start)
    seen: set[tuple] = set()
    deduped = []
    for s in symbols:
        key = (s["name"], s["line_start"])
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    return deduped


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_symbol(
    *,
    name: str,
    qualified_name: str | None,
    symbol_type: str,
    parameters: str | None,
    return_type: str | None,
    docstring: str | None,
    line_start: int | None,
    line_end: int | None,
    class_name: str | None,
    is_async: bool,
) -> dict[str, Any]:
    return {
        "name": name,
        "qualified_name": qualified_name,
        "symbol_type": symbol_type,
        "parameters": parameters,
        "return_type": return_type,
        "docstring": docstring,
        "line_start": line_start,
        "line_end": line_end,
        "class_name": class_name,
        "is_async": is_async,
    }