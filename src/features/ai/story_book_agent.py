"""LangGraph agent that turns a repository's extracted context into a "Storybook":
a living, interactive guide that walks a developer from project setup ->
everyday tasks -> feature exploration (with how-each-feature-evolved-over-time).

The agent is a parent graph with three SUBGRAPHS:
  - project_setup       (architecture story + repo overview)
  - everyday_tasks      (entry points / hub files derived from the graph)
  - feature_exploration (discover flows -> per-flow story -> evolution note)

Input is the `repo_context_*.json` produced by `scripts/dump_repo_context.py`
and loaded by `notebooks/story_book_agent.ipynb`.

Each subgraph wraps the existing AI services in `src/features/ai`, so no new
LLM prompts are invented except the optional evolution note (which degrades
gracefully until git/PR history ingestion exists).
"""

from __future__ import annotations

import json
import logging
import operator
from pathlib import Path
from typing import Annotated, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send

from src.features.ai.flow_discovery_service import discover_flows
from src.features.ai.flow_story_service import generate_flow_story
from src.features.ai.schema import (
    DiscoverFlowsRequest,
    FlowEdgeSchema,
    FlowNodeSchema,
    FlowStoryEdgeRequest,
    FlowStoryRequest,
    FlowStoryStepRequest,
)
from src.features.ai.service import generate_architecture_story

logger = logging.getLogger("api-main.ai.story_book_agent")

DATA_DIR = Path("notebooks") / "data"


# ─── Shared state (used by parent graph AND every subgraph) ──────────────────
class StoryBookState(TypedDict):
    repo_id: str
    context: dict  # raw repo_context json
    intent: str

    file_nodes: list[dict]
    file_edges: list[dict]
    function_nodes: list[dict]
    function_edges: list[dict]
    overview_stats: dict
    repo_meta: dict

    # routing
    pending_stages: list[str]
    current_stage: str

    # feature-exploration working memory (reducers accumulate across fan-out)
    flows: list[dict]
    stories: Annotated[list[dict], operator.add]
    evolutions: Annotated[list[dict], operator.add]
    flow: Optional[dict]  # set per-branch by Send

    # outputs
    setup_view: Optional[dict]
    tasks_view: Optional[dict]
    features_view: Optional[dict]
    book: Optional[dict]
    errors: Annotated[list[str], operator.add]


# ─── Context -> schema mapping helpers ────────────────────────────────────────
def _to_flow_story_step(n: dict) -> FlowStoryStepRequest:
    return FlowStoryStepRequest(
        id=n["id"],
        label=n["label"],
        node_type=n.get("node_type", "function"),
        file_path=n.get("file_path"),
        is_async=n.get("is_async", False),
        line_start=n.get("line_start"),
    )


def _to_flow_node(n: dict) -> FlowNodeSchema:
    return FlowNodeSchema(
        id=n["id"],
        label=n["label"],
        node_type=n.get("node_type", "function"),
        file_path=n.get("file_path"),
        file_id=n.get("file_id"),
        is_async=bool(n.get("is_async", False)),
        line_start=n.get("line_start"),
        source_code=n.get("source_code"),
    )


def _to_flow_edge(e: dict) -> FlowEdgeSchema:
    return FlowEdgeSchema(
        source=e["source"],
        target=e["target"],
        edge_type=e.get("edge_type", "calls"),
    )


def _evolution_for_flow(flow: dict, context: dict) -> dict:
    """Evolution-over-time note.

    Until git/PR history ingestion exists, this returns a graceful placeholder
    instead of fabricating change history.
    """
    return {
        "flow": flow.get("name"),
        "summary": (
            "Evolution history not yet ingested. Connect git/PR history to "
            "enable 'how this feature changed over time'."
        ),
        "available_signals": {
            "default_branch": context.get("default_branch"),
            "language": context.get("language"),
            "functions_in_flow": flow.get("function_count"),
        },
    }


