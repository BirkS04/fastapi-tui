"""
Statistics Dashboard - Zeigt Endpoint-Statistiken mit Reactive State
"""

from datetime import timedelta
from textual.app import ComposeResult
from textual.widgets import Static, DataTable, Label, Digits
from textual.containers import Container, Vertical, Horizontal, Grid
from textual.reactive import reactive
from typing import Dict, Optional
from rich.text import Text
from rich.panel import Panel
from rich.align import Align

from ..core.models import EndpointStats, SystemStats


class StatsDashboard(Vertical):
    """Dashboard mit Statistiken für alle Endpoints"""
    
    # Reactive Properties
    stats: reactive[Dict[str, EndpointStats]] = reactive({}, always_update=True)
    system_stats: reactive[Optional[SystemStats]] = reactive(None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "📊 Statistics Dashboard"
        self._mounted = False
    
    def compose(self) -> ComposeResult:
        # 1. System & Global Stats Area
        with Horizontal(id="stats-header"):
            # System Metrics
            with Vertical(classes="stats-column"):
                yield Label("System Metrics", classes="section-title")
                with Grid(id="system-grid"):
                    yield Static(id="cpu-stat", classes="metric-box")
                    yield Static(id="ram-stat", classes="metric-box")
                    yield Static(id="uptime-stat", classes="metric-box")
                    yield Static(id="conns-stat", classes="metric-box")
            
            # Global Request Metrics
            with Vertical(classes="stats-column"):
                yield Label("Global Request Metrics", classes="section-title")
                with Grid(id="global-grid"):
                    yield Static(id="total-req-stat", classes="metric-box")
                    yield Static(id="error-rate-stat", classes="metric-box")
                    yield Static(id="avg-latency-stat", classes="metric-box")
                    yield Static(id="req-rate-stat", classes="metric-box")

        # 2. Endpoint Table
        yield Label("Endpoint Performance", classes="section-title table-title")
        yield DataTable(id="stats-table")
    
    def on_mount(self) -> None:
        """Widget wurde gemountet"""
        self._mounted = True
        
        # Stats-Tabelle konfigurieren
        table = self.query_one("#stats-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(
            "Endpoint",
            "Hits",
            "Success",
            "Errors",
            "Avg (ms)",
            "P95 (ms)",
            "P99 (ms)",
            "Min/Max",
            "Status Codes"
        )
        
        # Initial refresh
        self._refresh_display()
    
    # ============================================================================
    # REACTIVE WATCHERS
    # ============================================================================
    
    def watch_stats(self, old_stats: Dict[str, EndpointStats], new_stats: Dict[str, EndpointStats]) -> None:
        """Triggert UI-Update bei Stats-Änderung"""
        if self._mounted:
            self._refresh_display()
            
    def watch_system_stats(self, old_stats: Optional[SystemStats], new_stats: Optional[SystemStats]) -> None:
        """Triggert UI-Update bei System-Stats-Änderung"""
        if self._mounted:
            self._update_system_metrics()

    # ============================================================================
    # PUBLIC API
    # ============================================================================
    
    def update_stats(self, endpoint: str, stats: EndpointStats) -> None:
        """Aktualisiert die Statistiken für einen Endpoint."""
        current_stats = dict(self.stats)
        current_stats[endpoint] = stats
        self.stats = current_stats
        
    def update_system_stats(self, stats: SystemStats) -> None:
        """Aktualisiert die System-Statistiken."""
        self.system_stats = stats
    
    # ============================================================================
    # INTERNAL UI UPDATES
    # ============================================================================
    
    def _refresh_display(self) -> None:
        """Aktualisiert die gesamte Anzeige"""
        if not self._mounted:
            return
            
        try:
            self._update_global_metrics()
            self._update_table()
        except Exception as e:
            self.log(f"Error refreshing stats display: {e}")
            
    def _update_system_metrics(self) -> None:
        """Aktualisiert die System-Metriken"""
        if not self.system_stats:
            return
            
        s = self.system_stats
        
        # CPU
        cpu_color = "green" if s.cpu_percent < 50 else "yellow" if s.cpu_percent < 80 else "red"
        self.query_one("#cpu-stat", Static).update(
            f"[dim]CPU Usage[/]\n[{cpu_color}]{s.cpu_percent:.1f}%[/]"
        )
        
        # RAM
        ram_color = "green" if s.memory_percent < 70 else "yellow" if s.memory_percent < 90 else "red"
        self.query_one("#ram-stat", Static).update(
            f"[dim]RAM Usage[/]\n[{ram_color}]{s.memory_used_mb:.0f}MB / {s.memory_total_mb:.0f}MB ({s.memory_percent:.0f}%)[/]"
        )
        
        # Uptime
        uptime_str = str(timedelta(seconds=int(s.uptime_seconds)))
        self.query_one("#uptime-stat", Static).update(
            f"[dim]Uptime[/]\n[cyan]{uptime_str}[/]"
        )
        
        # Connections
        self.query_one("#conns-stat", Static).update(
            f"[dim]Active Conns[/]\n[blue]{s.active_connections}[/]"
        )

    def _update_global_metrics(self) -> None:
        """Aktualisiert die globalen Request-Metriken"""
        total_requests = sum(s.total_hits for s in self.stats.values())
        total_errors = sum(s.error_count for s in self.stats.values())
        
        # Weighted Avg Duration
        if total_requests > 0:
            weighted_avg = sum(
                s.avg_duration_ms * s.total_hits 
                for s in self.stats.values()
            ) / total_requests
            error_rate = (total_errors / total_requests) * 100
        else:
            weighted_avg = 0
            error_rate = 0
            
        # Total Requests
        self.query_one("#total-req-stat", Static).update(
            f"[dim]Total Requests[/]\n[bold white]{total_requests:,}[/]"
        )
        
        # Error Rate
        err_color = "green" if error_rate < 1 else "yellow" if error_rate < 5 else "red"
        self.query_one("#error-rate-stat", Static).update(
            f"[dim]Error Rate[/]\n[{err_color}]{error_rate:.2f}% ({total_errors})[/]"
        )
        
        # Avg Latency
        lat_color = "green" if weighted_avg < 200 else "yellow" if weighted_avg < 500 else "red"
        self.query_one("#avg-latency-stat", Static).update(
            f"[dim]Avg Latency[/]\n[{lat_color}]{weighted_avg:.0f} ms[/]"
        )
        
        # Request Rate (Approximate based on uptime if available)
        req_rate = "N/A"
        if self.system_stats and self.system_stats.uptime_seconds > 0:
            rate = total_requests / self.system_stats.uptime_seconds
            req_rate = f"{rate:.2f} req/s"
            
        self.query_one("#req-rate-stat", Static).update(
            f"[dim]Request Rate[/]\n[cyan]{req_rate}[/]"
        )

    def _update_table(self) -> None:
        """Aktualisiert die Stats-Tabelle"""
        table = self.query_one("#stats-table", DataTable)
        
        # Save current selection or scroll position if possible (Textual DataTable is tricky with full refresh)
        # For now, just clear and re-add.
        table.clear()
        
        # Sortiere nach Total Hits
        sorted_stats = sorted(
            self.stats.items(),
            key=lambda x: x[1].total_hits,
            reverse=True
        )
        
        for endpoint, stats in sorted_stats:
            # Endpoint Name
            endpoint_display = endpoint
            
            # Success Rate
            success_rate = (stats.success_count / stats.total_hits * 100) if stats.total_hits > 0 else 0
            success_text = Text(f"{stats.success_count} ({success_rate:.0f}%)")
            if success_rate >= 95: success_text.stylize("green")
            elif success_rate >= 80: success_text.stylize("yellow")
            else: success_text.stylize("red")
            
            # Error Count
            error_text = Text(str(stats.error_count))
            if stats.error_count > 0: error_text.stylize("red bold")
            else: error_text.stylize("dim")
            
            # Latency Colors
            def get_lat_color(ms):
                if ms < 100: return "green"
                if ms < 500: return "yellow"
                return "red"
            
            avg_text = Text(f"{stats.avg_duration_ms:.0f}", style=get_lat_color(stats.avg_duration_ms))
            p95_text = Text(f"{stats.p95:.0f}", style=get_lat_color(stats.p95))
            p99_text = Text(f"{stats.p99:.0f}", style=get_lat_color(stats.p99))
            
            min_max = f"{stats.min_duration_ms:.0f} / {stats.max_duration_ms:.0f}" if stats.min_duration_ms else "-"
            
            # Status Codes Summary
            codes = []
            for code, count in sorted(stats.status_codes.items()):
                color = "green" if code < 400 else "red" if code >= 500 else "yellow"
                codes.append(f"[{color}]{code}[/]:{count}")
            codes_str = " ".join(codes)
            
            table.add_row(
                endpoint_display,
                str(stats.total_hits),
                success_text,
                error_text,
                avg_text,
                p95_text,
                p99_text,
                min_max,
                codes_str,
                key=endpoint
            )