"""
TUI Core Module

Core models, events, and utilities for the TUI system.
"""

from .models import (
    EventType,
    EndpointHit,
    CustomEvent,
    EndpointStats,
    TUIEvent
)
from .events import (
    create_hit_id,
    create_pending_hit,
    create_completed_hit,
    create_custom_event,
    parse_event,
    normalize_endpoint
)

__all__ = [
    # Models
    "EventType",
    "EndpointHit",
    "CustomEvent",
    "EndpointStats",
    "TUIEvent",
    # Events
    "create_hit_id",
    "create_pending_hit", 
    "create_completed_hit",
    "create_custom_event",
    "parse_event",
    "normalize_endpoint",
]
