"""
JSON Viewer Widget - Smart collapsible JSON rendering
"""

from textual.widgets import Static, Tree
from textual.widget import Widget
from typing import Any, Dict, List, Union
import json


class JSONViewer(Static):
    """
    Smart JSON Viewer with two views:
    - Tree view: Collapsible with syntax highlighting
    - Text view: Selectable/copyable in AutoScrollLog
    """
    
    DEFAULT_CSS = """
    JSONViewer {
        height: auto;
        max-height: 30;
    }
    JSONViewer TabbedContent {
        height: auto;
    }
    JSONViewer TabPane {
        height: auto;
        max-height: 25;
    }
    JSONViewer Tree {
        height: auto;
        max-height: 20;
    }
    JSONViewer AutoScrollLog {
        height: auto;
        max-height: 20;
    }
    """
    
    def __init__(self, data: Union[Dict, List, Any], **kwargs):
        super().__init__(**kwargs)
        self.data = data
    
    def compose(self):
        """Creates tabbed view with Tree and Text modes"""
        from textual.widgets import TabbedContent, TabPane
        
        with TabbedContent():
            # Tab 1: Tree View (collapsible)
            with TabPane("🌳 Tree", id="json-tab-tree"):
                tree = Tree("JSON")
                tree.root.expand()
                self._build_tree(tree.root, self.data)
                yield tree
            
            # Tab 2: Text View (copyable)
            with TabPane("📋 Copy", id="json-tab-text"):
                from .auto_scroll_log import AutoScrollLog
                
                log = AutoScrollLog(highlight=True)
                try:
                    formatted = json.dumps(self.data, indent=2, ensure_ascii=False, default=str)
                except:
                    formatted = str(self.data)
                log.write(formatted)
                yield log
    
    def _build_tree(self, node, data, key=None):
        """Rekursiv Tree aufbauen"""
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    # Show preview info for collapsed objects/arrays
                    preview = self._get_preview(v)
                    safe_k = str(k).replace("[", r"\[")
                    child = node.add(f"[bold cyan]{safe_k}[/]: {preview}")
                    self._build_tree(child, v, k)
                else:
                    formatted_value = self._format_value(v)
                    safe_k = str(k).replace("[", r"\[")
                    node.add(f"[bold cyan]{safe_k}[/]: {formatted_value}", allow_expand=False)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    preview = self._get_preview(item)
                    child = node.add(f"[dim]{i}[/]: {preview}")
                    self._build_tree(child, item, i)
                else:
                    formatted_value = self._format_value(item)
                    node.add(f"[dim]{i}[/]: {formatted_value}", allow_expand=False)
        
        else:
            # Primitive value
            formatted_value = self._format_value(data)
            if key is not None:
                safe_key = str(key).replace("[", r"\[")
                node.add(f"[bold cyan]{safe_key}[/]: {formatted_value}", allow_expand=False)
            else:
                node.add(formatted_value, allow_expand=False)
    
    def _get_preview(self, value: Any) -> str:
        """Generates a preview string for collapsed objects/arrays"""
        if isinstance(value, dict):
            keys = list(value.keys())
            key_count = len(keys)
            # Show first 3 keys
            preview_keys = keys[:3]
            keys_str = ", ".join(f"[cyan]{str(k).replace('[', r'\[')}[/]" for k in preview_keys)
            if key_count > 3:
                keys_str += f", [dim]...+{key_count - 3}[/]"
            return f"[yellow]{{...}}[/] [dim]({key_count} keys: {keys_str})[/]"
        elif isinstance(value, list):
            return f"[yellow][[...]][/] [dim]({len(value)} items)[/]"
        return str(value).replace("[", r"\[")
    
    def _format_value(self, value: Any) -> str:
        """Formatiert einen Wert mit Syntax Highlighting"""
        if value is None:
            return "[dim italic]null[/]"
        elif isinstance(value, bool):
            return f"[yellow]{str(value).lower()}[/]"
        elif isinstance(value, (int, float)):
            return f"[magenta]{value}[/]"
        elif isinstance(value, str):
            # Escape markup characters
            clean = value.replace("[", r"\[")
            # Truncate long strings
            if len(clean) > 100:
                return f'[green]"{clean[:97]}..."[/]'
            return f'[green]"{clean}"[/]'
        else:
            val_str = str(value)
            clean = val_str.replace("[", r"\[")
            if len(clean) > 100:
                clean = clean[:97] + "..."
            return f"[white]{clean}[/]"


