"""
Exception Viewer Widget - Enhanced debugging tool with Variable Inspector
"""

from textual.widgets import Static, Tree, DataTable, Label, Collapsible, Button, TabbedContent, TabPane, TextArea
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual import on
from typing import Any, Dict, List
import json
from datetime import datetime
from .auto_scroll_log import AutoScrollLog

class ExceptionDetail(Container):
    """Detailed view of a single exception with traceback and frame info."""
    
    DEFAULT_CSS = """
    ExceptionDetail {
        height: 100%;
    }
    ExceptionDetail TextArea {
        height: 100%;
        border: none;
    }
    ExceptionDetail .action-bar {
        height: 2;
        width: 100%;
        margin: 0;
        padding: 0;
    }
    ExceptionDetail .exception-header {
        width: auto;
        padding: 0 1;
        height: auto;
    }
    ExceptionDetail .exception-meta {
        margin: 0;
        padding: 0 1;
        height: auto;
    }
    ExceptionDetail #btn-copy-details {
        width: auto;
        min-width: 4;
        min-height: 3;
        dock: right;
        content-align: center middle;
        text-align: center;
    }
    ExceptionDetail TabbedContent {
        height: 1fr;
        margin-top: 1;
    }
    """
    
    def __init__(self, exc_data: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.exc_data = exc_data
    
    def compose(self):
        # Header with exception type and message + copy button
        exc_type = self.exc_data.get("exception_type", "Unknown")
        message = self.exc_data.get("message", "No message")
        
        with Horizontal(classes="action-bar"):
            yield Static(f"[bold red]⚠ {exc_type}[/]: {message[:200]}", classes="exception-header")
            yield Button("📋copy", id="btn-copy-details", variant="primary")
        
        # Request info
        endpoint = self.exc_data.get("endpoint", "Unknown")
        method = self.exc_data.get("method", "?")
        timestamp = self.exc_data.get("timestamp", "")
        if isinstance(timestamp, str):
            timestamp = timestamp[:19]  # Trim to readable format
        
        yield Static(f"[dim]{method} {endpoint} @ {timestamp}[/]", classes="exception-meta")
        
        # Tabbed content for Inspector vs Traceback
        with TabbedContent(initial="tab-traceback"):
            with TabPane("🔍 Inspector", id="tab-inspector"):
                yield VariableInspector(self.exc_data)
            
            with TabPane("📦 Variables", id="tab-variables"):
                 # Show variables of the error frame directly
                frames = self.exc_data.get("frames", [])
                if frames:
                    error_frame = frames[-1]
                    variables = error_frame.get("variables", [])
                    if variables:
                        # Reuse VariableInspector logic but focused on variables
                        # Or just a simple table
                        yield Static("[bold]Variables at Error Time[/]", classes="section-header")
                        
                        # Create a simple table for quick view
                        table = DataTable(cursor_type="row")
                        table.add_column("Name", width=20)
                        table.add_column("Value", width=60)
                        
                        for var in variables:
                            name = var.get("name", "?")
                            preview = var.get("value_preview", "")
                            if var.get("is_sensitive"):
                                preview = "[red]***MASKED***[/]"
                            else:
                                preview = str(preview).replace("[", "\\[")
                            
                            safe_name = str(name).replace("[", "\\[")
                            table.add_row(f"[cyan]{safe_name}[/]", f"[green]{preview}[/]")
                        
                        yield table
                    else:
                         # Fallback to locals_preview
                        locals_preview = error_frame.get("locals_preview", {})
                        if locals_preview:
                            table = DataTable(cursor_type="row")
                            table.add_column("Name", width=20)
                            table.add_column("Value", width=60)
                            for k, v in locals_preview.items():
                                safe_k = str(k).replace("[", "\\[")
                                safe_v = str(v).replace("[", "\\[")
                                table.add_row(f"[cyan]{safe_k}[/]", f"[green]{safe_v}[/]")
                            yield table
                        else:
                            yield Static("[dim]No variables captured[/]")
                else:
                    yield Static("[dim]No stack frames available[/]")

            with TabPane("📜 Traceback", id="tab-traceback"):
                traceback_str = self.exc_data.get("traceback_str", "No traceback available")
                # Use AutoScrollLog for better UX
                log = AutoScrollLog(id="traceback-text", highlight=True)
                log.write(traceback_str)
                yield log

    @on(Button.Pressed, "#btn-copy-details")
    def on_copy_details(self):
        """Copy exception details to clipboard."""
        try:
            import pyperclip
            # Format a nice report
            lines = []
            lines.append(f"Exception: {self.exc_data.get('exception_type')}")
            lines.append(f"Message: {self.exc_data.get('message')}")
            lines.append(f"Endpoint: {self.exc_data.get('method')} {self.exc_data.get('endpoint')}")
            lines.append(f"Time: {self.exc_data.get('timestamp')}")
            lines.append("\nTraceback:")
            lines.append(self.exc_data.get("traceback_str", ""))
            
            text = "\n".join(lines)
            pyperclip.copy(text)
            self.notify("Exception details copied to clipboard!", title="Copied")
        except ImportError:
            self.notify("Please install 'pyperclip' to enable copying.", title="Error", severity="error")
        except Exception as e:
            self.notify(f"Failed to copy: {e}", title="Error", severity="error")


class VariableDetail(Static):
    """Detailed view of a single variable with expandable data."""
    
    DEFAULT_CSS = """
    VariableDetail {
        padding: 1;
        background: $surface;
        border: tall $primary;
        height: auto;
    }
    VariableDetail .var-header {
        text-style: bold;
        margin-bottom: 1;
    }
    """
    
    def __init__(self, var_data: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.var_data = var_data
    
    def compose(self):
        name = self.var_data.get("name", "?")
        type_name = self.var_data.get("type_name", "?")
        
        yield Static(f"[bold cyan]{name}[/]: [yellow]{type_name}[/]", classes="var-header")
        
        value_data = self.var_data.get("value_data")
        if value_data:
            yield from self._build_value_view(value_data)
        else:
            preview = self.var_data.get("value_preview", "")
            yield Static(f"[green]{preview}[/]")
    
    def _build_value_view(self, value_data: Dict[str, Any]):
        """Build view based on value type."""
        vtype = value_data.get("type", "unknown")
        
        if vtype == "dict":
            tree = Tree("Dictionary")
            tree.root.expand()
            for item in value_data.get("items", []):
                safe_key = str(item['key']).replace("[", "\\[")
                safe_val = str(item['value']).replace("[", "\\[")
                tree.root.add(f"[cyan]{safe_key}[/]: [green]{safe_val}[/] [dim]({item['type']})[/]")
            total = value_data.get("total", 0)
            if total > len(value_data.get("items", [])):
                tree.root.add(f"[dim]... and {total - len(value_data.get('items', []))} more[/]")
            yield tree
        
        elif vtype == "list":
            tree = Tree("List/Tuple")
            tree.root.expand()
            for item in value_data.get("items", []):
                safe_val = str(item['value']).replace("[", "\\[")
                tree.root.add(f"[dim]{item['index']}[/]: [green]{safe_val}[/] [dim]({item['type']})[/]")
            total = value_data.get("total", 0)
            if total > len(value_data.get("items", [])):
                tree.root.add(f"[dim]... and {total - len(value_data.get('items', []))} more[/]")
            yield tree
        
        elif vtype == "object":
            cls_name = value_data.get("class", "Object")
            tree = Tree(f"<{cls_name}>")
            tree.root.expand()
            for attr_name, attr_info in value_data.get("attributes", {}).items():
                safe_attr = str(attr_name).replace("[", "\\[")
                safe_val = str(attr_info['value']).replace("[", "\\[")
                tree.root.add(f"[cyan]{safe_attr}[/]: [green]{safe_val}[/] [dim]({attr_info['type']})[/]")
            yield tree
        
        elif vtype == "pydantic":
            yield Static("[bold]Pydantic Model[/]")
            tree = Tree("Fields")
            tree.root.expand()
            for k, v in value_data.get("data", {}).items():
                safe_k = str(k).replace("[", "\\[")
                safe_v = str(v).replace("[", "\\[")
                tree.root.add(f"[cyan]{safe_k}[/]: [green]{safe_v}[/]")
            yield tree
        
        elif vtype == "set":
            yield Static(f"Set with {value_data.get('total', 0)} items:")
            items = value_data.get("items", [])
            yield Static(f"[green]{', '.join(items)}[/]")


class FrameButton(Button):
    """Clickable button for stack frame."""
    
    DEFAULT_CSS = """
    FrameButton {
        width: 100%;
        height: auto;
        min-height: 2;
        background: transparent;
        border: none;
        text-align: left;
        padding: 0 1;
    }
    FrameButton:hover {
        background: $primary 20%;
    }
    FrameButton.selected {
        background: $accent;
    }
    FrameButton.error-frame {
        color: $error;
    }
    """


class VariableInspector(Container):
    """
    Interactive variable inspector for exception stack frames.
    Shows stack frames on left, variables on right.
    """
    
    DEFAULT_CSS = """
    VariableInspector {
        height: 100%;
        min-height: 20;
    }
    VariableInspector #frame-list-container {
        width: 35%;
        min-width: 30;
        border-right: tall $primary;
        height: 100%;
    }
    VariableInspector #variable-panel {
        width: 65%;
        padding: 0 1;
        height: 100%;
    }
    VariableInspector #var-table {
        height: auto;
        max-height: 50%;
        margin-bottom: 1;
    }
    VariableInspector #var-detail-container {
        height: auto;
        padding: 1;
        border-top: solid $primary;
    }
    """
    
    selected_frame_idx: reactive[int] = reactive(0)
    
    def __init__(self, exception_data: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.exception_data = exception_data
        self.frames = exception_data.get("frames", [])
    
    def compose(self):
        with Horizontal():
            # Left: Stack frames list (scrollable)
            with ScrollableContainer(id="frame-list-container"):
                yield Static("[bold]Stack Frames[/]", classes="section-header")
                for idx, frame in enumerate(self.frames):
                    is_last = idx == len(self.frames) - 1
                    filename = frame.get("filename", "?")
                    # Shorten filename
                    if len(filename) > 30:
                        filename = "..." + filename[-27:]
                    function = frame.get("function", "?")
                    lineno = frame.get("lineno", 0)
                    
                    prefix = "[red]→[/] " if is_last else "  "
                    label = f"{prefix}{filename}:{lineno}\n    [dim]in[/] [cyan]{function}[/]"
                    
                    btn = FrameButton(label, id=f"frame-{idx}")
                    if is_last:
                        btn.add_class("error-frame")
                    yield btn
            
            # Right: Variable details (scrollable)
            with ScrollableContainer(id="variable-panel"):
                yield Static("[bold]Variables[/]", classes="section-header")
                yield DataTable(id="var-table", cursor_type="row")
                yield ScrollableContainer(id="var-detail-container")
    
    def on_mount(self):
        # Setup variable table
        table = self.query_one("#var-table", DataTable)
        table.add_column("Name", key="name", width=15)
        table.add_column("Type", key="type", width=12)
        table.add_column("Value", key="value", width=40)
        table.add_column("", key="expand", width=2)
        
        # Show error frame (last one)
        if self.frames:
            self.selected_frame_idx = len(self.frames) - 1
    
    def watch_selected_frame_idx(self, old_idx: int, new_idx: int):
        self._show_frame_variables(new_idx)
        
        # Update frame highlighting
        for idx in range(len(self.frames)):
            try:
                frame_btn = self.query_one(f"#frame-{idx}", FrameButton)
                if idx == new_idx:
                    frame_btn.add_class("selected")
                else:
                    frame_btn.remove_class("selected")
            except Exception:
                pass
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle click on frame button."""
        button_id = event.button.id or ""
        if button_id.startswith("frame-"):
            try:
                idx = int(button_id.split("-")[1])
                self.selected_frame_idx = idx
            except (ValueError, IndexError):
                pass
    
    def _show_frame_variables(self, frame_idx: int):
        if frame_idx < 0 or frame_idx >= len(self.frames):
            return
        
        frame = self.frames[frame_idx]
        variables = frame.get("variables", [])
        
        # Update table
        table = self.query_one("#var-table", DataTable)
        table.clear()
        
        if not variables:
            # Fallback to locals_preview if variables list is empty (e.g. prod mode or old format)
            locals_preview = frame.get("locals_preview", {})
            for name, val in locals_preview.items():
                 safe_name = str(name).replace("[", "\\[")
                 safe_val = str(val).replace("[", "\\[")
                 table.add_row(
                    f"[cyan]{safe_name}[/]",
                    "[dim]?[/]",
                    f"[green]{safe_val}[/]",
                    "",
                    key=name
                )
        else:
            for var in variables:
                name = var.get("name", "?")
                type_name = var.get("type_name", "?")
                preview = var.get("value_preview", "")
                is_expand = var.get("is_expandable", False)
                is_sensitive = var.get("is_sensitive", False)
                
                # Format based on type
                if is_sensitive:
                    preview_styled = "[red]***MASKED***[/]"
                else:
                    safe_preview = str(preview).replace("[", "\\[")
                    preview_styled = f"[green]{safe_preview}[/]"
                
                expand_icon = "🔍" if is_expand else ""
                
                safe_name = str(name).replace("[", "\\[")
                table.add_row(
                    f"[cyan]{safe_name}[/]",
                    f"[yellow]{type_name}[/]",
                    preview_styled,
                    expand_icon,
                    key=name
                )
        
        # Clear detail container
        detail_container = self.query_one("#var-detail-container", ScrollableContainer)
        detail_container.remove_children()
    
    @on(DataTable.RowSelected, "#var-table")
    def on_variable_selected(self, event: DataTable.RowSelected):
        """Show expanded variable detail when row is selected."""
        if event.row_key is None:
            return
        
        var_name = str(event.row_key.value)
        frame = self.frames[self.selected_frame_idx]
        
        # Find the variable
        for var in frame.get("variables", []):
            if var.get("name") == var_name:
                if var.get("is_expandable") and not var.get("is_sensitive"):
                    self._show_variable_detail(var)
                break
    
    def _show_variable_detail(self, var_data: Dict[str, Any]):
        detail_container = self.query_one("#var-detail-container", ScrollableContainer)
        detail_container.remove_children()
        detail_container.mount(VariableDetail(var_data))


class ExceptionViewer(Container):
    """
    Exception list viewer for global exceptions tab.
    Shows list of recent exceptions with click-to-expand details.
    """
    
    exceptions: reactive[List[Dict[str, Any]]] = reactive([], always_update=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mounted = False
        self._selected_index = None
    
    def compose(self):
        yield DataTable(id="exceptions-table")
        yield ScrollableContainer(
            Static("[dim]Select an exception to view details[/]", id="exception-detail-placeholder"),
            id="exception-detail-container"
        )
    
    def on_mount(self):
        table = self.query_one("#exceptions-table", DataTable)
        table.cursor_type = "row"
        table.add_column("Time", key="time", width=10)
        table.add_column("Type", key="type", width=20)
        table.add_column("Endpoint", key="endpoint", width=30)
        table.add_column("Message", key="message", width=50)
        
        self._mounted = True
        self._refresh_table()
    
    def add_exception(self, exc_data: Dict[str, Any]):
        """Add a new exception to the list."""
        new_list = [exc_data] + self.exceptions[:99]  # Keep max 100
        self.exceptions = new_list
    
    def watch_exceptions(self, old_list, new_list):
        if self._mounted:
            self._refresh_table()
    
    def _refresh_table(self):
        table = self.query_one("#exceptions-table", DataTable)
        table.clear()
        
        for i, exc in enumerate(self.exceptions):
            timestamp = exc.get("timestamp", "")
            if isinstance(timestamp, str):
                # Parse ISO format
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    time_str = dt.strftime("%H:%M:%S")
                except:
                    time_str = timestamp[:8]
            elif isinstance(timestamp, datetime):
                time_str = timestamp.strftime("%H:%M:%S")
            else:
                time_str = "?"
            
            exc_type = exc.get("exception_type", "Unknown")[:18]
            endpoint = exc.get("endpoint", "?")[:28]
            message = exc.get("message", "")[:48]
            
            table.add_row(
                time_str,
                exc_type,
                endpoint,
                message,
                key=str(i)
            )
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        if event.data_table.id == "exceptions-table":
            try:
                index = int(event.row_key.value)
                if 0 <= index < len(self.exceptions):
                    exc = self.exceptions[index]
                    self._show_exception_detail(exc)
            except (ValueError, TypeError):
                pass
    
    def _show_exception_detail(self, exc: Dict[str, Any]):
        container = self.query_one("#exception-detail-container", ScrollableContainer)
        container.remove_children()
        container.mount(ExceptionDetail(exc))


class RequestExceptionView(Container):
    """
    Exception view for request inspector.
    Shows list of exceptions for the request, each with full details.
    """
    
    DEFAULT_CSS = """
    RequestExceptionView .jump-btn {
        width: auto;
        min-width: 30;
        height: 3;
        margin-bottom: 1;
        background: $primary;
        color: $text;
    }
    """

    def __init__(self, exceptions: List[Dict[str, Any]], **kwargs):
        super().__init__(**kwargs)
        self.exceptions = exceptions
    
    def compose(self):
        if not self.exceptions:
            yield Static("[dim green]✓ No exceptions occurred[/]")
            return

        yield Label(f"[bold red]⚠ {len(self.exceptions)} Exceptions Occurred[/]")
        
        for i, exc in enumerate(self.exceptions):
            with Collapsible(title=f"{i+1}. {exc.get('exception_type', 'Error')}: {exc.get('message', '')[:50]}", collapsed=(i > 0)):
                # Add button to jump to global tab
                yield Button("🔍 View in Global Exceptions Tab", id=f"jump-to-exc-{i}", classes="jump-btn")
                yield ExceptionDetail(exc)

    @on(Button.Pressed)
    def on_jump_button(self, event: Button.Pressed):
        """Handle jump button click."""
        if event.button.id and event.button.id.startswith("jump-to-exc-"):
            try:
                idx = int(event.button.id.split("-")[-1])
                if 0 <= idx < len(self.exceptions):
                    target_exc = self.exceptions[idx]
                    # Find main app and switch tab
                    app = self.app
                    try:
                        # Switch to Exceptions tab (ID is "tabs" in fastapi_tui.py)
                        tabbed = app.query_one("#tabs", TabbedContent)
                        tabbed.active = "exceptions-tab"
                        
                        # Try to find and select this exception in the global viewer
                        viewer = app.query_one("#exceptions-viewer", ExceptionViewer)
                        table = viewer.query_one("#exceptions-table", DataTable)
                        
                        # Simple matching by timestamp and message
                        target_ts = target_exc.get("timestamp")
                        target_msg = target_exc.get("message")
                        
                        for i, exc in enumerate(viewer.exceptions):
                            if exc.get("timestamp") == target_ts and exc.get("message") == target_msg:
                                # Found it! Select the row
                                row_key = str(i)
                                if table.is_valid_row_index(i):
                                    table.move_cursor(row=i)
                                    # Manually trigger selection logic since move_cursor doesn't always fire event
                                    viewer._show_exception_detail(exc)
                                break
                                
                    except Exception as e:
                        # Fallback: just switch tab
                        pass
            except Exception:
                pass