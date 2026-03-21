"""

Generates a narrative flow story from a raw function call graph.
Mirrors the architecture story pattern — uses Qwen via Bedrock,
validates the response, and retries if steps are malformed.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.features.ai.bedrock import invoke_qwen
from src.features.ai.schema import FlowStoryRequest, FlowStoryResponse, FlowStoryStep

logger = logging.getLogger("api-main.ai.flow_story_service")

SYSTEM_PROMPT = """You are a senior software engineer writing developer documentation for a new joiner.
You will be given a raw function call graph extracted from a real codebase.
Your job is to turn it into a clear, engaging, step-by-step execution narrative.
Be specific — use the real function names, file paths, and line numbers you are given.
Explain WHY each step happens, not just what it does.
Always respond with valid JSON only. No markdown fences, no explanation outside the JSON."""


# ─── Prompt builders ─────────────────────────────────────────────────────────


def _build_node_lines(nodes: list[dict]) -> str:
    lines = []
    for n in nodes:
        parts = [f"  [{n['id']}] {n['label']} ({n['node_type']}"]
        if n.get("is_async"):
            parts.append(", async")
        if n.get("file_path"):
            parts.append(f") — {n['file_path']}")
            if n.get("line_start"):
                parts[-1] += f":{n['line_start']}"
        else:
            parts.append(")")
        lines.append("".join(parts))
    return "\n".join(lines)


def _build_edge_lines(edges: list[dict], node_map: dict[str, dict]) -> str:
    lines = []
    for e in edges:
        src = node_map.get(e["source"], {}).get("label", e["source"])
        tgt = node_map.get(e["target"], {}).get("label", e["target"])
        lines.append(f"  {src} -> {tgt}  ({e['edge_type']})")
    return "\n".join(lines)


def build_flow_prompt(request: FlowStoryRequest) -> str:
    nodes = [n.model_dump() for n in request.function_nodes]
    edges = [e.model_dump() for e in request.function_edges]
    node_map = {n["id"]: n for n in nodes}

    node_lines = _build_node_lines(nodes)
    edge_lines = _build_edge_lines(edges, node_map)
    feature = request.feature_name or "repository overview"

    return f"""Feature / entry point being traced: "{feature}"

FUNCTIONS IN THIS FLOW ({len(nodes)} total):
{node_lines}

CALL RELATIONSHIPS ({len(edges)} total):
{edge_lines}

Generate a narrative walkthrough of this execution flow for a developer who has never seen this code.
Cover every meaningful function. Order the steps to follow the actual execution sequence.

Respond with this exact JSON structure and nothing else:
{{
  "name": "short title for this flow (max 6 words)",
  "description": "one sentence describing what this entire flow accomplishes",
  "steps": [
    {{
      "id": "step-1",
      "name": "the exact function name",
      "description": "2-3 sentences: what this function does, why it is called here, and what would break if it was removed",
      "type": "function|service|database|external",
      "file": "relative/file/path.ts or null",
      "line": 42,
      "is_async": false,
      "insight": "one sharp observation e.g. Entry point or Side effect risk or Pure utility or Async boundary"
    }}
  ]
}}

Rules for type classification:
- "database" — any function that reads/writes to a DB, ORM, repository, or runs queries
- "service" — service classes, business logic orchestrators, API client calls
- "external" — GitHub API, OAuth, third-party HTTP calls, webhooks
- "function" — everything else (pure functions, handlers, utilities, hooks)

Rules for steps:
- Follow execution order: entry point first, then what it calls, then what those call
- Every function in the FUNCTIONS list must appear in exactly one step
- Keep step names equal to the function name (do not rename)
- File paths and line numbers must match the input exactly — do not invent them
- If a function has no file path in the input, set file to null
- Descriptions must be specific to THIS codebase, not generic
- The insight field must be a short label (3-6 words max), not a sentence
"""


def build_retry_prompt(
    previous_steps: int,
    missing_ids: list[str],
    missing_labels: list[str],
) -> str:
    lines = "\n".join(
        f"  [{mid}] {mlabel}" for mid, mlabel in zip(missing_ids, missing_labels)
    )
    return f"""Your previous response had {previous_steps} steps but missed these functions:

