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

# Widgets
from .widgets.endpoint_list import EndpointList
from .widgets.request_viewer import RequestViewer
from .widgets.stats_dashboard import StatsDashboard
from .widgets.exception_viewer import ExceptionViewer
from .widgets.server_logs_viewer import ServerLogsViewer
from .widgets.session_manager import SessionManager

# Core
from .config import get_config
from .persistence import get_persistence
from .core.models import EndpointHit, CustomEvent, EndpointStats, TUIEvent, SystemStats

try:
    import psutil
except ImportError:
    psutil = None


class FastAPITUI(App):
    """
    Haupt-TUI-Anwendung für FastAPI-Monitoring
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
    
    # State für Session Management
    viewing_session_id: Optional[str] = None
    
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
                            yield Container(id="endpoint-viewer-container")
                        
                        with TabPane("Server Logs", id="logs-tab"):
                            yield ServerLogsViewer(id="server-logs")
                        
                        with TabPane("Exceptions", id="exceptions-tab"):
                            yield ExceptionViewer(id="exceptions-viewer")
                        
                        with TabPane("Statistics", id="stats-tab"):
                            yield StatsDashboard(id="stats-panel")
                        
                        # Session Manager Tab (nur wenn Persistence an)
                        if self.config.enable_persistence:
                            with TabPane("Sessions", id="sessions-tab"):
                                yield SessionManager(id="session-manager")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """App wurde gestartet"""
        # Initial Placeholder
        self.query_one("#endpoint-viewer-container").mount(
            Static("Select an endpoint to view details", id="placeholder")
        )

        # UI Settings anwenden
        if not self.config.show_sidebar:
            self.query_one("#endpoint-list", EndpointList).add_class("hidden")
            
        if not self.config.show_stats_panel:
            self.query_one("#stats-panel", StatsDashboard).styles.display = "none"
            self.config.enable_stats = False 

        # 1. Initiale Session setzen
        persistence = get_persistence()
        self.viewing_session_id = persistence.current_session_id

        # 2. Lade Historie (für die aktuelle Session)
        self.load_history(self.viewing_session_id)
        
        # 3. Starte Event-Processing
        self.set_interval(0.1, self.process_events)
        
        # 4. Starte System-Stats Collection
        if self.config.enable_stats:
            self.set_interval(2.0, self._collect_system_stats)

    def load_history(self, session_id: Optional[str] = None):
        """Lädt historische Daten aus der Persistenz"""
        persistence = get_persistence()
        target_session = session_id or persistence.current_session_id
        
        # 1. Logs laden
        logs = persistence.get_recent_logs(session_id=target_session)
        server_logs = self.query_one("#server-logs", ServerLogsViewer)
        for log in logs:
            log_data = {
                "timestamp": log.get("timestamp"),
                "level": log.get("level", "INFO"),
                "message": log.get("message", ""),
                "type": log.get("type", log.get("level", "INFO"))
            }
            server_logs.add_log(log_data)
            
        # 2. Hits (Requests) laden
        hits = persistence.get_recent_hits(session_id=target_session)
        
        # Exception Viewer holen
        exc_viewer = self.query_one("#exceptions-viewer", ExceptionViewer)
        
        for hit_data in reversed(hits): # Älteste zuerst
            hit = EndpointHit(**hit_data)
            
            # A) Request verarbeiten (baut Endpoint Liste & Request Viewer auf)
            self._handle_hit(hit, save=False)
            
            # B) Exceptions extrahieren und in den globalen Viewer laden
            
            # FIX: Wir prüfen das rohe Dict auf Legacy-Daten, da das Model kein 'exception' Feld hat
            if "exception" in hit_data and hit_data["exception"]:
                exc_viewer.add_exception(hit_data["exception"])
            
            # Standard Model-Feld (Liste)
            if hit.exceptions:
                for exc in hit.exceptions:
                    exc_viewer.add_exception(exc)

    def process_events(self) -> None:
        """Verarbeitet Events aus der Queue"""
        persistence = get_persistence()
        
        # Prüfen ob wir LIVE sind
        is_live_view = (self.viewing_session_id == persistence.current_session_id)
        
        try:
            while not self.event_queue.empty():
                event = self.event_queue.get_nowait()
                
                if is_live_view:
                    # Normaler Modus: Speichern und Anzeigen
                    self._handle_event(event, save=True)
                else:
                    # History Modus: NUR Speichern (im Hintergrund), NICHT Anzeigen
                    self._save_event_only(event)
                    
        except Exception as e:
            self.log(f"Error processing events: {e}")
    
    def _save_event_only(self, event: Dict[str, Any]) -> None:
        """Speichert Events in die DB ohne UI-Update (für Background-Processing)"""
        persistence = get_persistence()
        event_type = event.get("type")
        
        if event_type == "hit":
            persistence.save_hit(event.get("data", {}))
        elif event_type == "log":
            d = event.get("data", {})
            persistence.save_log(d.get("level", "INFO"), d.get("message", ""), d.get("timestamp", datetime.now()))
        elif event_type == "request":
            data = event.get("data", {})
            # Legacy Request zu Hit Konvertierung für DB (vereinfacht)
            hit = EndpointHit(
                id=data.get("id") or str(uuid.uuid4()),
                endpoint=data.get("endpoint"),
                method=data.get("method"),
                status_code=data.get("status_code"),
                duration_ms=data.get("duration_ms"),
                timestamp=data.get("timestamp") if isinstance(data.get("timestamp"), datetime) else datetime.now(),
                client=data.get("client", "unknown"),
                request_params=data.get("request_params"),
                request_body=data.get("request_body"),
                request_headers=data.get("request_headers"),
                response_body=data.get("response_body"),
                runtime_logs=data.get("runtime_logs", []),
                pending=data.get("pending", False)
            )
            persistence.save_hit(hit.model_dump())

    def _handle_event(self, event: Dict[str, Any], save: bool = True) -> None:
        """Verarbeitet ein einzelnes Event"""
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
            if "type" not in log_data:
                log_data["type"] = log_data.get("level", "INFO")
            self._handle_log(log_data)
        
        elif event_type == "startup_routes":
            routes = event.get("data", [])
            endpoint_list = self.query_one("#endpoint-list", EndpointList)
            for route in routes:
                path = route.get("path")
                methods = route.get("methods", [])
                method = next((m for m in methods if m not in ["HEAD", "OPTIONS"]), "GET")
                if path:
                    endpoint_list.add_endpoint(path, method)
                    self.add_window(path)
            
        elif event_type == "request":
            self._handle_legacy_request(event, save=save)
        
        elif event_type == "runtime_log_update":
            self._handle_runtime_log_update(event.get("data", {}))
        
        elif event_type == "exception":
            self._handle_exception_event(event.get("data", {}))

    def _handle_legacy_request(self, req: Dict[str, Any], save: bool = True):
        persistence = get_persistence()
        data = req.get("data", req)
        request_id = data.get("id")
        endpoint = data.get("endpoint")
        
        existing_hit = None
        if endpoint in self.endpoint_viewers:
            viewer = self.endpoint_viewers[endpoint]
            if hasattr(viewer, 'hits'): 
                for hit in viewer.hits:
                    if hit.id == request_id:
                        existing_hit = hit
                        break
        
        if data.get("pending") or (not data.get("completed")):
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
            if existing_hit:
                existing_hit.status_code = data.get("status_code") or data.get("status")
                existing_hit.duration_ms = data.get("duration_ms") or data.get("duration")
                existing_hit.response_body = data.get("response_body")
                existing_hit.runtime_logs = data.get("runtime_logs", [])
                existing_hit.pending = False
                
                if data.get("exception"):
                    exc_data = data.get("exception")
                    # FIX: Nur zur Liste hinzufügen, nicht als Attribut setzen
                    existing_hit.exceptions = existing_hit.exceptions + [exc_data]
                
                if endpoint in self.endpoint_viewers:
                    self.endpoint_viewers[endpoint].add_hit(existing_hit)
                
                if save: 
                    try:
                        persistence.save_hit(existing_hit.model_dump())
                    except Exception as e:
                        self.log(f"❌ DB Error saving hit: {e}")

                if endpoint in self.endpoint_stats:
                    self.endpoint_stats[endpoint].update(existing_hit, count_hit=False)
                    self._update_stats(endpoint, self.endpoint_stats[endpoint])
                else:
                    self.endpoint_stats[endpoint] = EndpointStats(endpoint=endpoint)
                    self.endpoint_stats[endpoint].update(existing_hit, count_hit=True)
                    self._update_stats(endpoint, self.endpoint_stats[endpoint])

            else:
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
        request_id = data.get("request_id")
        all_logs = data.get("all_logs", [])
        if not request_id: return
        for endpoint, viewer in self.endpoint_viewers.items():
            if hasattr(viewer, 'hits'):
                for hit in viewer.hits:
                    if hit.id == request_id:
                        hit.runtime_logs = all_logs
                        viewer.add_hit(hit)
                        return

    def _handle_exception_event(self, data: Dict[str, Any]) -> None:
        try:
            exceptions_viewer = self.query_one("#exceptions-viewer", ExceptionViewer)
            exceptions_viewer.add_exception(data)
        except Exception: pass
        
        request_id = data.get("request_id")
        if request_id:
            for endpoint, viewer in self.endpoint_viewers.items():
                if hasattr(viewer, 'hits'):
                    for hit in viewer.hits:
                        if hit.id == request_id:
                            # FIX: Nur zur Liste hinzufügen
                            hit.exceptions = hit.exceptions + [data]
                            viewer.add_hit(hit)
                            try:
                                inspector = viewer.query_one("RequestInspector")
                                if inspector.hit and inspector.hit.id == request_id:
                                    inspector.force_refresh_data(hit)
                            except: pass
                            return

    def _handle_log(self, log_data: Dict[str, Any]) -> None:
        server_logs = self.query_one("#server-logs", ServerLogsViewer)
        server_logs.add_log(log_data)
    
    def _handle_hit(self, hit: EndpointHit, save: bool = True) -> None:
        endpoint_list = self.query_one("#endpoint-list", EndpointList)
        endpoint_list.add_endpoint(hit.endpoint, hit.method)
        
        if hit.endpoint not in self.endpoint_viewers:
            self.add_window(hit.endpoint)
        
        if hit.endpoint in self.endpoint_viewers:
            viewer = self.endpoint_viewers[hit.endpoint]
            viewer.add_hit(hit)
        
        if hit.endpoint not in self.endpoint_stats:
            self.endpoint_stats[hit.endpoint] = EndpointStats(endpoint=hit.endpoint)
        
        self.endpoint_stats[hit.endpoint].update(hit)
        self._update_stats(hit.endpoint, self.endpoint_stats[hit.endpoint])
    
    def _handle_custom_event(self, event: CustomEvent) -> None:
        endpoint_list = self.query_one("#endpoint-list", EndpointList)
        if event.endpoint not in endpoint_list.endpoints:
            endpoint_list.add_endpoint(event.endpoint, "CUSTOM")
        
        if event.endpoint not in self.endpoint_viewers:
            self.add_window(event.endpoint)
        
        if event.endpoint in self.endpoint_viewers:
            viewer = self.endpoint_viewers[event.endpoint]
            viewer.add_event(event)
    
    def _update_stats(self, endpoint: str, stats: EndpointStats) -> None:
        stats_dashboard = self.query_one("#stats-panel", StatsDashboard)
        stats_dashboard.update_stats(endpoint, stats)
    
    def add_window(self, endpoint: str) -> None:
        if endpoint in self.endpoint_viewers:
            return
        viewer = RequestViewer(endpoint)
        viewer.display = False
        self.endpoint_viewers[endpoint] = viewer
        container = self.query_one("#endpoint-viewer-container", Container)
        container.mount(viewer)
    
    def _collect_system_stats(self) -> None:
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
            except Exception: pass
        
        uptime = (datetime.now() - self.start_time).total_seconds()
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
        try:
            dashboard = self.query_one("#stats-panel", StatsDashboard)
            dashboard.update_system_stats(stats)
        except Exception: pass

    def on_endpoint_list_endpoint_selected(self, message: EndpointList.EndpointSelected) -> None:
        self.current_endpoint = message.endpoint
        self.query_one("#tabs", TabbedContent).active = "endpoints-tab"
        for endpoint, viewer in self.endpoint_viewers.items():
            if endpoint == message.endpoint:
                viewer.display = True
            else:
                viewer.display = False
    
    def on_session_manager_session_selected(self, message: SessionManager.SessionSelected) -> None:
        """Handler wenn Session ausgewählt wurde"""
        new_session_id = message.session_id
        
        if self.viewing_session_id == new_session_id:
            self.notify("Already viewing this session")
            return
            
        self.viewing_session_id = new_session_id
        persistence = get_persistence()
        is_live = (new_session_id == persistence.current_session_id)
        
        status_msg = "LIVE Session" if is_live else "HISTORICAL Session"
        self.notify(f"Switched to {status_msg}")
        
        # 1. UI LEEREN
        self._clear_ui_state()
        
        # 2. DATEN LADEN
        self.load_history(new_session_id)
    
    def _clear_ui_state(self) -> None:
        """Setzt die gesamte UI zurück."""
        # 1. Endpoint List leeren
        self.query_one("#endpoint-list", EndpointList).clear()
        
        # 2. Logs leeren
        try:
            self.query_one("#server-logs", ServerLogsViewer).clear()
        except: pass
        
        # 3. Stats leeren
        self.query_one("#stats-panel", StatsDashboard).clear()

        # 4. Exceptions leeren
        try:
            self.query_one("#exceptions-viewer", ExceptionViewer).clear()
        except: pass
        
        # 5. Request Viewers entfernen (SICHERE METHODE)
        container = self.query_one("#endpoint-viewer-container", Container)
        
        # Wir entfernen alle Kinder, die NICHT der Placeholder sind
        for child in list(container.children):
            if child.id != "placeholder":
                child.remove()
        
        # Falls der Placeholder aus irgendeinem Grund weg ist, neu erstellen
        if not container.query("#placeholder"):
             container.mount(Static("Select an endpoint to view details", id="placeholder"))
        
        self.endpoint_viewers = {}
        
        # 6. Interne Stats resetten
        self.endpoint_stats = {}

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one("#endpoint-list", EndpointList)
        if sidebar.has_class("hidden"):
            sidebar.remove_class("hidden")
        else:
            sidebar.add_class("hidden")
    
    def action_refresh(self) -> None:
        self.refresh()
    
    def action_quit(self) -> None:
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