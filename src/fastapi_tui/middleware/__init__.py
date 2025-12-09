"""
TUI Middleware Module

Middleware components for capturing HTTP traffic.
"""

from .request_logger import TUIMiddleware

__all__ = ["TUIMiddleware"]
