import json
from textual.app import ComposeResult
from textual.containers import Container, Vertical, ScrollableContainer, Horizontal
from textual.widgets import Static, TabbedContent, TabPane, Label, Button
from textual.reactive import reactive
from textual import on
from datetime import datetime

from ..core.models import EndpointHit
from .json_viewer import JSONViewer, RuntimeLogsViewer
from .exception_viewer import RequestExceptionView

# --- Clipboard Helper ---
try:
    from ..clipboard_utils import copy_and_notify
except ImportError:
    def copy_and_notify(widget, text, message):
        """Fallback, falls clipboard_utils nicht existiert."""
        try:
            import pyperclip
            pyperclip.copy(text)
            widget.notify(message)
        except ImportError:
            widget.notify("Clipboard module not found (install pyperclip)", severity="error")

# Debug Helper
def log_debug(msg):
    with open("debug.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [INSPECTOR] {msg}\n")

# --- Helper Widgets für den Inhalt ---

class RequestLayout(Vertical):
    """
    Baut das Layout für den Request-Tab auf (4 Unter-Tabs + Buttons).
    Nutzt compose() für sicheres Rendering der verschachtelten Tabs.
    """
    DEFAULT_CSS = """
    RequestLayout {
        height: auto;
        width: 100%;
    }
    .section-label {
        margin-top: 1;
        margin-bottom: 1;
    }
    .spacer {
        height: 1;
    }
    .copy-button-bar {
        height: auto;
        margin-bottom: 1;
        align: left middle;
    }
    .copy-button-bar Button {
        margin-right: 1;
    }
    .code-block {
        margin: 1;
        color: auto;
    }
    """

    def __init__(self, hit: EndpointHit):
        super().__init__()
        self.hit = hit

    def compose(self) -> ComposeResult:
        # Query Params (immer sichtbar oben)
        if self.hit.request_params:
            yield Label("[bold]Query Parameters:[/]", classes="section-label")
            yield JSONViewer(self.hit.request_params)
            yield Label("", classes="spacer")

        # Die 4 angeforderten Tabs
        with TabbedContent():
            # 1. Body Tree
            with TabPane("Body Tree"):
                if self.hit.request_body:
                    yield JSONViewer(self.hit.request_body)
                else:
                    yield Static("[dim]No Body[/]", classes="code-block")

            # 2. Body Copy
            with TabPane("Body Copy"):
                body_str = json.dumps(self.hit.request_body, indent=2) if self.hit.request_body else "{}"
                yield Horizontal(
                    Button("Copy cURL", id="btn-req-curl", variant="primary"),
                    Button("Copy Full JSON", id="btn-req-full-json"),
                    Button("Copy Body JSON", id="btn-req-body-json"),
                    classes="copy-button-bar"
                )
                yield Static(body_str, classes="code-block")

            # 3. Headers Tree
            with TabPane("Headers Tree"):
                if self.hit.request_headers:
                    yield JSONViewer(self.hit.request_headers)
                else:
                    yield Static("[dim]No Headers[/]", classes="code-block")

            # 4. Headers Copy
            with TabPane("Headers Copy"):
                headers_str = json.dumps(self.hit.request_headers, indent=2) if self.hit.request_headers else "{}"
                yield Horizontal(
                    Button("Copy Headers JSON", id="btn-req-headers-json"),
                    classes="copy-button-bar"
                )
                yield Static(headers_str, classes="code-block")


class ResponseLayout(Vertical):
    """
    Baut das Layout für den Response-Tab auf (Tree/Copy Tabs + Buttons).
    """
    DEFAULT_CSS = """
    ResponseLayout {
        height: auto;
        width: 100%;
    }
    .copy-button-bar {
        height: auto;
        margin-bottom: 1;
        align: left middle;
    }
    .copy-button-bar Button {
        margin-right: 1;
    }
    .code-block {
        margin: 1;
        color: auto;
    }
    """

    def __init__(self, hit: EndpointHit):
        super().__init__()
        self.hit = hit

    def compose(self) -> ComposeResult:
        if self.hit.pending:
            yield Static("\n[yellow]⏳ Response pending... waiting for server[/]\n", classes="pending-msg")
            return

        yield Label(f"[bold]Status: {self.hit.status_code}[/]", classes="section-label")

        with TabbedContent():
            # 1. Response Tree
            with TabPane("Response Tree"):
                if self.hit.response_body:
                    yield JSONViewer(self.hit.response_body)
                else:
                    yield Static("[dim]No Response Body[/]", classes="code-block")

            # 2. Response Copy
            with TabPane("Response Copy"):
                res_str = json.dumps(self.hit.response_body, indent=2) if self.hit.response_body else "{}"
                yield Horizontal(
                    Button("Copy Full Response JSON", id="btn-res-full-json"),
                    Button("Copy Body JSON", id="btn-res-body-json", variant="primary"),
                    classes="copy-button-bar"
                )
                yield Static(res_str, classes="code-block")


