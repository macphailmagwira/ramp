"""Storybook agent subgraphs.

Each subgraph (SET UP, and later LEARN / BUILD) knows how to build its own
LangGraph subgraph and exposes a ``SETUP_NAME``-style key plus a ``build_*``
factory. The orchestrator in ``src.features.ai.story_book_agent`` fans them out.
"""

from src.features.ai.storybook.setup import SETUP_NAME, build_setup

__all__ = ["SETUP_NAME", "build_setup"]
