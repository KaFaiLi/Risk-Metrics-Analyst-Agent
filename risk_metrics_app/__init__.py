"""Risk Metrics Analyst Agent package.

``run_app`` is imported lazily so that headless consumers (e.g. the
``process_extraction.py`` data pipeline) can use the data-shaping modules
without pulling in Streamlit and the rest of the UI stack.
"""

__all__ = ["run_app"]


def __getattr__(name: str):
    if name == "run_app":
        from .app import run_app

        return run_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
