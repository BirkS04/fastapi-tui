"""
TUI Persistence Module

SQLite-based persistence layer for TUI events.
"""

from .sqlite import TUIPersistence, get_persistence

__all__ = ["TUIPersistence", "get_persistence"]
