"""
TUI Handlers - Hit Handler

Handles endpoint hit events (pending and completed requests).
"""

from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..core.models import EndpointHit

if TYPE_CHECKING:
    from ..persistence.sqlite import TUIPersistence


def parse_hit_from_data(data: Dict[str, Any]) -> EndpointHit:
    """Parse a hit from raw event data"""
    # Handle timestamp parsing
    timestamp = data.get("timestamp")
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp)
        except ValueError:
            timestamp = datetime.now()
    elif not isinstance(timestamp, datetime):
        timestamp = datetime.now()
    
    return EndpointHit(
        id=data.get("id", ""),
        endpoint=data.get("endpoint", ""),
        method=data.get("method", "GET"),
        status_code=data.get("status_code"),
        duration_ms=data.get("duration_ms"),
        timestamp=timestamp,
        client=data.get("client", "unknown"),
        request_params=data.get("request_params"),
        request_body=data.get("request_body"),
        request_headers=data.get("request_headers"),
        response_body=data.get("response_body"),
        response_headers=data.get("response_headers"),
        runtime_logs=data.get("runtime_logs", []),
        exceptions=data.get("exceptions", []),
        pending=data.get("pending", True),
        error=data.get("error")
    )


def merge_hits(existing: EndpointHit, update: EndpointHit) -> EndpointHit:
    """Merge an update into an existing hit (for pending -> completed)"""
    # Update non-None fields from the update
    if update.status_code is not None:
        existing.status_code = update.status_code
    if update.duration_ms is not None:
        existing.duration_ms = update.duration_ms
    if update.response_body is not None:
        existing.response_body = update.response_body
    if update.response_headers is not None:
        existing.response_headers = update.response_headers
    if update.runtime_logs:
        existing.runtime_logs = update.runtime_logs
    if update.exceptions:
        existing.exceptions = update.exceptions
    if update.error is not None:
        existing.error = update.error
    
    existing.pending = update.pending
    
    return existing


def save_hit(hit: EndpointHit, persistence: "TUIPersistence") -> None:
    """Save a hit to persistence"""
    hit_dict = hit.model_dump()
    # Convert datetime for JSON serialization
    hit_dict["timestamp"] = hit.timestamp.isoformat()
    persistence.save_hit(hit_dict)


def is_pending_update(data: Dict[str, Any]) -> bool:
    """Check if this is an update to a pending request"""
    return data.get("pending", True) == False and data.get("completed", False) == True


def get_hit_display_status(hit: EndpointHit) -> tuple:
    """Get display status (color, icon) for a hit"""
    if hit.pending:
        return "yellow", "⏳"
    elif hit.status_code and hit.status_code >= 400:
        return "red", "✗"
    else:
        return "green", "✓"
