"""
Dependency Graph Service
========================

WHAT THIS FILE DOES (in plain English):
This file figures out how the files in a repository depend on each other -
i.e., which files `import` or `require` which other files - and saves that
information to the database as a "dependency graph".

Think of it like mapping out a family tree, but for code files: if
"app.py" has `import utils`, we want to record an edge (a connection)
saying "app.py depends on utils.py".

This graph is useful later for things like:
    - Visualizing how a codebase is structured
    - Figuring out what might break if you change a given file
    - Understanding "blast radius" of a change

KEY TERMS FOR BEGINNERS:
- "async def" / "await": this is asynchronous code. `await` means "pause
  here until this operation (usually a database call) finishes, but let
  other code run in the meantime."
- "edge": in graph terminology, an edge is a connection between two things
  (called "nodes"). Here, a node is a file, and an edge means "file A
  imports/depends on file B".
- "resolve an import": when code says `import foo`, that's just a name -
  it doesn't directly tell us which actual file "foo" refers to. Resolving
  means figuring out the actual file path that import points to.
- "logger.info": writes a normal, human-readable status update to our logs.
- "logger.debug": writes MORE detailed information (only really needed when
  troubleshooting). Per team convention, debug logs also include the actual
  data/values involved, not just a description of what happened.
"""

import uuid
import logging
from pathlib import Path
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import API_MAIN_LOGGER_NAME_PREFIX
from src.features.github.models import FileDependency, RepositoryFile
from src.features.github.repository import FileDependencyRepository, RepositoryFileRepository
from src.features.github.services.dependency_parser import parse_dependencies, resolve_import_to_path

# The logger is how this module writes messages to our centralized logging
# system. Using a hierarchical name (prefix + ".dependency_service") lets us
# filter/search logs specifically from this file later on.
logger = logging.getLogger(f"{API_MAIN_LOGGER_NAME_PREFIX}.dependency_service")

# We only attempt to parse imports/dependencies for these file extensions.
# Other file types (images, config files, unsupported languages, etc.) are
# skipped entirely since we don't have a parser for them.
PARSEABLE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}


