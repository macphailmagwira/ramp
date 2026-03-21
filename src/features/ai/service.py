import json
import logging
from src.features.ai.bedrock import invoke_qwen
from src.features.ai.schema import ArchitectureStoryResponse

logger = logging.getLogger("api-main.ai.service")

SYSTEM_PROMPT = """You are a senior software engineer onboarding a new developer to a codebase.
Given a dependency graph of files and their imports, generate an engaging guided walkthrough.
Be specific — reference actual file names and real patterns you observe.
Point out architectural decisions, potential risks, and how data flows through the system.
Always respond with valid JSON only. No markdown fences, no explanation outside the JSON."""


def build_story_prompt(files: list[str], edges: list[dict]) -> str:
    edge_lines = "\n".join(f"  {e['source']} -> {e['target']}" for e in edges)
    file_lines = "\n".join(f"  {f}" for f in files)
    return f"""Here is a codebase dependency graph:

FILES ({len(files)} total):
{file_lines}

IMPORT DEPENDENCIES ({len(edges)} total):
{edge_lines}

Generate a guided story walkthrough with as many steps as needed to fully explain this codebase
to a new developer. Cover every meaningful file and dependency relationship.
Do not limit the number of steps.

Respond with this exact JSON structure and nothing else:
{{
  "summary": "2-3 sentence plain English overview of what this codebase is and how it is structured",
  "steps": [
    {{
      "title": "short compelling title for this step",
      "description": "2-3 sentences explaining what this file does, WHY it connects to the files it imports, and what would break if it was removed. If it has no connections, explain what it does in isolation and why it stands alone.",
      "highlight_nodes": ["exact/file/path.tsx"],
      "highlight_edges": [["source/file.tsx", "target/file.tsx"]],
      "insight": "one sharp engineering observation such as Entry point or God file risk or Clean separation or Standalone utility"
    }}
  ]
}}

Rules:
- highlight_nodes must contain exact file paths from the FILES list above
- highlight_edges must only contain [source, target] pairs that exist in the DEPENDENCIES list
- For EVERY file in a step: if it has edges in the dependency graph, those edges MUST appear in highlight_edges of that same step
- If a file imports nothing and nothing imports it, explicitly say it is standalone and describe its purpose
- If a file is an entry point, name the chain: "X boots Y which mounts Z"
- If a file is a hub (imported by many), explain what breaks without it
- Order steps logically: entry point first, then hub files, then layers, then leaves
- Every file in FILES must appear in at least one step's highlight_nodes
- Every dependency in DEPENDENCIES must appear in at least one step's highlight_edges
- If there are no edges for a step, use an empty array for highlight_edges
- Group related files in the same step when it makes the story flow naturally
- When two files are connected by an edge, they should ideally appear in the same step together
- Never repeat a file or edge across steps — each file and each edge must appear in exactly one step's highlight_nodes and highlight_edges respectively"""


def build_retry_prompt(
    files: list[str],
    edges: list[dict],
    previous_steps: int,
    missing_files: list[str],
    missing_edges: list[tuple],
    disconnected_nodes: list[dict],
) -> str:
    feedback_parts = []

    if missing_files:
        lines = "\n".join(f"  {f}" for f in missing_files)
        feedback_parts.append(f"MISSING FILES (not in any step):\n{lines}")

    if missing_edges:
        lines = "\n".join(f"  {s} -> {t}" for s, t in missing_edges)
        feedback_parts.append(f"MISSING EDGES (not in any step):\n{lines}")

    if disconnected_nodes:
        lines = "\n".join(
            f"  '{d['file']}' in step '{d['step_title']}' is missing edges: "
            + ", ".join(f"{e[0]} -> {e[1]}" for e in d["missing_edges"])
            for d in disconnected_nodes
        )
        feedback_parts.append(
            f"DISCONNECTED NODES (file appears in step but its connections are missing from that same step):\n{lines}\n"
            f"Fix: add the missing edges to the same step as the file, or move the file to a step that already includes its connected files."
        )

    feedback = "\n\n".join(feedback_parts)

    return f"""Your previous story had {previous_steps} steps but had these issues:

Do not repeat any files or edges that already appeared in the previous steps — only introduce new ones.

{feedback}

Generate ONLY the additional or corrected steps needed to fix the above issues.
Return as JSON with the same structure. No markdown, no explanation:

{{
  "summary": "same summary as before, unchanged",
  "steps": [
    {{
      "title": "...",
      "description": "Explain what this file does, why it connects to what it imports, and what would break without it. If standalone, say so explicitly.",
      "highlight_nodes": ["exact/file/path.tsx"],
      "highlight_edges": [["source.tsx", "target.tsx"]],
      "insight": "..."
    }}
  ]
}}"""


