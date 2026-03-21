from __future__ import annotations

import logging
import uuid
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX
from src.features.github.models import RepositoryFile, RepositoryFunction
from src.features.github.repository import (
    FunctionCallRepository,
    RepositoryFileRepository,
    RepositoryFunctionRepository,
)
from src.features.github.services.call_graph_extractor import extract_calls
from src.features.github.services.symbol_extractor import extract_symbols

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.symbol_service")

PARSEABLE = {".py", ".ts", ".tsx", ".js", ".jsx"}


class SymbolExtractionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.file_repo = RepositoryFileRepository(db)
        self.func_repo = RepositoryFunctionRepository(db)
        self.call_repo = FunctionCallRepository(db)

    async def extract_and_store_symbols(
        self,
        connected_repo_id: uuid.UUID,
        file_contents: dict[str, str],
    ) -> int:
        files: List[RepositoryFile] = await self.file_repo.get_by_repo(connected_repo_id)
        total = 0

        for f in files:
            if f.is_binary or f.extension not in PARSEABLE:
                continue
            content = file_contents.get(f.path)
            if not content:
                continue

            symbols = extract_symbols(f.path, content)
            if not symbols:
                continue

            await self.func_repo.replace_for_repo(connected_repo_id, f.id, symbols)
            total += len(symbols)
            logger.debug("Symbols extracted | file=%s count=%d", f.path, len(symbols))

        logger.info(
            "Symbol extraction complete | repo=%s total_symbols=%d",
            connected_repo_id,
            total,
        )
        return total

    async def build_call_graph(
        self,
        connected_repo_id: uuid.UUID,
        file_contents: dict[str, str],
    ) -> int:
        all_funcs: List[RepositoryFunction] = await self.func_repo.get_by_repo(connected_repo_id)

        name_to_funcs: dict[str, list[RepositoryFunction]] = {}
        for fn in all_funcs:
            name_to_funcs.setdefault(fn.name, []).append(fn)

        qname_to_func: dict[str, RepositoryFunction] = {
            fn.qualified_name: fn for fn in all_funcs if fn.qualified_name
        }

        known_names: set[str] = set(name_to_funcs.keys())

        files: List[RepositoryFile] = await self.file_repo.get_by_repo(connected_repo_id)

        edges: list[dict] = []

        for f in files:
            if f.is_binary or f.extension not in PARSEABLE:
                continue
            content = file_contents.get(f.path)
            if not content:
                continue

            raw_calls = extract_calls(f.path, content, known_names)

            for caller_qname, callee_name, call_line in raw_calls:
                caller_fn: RepositoryFunction | None = qname_to_func.get(caller_qname)
                if caller_fn is None:
                    candidates = name_to_funcs.get(caller_qname, [])
                    same_file = [c for c in candidates if c.file_id == f.id]
                    caller_fn = same_file[0] if same_file else (candidates[0] if candidates else None)

                if caller_fn is None:
                    continue

                callee_candidates = name_to_funcs.get(callee_name, [])
                if not callee_candidates:
                    continue
                same_file_callee = [c for c in callee_candidates if c.file_id == f.id]
                callee_fn: RepositoryFunction = same_file_callee[0] if same_file_callee else callee_candidates[0]

                if callee_fn.id == caller_fn.id:
                    continue

                edges.append(
                    {
                        "connected_repo_id": connected_repo_id,
                        "source_function_id": caller_fn.id,
                        "target_function_id": callee_fn.id,
                        "call_line": call_line,
                    }
                )

        seen: set[tuple] = set()
        deduped = []
        for e in edges:
            key = (e["source_function_id"], e["target_function_id"])
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        await self.call_repo.replace_for_repo(connected_repo_id, deduped)
        logger.info(
            "Call graph built | repo=%s edges=%d",
            connected_repo_id,
            len(deduped),
        )
        return len(deduped)