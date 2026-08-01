"""
Repository Scanner Service
===========================

WHAT THIS FILE DOES (in plain English):
This file is responsible for taking a GitHub repository URL and turning it into
useful, searchable data that gets stored in our database. Think of it like a
librarian who:
    1. Goes and fetches a book (clones the repo)
    2. Reads every page and makes an index (walks the file tree)
    3. Notes which chapters reference other chapters (dependency graph)
    4. Lists every character/term mentioned and where (symbol extraction)
    5. Notes who talks to whom in the story (call graph)

While all of this happens, we keep updating a "progress bar" value in the
database so that a user watching a UI can see how far along the scan is.

KEY TERMS FOR BEGINNERS:
- "async def" means this function can run without blocking other code while
  it waits (e.g., while waiting for the database or a subprocess to finish).
- "await" means "pause here until this asynchronous operation finishes".
- A "temp directory" is a throwaway folder on disk we use to store the cloned
  repo temporarily; we delete it when we're done (even if something fails).
- "logger.info" writes a normal, human-readable status update to our logs.
- "logger.debug" writes MORE detailed information, usually only turned on
  when actively troubleshooting a problem. Per team convention here, debug
  logs also print out actual data/output values (not just "it happened"),
  so that anyone reading the logs can see exactly what was found/produced.
"""

import os
import shutil
import tempfile
import uuid
import subprocess
import logging
from pathlib import Path
from typing import List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX
from src.features.github.repository import RepositoryFileRepository
from src.features.github.services.dependency_service import DependencyGraphService
from src.features.github.services.symbol_service import SymbolExtractionService
from src.features.github.models import ConnectedRepository


# The logger is how this module writes messages to our centralized logging
# system. Using a hierarchical name (prefix + ".scanner.service") lets us
# filter/search logs specifically from this file later on.
logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.scanner.service")

# Directories we never want to scan. These are typically auto-generated,
# huge, or irrelevant to understanding the actual source code
# (e.g. "node_modules" can contain tens of thousands of files!).
IGNORED_DIRS = {
    ".git", "node_modules", "dist", "build", "__pycache__",
    ".next", ".nuxt", "coverage", ".venv", "venv", "env",
    ".mypy_cache", ".pytest_cache", "vendor", "target",
}

# File extensions that are NOT plain text/source code - things like images,
# archives, fonts, and compiled files. We can't (and don't need to) read
# these as text, so we just flag them as "is_binary" and move on.
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".mp4", ".mov", ".woff",
    ".woff2", ".ttf", ".otf", ".eot", ".pyc", ".class",
}

# Maps a file extension to a human-friendly programming language name.
# Used purely for display/metadata purposes (e.g. showing "Python" instead
# of ".py" in a UI).
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

# NOTE: This list isn't directly used in the code below (progress percentages
# are hardcoded at each call site), but it documents the overall shape of a
# scan so it's easy to see all the phases at a glance.
SCAN_STEPS = [
    ("cloning", 10),
    ("indexing_files", 30),
    ("mapping_deps", 50),
    ("extracting_symbols", 70),
    ("building_call_graph", 85),
    ("generating_docs", 95),
    ("complete", 100),
]


async def _update_scan_status(
    db: AsyncSession,
    repo_id: uuid.UUID,
    status: str,
    progress: int,
) -> None:
    """
    Update the scan_status and scan_progress columns on a repository's
    database row, then commit that change immediately.

    WHY THIS EXISTS:
    A repo scan can take a while (cloning, parsing, analyzing). Rather than
    make the user stare at a blank screen, we continuously write out our
    current status (e.g. "cloning", "indexing_files") and a 0-100 progress
    number so a frontend can poll this row and show a live progress bar.

    Args:
        db: The active database session (async) used to run the update.
        repo_id: Which repository row to update.
        status: A short string describing the current phase (e.g. "cloning").
        progress: A percentage (0-100) indicating how far along we are.

    Returns:
        None. This function's only job is a side effect (writing to the DB).
    """
    logger.debug(
        "Updating scan status | repo=%s status=%s progress=%d",
        repo_id, status, progress,
    )
    await db.execute(
        update(ConnectedRepository)
        .where(ConnectedRepository.id == repo_id)
        .values(scan_status=status, scan_progress=progress)
    )
    await db.commit()
    logger.debug(
        "Scan status committed to database | repo=%s status=%s progress=%d",
        repo_id, status, progress,
    )