# --- Main Inspector Class ---

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
        if self.hit:
            self._update_ui()

    def watch_hit(self, old_hit: EndpointHit, new_hit: EndpointHit) -> None:
        """Wird gefeuert, wenn sich self.hit ändert."""
        if not self.is_mounted:
            return
        # if new_hit:
        #     self._update_ui()

    def force_refresh_data(self, new_hit: EndpointHit):
        """Hilfsmethode für Updates von außen."""
        self.hit = new_hit 
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
            # Hier nutzen wir nun die neue Layout-Klasse
            req_container.mount(RequestLayout(self.hit))

            # 3. Response Tab Update
            res_container = self.query_one("#response-content", ScrollableContainer)
            res_container.remove_children()
            # Hier nutzen wir nun die neue Layout-Klasse
            res_container.mount(ResponseLayout(self.hit))

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

    # --- Button Handlers ---

    @on(Button.Pressed)
    def handle_copy_buttons(self, event: Button.Pressed):
        """Handelt alle Copy-Buttons im Inspector (Bubbling Events)."""
        if not self.hit:
            return

        btn_id = event.button.id
        
        def to_json(data):
            return json.dumps(data, indent=2, ensure_ascii=False)

        text_to_copy = ""
        msg = "Copied!"

        # --- Request Actions ---
        if btn_id == "btn-req-curl":
            text_to_copy = self._generate_curl()
            msg = "cURL copied to clipboard!"
        
        elif btn_id == "btn-req-full-json":
            full_req = {
                "method": self.hit.method,
                "url": self.hit.endpoint,
                "headers": self.hit.request_headers,
                "body": self.hit.request_body,
                "params": self.hit.request_params
            }
            text_to_copy = to_json(full_req)
            msg = "Full Request JSON copied!"

        elif btn_id == "btn-req-body-json":
            text_to_copy = to_json(self.hit.request_body) if self.hit.request_body else "{}"
            msg = "Request Body copied!"

        elif btn_id == "btn-req-headers-json":
            text_to_copy = to_json(self.hit.request_headers) if self.hit.request_headers else "{}"
            msg = "Request Headers copied!"

        # --- Response Actions ---
        elif btn_id == "btn-res-full-json":
            full_res = {
                "status": self.hit.status_code,
                "duration_ms": self.hit.duration_ms,
                "body": self.hit.response_body
            }
            text_to_copy = to_json(full_res)
            msg = "Full Response JSON copied!"

        elif btn_id == "btn-res-body-json":
            text_to_copy = to_json(self.hit.response_body) if self.hit.response_body else "{}"
            msg = "Response Body copied!"

        if text_to_copy:
            copy_and_notify(self, text_to_copy, msg)

    def _generate_curl(self) -> str:
        """Generiert einen cURL Command String."""
        method = self.hit.method or "GET"
        url = self.hit.endpoint or "/"
        
        parts = [f"curl -X {method} '{url}'"]
        
        if self.hit.request_headers:
            for k, v in self.hit.request_headers.items():
                parts.append(f"-H '{k}: {v}'")
        
        if self.hit.request_body:
            body_str = json.dumps(self.hit.request_body)
            # Einfaches Escaping für Single Quotes
            body_str = body_str.replace("'", "'\\''")
            parts.append(f"-d '{body_str}'")
            
        return " \\\n  ".join(parts)

    # --- UI Builders (nur noch für Header/Logs/Exception) ---

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

    def _build_logs_widgets(self) -> list:
        widgets = []
        if self.hit.runtime_logs:
            widgets.append(Label("[bold]Runtime Logs:[/]", classes="section-label"))
            widgets.append(RuntimeLogsViewer(self.hit.runtime_logs))
        else:
            widgets.append(Static("[dim]No runtime logs captured[/]"))
        return widgets

    def _build_exception_widgets(self) -> list:
        widgets = []
        if self.hit.exceptions:
            widgets.append(RequestExceptionView(self.hit.exceptions))
        elif self.hit.exception:
            widgets.append(RequestExceptionView([self.hit.exception]))
        else:
            widgets.append(Static("[dim green]✓ No exception occurred[/]"))
        return widgets