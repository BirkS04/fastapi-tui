from textual.widgets import Log
from textual import events

# --- KORRIGIERTE KLASSE FÜR AUTO-SCROLL ---
class AutoScrollLog(Log):
    """
    Ein Log-Widget mit asymmetrischem, exponentiellem Auto-Scroll.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scroll_timer = None
        self._scroll_direction = 0
        self._current_speed = 1
        
        # --- KONFIGURATION ---
        self._top_zone_size = 3      # Oben kleiner Bereich (3 Zeilen)
        self._bottom_zone_size = 4   # Unten größerer Bereich (5 Zeilen)
        
        self._min_speed = 1          # Start-Geschwindigkeit
        self._max_speed = 8          # Maximale Geschwindigkeit (Turbo am Rand)
        self._exponent = 3.0         # Wie stark die Kurve ansteigt (2=Quadratisch, 3=Kubisch)

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if event.button == 1:
            height = self.size.height
            y = event.y
            
            # --- OBERE ZONE (kleiner) ---
            if y < self._top_zone_size:
                # Wenn Maus ausserhalb (negativ), dann volle Power (1.0)
                if y < 0:
                    raw_intensity = 1.0
                else:
                    # 0 am inneren Rand der Zone, 1 am äußeren Rand
                    raw_intensity = 1.0 - (y / self._top_zone_size)
                
                self._update_speed(raw_intensity)
                self._start_auto_scroll(-1)

            # --- UNTERE ZONE (größer) ---
            elif y >= height - self._bottom_zone_size:
                dist = (height - 1) - y
                # Wenn Maus ausserhalb (unterhalb), volle Power
                if dist < 0:
                    raw_intensity = 1.0
                else:
                    raw_intensity = 1.0 - (dist / self._bottom_zone_size)
                
                self._update_speed(raw_intensity)
                self._start_auto_scroll(1)

            else:
                self._stop_auto_scroll()
        else:
            self._stop_auto_scroll()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        self._stop_auto_scroll()

    def on_unmount(self) -> None:
        self._stop_auto_scroll()

    def _update_speed(self, raw_intensity: float) -> None:
        """
        Berechnet die Geschwindigkeit exponentiell.
        raw_intensity: 0.0 (Start der Zone) bis 1.0 (Rand)
        """
        # Exponentielle Kurve: (x ^ exponent)
        # Bei exponent 3: 0.5 input -> 0.125 output (sehr sanft)
        #                 0.9 input -> 0.729 output (zieht an)
        #                 1.0 input -> 1.0   output (vollgas)
        curve = raw_intensity ** self._exponent
        
        speed = self._min_speed + (self._max_speed - self._min_speed) * curve
        self._current_speed = int(round(speed))

    def _start_auto_scroll(self, direction: int) -> None:
        self._scroll_direction = direction
        if self._scroll_timer is None:
            self._scroll_timer = self.set_interval(0.05, self._perform_scroll)

    def _stop_auto_scroll(self) -> None:
        if self._scroll_timer:
            self._scroll_timer.stop()
            self._scroll_timer = None
        self._scroll_direction = 0
        self._current_speed = 1

    def _perform_scroll(self) -> None:
        if self._scroll_direction == -1:
            self.scroll_relative(y=-self._current_speed, animate=False)
        elif self._scroll_direction == 1:
            self.scroll_relative(y=self._current_speed, animate=False)
