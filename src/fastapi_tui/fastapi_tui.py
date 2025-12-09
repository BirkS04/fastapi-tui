"""
FastAPI TUI - Haupt-TUI-Anwendung mit Reactive State (OPTIMIERT)
"""

import asyncio
from datetime import datetime
from typing import Dict, Optional, Any
import uuid
from queue import Queue
import threading

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static
from textual.reactive import reactive
from textual.binding import Binding
from .widgets.endpoint_list import EndpointList
from .widgets.request_viewer import RequestViewer
from .widgets.stats_dashboard import StatsDashboard
from .widgets.exception_viewer import ExceptionViewer
from .widgets.server_logs_viewer import ServerLogsViewer
# ÄNDERUNG: Lazy Loading Import nutzen
from .persistence import get_persistence
from .core.models import EndpointHit, CustomEvent, EndpointStats, TUIEvent, SystemStats
from .config import get_config

try:
    import psutil
except ImportError:
    psutil = None


class FastAPITUI(App):
    """
    Haupt-TUI-Anwendung für FastAPI-Monitoring
    
    Usage:
        tui = FastAPITUI()
        tui.run()
    """
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #content-area {
        height: 1fr;
        width: 100%;
    }
    
    #endpoint-list {
        width: 30;
        height: 100%;
        border-right: solid $accent;
        background: $panel;
    }
    
    #endpoint-list.hidden {
        width: 0;
        border-right: none;
    }
    
    #right-panel {
        width: 1fr;
        height: 100%;
    }
    
    #main-content {
        height: 1fr;
        width: 100%;
    }
    
    #stats-panel {
        height: auto;
        width: 100%;
        background: $surface;
        overflow-y: auto;
    }
    
    #stats-header {
        height: auto;
        min-height: 12;
        margin-bottom: 1;
    }
    
    .stats-column {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }
    
    .section-title {
        text-align: center;
        text-style: bold;
        background: $accent;
        color: $text;
        width: 100%;
    }
    
    .table-title {
        margin-top: 1;
    }
    
    #system-grid, #global-grid {
        grid-size: 2 2;
        grid-gutter: 1;
        height: auto;
        margin-top: 1;
    }
    
    .metric-box {
        border: solid $primary;
        height: 4;
        content-align: center middle;
        background: $surface-lighten-1;
    }
    
    /* Enable horizontal and vertical scrolling in all ScrollableContainers */
    ScrollableContainer {
        overflow: auto auto;
    }
    
    #request-content, #response-content, #logs-content, #exception-content {
        min-width: 200;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("e", "toggle_sidebar", "Toggle Sidebar"),
        Binding("r", "refresh", "Refresh"),
    ]
    
    TITLE = "FastAPI TUI Monitor"
    
    # Reactive State
    current_endpoint: reactive[str] = reactive("")
    
    def __init__(self, event_queue: Optional[Queue] = None):
        super().__init__()
        self.event_queue = event_queue or Queue()
        self.endpoint_stats: Dict[str, EndpointStats] = {}
        self.endpoint_viewers: Dict[str, RequestViewer] = {}
        self.running = True
        self.start_time = datetime.now()
        self.config = get_config()
    
    def compose(self) -> ComposeResult:
        """Layout der App"""
        yield Header()
        
        with Horizontal(id="content-area"):
            # Endpoint-Liste (Sidebar)
            yield EndpointList(id="endpoint-list")
            
            # Right Panel (Main Content + Stats)
            with Vertical(id="right-panel"):
                with Vertical(id="main-content"):
                    with TabbedContent(id="tabs"):
                        with TabPane("Endpoints", id="endpoints-tab"):
                            # Container für den RequestViewer
                            yield Container(id="endpoint-viewer-container")
                        
                        with TabPane("Server Logs", id="logs-tab"):
                            # ServerLogsViewer mit Untertabs
                            yield ServerLogsViewer(id="server-logs")
                        
                        with TabPane("Exceptions", id="exceptions-tab"):
                            yield ExceptionViewer(id="exceptions-viewer")
                        
                        with TabPane("Statistics", id="stats-tab"):
                            yield StatsDashboard(id="stats-panel")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """App wurde gestartet"""
        # Initial Placeholder
        self.query_one("#endpoint-viewer-container").mount(
            Static("Select an endpoint to view details", id="placeholder")
        )

        # --- NEU: UI Settings anwenden ---
        
        # 1. Sidebar ausblenden?
        if not self.config.show_sidebar:
            sidebar = self.query_one("#endpoint-list", EndpointList)
            sidebar.add_class("hidden")
            
        # 2. Stats Panel ausblenden?
        if not self.config.show_stats_panel:
            # Wir entfernen den Tab "Statistics" komplett oder verstecken ihn
            # Da Tabs schwer dynamisch zu verstecken sind, entfernen wir den Inhalt
            # oder wir lassen es einfach leer.
            # Einfacher: Wir setzen das Panel auf display: none via CSS im Code
            stats_panel = self.query_one("#stats-panel", StatsDashboard)
            stats_panel.styles.display = "none"
            
            # Optional: Wenn Stats aus sind, sammeln wir auch keine System-Stats
            # (Performance sparen)
            self.config.enable_stats = False 

        # ---------------------------------

        # 1. Lade Historie aus DB
        self.load_history()
        
        # 2. Starte Event-Processing
        self.set_interval(0.1, self.process_events)
        
        # 3. Starte System-Stats Collection (nur wenn aktiviert)
        if self.config.enable_stats:
            self.set_interval(2.0, self._collect_system_stats)

    def load_history(self):
        """Lädt historische Daten aus der Persistenz"""
        # ÄNDERUNG: Instanz hier holen
        persistence = get_persistence()
        
        # Logs laden
        logs = persistence.get_recent_logs()
        server_logs = self.query_one("#server-logs", ServerLogsViewer)
        for log in logs:
            log_data = {
                "timestamp": log.get("timestamp"),
                "level": log.get("level", "INFO"),
                "message": log.get("message", ""),
                "type": log.get("type", log.get("level", "INFO"))
            }
            server_logs.add_log(log_data)
            
        # Hits laden
        hits = persistence.get_recent_hits()
        # Wir verarbeiten sie als wären es neue Events, aber ohne erneut zu speichern
        for hit_data in reversed(hits): # Älteste zuerst
            hit = EndpointHit(**hit_data)
            self._handle_hit(hit, save=False)

    def process_events(self) -> None:
        """Verarbeitet Events aus der Queue"""
        try:
            while not self.event_queue.empty():
                event = self.event_queue.get_nowait()
                self._handle_event(event, save=True)
        except Exception as e:
            self.log(f"Error processing events: {e}")
    
    def _handle_event(self, event: Dict[str, Any], save: bool = True) -> None:
        """Verarbeitet ein einzelnes Event"""
        # ÄNDERUNG: Instanz hier holen
        persistence = get_persistence()
        
        event_type = event.get("type")
        
        if event_type == "hit":
            hit_data = event.get("data", {})
            hit = EndpointHit(**hit_data)
            if save: persistence.save_hit(hit_data)
            self._handle_hit(hit, save=save)
        
        elif event_type == "custom":
            event_data = event.get("data", {})
            custom_event = CustomEvent(**event_data)
            self._handle_custom_event(custom_event)
        
        elif event_type == "stats_update":
            stats_data = event.get("data", {})
            endpoint = stats_data.get("endpoint")
            if endpoint:
                stats = EndpointStats(**stats_data)
                self._update_stats(endpoint, stats)
        
        elif event_type == "log":
            log_data = event.get("data", {})
            if save: 
                persistence.save_log(
                    log_data.get("level", "INFO"), 
                    log_data.get("message", ""), 
                    log_data.get("timestamp", datetime.now())
                )
            # Ensure 'type' field exists for proper routing
            if "type" not in log_data:
                log_data["type"] = log_data.get("level", "INFO")
            self._handle_log(log_data)
        
        elif event_type == "startup_routes":
            # Initialisiere Endpoints
            routes = event.get("data", [])
            endpoint_list = self.query_one("#endpoint-list", EndpointList)
            for route in routes:
                path = route.get("path")
                methods = route.get("methods", [])
                # Filtere HEAD/OPTIONS wenn gewünscht, oder nimm die erste Methode
                method = next((m for m in methods if m not in ["HEAD", "OPTIONS"]), "GET")
                if path:
                    endpoint_list.add_endpoint(path, method)
                    # Auch gleich Viewer erstellen
                    self.add_window(path)
            
        elif event_type == "request":
            # Support für das Format aus app/main.py (request_queue)
            # Wir konvertieren es in ein EndpointHit
            self._handle_legacy_request(event, save=save)
        
        elif event_type == "runtime_log_update":
            # Real-time runtime log updates
            self._handle_runtime_log_update(event.get("data", {}))
        
        elif event_type == "exception":
            # Global exception event
            self._handle_exception_event(event.get("data", {}))

    def _handle_legacy_request(self, req: Dict[str, Any], save: bool = True):
        """
        Konvertiert Legacy Request Format zu EndpointHit.
        """
        # ÄNDERUNG: Instanz hier holen
        persistence = get_persistence()
        
        data = req.get("data", req)
        request_id = data.get("id")
        endpoint = data.get("endpoint")
        
        # Check if this is an update to an existing request
        existing_hit = None
        if endpoint in self.endpoint_viewers:
            viewer = self.endpoint_viewers[endpoint]
            # Wir suchen im Viewer nach dem Hit (Annahme: viewer.hits ist zugänglich)
            if hasattr(viewer, 'hits'): 
                for hit in viewer.hits:
                    if hit.id == request_id:
                        existing_hit = hit
                        break
        
        if data.get("pending") or (not data.get("completed")):
            # PENDING Request - Create new entry if not exists
            if not existing_hit:
                hit = EndpointHit(
                    id=request_id or str(uuid.uuid4()),
                    endpoint=endpoint,
                    method=data.get("method"),
                    status_code=None,
                    duration_ms=None,
                    timestamp=data.get("timestamp") if isinstance(data.get("timestamp"), datetime) else datetime.now(),
                    client=data.get("client", "unknown"),
                    request_params=data.get("request_params"),
                    request_body=data.get("request_body"),
                    request_headers=data.get("request_headers"),
                    runtime_logs=data.get("runtime_logs", []),
                    pending=True
                )
                
                if save: persistence.save_hit(hit.model_dump())
                self._handle_hit(hit, save=save)
            
        elif data.get("completed"):
            # COMPLETED Request - Update existing or create new
            if existing_hit:
                # 1. Objekt Update (In-Memory)
                existing_hit.status_code = data.get("status_code") or data.get("status")
                existing_hit.duration_ms = data.get("duration_ms") or data.get("duration")
                existing_hit.response_body = data.get("response_body")
                existing_hit.runtime_logs = data.get("runtime_logs", [])
                existing_hit.pending = False
                
                # Handle exception if present in update
                if data.get("exception"):
                    exc_data = data.get("exception")
                    # Append to exceptions list - create NEW list to trigger reactivity
                    existing_hit.exceptions = existing_hit.exceptions + [exc_data]
                    # Also set legacy field for backward compatibility
                    existing_hit.exception = exc_data
                
                # UI-Update VOR dem Speichern machen!
                if endpoint in self.endpoint_viewers:
                    # Das hier updated jetzt sofort das TUI
                    self.endpoint_viewers[endpoint].add_hit(existing_hit)
                
                # Speichern in DB (in try/except, damit UI nicht stirbt)
                if save: 
                    try:
                        persistence.save_hit(existing_hit.model_dump())
                    except Exception as e:
                        # Fehler ins TUI Log schreiben, damit wir es sehen
                        self.log(f"❌ DB Error saving hit: {e}")

                # Update Stats for completed request
                if endpoint in self.endpoint_stats:
                    self.endpoint_stats[endpoint].update(existing_hit, count_hit=False)
                    self._update_stats(endpoint, self.endpoint_stats[endpoint])
                else:
                    # Should not happen if pending request created stats, but just in case
                    self.endpoint_stats[endpoint] = EndpointStats(endpoint=endpoint)
                    self.endpoint_stats[endpoint].update(existing_hit, count_hit=True) # Count it if it was missing
                    self._update_stats(endpoint, self.endpoint_stats[endpoint])

                self.log(f"✅ Updated request {request_id[:8]} to status {existing_hit.status_code}")
            else:
                # Create new completed hit (fallback)
                hit = EndpointHit(
                    id=request_id or str(uuid.uuid4()),
                    endpoint=endpoint,
                    method=data.get("method"),
                    status_code=data.get("status_code") or data.get("status"),
                    duration_ms=data.get("duration_ms") or data.get("duration"),
                    timestamp=data.get("timestamp") if isinstance(data.get("timestamp"), datetime) else datetime.now(),
                    client=data.get("client", "unknown"),
                    request_params=data.get("request_params"),
                    request_body=data.get("request_body"),
                    request_headers=data.get("request_headers"),
                    response_body=data.get("response_body"),
                    runtime_logs=data.get("runtime_logs", []),
                    pending=False
                )
                
                if save: persistence.save_hit(hit.model_dump())
                self._handle_hit(hit, save=save)

    def _handle_runtime_log_update(self, data: Dict[str, Any]) -> None:
        """
        Handles real-time runtime log updates.
        Updates the hit's runtime_logs and refreshes the inspector if visible.
        """
        request_id = data.get("request_id")
        all_logs = data.get("all_logs", [])
        
        if not request_id:
            return
        
        # Find the hit and update its logs
        for endpoint, viewer in self.endpoint_viewers.items():
            if hasattr(viewer, 'hits'):
                for hit in viewer.hits:
                    if hit.id == request_id:
                        # Update the logs on the hit object
                        hit.runtime_logs = all_logs
                        # Trigger UI update via add_hit (which calls watch_hits)
                        viewer.add_hit(hit)
                        return

    def _handle_exception_event(self, data: Dict[str, Any]) -> None:
        """
        Handles global exception events.
        Adds to global exceptions list and updates request if linked.
        """
        # Add to global exceptions viewer
        try:
            exceptions_viewer = self.query_one("#exceptions-viewer", ExceptionViewer)
            exceptions_viewer.add_exception(data)
        except Exception:
            pass  # Viewer not mounted yet
        
        # Also attach to the corresponding request if we have a request_id
        request_id = data.get("request_id")
        if request_id:
            for endpoint, viewer in self.endpoint_viewers.items():
                if hasattr(viewer, 'hits'):
                    for hit in viewer.hits:
                        if hit.id == request_id:
                            # Append to exceptions list - create NEW list to trigger reactivity
                            hit.exceptions = hit.exceptions + [data]
                            # Also set legacy field for backward compatibility
                            hit.exception = data 
                            # Force update in viewer
                            viewer.add_hit(hit)
                            # Also force refresh in inspector if it's open
                            try:
                                inspector = viewer.query_one("RequestInspector")
                                if inspector.hit and inspector.hit.id == request_id:
                                    inspector.force_refresh_data(hit)
                            except:
                                pass
                            return

    def _handle_log(self, log_data: Dict[str, Any]) -> None:
        """Verarbeitet ein Log-Event"""
        server_logs = self.query_one("#server-logs", ServerLogsViewer)
        server_logs.add_log(log_data)
    
    def _handle_hit(self, hit: EndpointHit, save: bool = True) -> None:
        """
        Verarbeitet einen Endpoint-Hit.
        OPTIMIERT: Nutzt reactive state in allen Widgets!
        """
        # Füge zur Endpoint-Liste hinzu (triggert watch_endpoints())
        endpoint_list = self.query_one("#endpoint-list", EndpointList)
        endpoint_list.add_endpoint(hit.endpoint, hit.method)
        
        # Erstelle oder update Viewer
        if hit.endpoint not in self.endpoint_viewers:
            self.add_window(hit.endpoint)
        
        # ✅ add_hit() triggert automatisch watch_hits() im RequestViewer!
        if hit.endpoint in self.endpoint_viewers:
            viewer = self.endpoint_viewers[hit.endpoint]
            viewer.add_hit(hit)
        
        # Update Stats
        if hit.endpoint not in self.endpoint_stats:
            self.endpoint_stats[hit.endpoint] = EndpointStats(endpoint=endpoint)
            self.log(f"Created new stats for {hit.endpoint}")
        
        self.endpoint_stats[hit.endpoint].update(hit)
        self.log(f"Stats updated for {hit.endpoint}: {self.endpoint_stats[hit.endpoint].total_hits} total hits")
        self._update_stats(hit.endpoint, self.endpoint_stats[hit.endpoint])
    
    def _handle_custom_event(self, event: CustomEvent) -> None:
        """
        Verarbeitet ein Custom-Event.
        OPTIMIERT: Nutzt reactive state!
        """
        # Füge zur Endpoint-Liste hinzu falls noch nicht vorhanden
        endpoint_list = self.query_one("#endpoint-list", EndpointList)
        if event.endpoint not in endpoint_list.endpoints:
            endpoint_list.add_endpoint(event.endpoint, "CUSTOM")
        
        # Erstelle oder update Viewer
        if event.endpoint not in self.endpoint_viewers:
            self.add_window(event.endpoint)
        
        # ✅ add_event() triggert automatisch watch_events() im RequestViewer!
        if event.endpoint in self.endpoint_viewers:
            viewer = self.endpoint_viewers[event.endpoint]
            viewer.add_event(event)
    
    def _update_stats(self, endpoint: str, stats: EndpointStats) -> None:
        """
        Aktualisiert die Statistiken.
        OPTIMIERT: Nutzt reactive state im StatsDashboard!
        """
        stats_dashboard = self.query_one("#stats-panel", StatsDashboard)
        # ✅ update_stats() triggert automatisch watch_stats() im Dashboard!
        stats_dashboard.update_stats(endpoint, stats)
    
    def add_window(self, endpoint: str) -> None:
        """
        Fügt ein neues Window für einen Endpoint hinzu
        
        Args:
            endpoint: Name des Endpoints
        """
        if endpoint in self.endpoint_viewers:
            return
        
        viewer = RequestViewer(endpoint)
        viewer.display = False  # Initially hidden
        self.endpoint_viewers[endpoint] = viewer
        
        # Mount viewer to container immediately
        container = self.query_one("#endpoint-viewer-container", Container)
        container.mount(viewer)
    
    def log_event(
        self, 
        endpoint: str, 
        message: str, 
        data: Optional[Dict[str, Any]] = None,
        level: str = "info"
    ) -> None:
        """
        Loggt ein Custom-Event
        
        Args:
            endpoint: Name des Endpoints
            message: Event-Message
            data: Optionale zusätzliche Daten
            level: Log-Level (info, warning, error)
        """
        event = CustomEvent(
            id=str(uuid.uuid4()),
            endpoint=endpoint,
            message=message,
            data=data,
            level=level
        )
        
        self.event_queue.put({
            "type": "custom",
            "data": event.model_dump()
        })


    def _collect_system_stats(self) -> None:
        """Sammelt System-Metriken"""
        cpu = 0.0
        mem_percent = 0.0
        mem_used = 0.0
        mem_total = 0.0
        
        if psutil:
            try:
                cpu = psutil.cpu_percent()
                mem = psutil.virtual_memory()
                mem_percent = mem.percent
                mem_used = mem.used / (1024 * 1024)
                mem_total = mem.total / (1024 * 1024)
            except Exception:
                pass
        
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        # Count active connections (approximate by pending requests)
        active_connections = sum(
            1 for viewer in self.endpoint_viewers.values() 
            if hasattr(viewer, 'hits') 
            for hit in viewer.hits 
            if hit.pending
        )
        
        stats = SystemStats(
            cpu_percent=cpu,
            memory_percent=mem_percent,
            memory_used_mb=mem_used,
            memory_total_mb=mem_total,
            active_connections=active_connections,
            uptime_seconds=uptime
        )
        
        # Update Dashboard
        try:
            dashboard = self.query_one("#stats-panel", StatsDashboard)
            dashboard.update_system_stats(stats)
        except Exception:
            pass  # Dashboard might not be mounted yet

    def on_endpoint_list_endpoint_selected(self, message: EndpointList.EndpointSelected) -> None:
        """Endpoint wurde in der Liste ausgewählt"""
        self.current_endpoint = message.endpoint
        
        # 1. Wechsle zum Endpoints Tab
        self.query_one("#tabs", TabbedContent).active = "endpoints-tab"
        
        # 2. Verstecke alle Viewer und zeige nur den ausgewählten
        container = self.query_one("#endpoint-viewer-container", Container)
        
        for endpoint, viewer in self.endpoint_viewers.items():
            if endpoint == message.endpoint:
                viewer.display = True
            else:
                viewer.display = False
    
    def action_toggle_sidebar(self) -> None:
        """Toggle Endpoint Sidebar"""
        sidebar = self.query_one("#endpoint-list", EndpointList)
        if sidebar.has_class("hidden"):
            sidebar.remove_class("hidden")
        else:
            sidebar.add_class("hidden")
    
    def action_refresh(self) -> None:
        """Refresh Display"""
        self.refresh()
    
    def action_quit(self) -> None:
        """Quit App"""
        self.running = False
        self.exit()