class DependencyGraphService:
    """
    Builds and persists a "dependency graph" for a repository: a set of
    edges recording which files import/depend on which other files.

    Think of an instance of this class as a single "graph builder" - you
    create one (giving it a database session), then call `.build(...)` on
    it to do the actual analysis and save the results.
    """

    def __init__(self, db: AsyncSession):
        """
        Set up the service with a database session and the repositories it
        needs to read files and write dependency edges.

        Args:
            db: An active SQLAlchemy async database session, shared with
                the rest of the scan so everything happens in the same
                transaction context.
        """
        self.db = db
        self.file_repo = RepositoryFileRepository(db)
        self.dep_repo = FileDependencyRepository(db)
        logger.debug(
            "DependencyGraphService initialized | file_repo=%r dep_repo=%r",
            self.file_repo, self.dep_repo,
        )

    async def build(
        self,
        connected_repo_id: uuid.UUID,
        file_contents: dict[str, str],  # path -> content
    ) -> int:
        """
        Analyze every parseable file in a repository, figure out what it
        imports, resolve those imports to actual files in the same repo,
        and save the resulting dependency edges to the database.

        HOW THIS WORKS, STEP BY STEP:
            1. Load all known files for this repo from the database (we
               need their database IDs, not just their paths, so we can
               link them together with foreign keys).
            2. Build a quick lookup dictionary: file path -> file object,
               so we can look up "does this repo have a file at this
               path?" quickly.
            3. For each file that has a "parseable" extension (see
               PARSEABLE_EXTENSIONS) and whose content we have on hand:
                 a. Parse out its raw import statements (e.g. "import
                    utils", "from ./helpers import x") using
                    `parse_dependencies`.
                 b. For each raw import, try to resolve it to an actual
                    file path within the repo using
                    `resolve_import_to_path`. Some imports won't resolve -
                    e.g. importing a third-party library like "requests"
                    that isn't part of this repo - and those are skipped.
                 c. If it resolves to a real file (and isn't the file
                    importing itself), record an "edge": this file depends
                    on that other file.
            4. Replace any previously-stored dependency edges for this
               repo with the newly computed set (so re-scanning a repo
               doesn't leave stale/duplicate edges behind).

        Args:
            connected_repo_id: The database ID of the repository being
                analyzed.
            file_contents: A dictionary mapping each file's relative path
                (e.g. "src/app.py") to its full text content. Typically
                produced once by the scanner and reused across multiple
                analysis steps to avoid re-reading files from disk.

        Returns:
            The number of dependency edges that were found and saved (an
            int). Useful for logging/progress reporting.
        """
        logger.info("Building dependency graph | repo=%s", connected_repo_id)
        logger.debug(
            "Dependency graph build input | repo=%s files_with_content=%d",
            connected_repo_id, len(file_contents),
        )

        # Load every known file row for this repo from the database. We need
        # these (rather than just the raw paths) because each row has a
        # database `id` - and dependency edges are stored as
        # source_file_id -> target_file_id, not as path strings.
        files: List[RepositoryFile] = await self.file_repo.get_by_repo(connected_repo_id)
        logger.debug(
            "Loaded files for repo | repo=%s file_count=%d",
            connected_repo_id, len(files),
        )

        # Build lookup: path -> file object
        # This lets us quickly answer "is there a file at this path?" (and
        # if so, get its ID) without looping through the whole file list
        # every time.
        path_to_file = {f.path: f for f in files}
        all_paths = list(path_to_file.keys())
        logger.debug(
            "Built path lookup table | repo=%s unique_paths=%d",
            connected_repo_id, len(all_paths),
        )

        edges = []
        parsed_file_count = 0
        skipped_no_content = 0
        unresolved_imports = 0

        for file in files:
            # Skip any file whose extension we don't have a parser for
            # (e.g. images, YAML, Markdown, unsupported languages).
            if file.extension not in PARSEABLE_EXTENSIONS:
                continue

            content = file_contents.get(file.path)
            if not content:
                # We might not have content for a file if it was empty, or
                # if it failed to be read earlier in the scan pipeline.
                skipped_no_content += 1
                continue

            parsed_file_count += 1

            # Ask the dependency parser to extract raw import statements
            # from this file's source code. Each result is a tuple of
            # (raw_import_string, import_type) - e.g. ("./utils", "relative")
            # or ("requests", "package").
            raw_imports = parse_dependencies(file.path, content)
            logger.debug(
                "Parsed imports for file | repo=%s path=%s imports_found=%d raw_imports=%s",
                connected_repo_id, file.path, len(raw_imports), raw_imports,
            )

            for raw_import, import_type in raw_imports:
                # Try to turn the raw import string (like "./utils" or
                # "../models/user") into an actual file path that exists in
                # this repo (like "src/utils.py").
                resolved = resolve_import_to_path(
                    file.path, raw_import, import_type, all_paths
                )
                if not resolved:
                    # This is common and expected - e.g. imports of
                    # third-party libraries (like "react" or "requests")
                    # won't resolve to any file inside this repo.
                    unresolved_imports += 1
                    continue

                target_file = path_to_file.get(resolved)
                if not target_file or target_file.id == file.id:
                    # Either the resolved path somehow isn't in our lookup
                    # (shouldn't normally happen), or the file is importing
                    # itself (e.g. a self-reference) - either way, skip it.
                    continue

                # Record this as a dependency edge: `file` depends on
                # `target_file`.
                edges.append({
                    "connected_repo_id": connected_repo_id,
                    "source_file_id": file.id,
                    "target_file_id": target_file.id,
                    "import_type": import_type,
                })

        logger.info(
            "Dependency parsing finished | repo=%s parsed_files=%d edges_found=%d "
            "skipped_no_content=%d unresolved_imports=%d",
            connected_repo_id, parsed_file_count, len(edges),
            skipped_no_content, unresolved_imports,
        )
        logger.debug(
            "Dependency edges computed (pre-save) | repo=%s edges=%s",
            connected_repo_id, edges,
        )

        # Overwrite any previously stored edges for this repo with the fresh
        # set we just computed. This keeps the dependency graph in sync with
        # the latest scan (rather than accumulating stale/duplicate edges
        # across multiple scans of the same repo).
        await self.dep_repo.replace_for_repo(connected_repo_id, edges)
        logger.info("Dependency edges saved | repo=%s edges=%d", connected_repo_id, len(edges))
        logger.debug(
            "Dependency edges save confirmed | repo=%s saved_edge_count=%d",
            connected_repo_id, len(edges),
        )

        return len(edges)