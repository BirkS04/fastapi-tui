"""
TUI Handlers Module

Event handling utilities for the TUI system.
"""

from .hit_handler import (
    parse_hit_from_data,
    merge_hits,
    save_hit,
    is_pending_update,
    get_hit_display_status
)
from .log_handler import (
    format_log_line,
    write_log_to_widget,
    parse_log_level,
    should_display_log
)
from .exception_handler import (
    parse_exception_data,
    format_exception_summary,
    format_exception_detail,
    group_exceptions_by_type,
    get_exception_color,
    link_exception_to_request
)
from .stats_handler import (
    calculate_stats,
    get_success_rate,
    get_error_rate,
    get_status_code_distribution,
    format_duration,
    get_stats_color,
    get_performance_indicator,
    filter_hits_by_time,
    aggregate_stats
)

__all__ = [
    # Hit handler
    "parse_hit_from_data",
    "merge_hits",
    "save_hit",
    "is_pending_update",
    "get_hit_display_status",
    # Log handler
    "format_log_line",
    "write_log_to_widget",
    "parse_log_level",
    "should_display_log",
    # Exception handler
    "parse_exception_data",
    "format_exception_summary",
    "format_exception_detail",
    "group_exceptions_by_type",
    "get_exception_color",
    "link_exception_to_request",
    # Stats handler
    "calculate_stats",
    "get_success_rate",
    "get_error_rate",
    "get_status_code_distribution",
    "format_duration",
    "get_stats_color",
    "get_performance_indicator",
    "filter_hits_by_time",
    "aggregate_stats",
]
