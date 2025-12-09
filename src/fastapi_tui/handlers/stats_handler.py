"""
TUI Handlers - Stats Handler

Handles statistics calculation and updates.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from ..core.models import EndpointHit, EndpointStats


def calculate_stats(hits: List[EndpointHit]) -> EndpointStats:
    """Calculate statistics from a list of hits"""
    if not hits:
        return EndpointStats(endpoint="")
    
    stats = EndpointStats(endpoint=hits[0].endpoint)
    
    for hit in hits:
        stats.update(hit)
    
    return stats


def get_success_rate(stats: EndpointStats) -> float:
    """Calculate success rate percentage"""
    if stats.total_hits == 0:
        return 0.0
    return (stats.success_count / stats.total_hits) * 100


def get_error_rate(stats: EndpointStats) -> float:
    """Calculate error rate percentage"""
    if stats.total_hits == 0:
        return 0.0
    return (stats.error_count / stats.total_hits) * 100


def get_status_code_distribution(stats: EndpointStats) -> Dict[str, int]:
    """Get distribution of status codes grouped by category"""
    distribution = {
        "2xx": 0,
        "3xx": 0,
        "4xx": 0,
        "5xx": 0
    }
    
    for code, count in stats.status_codes.items():
        if 200 <= code < 300:
            distribution["2xx"] += count
        elif 300 <= code < 400:
            distribution["3xx"] += count
        elif 400 <= code < 500:
            distribution["4xx"] += count
        elif 500 <= code < 600:
            distribution["5xx"] += count
    
    return distribution


def format_duration(ms: Optional[float]) -> str:
    """Format duration in human-readable form"""
    if ms is None:
        return "N/A"
    
    if ms < 1:
        return f"{ms * 1000:.2f}μs"
    elif ms < 1000:
        return f"{ms:.2f}ms"
    else:
        return f"{ms / 1000:.2f}s"


def get_stats_color(stats: EndpointStats) -> str:
    """Get color based on stats health"""
    error_rate = get_error_rate(stats)
    
    if error_rate > 50:
        return "red"
    elif error_rate > 10:
        return "yellow"
    else:
        return "green"


def get_performance_indicator(stats: EndpointStats) -> str:
    """Get a performance indicator emoji"""
    if stats.avg_duration_ms is None or stats.avg_duration_ms == 0:
        return "⏳"
    elif stats.avg_duration_ms < 100:
        return "🚀"  # Fast
    elif stats.avg_duration_ms < 500:
        return "✓"   # OK
    elif stats.avg_duration_ms < 1000:
        return "⚠️"   # Slow
    else:
        return "🐢"   # Very slow


def filter_hits_by_time(
    hits: List[EndpointHit],
    minutes: int = 60
) -> List[EndpointHit]:
    """Filter hits to only those within the last N minutes"""
    cutoff = datetime.now() - timedelta(minutes=minutes)
    return [h for h in hits if h.timestamp > cutoff]


def aggregate_stats(all_stats: Dict[str, EndpointStats]) -> Dict[str, Any]:
    """Aggregate stats across all endpoints"""
    total_hits = sum(s.total_hits for s in all_stats.values())
    total_success = sum(s.success_count for s in all_stats.values())
    total_errors = sum(s.error_count for s in all_stats.values())
    
    avg_durations = [s.avg_duration_ms for s in all_stats.values() if s.avg_duration_ms > 0]
    overall_avg = sum(avg_durations) / len(avg_durations) if avg_durations else 0
    
    return {
        "total_hits": total_hits,
        "total_success": total_success,
        "total_errors": total_errors,
        "success_rate": (total_success / total_hits * 100) if total_hits > 0 else 0,
        "avg_duration_ms": overall_avg,
        "endpoint_count": len(all_stats)
    }
