"""Dump a repository's unified data (file graph + function graph + metadata)
to JSON. Accepts either a ConnectedRepository.id (UUID) or a GitHub numeric
repo_id.

Usage:
    python scripts/dump_repo_context.py <repo_id>

Output:
    notebooks/repo_context_<connected_repo_id>.json
"""

import asyncio
import json
import sys
import uuid
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
import src.db.base  # noqa: registers all ORM models (incl. User)
from src.features.github.models import (
    ConnectedRepository,
    RepositoryFile,
    FileDependency,
    RepositoryFunction,
    FunctionCall,
)


def make_engine():
    return create_async_engine(settings.DATABASE_URL, echo=False, future=True)


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _top_folder(path: str) -> str:
    parts = Path(path).parts
    return str(Path(*parts[:-1])) if len(parts) > 1 else "__root__"


async def fetch(connected_repo_id: str) -> dict:
    engine = make_engine()
    SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with SessionFactory() as db:
            # ---- Resolve repo (UUID id OR GitHub numeric repo_id) ----
            repo = None
            if _is_uuid(connected_repo_id):
                repo = (
                    await db.execute(
                        select(ConnectedRepository).where(
                            ConnectedRepository.id == uuid.UUID(connected_repo_id)
                        )
                    )
                ).scalar_one_or_none()
            if repo is None:
                # repo_id (GitHub numeric) is NOT unique — multiple users can
                # connect the same repo. Take the most recently updated active one.
                matches = (
                    await db.execute(
                        select(ConnectedRepository)
                        .where(ConnectedRepository.repo_id == str(connected_repo_id))
                        .order_by(ConnectedRepository.updated_at.desc())
                    )
                ).scalars().all()
                repo = matches[0] if matches else None
            if repo is None:
                raise ValueError(f"No ConnectedRepository found for '{connected_repo_id}'")
            repo_id = repo.id

            # ---- Files ----
            files = list(
                (
                    await db.execute(
                        select(RepositoryFile).where(
                            RepositoryFile.connected_repo_id == repo_id
                        )
                    )
                ).scalars().all()
            )
            file_by_id = {f.id: f for f in files}

            file_nodes = [
                {
                    "id": f.path,
                    "label": f.name,
                    "node_type": "file",
                    "file_path": f.path,
                    "file_id": str(f.id),
                }
                for f in files
                if not f.is_binary
            ]

            # ---- File dependencies (imports) ----
            deps = list(
                (
                    await db.execute(
                        select(FileDependency).where(
                            FileDependency.connected_repo_id == repo_id
                        )
                    )
                ).scalars().all()
            )
            file_edges = []
            seen = set()
            for d in deps:
                src = file_by_id.get(d.source_file_id)
                tgt = file_by_id.get(d.target_file_id)
                if not src or not tgt:
                    continue
                key = (src.path, tgt.path)
                if key in seen:
                    continue
                seen.add(key)
                file_edges.append(
                    {
                        "source": src.path,
                        "target": tgt.path,
                        "edge_type": d.import_type or "import",
                    }
                )

            # ---- Functions / symbols ----
            funcs = list(
                (
                    await db.execute(
                        select(RepositoryFunction).where(
                            RepositoryFunction.connected_repo_id == repo_id
                        )
                    )
                ).scalars().all()
            )
            function_nodes = [
                {
                    "id": str(fn.id),
                    "label": fn.qualified_name or fn.name,
                    "node_type": fn.symbol_type or "function",
                    "file_path": file_by_id.get(fn.file_id).path if fn.file_id in file_by_id else None,
                    "file_id": str(fn.file_id) if fn.file_id else None,
                    "line_start": fn.line_start,
                    "line_end": fn.line_end,
                    "is_async": fn.is_async,
                    "source_code": fn.source_code,
                    "symbol_type": fn.symbol_type,
                    "return_type": fn.return_type,
                    "parameters": fn.parameters,
                    "docstring": fn.docstring,
                }
                for fn in funcs
            ]

            # ---- Function calls ----
            calls = list(
                (
                    await db.execute(
                        select(FunctionCall).where(
                            FunctionCall.connected_repo_id == repo_id
                        )
                    )
                ).scalars().all()
            )
            function_edges = [
                {
                    "source": str(c.source_function_id),
                    "target": str(c.target_function_id),
                    "edge_type": "calls",
                    "call_line": c.call_line,
                }
                for c in calls
            ]

            # ---- Derived metadata ----
            folders = {_top_folder(f.path) for f in files if not f.is_binary}
            languages = Counter(f.language for f in files if f.language)
            language = languages.most_common(1)[0][0] if languages else None

            return {
                "connected_repo_id": str(repo_id),
                "repo_id": repo.repo_id,
                "full_name": repo.full_name,
                "default_branch": repo.default_branch,
                "language": language,
                "description": repo.description,
                "overview_stats": {
                    "files": len(file_nodes),
                    "folders": len(folders),
                    "functions": len(function_nodes),
                    "dependencies": len(file_edges),
                },
                "file_nodes": file_nodes,
                "file_edges": file_edges,
                "function_nodes": function_nodes,
                "function_edges": function_edges,
            }
    finally:
        await engine.dispose()


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python scripts/dump_repo_context.py <repo_id>")
        raise SystemExit(1)

    repo_id = sys.argv[1]
    data = asyncio.run(fetch(repo_id))

    out = ROOT / "notebooks" / "data" / f"repo_context_{data['connected_repo_id']}.json"
    out.write_text(json.dumps(data, indent=2))

    s = data["overview_stats"]
    print(f"Repo       : {data['full_name']} ({data['connected_repo_id']})")
    print(f"Language   : {data['language']}")
    print(f"Branch     : {data['default_branch']}")
    print("---")
    print(f"Files      : {s['files']}")
    print(f"Folders    : {s['folders']}")
    print(f"Functions  : {s['functions']}")
    print(f"File deps  : {s['dependencies']}")
    print(f"Call edges : {len(data['function_edges'])}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
