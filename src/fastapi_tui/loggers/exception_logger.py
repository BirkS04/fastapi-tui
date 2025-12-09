"""
Exception Logger - Captures exceptions with full context for TUI display.
Supports dev/prod mode distinction.
"""

import os
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from queue import Queue

from .runtime_logger import log_queue_ctx, request_id_ctx


# Sensitive variable names to filter
SENSITIVE_PATTERNS = ['password', 'token', 'secret', 'key', 'auth', 'credential', 'api_key']


def is_dev_mode() -> bool:
    """Check if running in development mode."""
    env = os.getenv("ENV", "development").lower()
    return env in ("development", "dev", "local")


class StackFrame(BaseModel):
    """Represents a single stack frame."""
    filename: str
    function: str
    lineno: int
    locals_preview: Dict[str, str] = Field(default_factory=dict)


class ExceptionInfo(BaseModel):
    """Complete exception information for display."""
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    exception_type: str
    message: str
    traceback_str: str
    frames: List[StackFrame] = Field(default_factory=list)
    request_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


def _is_sensitive(name: str) -> bool:
    """Check if a variable name contains sensitive patterns."""
    name_lower = name.lower()
    return any(pattern in name_lower for pattern in SENSITIVE_PATTERNS)


def _safe_repr(value: Any, max_length: int = 100) -> str:
    """Safely get a string representation of a value."""
    try:
        r = repr(value)
        if len(r) > max_length:
            return r[:max_length - 3] + "..."
        return r
    except Exception:
        return f"<{type(value).__name__}: repr failed>"


def _extract_locals(frame_locals: Dict[str, Any], max_vars: int = 10) -> Dict[str, str]:
    """Extract and sanitize local variables from a frame."""
    result = {}
    count = 0
    
    for name, value in frame_locals.items():
        if count >= max_vars:
            break
        
        # Skip private/dunder variables
        if name.startswith('_'):
            continue
        
        # Mask sensitive values
        if _is_sensitive(name):
            result[name] = "***MASKED***"
        else:
            result[name] = _safe_repr(value)
        
        count += 1
    
    return result


def capture_exception(
    exc: Exception,
    endpoint: Optional[str] = None,
    method: Optional[str] = None,
    log_queue: Optional[Queue] = None
) -> ExceptionInfo:
    """
    Captures an exception with full context.
    Sends to TUI queue if in dev mode.
    
    Returns ExceptionInfo for further processing.
    """
    exc_type, exc_value, exc_traceback = sys.exc_info()
    
    # Build frames list (only in dev mode for performance/security)
    frames = []
    if is_dev_mode() and exc_traceback:
        tb = exc_traceback
        while tb is not None:
            frame = tb.tb_frame
            
            # Extract locals (with filtering)
            locals_preview = _extract_locals(dict(frame.f_locals))
            
            frames.append(StackFrame(
                filename=frame.f_code.co_filename,
                function=frame.f_code.co_name,
                lineno=tb.tb_lineno,
                locals_preview=locals_preview
            ))
            tb = tb.tb_next
    
    # Get request_id from context if available
    try:
        request_id = request_id_ctx.get()
    except LookupError:
        request_id = None
    
    # Create exception info
    exc_info = ExceptionInfo(
        exception_type=exc_type.__name__ if exc_type else type(exc).__name__,
        message=str(exc),
        traceback_str=traceback.format_exc(),
        frames=frames,
        request_id=request_id,
        endpoint=endpoint,
        method=method
    )
    
    # Send to TUI queue if available (dev mode)
    if is_dev_mode():
        try:
            queue = log_queue
            if queue is None:
                try:
                    queue = log_queue_ctx.get()
                except LookupError:
                    queue = None
            
            if queue:
                queue.put_nowait({
                    "type": "exception",
                    "data": exc_info.model_dump()
                })
            else:
                print("[TUI] No queue available for exception logging (ctx or arg)")
        except Exception as e:
            print(f"[TUI] Error sending exception log: {e}")
            pass
    else:
        print("[TUI] Not in dev mode, skipping exception logging")
    
    return exc_info


def get_error_response_detail(exc: Exception) -> str:
    """Returns appropriate error detail based on mode."""
    if is_dev_mode():
        return str(exc)
    return "An internal error occurred. Please try again later."