{lines}

Generate ONLY the additional steps needed to cover the missing functions above.
Do not repeat functions already covered. Return JSON with the same structure:

{{
  "name": "unchanged",
  "description": "unchanged",
  "steps": [
    {{
      "id": "step-N",
      "name": "...",
      "description": "...",
      "type": "function|service|database|external",
      "file": "...",
      "line": null,
      "is_async": false,
      "insight": "..."
    }}
  ]
}}"""


# ─── Validation ───────────────────────────────────────────────────────────────


def validate_flow_story(
    story: dict,
    expected_ids: set[str],
    id_to_label: dict[str, str],
) -> tuple[list[str], list[str]]:
    """
    Returns (missing_ids, missing_labels) for functions not covered by any step.
    Uses function name matching as a fallback since LLM uses labels not ids.
    """
    covered_names: set[str] = set()
    for step in story.get("steps", []):
        name = step.get("name", "").strip()
        if name:
            covered_names.add(name.lower())

    missing_ids = []
    missing_labels = []
    for fid in expected_ids:
        label = id_to_label.get(fid, fid)
        if label.lower() not in covered_names:
            missing_ids.append(fid)
            missing_labels.append(label)

    return missing_ids, missing_labels


# ─── Parse ────────────────────────────────────────────────────────────────────


def parse_raw(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ─── Main entry point ─────────────────────────────────────────────────────────


async def generate_flow_story(
    request: FlowStoryRequest,
    max_retries: int = 2,
) -> FlowStoryResponse:

    if not request.function_nodes:
        return FlowStoryResponse(
            name="Empty Flow",
            description="No functions were found for this feature.",
            entry_point=request.feature_name,
            steps=[],
        )

    expected_ids = {n.id for n in request.function_nodes}
    id_to_label = {n.id: n.label for n in request.function_nodes}

    # ── Initial generation ────────────────────────────────────────────────────
    prompt = build_flow_prompt(request)
    raw = invoke_qwen(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=4000)
    story_data = parse_raw(raw)

    logger.info(
        "Flow story generated | feature=%s steps=%d functions=%d",
        request.feature_name,
        len(story_data.get("steps", [])),
        len(request.function_nodes),
    )

    # ── Validation + retry loop ───────────────────────────────────────────────
    for attempt in range(max_retries):
        missing_ids, missing_labels = validate_flow_story(
            story_data, expected_ids, id_to_label
        )

        if not missing_ids:
            logger.info("Flow story validation passed on attempt %d", attempt + 1)
            break

        logger.warning(
            "Flow story incomplete | attempt=%d missing=%d",
            attempt + 1,
            len(missing_ids),
        )

        if attempt == max_retries - 1:
            logger.warning("Max retries reached, returning best story so far")
            break

        retry_prompt = build_retry_prompt(
            previous_steps=len(story_data.get("steps", [])),
            missing_ids=missing_ids,
            missing_labels=missing_labels,
        )
        raw = invoke_qwen(prompt=retry_prompt, system=SYSTEM_PROMPT, max_tokens=2000)
        retry_data = parse_raw(raw)
        story_data["steps"].extend(retry_data.get("steps", []))

        logger.info(
            "Flow story retry %d merged | total_steps=%d",
            attempt + 1,
            len(story_data["steps"]),
        )

    # ── Build response ────────────────────────────────────────────────────────
    steps = []
    for s in story_data.get("steps", []):
        steps.append(
            FlowStoryStep(
                id=s.get("id", f"step-{len(steps)+1}"),
                name=s.get("name", ""),
                description=s.get("description", ""),
                type=s.get("type", "function"),
                file=s.get("file") or None,
                line=s.get("line") or None,
                is_async=s.get("is_async", False),
                insight=s.get("insight") or None,
            )
        )

    return FlowStoryResponse(
        name=story_data.get("name", request.feature_name or "Flow"),
        description=story_data.get("description", ""),
        entry_point=request.feature_name,
        steps=steps,
    )