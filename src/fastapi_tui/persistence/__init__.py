"""
TUI Persistence Module

SQLite-based persistence layer for TUI events.
"""

from .sqlite import TUIPersistence, persistence

__all__ = ["TUIPersistence", "persistence"]