class RuntimeLogsViewer(Static):
    """
    Viewer for runtime logs with two views:
    - Tree view: Recursive collapsible with syntax highlighting
    - Text view: Selectable/copyable plain text in TextArea
    
    Supports Pydantic models via model_dump().
    """
    
    DEFAULT_CSS = """
    RuntimeLogsViewer {
        height: auto;
    }
    RuntimeLogsViewer TabbedContent {
        height: auto;
    }
    RuntimeLogsViewer TabPane {
        height: auto;
        max-height: 40;
    }
    RuntimeLogsViewer Tree {
        height: auto;
        max-height: 35;
    }
    RuntimeLogsViewer TextArea {
        height: auto;
        max-height: 35;
    }
    RuntimeLogsViewer .copy-btn {
        dock: top;
        margin-bottom: 1;
    }
    """
    
    def __init__(self, logs: List[Any], **kwargs):
        super().__init__(**kwargs)
        self.logs = logs
        self._converted_logs = None
    
    def _convert_to_serializable(self, obj: Any) -> Any:
        """Convert Pydantic models and other objects to serializable dicts"""
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        if hasattr(obj, 'dict'):
            return obj.dict()
        if hasattr(obj, '__dataclass_fields__'):
            import dataclasses
            return dataclasses.asdict(obj)
        if isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        return obj
    
    def _get_converted_logs(self) -> List[Any]:
        """Get logs with Pydantic/dataclass objects converted"""
        if self._converted_logs is None:
            self._converted_logs = [self._convert_to_serializable(log) for log in self.logs]
        return self._converted_logs
    
    def compose(self):
        """Creates tabbed view with Tree and Text modes"""
        from textual.widgets import TabbedContent, TabPane, Button, TextArea
        
        converted = self._get_converted_logs()
        
        with TabbedContent():
            # Tab 1: Tree View (collapsible)
            with TabPane("🌳 Tree View", id="tab-tree"):
                tree = Tree("📝 Runtime Logs", id="logs-tree")
                tree.root.expand()
                
                for i, log in enumerate(converted):
                    if isinstance(log, (dict, list)):
                        preview = self._get_preview(log)
                        child = tree.root.add(f"[bold blue]{i+1}.[/] {preview}")
                        self._build_tree(child, log)
                    else:
                        formatted = self._format_value(log)
                        tree.root.add(f"[bold blue]{i+1}.[/] {formatted}", allow_expand=False)
                
                yield tree
            
            # Tab 2: Text View (selectable/copyable)
            with TabPane("📋 Text View (Copy)", id="tab-text"):
                from .auto_scroll_log import AutoScrollLog
                
                log_widget = AutoScrollLog(id="logs-textarea", highlight=True)
                
                # Write logs to the widget
                for i, log in enumerate(converted):
                    if isinstance(log, (dict, list)):
                        try:
                            formatted = json.dumps(log, indent=2, ensure_ascii=False, default=str)
                        except:
                            formatted = str(log)
                        log_widget.write(f"--- Log {i+1} ---\n{formatted}\n\n")
                    else:
                        log_widget.write(f"--- Log {i+1} ---\n{log}\n\n")
                
                yield log_widget
    
    def _build_tree(self, node, data, key=None):
        """Recursively build tree nodes with syntax highlighting"""
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    preview = self._get_preview(v)
                    safe_k = str(k).replace("[", r"\[")
                    child = node.add(f"[bold cyan]{safe_k}[/]: {preview}")
                    self._build_tree(child, v, k)
                else:
                    formatted_value = self._format_value(v)
                    safe_k = str(k).replace("[", r"\[")
                    node.add(f"[bold cyan]{safe_k}[/]: {formatted_value}", allow_expand=False)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    preview = self._get_preview(item)
                    child = node.add(f"[dim]\\[{i}][/]: {preview}")
                    self._build_tree(child, item, i)
                else:
                    formatted_value = self._format_value(item)
                    node.add(f"[dim]\\[{i}][/]: {formatted_value}", allow_expand=False)
        
        else:
            formatted_value = self._format_value(data)
            if key is not None:
                safe_key = str(key).replace("[", r"\[")
                node.add(f"[bold cyan]{safe_key}[/]: {formatted_value}", allow_expand=False)
            else:
                node.add(formatted_value, allow_expand=False)
    
    def _get_preview(self, value: Any) -> str:
        """Generates a preview string for collapsed objects/arrays"""
        if isinstance(value, dict):
            keys = list(value.keys())[:3]
            key_str = ", ".join(f"[cyan]{str(k).replace('[', r'\[')}[/]" for k in keys)
            if len(value) > 3:
                key_str += f", [dim]...+{len(value) - 3}[/]"
            return f"[yellow]{{...}}[/] [dim]({len(value)} keys: {key_str})[/]"
        elif isinstance(value, list):
            return f"[yellow][[...]][/] [dim]({len(value)} items)[/]"
        return str(value).replace("[", r"\[")[:50]
    
    def _format_value(self, value: Any) -> str:
        """Formatiert einen Wert mit Syntax Highlighting"""
        if value is None:
            return "[dim italic]null[/]"
        elif isinstance(value, bool):
            return f"[yellow]{str(value).lower()}[/]"
        elif isinstance(value, (int, float)):
            return f"[magenta]{value}[/]"
        elif isinstance(value, str):
            clean = value.replace("[", r"\[")
            if len(clean) > 200:
                return f"[green]\"{clean[:200]}...\"[/]"
            return f"[green]\"{clean}\"[/]"
        else:
            # Fallback for other types (including bytes)
            val_str = str(value)
            # Escape markup characters
            clean = val_str.replace("[", r"\[")
            if len(clean) > 200:
                clean = clean[:200] + "..."
            return f"[white]{clean}[/]"