# ─── Subgraph 1: Project Setup ────────────────────────────────────────────────
def _build_setup_subgraph():
    g = StateGraph(StoryBookState)

    async def architecture(state: StoryBookState) -> dict:
        files = [n.get("file_path") or n.get("id") for n in state["file_nodes"]]
        story = await generate_architecture_story(
            files=files, edges=state["file_edges"]
        )
        return {
            "setup_view": {
                "repo_meta": state["repo_meta"],
                "overview": state["overview_stats"],
                "architecture_story": story.model_dump(),
            }
        }

    g.add_node("architecture", architecture)
    g.add_edge(START, "architecture")
    g.add_edge("architecture", END)
    return g.compile()


# ─── Subgraph 2: Everyday Tasks ───────────────────────────────────────────────
def _build_tasks_subgraph():
    g = StateGraph(StoryBookState)

    def derive(state: StoryBookState) -> dict:
        fn_by_id = {n["id"]: n for n in state["function_nodes"]}
        indegree = {n["id"]: 0 for n in state["function_nodes"]}
        for e in state["function_edges"]:
            if e["target"] in indegree:
                indegree[e["target"]] += 1
        entry_points = [
            {
                "label": fn_by_id[i]["label"],
                "file": fn_by_id[i].get("file_path"),
                "line": fn_by_id[i].get("line_start"),
            }
            for i, d in indegree.items()
            if d == 0
        ][:15]

        file_deg: dict[str, int] = {}
        for e in state["file_edges"]:
            file_deg[e["source"]] = file_deg.get(e["source"], 0) + 1
            file_deg[e["target"]] = file_deg.get(e["target"], 0) + 1
        hub_files = sorted(file_deg.items(), key=lambda kv: kv[1], reverse=True)[:10]

        return {
            "tasks_view": {
                "entry_points": entry_points,
                "hub_files": [{"file": f, "connections": c} for f, c in hub_files],
                "note": (
                    "Start here: entry points have no inbound calls; hub files "
                    "are imported by many modules."
                ),
            }
        }

    g.add_node("derive", derive)
    g.add_edge(START, "derive")
    g.add_edge("derive", END)
    return g.compile()