class TUIManager:
    """
    Manager für TUI in separatem Thread
    
    Usage:
        manager = TUIManager()
        manager.start()
        
        # Log events
        manager.log_hit(endpoint="/api/test", method="GET", ...)
        manager.log_event(endpoint="/api/test", message="Processing...")
    """
    
    def __init__(self):
        self.event_queue = Queue()
        self.tui_thread: Optional[threading.Thread] = None
        self.tui_app: Optional[FastAPITUI] = None
        self.started = False
    
    def start(self) -> None:
        """Startet das TUI in einem separaten Thread"""
        if self.started:
            return
        
        self.started = True
        self.tui_thread = threading.Thread(target=self._run_tui, daemon=True)
        self.tui_thread.start()
        
        # Warte kurz damit das TUI starten kann
        import time
        time.sleep(0.5)
    
    def _run_tui(self) -> None:
        """Führt das TUI aus"""
        self.tui_app = self._create_tui_app()
        self.tui_app.run()
    
    def _create_tui_app(self) -> FastAPITUI:
        """Erstellt eine TUI-App-Instanz mit der shared event queue"""
        return FastAPITUI(event_queue=self.event_queue)
    
    def log_hit(
        self,
        endpoint: str,
        method: str,
        status_code: Optional[int] = None,
        duration_ms: Optional[float] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """Loggt einen Endpoint-Hit"""
        hit = EndpointHit(
            id=str(uuid.uuid4()),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            request_data=request_data,
            response_data=response_data,
            error=error
        )
        
        self.event_queue.put({
            "type": "hit",
            "data": hit.model_dump()
        })
    
    def log_event(
        self,
        endpoint: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        level: str = "info"
    ) -> None:
        """Loggt ein Custom-Event"""
        # Auto-start TUI wenn noch nicht gestartet
        if not self.started:
            self.start()
        
        event = CustomEvent(
            id=str(uuid.uuid4()),
            endpoint=endpoint,
            message=message,
            data=data,
            level=level
        )
        
        # DEBUG: Print to verify event is being sent
        print(f"[TUI] Logging event: {endpoint} - {message}")
        
        self.event_queue.put({
            "type": "custom",
            "data": event.model_dump()
        })
    
    def log_log(self, level: str, message: str) -> None:
        """Loggt eine Server-Log-Nachricht"""
        # Auto-start TUI wenn noch nicht gestartet
        if not self.started:
            self.start()
            
        self.event_queue.put({
            "type": "log",
            "data": {
                "level": level,
                "message": message
            }
        })
    
    def add_window(self, endpoint: str) -> None:
        """Fügt ein neues Window hinzu"""
        if self.tui_app:
            self.tui_app.add_window(endpoint)
    
    def stop(self) -> None:
        """Stoppt das TUI"""
        if self.tui_app:
            self.tui_app.running = False
            self.tui_app.exit()


# Globale TUI-Instanz
_tui_manager: Optional[TUIManager] = None


def get_tui_manager() -> TUIManager:
    """Gibt die globale TUI-Manager-Instanz zurück"""
    global _tui_manager
    if _tui_manager is None:
        print("[TUI] Creating new TUIManager instance")
        _tui_manager = TUIManager()
    else:
        print(f"[TUI] Reusing existing TUIManager instance (queue size: {_tui_manager.event_queue.qsize()})")
    return _tui_manager