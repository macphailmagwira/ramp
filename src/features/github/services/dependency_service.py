import uuid
import logging
from pathlib import Path
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX
from src.features.github.models import FileDependency, RepositoryFile
from src.features.github.repository import FileDependencyRepository, RepositoryFileRepository
from src.features.github.services.dependency_parser import parse_dependencies, resolve_import_to_path

logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.dependency_service")

PARSEABLE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}


class DependencyGraphService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.file_repo = RepositoryFileRepository(db)
        self.dep_repo = FileDependencyRepository(db)

    async def build(
        self,
        connected_repo_id: uuid.UUID,
        file_contents: dict[str, str],  # path -> content
    ) -> int:
        """
        Parse all files, resolve imports to file IDs, persist to file_dependencies.
        Returns number of dependency edges saved.
        """
        files: List[RepositoryFile] = await self.file_repo.get_by_repo(connected_repo_id)

        # Build lookup: path -> file object
        path_to_file = {f.path: f for f in files}
        all_paths = list(path_to_file.keys())

        edges = []

        for file in files:
            if file.extension not in PARSEABLE_EXTENSIONS:
                continue
            content = file_contents.get(file.path)
            if not content:
                continue

            raw_imports = parse_dependencies(file.path, content)

            for raw_import, import_type in raw_imports:
                resolved = resolve_import_to_path(
                    file.path, raw_import, import_type, all_paths
                )
                if not resolved:
                    continue

                target_file = path_to_file.get(resolved)
                if not target_file or target_file.id == file.id:
                    continue

                edges.append({
                    "connected_repo_id": connected_repo_id,
                    "source_file_id": file.id,
                    "target_file_id": target_file.id,
                    "import_type": import_type,
                })

        await self.dep_repo.replace_for_repo(connected_repo_id, edges)
        logger.info("Dependency edges saved | repo=%s edges=%d", connected_repo_id, len(edges))
        return len(edges)