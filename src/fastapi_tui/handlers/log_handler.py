"""
TUI Handlers - Log Handler

Handles server log events.
"""

from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from textual.widgets import Log
    from ..widgets.auto_scroll_log import AutoScrollLog


def format_log_line(log_data: Dict[str, Any]) -> str:
    """Format a log entry for display"""
    timestamp = log_data.get("timestamp", datetime.now())
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp)
        except ValueError:
            timestamp = datetime.now()
    
    level = log_data.get("level", "INFO").upper()
    message = log_data.get("message", "")
    
    # Color based on level
    level_colors = {
        "DEBUG": "dim",
        "INFO": "blue",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold red"
    }
    color = level_colors.get(level, "white")
    
    time_str = timestamp.strftime("%H:%M:%S")
    return f"[dim]{time_str}[/] [{color}]{level:8}[/] {message}"


def write_log_to_widget(widget, log_data: Dict[str, Any]) -> None:
    """Write a log entry to a log widget"""
    line = format_log_line(log_data)
    
    # Try AutoScrollLog first, then regular Log
    if hasattr(widget, 'write'):
        widget.write(line)
    elif hasattr(widget, 'write_line'):
        widget.write_line(line)


def parse_log_level(level: str) -> int:
    """Convert log level string to numeric value for sorting"""
    levels = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50
    }
    return levels.get(level.upper(), 20)


def should_display_log(log_data: Dict[str, Any], min_level: str = "DEBUG") -> bool:
    """Check if a log should be displayed based on minimum level"""
    log_level = parse_log_level(log_data.get("level", "INFO"))
    min_level_value = parse_log_level(min_level)
    return log_level >= min_level_value