# ─── Subgraph 3: Feature Exploration (flows + stories + evolution) ────────────
def _build_exploration_subgraph():
    g = StateGraph(StoryBookState)

    async def discover(state: StoryBookState) -> dict:
        req = DiscoverFlowsRequest(
            repo_id=state["repo_id"],
            function_nodes=[_to_flow_story_step(n) for n in state["function_nodes"]],
            function_edges=[
                FlowStoryEdgeRequest(
                    source=e["source"],
                    target=e["target"],
                    edge_type=e.get("edge_type", "calls"),
                )
                for e in state["function_edges"]
            ],
        )
        res = await discover_flows(req)
        return {"flows": [f.model_dump() for f in res.flows]}

    def plan(state: StoryBookState) -> Command:
        # Fan out one story-generation branch per discovered flow.
        # The Send arg becomes the branch's state, so carry the graph it needs.
        return Command(
            goto=[
                Send(
                    "story",
                    {
                        "flow": f,
                        "function_nodes": state["function_nodes"],
                        "function_edges": state["function_edges"],
                    },
                )
                for f in state["flows"]
            ]
        )

    async def story(state: StoryBookState) -> dict:
        f = state["flow"]
        req = FlowStoryRequest(
            feature_name=f.get("name"),
            function_nodes=[_to_flow_node(n) for n in state["function_nodes"]],
            function_edges=[_to_flow_edge(e) for e in state["function_edges"]],
        )
        s = await generate_flow_story(req)
        return {"stories": [s.model_dump()]}

    def evo_plan(state: StoryBookState) -> Command:
        return Command(
            goto=[
                Send(
                    "evo",
                    {"flow": f, "context": state["context"]},
                )
                for f in state["flows"]
            ]
        )

    def evo(state: StoryBookState) -> dict:
        return {"evolutions": [_evolution_for_flow(state["flow"], state["context"])]}

    def finalize(state: StoryBookState) -> dict:
        evo_by_flow = {e["flow"]: e for e in state["evolutions"]}
        features = []
        for s in state["stories"]:
            name = s.get("name") or s.get("entry_point")
            features.append({"story": s, "evolution": evo_by_flow.get(name)})
        return {
            "features_view": {
                "features": features,
                "flow_count": len(state["flows"]),
            }
        }

    g.add_node("discover", discover)
    g.add_node("story", story)
    g.add_node("evo", evo)
    g.add_node("finalize", finalize)
    g.add_node("plan", plan)
    g.add_node("evo_plan", evo_plan)

    g.add_edge(START, "discover")
    g.add_edge("discover", "plan")
    g.add_edge("story", "evo_plan")
    g.add_edge("evo", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


# ─── Parent graph: router -> subgraphs -> assemble -> persist ─────────────────
def _stages_for_intent(intent: str) -> list[str]:
    if intent in ("feature", "how_does_it_work", "what_changed"):
        return ["feature_exploration"]
    if intent == "setup":
        return ["project_setup"]
    if intent == "tasks":
        return ["everyday_tasks"]
    # default / onboarding: full journey
    return ["project_setup", "everyday_tasks", "feature_exploration"]


def build_story_book_graph() -> StateGraph:
    g = StateGraph(StoryBookState)

    def router(state: StoryBookState) -> dict:
        pending = state.get("pending_stages") or []
        if not pending:
            return {"current_stage": "assemble", "pending_stages": []}
        return {"current_stage": pending[0], "pending_stages": pending[1:]}

    def route_target(state: StoryBookState) -> str:
        return state.get("current_stage") or "assemble"

    def assemble(state: StoryBookState) -> dict:
        book = {
            "repo_id": state["repo_id"],
            "full_name": (state["repo_meta"] or {}).get("full_name"),
            "intent": state["intent"],
            "project_setup": state.get("setup_view"),
            "everyday_tasks": state.get("tasks_view"),
            "features": state.get("features_view"),
        }
        return {"book": book}

    def persist(state: StoryBookState) -> dict:
        book = state.get("book") or {}
        out = DATA_DIR / f"story_book_{state['repo_id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(book, indent=2))
        logger.info("Storybook persisted -> %s", out)
        return {}

    g.add_node("router", router)
    g.add_node("project_setup", _build_setup_subgraph())
    g.add_node("everyday_tasks", _build_tasks_subgraph())
    g.add_node("feature_exploration", _build_exploration_subgraph())
    g.add_node("assemble", assemble)
    g.add_node("persist", persist)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        route_target,
        {
            "project_setup": "project_setup",
            "everyday_tasks": "everyday_tasks",
            "feature_exploration": "feature_exploration",
            "assemble": "assemble",
        },
    )
    g.add_edge("project_setup", "router")
    g.add_edge("everyday_tasks", "router")
    g.add_edge("feature_exploration", "router")
    g.add_edge("assemble", "persist")
    g.add_edge("persist", END)
    return g


_GRAPH = build_story_book_graph().compile()


async def generate_story_book(context: dict, intent: str = "onboarding") -> dict:
    """Run the Storybook agent over a repo_context dict and return the book."""
    repo_id = (
        context.get("connected_repo_id")
        or context.get("repo_id")
        or "unknown"
    )
    init: StoryBookState = {
        "repo_id": repo_id,
        "context": context,
        "intent": intent,
        "file_nodes": context.get("file_nodes", []),
        "file_edges": context.get("file_edges", []),
        "function_nodes": context.get("function_nodes", []),
        "function_edges": context.get("function_edges", []),
        "overview_stats": context.get("overview_stats", {}),
        "repo_meta": {
            "full_name": context.get("full_name"),
            "default_branch": context.get("default_branch"),
            "language": context.get("language"),
            "description": context.get("description"),
        },
        "pending_stages": _stages_for_intent(intent),
        "current_stage": "",
        "flows": [],
        "stories": [],
        "evolutions": [],
        "flow": None,
        "setup_view": None,
        "tasks_view": None,
        "features_view": None,
        "book": None,
        "errors": [],
    }
    result = await _GRAPH.ainvoke(init)
    return result.get("book") or {}
