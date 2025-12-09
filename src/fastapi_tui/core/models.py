"""
TUI Core - Models

Pydantic models for the TUI system.
"""

from datetime import datetime
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class EventType(str, Enum):
    """Event types for the TUI"""
    REQUEST = "request"
    RESPONSE = "response"
    CUSTOM = "custom"
    ERROR = "error"
    INFO = "info"


class EndpointHit(BaseModel):
    """Represents a single API hit"""
    id: str
    endpoint: str
    method: str
    status_code: Optional[int] = None
    duration_ms: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    client: str = "unknown"
    
    # Request Details
    request_params: Optional[Dict[str, Any]] = None
    request_body: Optional[Dict[str, Any]] = None
    request_headers: Optional[Dict[str, str]] = None
    
    # Response Details
    response_body: Optional[Dict[str, Any]] = None
    response_headers: Optional[Dict[str, str]] = None
    
    # Custom Runtime Logs
    runtime_logs: List[Any] = Field(default_factory=list)
    
    # Exception info
    exceptions: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Status tracking
    pending: bool = True
    error: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CustomEvent(BaseModel):
    """User-defined event for custom logging"""
    id: str
    endpoint: str
    event_type: EventType = EventType.CUSTOM
    timestamp: datetime = Field(default_factory=datetime.now)
    message: str
    data: Optional[Dict[str, Any]] = None
    level: str = "info"
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EndpointStats(BaseModel):
    """Statistics for an endpoint"""
    endpoint: str
    total_hits: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_duration_ms: float = 0.0
    min_duration_ms: Optional[float] = None
    max_duration_ms: Optional[float] = None
    last_hit: Optional[datetime] = None
    status_codes: Dict[int, int] = Field(default_factory=dict)
    
    durations: List[float] = Field(default_factory=list)
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    
    def update(self, hit: EndpointHit, count_hit: bool = True) -> None:
        """Update statistics with a new hit"""
        if count_hit:
            self.total_hits += 1
        self.last_hit = hit.timestamp
        
        if hit.status_code:
            if hit.status_code < 400:
                self.success_count += 1
            else:
                self.error_count += 1
            
            self.status_codes[hit.status_code] = self.status_codes.get(hit.status_code, 0) + 1
        
        if hit.duration_ms is not None:
            # Add to history (keep last 1000 for memory efficiency)
            self.durations.append(hit.duration_ms)
            if len(self.durations) > 1000:
                self.durations.pop(0)
            
            # Calculate Averages
            if self.avg_duration_ms == 0:
                self.avg_duration_ms = hit.duration_ms
            else:
                self.avg_duration_ms = (
                    (self.avg_duration_ms * (self.total_hits - 1) + hit.duration_ms) 
                    / self.total_hits
                )
            
            if self.min_duration_ms is None or hit.duration_ms < self.min_duration_ms:
                self.min_duration_ms = hit.duration_ms
            if self.max_duration_ms is None or hit.duration_ms > self.max_duration_ms:
                self.max_duration_ms = hit.duration_ms
                
            # Calculate Percentiles (if we have enough data)
            if self.durations:
                sorted_durations = sorted(self.durations)
                n = len(sorted_durations)
                self.p50 = sorted_durations[int(n * 0.5)]
                self.p95 = sorted_durations[int(n * 0.95)]
                self.p99 = sorted_durations[int(n * 0.99)]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class TUIEvent(BaseModel):
    """Wrapper for all TUI events"""
    type: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SystemStats(BaseModel):
    """System statistics"""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    active_connections: int = 0
    uptime_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)