def validate_story(
    story_data: dict,
    files: list[str],
    edges: list[dict],
) -> tuple[list[str], list[tuple], list[dict]]:
    """
    Returns (missing_files, missing_edges, disconnected_nodes).

    missing_files:      files not covered in any step's highlight_nodes
    missing_edges:      edges not covered in any step's highlight_edges
    disconnected_nodes: files that appear in a step but whose edges are
                        missing from that same step (when both connected
                        files are present in the step)
    """
    covered_nodes: set[str] = set()
    covered_edges: set[tuple] = set()

    # Build edge lookup: file -> all edges it participates in
    file_edge_map: dict[str, list[tuple]] = {}
    for e in edges:
        file_edge_map.setdefault(e["source"], []).append((e["source"], e["target"]))
        file_edge_map.setdefault(e["target"], []).append((e["source"], e["target"]))

    disconnected_nodes: list[dict] = []

    for step in story_data.get("steps", []):
        step_nodes = set(step.get("highlight_nodes", []))
        step_edges = set(
            (e[0], e[1])
            for e in step.get("highlight_edges", [])
            if len(e) == 2
        )

        for node in step_nodes:
            covered_nodes.add(node)
            node_edges = file_edge_map.get(node, [])

            # Flag edges where BOTH ends are in this step but the edge itself is missing
            missing_in_step = [
                e for e in node_edges
                if e not in step_edges
                and e[0] in step_nodes
                and e[1] in step_nodes
            ]

            if missing_in_step:
                disconnected_nodes.append({
                    "file": node,
                    "step_title": step.get("title", ""),
                    "missing_edges": missing_in_step,
                })

        for edge in step.get("highlight_edges", []):
            if len(edge) == 2:
                covered_edges.add((edge[0], edge[1]))

    missing_files = [f for f in files if f not in covered_nodes]
    missing_edges = [
        (e["source"], e["target"])
        for e in edges
        if (e["source"], e["target"]) not in covered_edges
    ]

    return missing_files, missing_edges, disconnected_nodes


def parse_raw(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


async def generate_architecture_story(
    files: list[str],
    edges: list[dict],
    max_retries: int = 2,
) -> ArchitectureStoryResponse:

    # Initial generation
    prompt = build_story_prompt(files, edges)
    raw = invoke_qwen(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=6000)
    story_data = parse_raw(raw)

    logger.info(
        "Story generated | steps=%d files=%d edges=%d",
        len(story_data.get("steps", [])), len(files), len(edges),
    )

    # Validation + retry loop
    for attempt in range(max_retries):
        missing_files, missing_edges, disconnected_nodes = validate_story(
            story_data, files, edges
        )

        if not missing_files and not missing_edges and not disconnected_nodes:
            logger.info("Story validation passed on attempt %d", attempt + 1)
            break

        logger.warning(
            "Story incomplete | attempt=%d missing_files=%d missing_edges=%d disconnected=%d",
            attempt + 1,
            len(missing_files),
            len(missing_edges),
            len(disconnected_nodes),
        )

        if attempt == max_retries - 1:
            logger.warning("Max retries reached, returning best story so far")
            break

        retry_prompt = build_retry_prompt(
            files=files,
            edges=edges,
            previous_steps=len(story_data.get("steps", [])),
            missing_files=missing_files,
            missing_edges=missing_edges,
            disconnected_nodes=disconnected_nodes,
        )
        raw = invoke_qwen(prompt=retry_prompt, system=SYSTEM_PROMPT, max_tokens=3000)
        retry_data = parse_raw(raw)

        # Merge new/corrected steps into existing story
        story_data["steps"].extend(retry_data.get("steps", []))
        logger.info(
            "Story retry %d merged | total_steps=%d",
            attempt + 1,
            len(story_data["steps"]),
        )

    return ArchitectureStoryResponse(**story_data)