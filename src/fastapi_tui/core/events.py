"""
TUI Core - Events

Event parsing, creation, and utility functions.
"""

from typing import Any, Dict, Optional
from datetime import datetime
import uuid

from .models import EndpointHit, CustomEvent, EndpointStats, EventType


def create_hit_id() -> str:
    """Generate a unique hit ID"""
    return str(uuid.uuid4())


def create_pending_hit(
    request_id: str,
    endpoint: str,
    method: str,
    client: str = "unknown",
    request_params: Optional[Dict[str, Any]] = None,
    request_body: Optional[Dict[str, Any]] = None,
    request_headers: Optional[Dict[str, str]] = None,
    timestamp: Optional[datetime] = None
) -> EndpointHit:
    """Create a pending hit (request received, not yet responded)"""
    return EndpointHit(
        id=request_id,
        endpoint=endpoint,
        method=method,
        client=client,
        timestamp=timestamp or datetime.now(),
        request_params=request_params,
        request_body=request_body,
        request_headers=request_headers,
        pending=True
    )


def create_completed_hit(
    request_id: str,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    client: str = "unknown",
    request_params: Optional[Dict[str, Any]] = None,
    request_body: Optional[Dict[str, Any]] = None,
    request_headers: Optional[Dict[str, str]] = None,
    response_body: Optional[Dict[str, Any]] = None,
    runtime_logs: Optional[list] = None,
    timestamp: Optional[datetime] = None
) -> EndpointHit:
    """Create a completed hit (response sent)"""
    return EndpointHit(
        id=request_id,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        duration_ms=duration_ms,
        client=client,
        timestamp=timestamp or datetime.now(),
        request_params=request_params,
        request_body=request_body,
        request_headers=request_headers,
        response_body=response_body,
        runtime_logs=runtime_logs or [],
        pending=False
    )


def create_custom_event(
    endpoint: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    level: str = "info"
) -> CustomEvent:
    """Create a custom event for logging"""
    return CustomEvent(
        id=str(uuid.uuid4()),
        endpoint=endpoint,
        message=message,
        data=data,
        level=level
    )


def parse_event(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and normalize a raw event from the queue"""
    event_type = raw_event.get("type", "unknown")
    data = raw_event.get("data", {})
    
    return {
        "type": event_type,
        "data": data,
        "timestamp": raw_event.get("timestamp", datetime.now())
    }


def normalize_endpoint(path: str, app_routes: list = None) -> str:
    """
    Normalize an endpoint path to its route template.
    E.g., /items/123 -> /items/{id}
    """
    if not app_routes:
        return path
    
    try:
        from starlette.routing import Match
        
        # Create a mock scope for matching
        scope = {
            "type": "http",
            "path": path,
            "method": "GET"
        }
        
        for route in app_routes:
            if hasattr(route, 'matches'):
                match, _ = route.matches(scope)
                if match == Match.FULL:
                    return route.path
    except Exception:
        pass
    
    return path