class RepoScannerService:
    """
    Coordinates the entire process of scanning a connected GitHub repository:
    cloning it, cataloguing its files, and running deeper code analysis
    (dependencies, symbols, call graph).

    Think of an instance of this class as a single "scan worker" - you create
    one, call `.scan(...)` on it, and it does all the heavy lifting.
    """

    def __init__(self, db: AsyncSession):
        """
        Set up the scanner with a database session.

        Args:
            db: An active SQLAlchemy async database session. This is reused
                by the RepositoryFileRepository (for saving file metadata)
                and passed along to sub-services (dependency/symbol services)
                so everything shares the same database transaction context.
        """
        self.file_repo = RepositoryFileRepository(db)
        logger.debug("RepoScannerService initialized | file_repo=%r", self.file_repo)

    async def scan(
        self,
        connected_repo_id: uuid.UUID,
        user_id: uuid.UUID,
        clone_url: str,
        access_token: str,
        default_branch: str = "main",
    ) -> int:
        """
        Run a full scan of a repository from start to finish.

        HIGH-LEVEL STEPS (in order):
            1. Clone the repo into a temporary folder on disk.
            2. Walk the folder tree to list every file (skipping ignored
               folders like node_modules, .git, etc.).
            3. Save that file list to the database.
            4. Read the actual text content of source files we can parse
               (Python/JS/TS) into memory, so later steps don't need to
               keep re-reading from disk.
            5. Build a "dependency graph" - which files import/require
               which other files.
            6. Extract "symbols" - functions, classes, variables, etc.
            7. Build a "call graph" - which functions call which other
               functions.
            8. Mark the scan complete.

        At every step, we update a status/progress value on the repo's
        database row (see `_update_scan_status`), and if anything goes
        wrong we mark the scan as "failed" and re-raise the error so the
        caller knows something broke.

        No matter what happens (success or failure), the temporary clone
        directory is always deleted at the end - we don't want to leave
        cloned repos sitting around on disk forever.

        Args:
            connected_repo_id: The database ID of the repo being scanned.
            user_id: The ID of the user who owns/triggered this scan.
            clone_url: The HTTPS git URL to clone (e.g.
                "https://github.com/org/repo.git").
            access_token: A GitHub access token used to authenticate the
                clone (needed for private repos).
            default_branch: Which branch to clone. Defaults to "main".

        Returns:
            The total number of files found in the repository (an int).

        Raises:
            Exception: Re-raises whatever error occurred during the scan
                (e.g. clone failure, parsing errors) after logging it and
                marking the scan as "failed" in the database.
        """
        # Create a brand new, empty temp folder on disk. Example result:
        # "/tmp/ramp_scan_a1b2c3d4"
        tmpdir = tempfile.mkdtemp(prefix="ramp_scan_")
        db = self.file_repo.db

        logger.info(
            "Starting repo scan | repo=%s user=%s branch=%s tmpdir=%s",
            connected_repo_id, user_id, default_branch, tmpdir,
        )
        logger.debug(
            "Scan input parameters | repo=%s user=%s clone_url=%s branch=%s tmpdir=%s",
            connected_repo_id, user_id, clone_url, default_branch, tmpdir,
        )

        try:
            # --- Step 1: Clone the repository -------------------------------
            await _update_scan_status(db, connected_repo_id, "cloning", 5)
            await self._clone(clone_url, access_token, tmpdir, default_branch)
            logger.info("Clone step finished | repo=%s", connected_repo_id)

            # --- Step 2: Walk the file tree ---------------------------------
            await _update_scan_status(db, connected_repo_id, "indexing_files", 15)
            files = self._walk(Path(tmpdir))
            logger.info(
                "File walk finished | repo=%s files_found=%d",
                connected_repo_id, len(files),
            )
            logger.debug(
                "File walk output (first 20 of %d) | repo=%s sample=%s",
                len(files), connected_repo_id, files[:20],
            )

            # --- Step 3: Persist file metadata to the database --------------
            await _update_scan_status(db, connected_repo_id, "indexing_files", 25)
            await self.file_repo.replace_for_repo(connected_repo_id, user_id, files)
            logger.info(
                "Metadata persisted | repo=%s files=%d", connected_repo_id, len(files)
            )
            logger.debug(
                "Metadata persistence details | repo=%s user=%s total_files=%d",
                connected_repo_id, user_id, len(files),
            )

            # --- Read parseable source files once; reuse for all analysis steps ---
            # We only read files whose extension we know how to meaningfully
            # analyze (Python/JS/TS). This dict maps "relative/path.py" ->
            # "the full text contents of that file".
            file_contents = self._read_parseable_files(Path(tmpdir), files)
            logger.info(
                "Read parseable file contents | repo=%s parseable_files=%d",
                connected_repo_id, len(file_contents),
            )
            logger.debug(
                "Parseable file paths read | repo=%s paths=%s",
                connected_repo_id, list(file_contents.keys()),
            )

            # --- Step 4: Dependency graph ------------------------------------
            await _update_scan_status(db, connected_repo_id, "mapping_deps", 40)
            logger.info("Parsing dependencies | repo=%s", connected_repo_id)
            dep_service = DependencyGraphService(self.file_repo.db)
            edge_count = await dep_service.build(connected_repo_id, file_contents)
            logger.info(
                "Dependency graph built | repo=%s edges=%d", connected_repo_id, edge_count
            )
            logger.debug(
                "Dependency graph build output | repo=%s edge_count=%d files_analyzed=%d",
                connected_repo_id, edge_count, len(file_contents),
            )

            # --- Step 5: Symbol extraction ------------------------------------
            await _update_scan_status(db, connected_repo_id, "extracting_symbols", 60)
            logger.info("Extracting symbols | repo=%s", connected_repo_id)
            sym_service = SymbolExtractionService(self.file_repo.db)
            sym_count = await sym_service.extract_and_store_symbols(
                connected_repo_id, file_contents
            )
            logger.info(
                "Symbols stored | repo=%s symbols=%d", connected_repo_id, sym_count
            )
            logger.debug(
                "Symbol extraction output | repo=%s symbol_count=%d",
                connected_repo_id, sym_count,
            )

            # --- Step 6: Call graph --------------------------------------------
            await _update_scan_status(db, connected_repo_id, "building_call_graph", 80)
            call_count = await sym_service.build_call_graph(
                connected_repo_id, file_contents
            )
            logger.info(
                "Call graph built | repo=%s calls=%d", connected_repo_id, call_count
            )
            logger.debug(
                "Call graph build output | repo=%s call_count=%d",
                connected_repo_id, call_count,
            )

            # --- Step 7: Mark scan complete --------------------------------------
            await _update_scan_status(db, connected_repo_id, "complete", 100)
            logger.info(
                "Scan complete | repo=%s total_files=%d edges=%d symbols=%d calls=%d",
                connected_repo_id, len(files), edge_count, sym_count, call_count,
            )

            return len(files)

        except Exception:
            # `logger.exception` automatically includes the full stack trace,
            # which is extremely helpful when debugging why a scan failed.
            logger.exception("Scan error | repo=%s", connected_repo_id)
            await _update_scan_status(db, connected_repo_id, "failed", 0)
            # Re-raise so the calling code (e.g. an API endpoint or background
            # job runner) knows the scan failed and can react accordingly.
            raise

        finally:
            # This block runs NO MATTER WHAT - whether the scan succeeded or
            # raised an exception. It's our cleanup step: we always want to
            # delete the temporary clone directory so we don't fill up disk
            # space with old repo clones.
            shutil.rmtree(tmpdir, ignore_errors=True)
            logger.debug("Temporary scan directory removed | tmpdir=%s", tmpdir)

    def _read_parseable_files(self, root: Path, files: List[dict]) -> dict[str, str]:
        """
        Read the full text content of "parseable" source files into memory.

        WHY: Later analysis steps (dependency graph, symbol extraction, call
        graph) all need to look at the actual source code text. Rather than
        have each of those steps re-read files from disk independently, we
        read everything once here and pass around a simple dictionary.

        Only files with certain extensions are considered "parseable" right
        now: .py, .ts, .tsx, .js, .jsx. Anything else (binary files, or
        source languages we don't yet analyze, like Go or Rust) is skipped.

        Args:
            root: The root folder the repo was cloned into (used to resolve
                each file's full path on disk).
            files: The list of file metadata dictionaries produced by
                `_walk`, each containing at least "path", "extension", and
                "is_binary".

        Returns:
            A dictionary mapping each file's relative path (as a string,
            e.g. "src/app.py") to that file's full text content (as a
            string).
        """
        PARSEABLE = {".py", ".ts", ".tsx", ".js", ".jsx"}
        contents = {}
        skipped_unreadable = []

        for f in files:
            if f.get("is_binary") or f.get("extension") not in PARSEABLE:
                # Skip binary files (images, fonts, etc.) and any file
                # extension we don't currently know how to analyze.
                continue

            full_path = root / f["path"]
            try:
                # `errors="replace"` means if a file has some invalid/odd
                # byte sequences, we substitute a placeholder character
                # instead of crashing the whole scan.
                contents[f["path"]] = full_path.read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                # File might have been deleted, be a broken symlink, have
                # permission issues, etc. We just skip it rather than fail
                # the entire scan over one unreadable file.
                skipped_unreadable.append(f["path"])

        logger.info(
            "Read parseable files from disk | readable=%d skipped_unreadable=%d",
            len(contents), len(skipped_unreadable),
        )
        logger.debug(
            "Parseable file read details | readable_paths=%s skipped_paths=%s",
            list(contents.keys()), skipped_unreadable,
        )

        return contents

    async def _clone(
        self, clone_url: str, access_token: str, dest: str, branch: str
    ) -> None:
        """
        Clone a GitHub repository into a local directory using `git clone`.

        HOW AUTHENTICATION WORKS:
        GitHub lets you authenticate an HTTPS clone by embedding a token
        directly in the URL, like:
            https://<TOKEN>@github.com/org/repo.git
        So we take the plain clone_url and inject the access_token right
        after "https://".

        WHY "--depth 1" AND "--single-branch":
        We only care about the current state of the code, not its full
        history, so we do a "shallow clone" (depth 1 = just the latest
        commit) of a single branch. This is much faster and uses far less
        disk space than cloning the entire repo history.

        Args:
            clone_url: The plain HTTPS clone URL (no token embedded).
            access_token: GitHub access token used to authenticate.
            dest: The local folder path to clone into.
            branch: Which branch to clone.

        Returns:
            None. On success, `dest` will contain the cloned repository
            files.

        Raises:
            RuntimeError: If the `git clone` command exits with a non-zero
                status code (i.e., it failed for any reason - bad token,
                branch doesn't exist, network issue, etc.).
        """
        # Insert the token right after "https://" so git can authenticate.
        # NOTE: we deliberately do NOT log `authed_url` anywhere, since it
        # contains a secret access token.
        authed_url = clone_url.replace("https://", f"https://{access_token}@")

        logger.info("Cloning repository | branch=%s dest=%s", branch, dest)
        logger.debug(
            "Clone command details | clone_url=%s branch=%s dest=%s timeout=120s",
            clone_url, branch, dest,
        )

        # `subprocess.run` executes the git command and waits for it to
        # finish. `capture_output=True` collects stdout/stderr so we can
        # inspect them (e.g. to build a useful error message).
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
            # Truncate to 500 chars so we don't flood logs/DB with a giant
            # error message.
            error_msg = result.stderr.decode()[:500]
            logger.error(
                "Git clone failed | branch=%s returncode=%d error=%s",
                branch, result.returncode, error_msg,
            )
            raise RuntimeError(f"Git clone failed: {error_msg}")

        logger.info("Git clone succeeded | branch=%s", branch)
        logger.debug(
            "Git clone output | branch=%s returncode=%d stdout=%s stderr=%s",
            branch,
            result.returncode,
            result.stdout.decode(errors="replace")[:500],
            result.stderr.decode(errors="replace")[:500],
        )

    def _walk(self, root: Path) -> List[dict]:
        """
        Walk the entire cloned repository folder tree and build a list of
        metadata dictionaries describing every file found (excluding files
        inside ignored directories like node_modules, .git, etc.).

        WHAT "os.walk" DOES:
        `os.walk(root)` visits every folder starting at `root`, and for each
        folder gives you: the folder's path, the list of sub-folder names
        inside it, and the list of file names inside it. By modifying the
        `dirnames` list in place (removing folders we want to skip), we tell
        `os.walk` not to bother descending into those folders at all - this
        is much faster than walking in and then discarding results.

        For every file we keep, we record:
            - path: the file's path relative to `root` (e.g. "src/app.py")
            - name: just the filename (e.g. "app.py")
            - extension: the lowercase file extension (e.g. ".py"), or None
              if there isn't one
            - language: a human-friendly language name looked up from
              LANGUAGE_MAP (e.g. "Python"), or None if unknown
            - size_bytes: the file's size in bytes
            - is_binary: True if the extension is in BINARY_EXTENSIONS

        Args:
            root: The folder to start walking from (the cloned repo's root).

        Returns:
            A list of dictionaries, one per file found, each shaped like:
                {
                    "path": "src/app.py",
                    "name": "app.py",
                    "extension": ".py",
                    "language": "Python",
                    "size_bytes": 1024,
                    "is_binary": False,
                }
        """
        results = []
        skipped_dirs = []

        logger.debug("Starting file walk | root=%s", root)

        for dirpath, dirnames, filenames in os.walk(root):
            # Figure out which sub-folders we're about to skip (either
            # explicitly ignored, like "node_modules", or hidden folders
            # starting with a dot, like ".github").
            pruned = [d for d in dirnames if d in IGNORED_DIRS or d.startswith(".")]
            skipped_dirs.extend(pruned)

            # Modifying `dirnames` in place tells os.walk to NOT descend
            # into these folders on future iterations.
            dirnames[:] = [
                d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")
            ]

            for filename in filenames:
                filepath = Path(dirpath) / filename
                # Path relative to the repo root, e.g. "src/utils/helpers.py"
                rel_path = str(filepath.relative_to(root))
                ext = filepath.suffix.lower()

                try:
                    size = filepath.stat().st_size
                except OSError:
                    # This can happen for broken symlinks or files that
                    # disappear mid-scan. We just record a size of 0 rather
                    # than crash the whole scan.
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

        logger.info(
            "File walk complete | root=%s total_files=%d skipped_dirs=%d",
            root, len(results), len(skipped_dirs),
        )
        logger.debug(
            "File walk full output | root=%s file_count=%d results=%s",
            root, len(results), results,
        )

        return results