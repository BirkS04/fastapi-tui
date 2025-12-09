"""
TUI Runner
Handles TUI startup with optional hot-reload support.
"""

import os
import sys
import time
import signal
import atexit
import threading
from multiprocessing import Queue as MPQueue
from typing import Optional, Callable
import subprocess
from .ipc import start_manager_server

class TUIRunner:
    def __init__(
        self,
        app_factory: Optional[Callable] = None,
        app_module: str = "app.main:app_for_reload",
        port: int = 8000,
        host: str = "0.0.0.0"
    ):
        self.app_factory = app_factory
        self.app_module = app_module
        self.port = port
        self.host = host
        self.queue = None
        self.manager = None
        self.api_process = None
        self.stop_event = threading.Event()
    
    def run(self, reload: bool = False) -> None:
        """Start the TUI with FastAPI backend"""
        self._setup_cleanup()
        
        # 1. STARTE IPC SERVER
        self.manager = start_manager_server()
        self.queue = self.manager.get_queue()
        
        self._print_banner(reload)
        
        # 2. Starte FastAPI
        if reload:
            self._start_api_with_reload()
        else:
            self._start_api_process()
        
        # Starte den Stream-Reader Thread
        # Dieser fängt alles ab, was main.py nicht via IPC sendet (z.B. C-Level Errors)
        self.log_thread = threading.Thread(target=self._monitor_process_output, daemon=True)
        self.log_thread.start()

        time.sleep(0.5)
        
        # Pre-load endpoints
        self._preload_endpoints()
        
        # 3. Starte TUI
        try:
            from .fastapi_tui import FastAPITUI
            tui = FastAPITUI(event_queue=self.queue)
            tui.run()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()
    
    def _monitor_process_output(self):
        """Liest stdout/stderr vom Subprozess und sendet es an die TUI Queue"""
        if not self.api_process or not self.api_process.stdout:
            return

        while not self.stop_event.is_set() and self.api_process.poll() is None:
            try:
                # Wir lesen Zeile für Zeile vom Subprozess
                line = self.api_process.stdout.readline()
                if not line:
                    break
                
                decoded_line = line.decode("utf-8", errors="replace").strip()
                if not decoded_line:
                    continue

                # Filter: Wir wollen keine Logs doppelt.
                # Wenn main.py via IPC sendet, kommt es dort an.
                # Wenn uvicorn aber direkt printet (z.B. beim Start), fangen wir es hier.
                # Wir markieren diese Logs als "RAW", damit man sie unterscheiden kann.
                
                # Einfacher Filter: Wenn es wie ein JSON-Log aussieht oder vom IPC kommt, ignorieren.
                # Da wir hier stdout/stderr pipen, sehen wir nur das, was wirklich auf die Konsole geschrieben wird.
                
                self.queue.put({
                    "type": "log",
                    "data": {
                        "level": "INFO", # Default Level für Raw Output
                        "message": decoded_line,
                        "type": "RAW"
                    }
                })
            except Exception:
                break

    def _setup_cleanup(self) -> None:
        atexit.register(self._cleanup)
        signal.signal(signal.SIGTERM, lambda s, f: self._cleanup())
    
    def _print_banner(self, reload: bool) -> None:
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🚀 FastAPI TUI Monitor starting...")
        print(f"🔗 Server running on http://localhost:{self.port}")
        print(f"🔌 IPC Server active")
        if reload:
            print("🔄 Hot-reload enabled")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    def _start_api_process(self) -> None:
        """Start FastAPI in a subprocess without reload"""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        cmd = [
            sys.executable, "-m", "uvicorn",
            self.app_module,
            "--host", self.host,
            "--port", str(self.port),
        ]
        
        # WICHTIG: PIPE nutzen, damit nichts auf den Screen leakt!
        self.api_process = subprocess.Popen(
            cmd, 
            env=env, 
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT # Stderr auch nach Stdout leiten
        )
    
    def _start_api_with_reload(self) -> None:
        """Start FastAPI with uvicorn --reload"""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        cmd = [
            sys.executable, "-m", "uvicorn",
            self.app_module,
            "--host", self.host,
            "--port", str(self.port),
            "--reload",
            "--reload-dir", "app"
        ]
        
        # WICHTIG: PIPE nutzen, damit nichts auf den Screen leakt!
        self.api_process = subprocess.Popen(
            cmd,
            env=env,
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
    
    def _preload_endpoints(self) -> None:
        if not self.app_factory:
            return
        try:
            temp_app = self.app_factory(log_queue=None) 
            routes = []
            for route in temp_app.routes:
                if hasattr(route, "path"):
                    routes.append({
                        "path": route.path,
                        "methods": list(getattr(route, "methods", []))
                    })
            
            self.queue.put({
                "type": "startup_routes",
                "data": routes
            })
        except Exception:
            pass
    
    def _cleanup(self) -> None:
        self.stop_event.set()
        if self.api_process:
            self.api_process.terminate()
            try:
                # Gib dem Prozess kurz Zeit
                self.api_process.wait(timeout=1)
            except:
                self.api_process.kill()
        if self.manager:
            self.manager.shutdown()

def run_tui(
    app_factory: Optional[Callable] = None,
    app_module: str = "app.main:app_for_reload",
    reload: bool = False,
    port: int = 8000,
    host: str = "0.0.0.0"
) -> None:
    runner = TUIRunner(
        app_factory=app_factory,
        app_module=app_module,
        port=port,
        host=host
    )
    runner.run(reload=reload)