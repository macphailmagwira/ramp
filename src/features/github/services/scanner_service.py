
import os
import shutil
import tempfile
import uuid
import subprocess
import logging
from pathlib import Path
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX
from src.features.github.repository import RepositoryFileRepository
from src.features.github.services.dependency_service import DependencyGraphService
from src.features.github.services.symbol_service import SymbolExtractionService  


logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.scanner.service")

IGNORED_DIRS = {
    ".git", "node_modules", "dist", "build", "__pycache__",
    ".next", ".nuxt", "coverage", ".venv", "venv", "env",
    ".mypy_cache", ".pytest_cache", "vendor", "target",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".mp4", ".mov", ".woff",
    ".woff2", ".ttf", ".otf", ".eot", ".pyc", ".class",
}

LANGUAGE_MAP = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".go": "Go",
    ".rs": "Rust", ".java": "Java", ".rb": "Ruby", ".php": "PHP",
    ".cs": "C#", ".cpp": "C++", ".c": "C", ".swift": "Swift",
    ".kt": "Kotlin", ".md": "Markdown", ".yaml": "YAML",
    ".yml": "YAML", ".json": "JSON", ".html": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".sql": "SQL",
    ".sh": "Shell", ".bash": "Shell", ".dockerfile": "Docker",
}


class RepoScannerService:
    def __init__(self, db: AsyncSession):
        self.file_repo = RepositoryFileRepository(db)

    async def scan(
        self,
        connected_repo_id: uuid.UUID,
        user_id: uuid.UUID,
        clone_url: str,
        access_token: str,
        default_branch: str = "main",
    ) -> int:
        tmpdir = tempfile.mkdtemp(prefix="ramp_scan_")

        try:
            await self._clone(clone_url, access_token, tmpdir, default_branch)
            files = self._walk(Path(tmpdir))

            await self.file_repo.replace_for_repo(connected_repo_id, user_id, files)
            logger.info("Metadata persisted | repo=%s files=%d", connected_repo_id, len(files))

            # --- Read parseable source files once; reuse for all analysis steps ---
            file_contents = self._read_parseable_files(Path(tmpdir), files)

            # --- Dependency graph ---
            logger.info("Parsing dependencies | repo=%s", connected_repo_id)
            dep_service = DependencyGraphService(self.file_repo.db)
            edge_count = await dep_service.build(connected_repo_id, file_contents)
            logger.info("Dependency graph built | repo=%s edges=%d", connected_repo_id, edge_count)

            # --- Symbol extraction + call graph (NEW) ---
            logger.info("Extracting symbols | repo=%s", connected_repo_id)
            sym_service = SymbolExtractionService(self.file_repo.db)
            sym_count = await sym_service.extract_and_store_symbols(
                connected_repo_id, file_contents
            )
            logger.info("Symbols stored | repo=%s symbols=%d", connected_repo_id, sym_count)

            call_count = await sym_service.build_call_graph(
                connected_repo_id, file_contents
            )
            logger.info("Call graph built | repo=%s calls=%d", connected_repo_id, call_count)

            return len(files)

        except Exception:
            logger.exception("Scan error | repo=%s", connected_repo_id)
            raise

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _read_parseable_files(self, root: Path, files: List[dict]) -> dict[str, str]:
        """Read content of parseable source files into memory."""
        PARSEABLE = {".py", ".ts", ".tsx", ".js", ".jsx"}
        contents = {}
        for f in files:
            if f.get("is_binary") or f.get("extension") not in PARSEABLE:
                continue
            full_path = root / f["path"]
            try:
                contents[f["path"]] = full_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        return contents

    async def _clone(
        self, clone_url: str, access_token: str, dest: str, branch: str
    ) -> None:
        authed_url = clone_url.replace("https://", f"https://{access_token}@")
        logger.debug("Running git clone | branch=%s dest=%s", branch, dest)

        result = subprocess.run(
            [
                "git", "clone",
                "--depth", "1",
                "--branch", branch,
                "--single-branch",
                authed_url,
                dest,
            ],
            capture_output=True,
            timeout=120,
        )

        if result.returncode != 0:
            error_msg = result.stderr.decode()[:500]
            logger.error("Git clone failed | branch=%s error=%s", branch, error_msg)
            raise RuntimeError(f"Git clone failed: {error_msg}")

        logger.debug("Git clone succeeded | branch=%s", branch)

    def _walk(self, root: Path) -> List[dict]:
        results = []
        skipped_dirs = []

        for dirpath, dirnames, filenames in os.walk(root):
            pruned = [d for d in dirnames if d in IGNORED_DIRS or d.startswith(".")]
            skipped_dirs.extend(pruned)
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]

            for filename in filenames:
                filepath = Path(dirpath) / filename
                rel_path = str(filepath.relative_to(root))
                ext = filepath.suffix.lower()
                try:
                    size = filepath.stat().st_size
                except OSError:
                    logger.debug("Could not stat file | path=%s", rel_path)
                    size = 0

                results.append({
                    "path": rel_path,
                    "name": filename,
                    "extension": ext or None,
                    "language": LANGUAGE_MAP.get(ext),
                    "size_bytes": size,
                    "is_binary": ext in BINARY_EXTENSIONS,
                })

        if skipped_dirs:
            logger.debug(
                "Skipped ignored dirs | count=%d dirs=%s",
                len(skipped_dirs), skipped_dirs,
            )

        return results