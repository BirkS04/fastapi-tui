import os
import sys
import time
import signal
import atexit
import threading
from multiprocessing import Queue as MPQueue
from typing import Optional, Callable, Any
import subprocess
from importlib import import_module # NEU: Für dynamischen Import
from .ipc import start_manager_server
from .config import get_config

class TUIRunner:
    def __init__(
        self,
        app: Optional[Any] = None,          # NEU: Direkte App-Instanz
        app_factory: Optional[Callable] = None,
        app_module: str = "app.main:app_for_reload",
        port: int = 8000,
        host: str = "0.0.0.0"
    ):
        self.app = app                      # NEU
        self.app_factory = app_factory
        self.app_module = app_module
        
        self.config = get_config()
        
        self.port = port if port != 8000 else self.config.port
        self.host = host if host != "0.0.0.0" else self.config.host
        
        self.queue = None
        self.manager = None
        self.api_process = None
        self.stop_event = threading.Event()
    
    def run(self, reload: bool = False) -> None:
        """Start the TUI with FastAPI backend"""
        self._setup_cleanup()
        
        reload = reload or self.config.reload
        
        # 1. STARTE IPC SERVER
        self.manager = start_manager_server()
        self.queue = self.manager.get_queue()
        
        self._print_banner(reload)
        
        # 2. Starte FastAPI
        if reload:
            self._start_api_with_reload()
        else:
            self._start_api_process()
        
        if self.config.enable_runtime_logs:
            self.log_thread = threading.Thread(target=self._monitor_process_output, daemon=True)
            self.log_thread.start()

        time.sleep(0.5)
        
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
        # ... (Code bleibt gleich wie vorher) ...
        if not self.api_process or not self.api_process.stdout:
            return

        while not self.stop_event.is_set() and self.api_process.poll() is None:
            try:
                line = self.api_process.stdout.readline()
                if not line:
                    break
                
                decoded_line = line.decode("utf-8", errors="replace").strip()
                if not decoded_line:
                    continue

                self.queue.put({
                    "type": "log",
                    "data": {
                        "level": self.config.log_level.value.upper(),
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
        # ... (Code bleibt gleich wie vorher) ...
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🚀 FastAPI TUI Monitor starting...")
        print(f"🔗 Server running on http://{self.host}:{self.port}")
        print(f"🔌 IPC Server active")
        if reload:
            print("🔄 Hot-reload enabled")
        if self.config.enable_persistence:
            print(f"💾 Persistence enabled ({self.config.db_path})")
        else: 
            print("💾 Persistence disabled")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    def _get_subprocess_env(self) -> dict:
        # ... (Code bleibt gleich wie vorher) ...
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["TUI_CONFIG_PAYLOAD"] = self.config.to_json_payload()
        return env

    def _start_api_process(self) -> None:
        # ... (Code bleibt gleich wie vorher) ...
        env = self._get_subprocess_env()
        cmd = [
            sys.executable, "-m", "uvicorn",
            self.app_module,
            "--host", self.host,
            "--port", str(self.port),
        ]
        self.api_process = subprocess.Popen(
            cmd, env=env, cwd=os.getcwd(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
    
    def _start_api_with_reload(self) -> None:
        # ... (Code bleibt gleich wie vorher) ...
        env = self._get_subprocess_env()
        cmd = [
            sys.executable, "-m", "uvicorn",
            self.app_module,
            "--host", self.host,
            "--port", str(self.port),
            "--reload",
        ]
        for reload_dir in self.config.reload_dirs:
            cmd.extend(["--reload-dir", reload_dir])
        
        self.api_process = subprocess.Popen(
            cmd, env=env, cwd=os.getcwd(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
    
    def _preload_endpoints(self) -> None:
        """
        Versucht die Routen zu laden. 
        Priorität: 
        1. Übergebene App-Instanz
        2. App Factory
        3. Dynamischer Import via app_module String
        """
        target_app = None
        
        # Strategie 1: Direkte Instanz
        if self.app:
            target_app = self.app
            
        # Strategie 2: Factory
        elif self.app_factory:
            try:
                target_app = self.app_factory()
            except Exception as e:
                print(f"[DEBUG] Factory failed: {e}")

        # Strategie 3: Dynamischer Import (Fallback)
        elif self.app_module:
            try:
                # z.B. "app.main:app" -> module="app.main", attr="app"
                module_path, app_name = self.app_module.split(":")
                mod = import_module(module_path)
                target_app = getattr(mod, app_name)
            except Exception as e:
                print(f"[DEBUG] Dynamic import failed for {self.app_module}: {e}")

        if not target_app:
            # print("[DEBUG] No app found for preload")
            return

        try:
            routes = []
            for route in target_app.routes:
                if hasattr(route, "path"):
                    routes.append({
                        "path": route.path,
                        "methods": list(getattr(route, "methods", []))
                    })
            
            self.queue.put({
                "type": "startup_routes",
                "data": routes
            })
        except Exception as e:
            print(f"[DEBUG] Error extracting routes: {e}")
    
    def _cleanup(self) -> None:
        # ... (Code bleibt gleich wie vorher) ...
        self.stop_event.set()
        if self.api_process:
            self.api_process.terminate()
            try:
                self.api_process.wait(timeout=1)
            except:
                self.api_process.kill()
        if self.manager:
            self.manager.shutdown()

def run_tui(
    app: Optional[Any] = None,          # NEU
    app_factory: Optional[Callable] = None,
    app_module: str = "app.main:app_for_reload",
    reload: bool = False,
    port: int = 8000,
    host: str = "0.0.0.0"
) -> None:
    runner = TUIRunner(
        app=app,                        # NEU
        app_factory=app_factory,
        app_module=app_module,
        port=port,
        host=host
    )
    runner.run(reload=reload)