from textual.app import ComposeResult
from textual.containers import Container, Vertical, ScrollableContainer
from textual.widgets import Static, TabbedContent, TabPane, Label
from textual.reactive import reactive
from datetime import datetime

from ..core.models import EndpointHit
from .json_viewer import JSONViewer, RuntimeLogsViewer
from .exception_viewer import RequestExceptionView

# Debug Helper
def log_debug(msg):
    with open("debug.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [INSPECTOR] {msg}\n")

class RequestInspector(Container):
    """
    Detaillierte Ansicht eines einzelnen Requests.
    Nutzt DOM-Updates statt Recompose für bessere Performance und Stabilität.
    Alle Tabs haben X/Y Scrolling.
    """
    
    hit: reactive[EndpointHit] = reactive(None, always_update=True)

    def __init__(self, hit: EndpointHit, **kwargs):
        super().__init__(**kwargs)
        self.hit = hit

    def compose(self) -> ComposeResult:
        """
        Erstellt das Grundgerüst. Dieses wird NICHT mehr zerstört.
        ScrollableContainer direkt als Tab-Inhalt für Scrolling.
        """
        # 1. Header (wird per update() geändert)
        yield Static("Loading...", id="inspector-header")
        
        # 2. Tabs mit ScrollableContainer für X/Y Scrolling
        with TabbedContent(id="inspector-tabs"):
            with TabPane("Request", id="tab-request"):
                yield ScrollableContainer(id="request-content")
            
            with TabPane("Response", id="tab-response"):
                yield ScrollableContainer(id="response-content")
            
            with TabPane("Logs", id="tab-logs"):
                yield ScrollableContainer(id="logs-content")
            
            with TabPane("Exception", id="tab-exception"):
                yield ScrollableContainer(id="exception-content")

    def on_mount(self):
        """Beim ersten Anzeigen einmal Daten laden"""
        # Hier ist is_mounted garantiert True
        if self.hit:
            self._update_ui()

    def watch_hit(self, old_hit: EndpointHit, new_hit: EndpointHit) -> None:
        """Wird gefeuert, wenn sich self.hit ändert."""
        
        # --- FIX START ---
        # Verhindert den Crash beim Start (__init__)
        if not self.is_mounted:
            return
        # --- FIX END ---

        # if new_hit:
        #     log_debug(f"WATCH_HIT triggered for {new_hit.id[:8]} | Pending: {new_hit.pending}")
        #     self._update_ui()

    def force_refresh_data(self, new_hit: EndpointHit):
        """Hilfsmethode für Updates von außen."""
        # log_debug(f"FORCE_REFRESH called for {new_hit.id[:8]}")
        self.hit = new_hit 
        # Force UI update even if hit object is same
        self._update_ui() 

    def _update_ui(self):
        """
        Aktualisiert die Inhalte der Container basierend auf self.hit
        """
        if not self.hit:
            return

        try:
            # 1. Header Update
            header = self.query_one("#inspector-header", Static)
            header.update(self._build_header_text())

            # 2. Request Tab Update
            req_container = self.query_one("#request-content", ScrollableContainer)
            req_container.remove_children()
            req_container.mount_all(self._build_request_widgets())

            # 3. Response Tab Update
            res_container = self.query_one("#response-content", ScrollableContainer)
            res_container.remove_children()
            res_container.mount_all(self._build_response_widgets())

            # 4. Logs Update
            log_container = self.query_one("#logs-content", ScrollableContainer)
            log_container.remove_children()
            log_container.mount_all(self._build_logs_widgets())
            
            # 5. Exception Update
            exc_container = self.query_one("#exception-content", ScrollableContainer)
            exc_container.remove_children()
            exc_container.mount_all(self._build_exception_widgets())
            
        except Exception as e:
            log_debug(f"Error in _update_ui: {e}")

    def _build_header_text(self) -> str:
        if self.hit.pending:
            status_text = "[yellow]⏳ PENDING[/]"
            duration_text = "..."
        else:
            color = "green" if self.hit.status_code and self.hit.status_code < 400 else "red"
            status_text = f"[{color}]{self.hit.status_code}[/]"
            duration_text = f"{self.hit.duration_ms:.2f}ms" if self.hit.duration_ms else "..."
        
        safe_method = str(self.hit.method).replace("[", "\\[")
        safe_endpoint = str(self.hit.endpoint).replace("[", "\\[")
        return f"[bold]{safe_method}[/] {safe_endpoint} | {status_text} | {duration_text}"

    def _build_request_widgets(self) -> list:
        widgets = []
        if self.hit.request_params:
            widgets.append(Label("[bold]Query Parameters:[/]", classes="section-label"))
            widgets.append(JSONViewer(self.hit.request_params))
        if self.hit.request_body:
            widgets.append(Label("[bold]Request Body:[/]", classes="section-label"))
            widgets.append(JSONViewer(self.hit.request_body))
        if self.hit.request_headers:
            widgets.append(Label("[bold]Headers:[/]", classes="section-label"))
            widgets.append(JSONViewer(self.hit.request_headers))
        
        if not widgets:
            widgets.append(Static("[dim]No request data captured[/]"))
        return widgets

    def _build_response_widgets(self) -> list:
        widgets = []
        if self.hit.pending:
            widgets.append(Static("\n[yellow]⏳ Response pending... waiting for server[/]\n", classes="pending-msg"))
        elif self.hit.response_body:
            widgets.append(Label(f"[bold]Status: {self.hit.status_code}[/]", classes="section-label"))
            widgets.append(JSONViewer(self.hit.response_body))
        else:
            widgets.append(Static("[dim]No response data captured[/]"))
        return widgets

    def _build_logs_widgets(self) -> list:
        widgets = []
        
        if self.hit.runtime_logs:
            widgets.append(Label("[bold]Runtime Logs:[/]", classes="section-label"))
            # Use RuntimeLogsViewer for flat list display with smart rendering
            widgets.append(RuntimeLogsViewer(self.hit.runtime_logs))
        else:
            widgets.append(Static("[dim]No runtime logs captured[/]"))
        return widgets

    def _build_exception_widgets(self) -> list:
        widgets = []
        
        if self.hit.exceptions:
            widgets.append(RequestExceptionView(self.hit.exceptions))
        elif self.hit.exception:
             # Fallback for legacy single exception
            widgets.append(RequestExceptionView([self.hit.exception]))
        else:
            widgets.append(Static("[dim green]✓ No exception occurred[/]"))
        return widgets