"""Storybook feature package.

The LangGraph agent lives in ``src.features.storybook.agent`` and is imported
lazily by the service layer, so importing this package (e.g. for the DB model)
does not pull in heavy graph dependencies at app startup.
"""
