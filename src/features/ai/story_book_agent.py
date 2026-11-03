"""LangGraph agent that turns a repository into a "Storybook": a living,
interactive guide that walks a developer through getting a project running.

This module is the *orchestrator*. It fans out one subgraph per "section" and
then assembles + persists the result. The actual section logic lives in their
own modules (see ``src.features.ai.storybook``); today the only section is SET UP
(``src.features.ai.storybook.setup``), but LEARN / BUILD can slot in later by
appending to ``SUBGRAPHS``.

The LLM call goes to Qwen on AWS Bedrock (``invoke_qwen`` in
``src.features.ai.bedrock``). The finished book is written to ``OUTPUT_DIR`` as
``story_book_<project>.json``.

This implementation replaces the earlier ``repo_context``-based version and is a
port of ``notebooks/story_book_agent.ipynb``.
"""

from __future__ import annotations

import json
import logging
import operator
from pathlib import Path
from typing import Annotated, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from src.features.ai.storybook.setup import SETUP_NAME, build_setup

logger = logging.getLogger("api-main.ai.story_book_agent")

OUTPUT_DIR = "outputs/storybook"  # where the finished book is saved


def merge_dicts(a, b):
    """Reducer: combine results from subgraphs that run at the same time."""
    return {**(a or {}), **(b or {})}


class StorybookState(TypedDict):
    project_root: str
    files: Optional[list]                       # stored RepositoryFile rows (DB source)
    output_dir: str
    sections: Annotated[dict, merge_dicts]     # {"set_up": {...}, "learn": {...}}
    errors: Annotated[list, operator.add]
    book: Optional[dict]


def as_node(name, builder):
    """Wrap a subgraph as one parent node. Only its output and errors come back."""
    subgraph = builder()

    async def run(state):
        try:
            result = await subgraph.ainvoke({
                "project_root": state["project_root"],
                "files": state.get("files"),
            })
            return {"sections": {name: result.get("output", {})},
                    "errors": result.get("errors", [])}
        except Exception as e:
            return {"sections": {name: {}}, "errors": [f"{name}: {e}"]}

    return run


def assemble(state):
    return {"book": {
        "project": Path(state["project_root"]).resolve().name,
        "sections": {name: state["sections"].get(name) for name, _ in SUBGRAPHS},
        "errors": state["errors"],
    }}


def persist(state):
    book = state["book"]
    out = Path(state["output_dir"]) / f"story_book_{book['project']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(book, indent=2))
    logger.info("Storybook persisted -> %s", out)
    return {}


def build_parent():
    g = StateGraph(StorybookState)
    for name, builder in SUBGRAPHS:
        g.add_node(name, as_node(name, builder))
        g.add_edge(START, name)                                   # all start together
    g.add_node("assemble", assemble)
    g.add_node("persist", persist)
    g.add_edge([name for name, _ in SUBGRAPHS], "assemble")       # wait for ALL
    g.add_edge("assemble", "persist")
    g.add_edge("persist", END)
    return g.compile()


SUBGRAPHS = [
    (SETUP_NAME, build_setup),
    # (LEARN_NAME, build_learn),   # later
    # (BUILD_NAME, build_build),   # later
]

GRAPH = build_parent()


async def generate_storybook(project_root=None, files=None, output_dir=OUTPUT_DIR):
    """Run the Storybook agent and return the book dict.

    Pass ``project_root`` to read files from a folder on disk (original path),
    or pass ``files`` (a list of stored RepositoryFile rows) to build the book
    from already-indexed repository content in the database.
    """
    result = await GRAPH.ainvoke({
        "project_root": str(project_root) if project_root else "",
        "files": files,
        "output_dir": output_dir,
        "sections": {}, "errors": [], "book": None,
    })
    return result["book"]
