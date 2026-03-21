import uuid
from collections import defaultdict
from pathlib import Path
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.features.github.schema import ArchEdgeSchema, ArchNodeSchema, ArchitectureGraphSchema
from src.features.github.repository import FileDependencyRepository, RepositoryFileRepository


class ArchitectureService:
    def __init__(self, db: AsyncSession):
        self.file_repo = RepositoryFileRepository(db)
        self.dep_repo = FileDependencyRepository(db)

    async def get_graph(self, connected_repo_id: uuid.UUID) -> ArchitectureGraphSchema:
        files = await self.file_repo.get_by_repo(connected_repo_id)
        deps = await self.dep_repo.get_by_repo(connected_repo_id)

        id_to_file = {f.id: f for f in files}

        # --- File level graph ---
        file_edges_map: dict[tuple, int] = defaultdict(int)

        for dep in deps:
            src = id_to_file.get(dep.source_file_id)
            tgt = id_to_file.get(dep.target_file_id)
            if src and tgt:
                file_edges_map[(src.path, tgt.path)] += 1

        file_nodes = [
            ArchNodeSchema(id=f.path, type="file")
            for f in files if not f.is_binary
        ]
        file_edges = [
            ArchEdgeSchema(source=src, target=tgt, weight=w)
            for (src, tgt), w in file_edges_map.items()
        ]

        # --- Folder level graph ---
        def top_folder(path: str) -> str:
            parts = Path(path).parts
            if len(parts) == 1:
                return "__root__"
            # Immediate parent folder of the file
            return str(Path(*parts[:-1]))

        folder_file_count: dict[str, int] = defaultdict(int)
        for f in files:
            if not f.is_binary:
                folder_file_count[top_folder(f.path)] += 1

        folder_edges_map: dict[tuple, int] = defaultdict(int)
        for dep in deps:
            src = id_to_file.get(dep.source_file_id)
            tgt = id_to_file.get(dep.target_file_id)
            if not src or not tgt:
                continue
            src_folder = top_folder(src.path)
            tgt_folder = top_folder(tgt.path)
            if src_folder != tgt_folder:
                folder_edges_map[(src_folder, tgt_folder)] += 1

        folder_ids = set(folder_file_count.keys())
        for src, tgt in folder_edges_map:
            folder_ids.add(src)
            folder_ids.add(tgt)

        folder_nodes = [
            ArchNodeSchema(id=fid, type="folder", file_count=folder_file_count.get(fid, 0))
            for fid in sorted(folder_ids)
        ]
        folder_edges = [
            ArchEdgeSchema(source=src, target=tgt, weight=w)
            for (src, tgt), w in folder_edges_map.items()
        ]

        return ArchitectureGraphSchema(
            nodes=folder_nodes,
            edges=folder_edges,
            file_nodes=file_nodes,
            file_edges=file_edges,
        )