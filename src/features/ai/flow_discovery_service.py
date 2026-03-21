
from __future__ import annotations

import json
import logging

from src.features.ai.bedrock import invoke_qwen
from src.features.ai.schema import (
    DiscoverFlowsRequest,
    DiscoverFlowsResponse,
    DiscoveredFlowSummary,
    EnrichFlowRequest,
    FlowStoryResponse,
    FlowStoryStep,
)

logger = logging.getLogger("api-main.ai.flow_discovery_service")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _node_lines(nodes: list[dict]) -> str:
    lines = []
    for n in nodes:
        line = f"  [{n['id']}] {n['label']} ({n['node_type']}"
        if n.get("is_async"):
            line += ", async"
        fp = n.get("file_path")
        ls = n.get("line_start")
        if fp and ls:
            line += f") — {fp}:{ls}"
        elif fp:
            line += f") — {fp}"
        else:
            line += ")"
        lines.append(line)
    return "\n".join(lines)


def _edge_lines(edges: list[dict], node_map: dict) -> str:
    lines = []
    for e in edges:
        src = node_map.get(e["source"], {}).get("label", e["source"])
        tgt = node_map.get(e["target"], {}).get("label", e["target"])
        lines.append(f"  {src} -> {tgt}")
    return "\n".join(lines)


# ─── POST /ai/discover-flows ──────────────────────────────────────────────────

DISCOVERY_SYSTEM = """You are a senior software architect analysing a codebase for a developer onboarding tool.
You receive a complete function call graph. Identify every distinct logical flow you can see.
A flow is a meaningful user-facing feature or system behaviour.
Always respond with valid JSON only. No markdown fences, no explanation outside the JSON."""


def _discovery_prompt(nodes: list[dict], edges: list[dict], node_map: dict) -> str:
    return f"""Here is the complete function call graph for a codebase.

FUNCTIONS ({len(nodes)} total):
{_node_lines(nodes)}

CALL RELATIONSHIPS ({len(edges)} total):
{_edge_lines(edges, node_map)}

Identify every distinct logical flow you can see.
Examples of flows: User Authentication, Repository Scan, Checkout, Data Sync, Notification Handling.

Respond ONLY with this JSON:
{{
  "flows": [
    {{
      "id": "flow-1",
      "name": "User Authentication",
      "description": "one sentence — what this flow does end to end"
    }}
  ]
}}

Rules:
- Name each flow clearly (2-5 words, title case)
- Only include flows with a clear purpose — skip noise
- Do not include function IDs, steps, or any other fields
"""


async def discover_flows(request: DiscoverFlowsRequest) -> DiscoverFlowsResponse:
    if not request.function_nodes:
        return DiscoverFlowsResponse(flows=[])

    nodes = [n.model_dump() for n in request.function_nodes]
    edges = [e.model_dump() for e in request.function_edges]
    node_map = {n["id"]: n for n in nodes}

    logger.info(
        "Discovering flows | functions=%d edges=%d",
        len(nodes), len(edges),
    )

    raw = invoke_qwen(
        prompt=_discovery_prompt(nodes, edges, node_map),
        system=DISCOVERY_SYSTEM,
        max_tokens=1500,
    )

    try:
        data = _parse(raw)
    except Exception as e:
        logger.error("Failed to parse discovery response | error=%s", e)
        return DiscoverFlowsResponse(flows=[])

    summaries = []
    for i, f in enumerate(data.get("flows", [])):
        summaries.append(
            DiscoveredFlowSummary(
                id=f.get("id", f"flow-{i+1}"),
                name=f.get("name", "Unnamed Flow"),
                description=f.get("description", ""),
                function_count=len(nodes),  # placeholder — full count shown per enrichment
            )
        )

    logger.info("Discovery complete | flows=%d", len(summaries))
    return DiscoverFlowsResponse(flows=summaries)


# ─── POST /ai/enrich-flow ─────────────────────────────────────────────────────

ENRICHMENT_SYSTEM = """You are a senior software engineer writing developer documentation for a new joiner.
You receive a full function call graph and a flow name.
Your job is to find the functions that belong to that flow and write a step-by-step execution narrative.
Be specific — use real function names, file paths, and line numbers.
Always respond with valid JSON only. No markdown fences, no explanation outside the JSON."""


def _enrichment_prompt(flow_name: str, nodes: list[dict], edges: list[dict], node_map: dict) -> str:
    return f"""Here is the complete function call graph for a codebase.

FUNCTIONS ({len(nodes)} total):
{_node_lines(nodes)}

CALL RELATIONSHIPS ({len(edges)} total):
{_edge_lines(edges, node_map)}

The user wants to understand the flow: "{flow_name}"

From the graph above:
1. Identify which functions belong to this flow
2. Determine the execution order
3. Write a narrative walkthrough for a developer who has never seen this code

If you cannot find a flow matching "{flow_name}" in the graph, return an empty steps array
with name set to "Not Found" and a helpful description.

Respond ONLY with this JSON:
{{
  "name": "exact flow name (2-5 words)",
  "description": "one sentence — what this flow does end to end",
  "entry_point": "name of the first function called",
  "steps": [
    {{
      "id": "step-1",
      "name": "exact function name from the graph",
      "description": "2-3 sentences: what it does, why it's here, what breaks without it",
      "type": "function|service|database|external",
      "file": "relative/path.ts or null",
      "line": 42,
      "is_async": false,
      "insight": "3-5 word label e.g. Entry point, Side effect risk, Async boundary"
    }}
  ]
}}

Type classification rules:
- "database"  — reads/writes DB, ORM, repository, runs queries
- "service"   — service class, business logic orchestrator, API client
- "external"  — GitHub API, OAuth, third-party HTTP, webhooks
- "function"  — everything else

Step rules:
- Follow execution order (entry point first)
- Use exact function names from the graph — do not rename
- File paths and line numbers must match the input exactly
- If a function has no file path, set file to null
- insight must be 3-5 words max
"""


async def enrich_flow(request: EnrichFlowRequest) -> FlowStoryResponse:
    nodes = [n.model_dump() for n in request.function_nodes]
    edges = [e.model_dump() for e in request.function_edges]
    node_map = {n["id"]: n for n in nodes}

    logger.info(
        "Enriching flow | name=%s functions=%d edges=%d",
        request.flow_name, len(nodes), len(edges),
    )

    raw = invoke_qwen(
        prompt=_enrichment_prompt(request.flow_name, nodes, edges, node_map),
        system=ENRICHMENT_SYSTEM,
        max_tokens=4000,
    )

    try:
        data = _parse(raw)
    except Exception as e:
        logger.error("Failed to parse enrichment response | error=%s flow=%s", e, request.flow_name)
        return FlowStoryResponse(
            name=request.flow_name,
            description="Failed to generate narrative.",
            entry_point=None,
            steps=[],
        )

    steps = []
    for s in data.get("steps", []):
        steps.append(FlowStoryStep(
            id=s.get("id", f"step-{len(steps)+1}"),
            name=s.get("name", ""),
            description=s.get("description", ""),
            type=s.get("type", "function"),
            file=s.get("file") or None,
            line=s.get("line") or None,
            is_async=s.get("is_async", False),
            insight=s.get("insight") or None,
        ))

    logger.info(
        "Enrichment complete | flow=%s steps=%d",
        request.flow_name, len(steps),
    )

    return FlowStoryResponse(
        name=data.get("name", request.flow_name),
        description=data.get("description", ""),
        entry_point=data.get("entry_point"),
        steps=steps,
    )