"""
TUI Handlers - Exception Handler

Handles exception events and error tracking.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


def parse_exception_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and normalize exception data"""
    return {
        "id": data.get("id", ""),
        "request_id": data.get("request_id"),
        "endpoint": data.get("endpoint", "unknown"),
        "method": data.get("method", "?"),
        "exception_type": data.get("exception_type", "Exception"),
        "message": data.get("message", "Unknown error"),
        "traceback": data.get("traceback", ""),
        "timestamp": data.get("timestamp", datetime.now()),
        "context": data.get("context", {})
    }


def format_exception_summary(exc_data: Dict[str, Any]) -> str:
    """Format a short summary of an exception"""
    exc_type = exc_data.get("exception_type", "Exception")
    message = exc_data.get("message", "")
    
    # Truncate long messages
    if len(message) > 60:
        message = message[:57] + "..."
    
    return f"{exc_type}: {message}"


def format_exception_detail(exc_data: Dict[str, Any]) -> str:
    """Format detailed exception information"""
    lines = []
    
    lines.append(f"[bold red]{exc_data.get('exception_type', 'Exception')}[/]")
    lines.append(f"[red]{exc_data.get('message', '')}[/]")
    lines.append("")
    
    if exc_data.get("endpoint"):
        lines.append(f"[bold]Endpoint:[/] {exc_data.get('method', '?')} {exc_data['endpoint']}")
    
    timestamp = exc_data.get("timestamp")
    if timestamp:
        if isinstance(timestamp, datetime):
            lines.append(f"[bold]Time:[/] {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            lines.append(f"[bold]Time:[/] {timestamp}")
    
    if exc_data.get("traceback"):
        lines.append("")
        lines.append("[bold]Traceback:[/]")
        lines.append(exc_data["traceback"])
    
    return "\n".join(lines)


def group_exceptions_by_type(exceptions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group exceptions by their type"""
    grouped = {}
    for exc in exceptions:
        exc_type = exc.get("exception_type", "Unknown")
        if exc_type not in grouped:
            grouped[exc_type] = []
        grouped[exc_type].append(exc)
    return grouped


def get_exception_color(exc_data: Dict[str, Any]) -> str:
    """Get color for exception based on type"""
    exc_type = exc_data.get("exception_type", "").lower()
    
    if "warning" in exc_type:
        return "yellow"
    elif "timeout" in exc_type or "connection" in exc_type:
        return "orange"
    else:
        return "red"


def link_exception_to_request(
    exception: Dict[str, Any],
    hits: Dict[str, Any]
) -> Optional[str]:
    """Try to link an exception to a request by request_id"""
    request_id = exception.get("request_id")
    if request_id and request_id in hits:
        return request_id
    return None
