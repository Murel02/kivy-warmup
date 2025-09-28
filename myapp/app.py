# app.py

from kivy.clock import Clock
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivymd.uix.screen import MDScreen
from kivy.uix.screenmanager import ScreenManager
from kivymd.app import MDApp
from kivy.core.window import Window
from kivy.lang import Builder
from pathlib import Path

from .hue import list_lights_detailed, list_rooms_detailed, load_config, save_config
from .ui import LightTile, RoomTile


class MainScreen(MDScreen):
    current_time = StringProperty("")
    loading_items = BooleanProperty(False)
    view = StringProperty("rooms")
    _gen = NumericProperty(0)
    _initialized = BooleanProperty(False)

    def switch_view(self, which: str):
        self.view = which
        self.fetch()

    def on_pre_enter(self):
        if not self._initialized:
            self._initialized = True
            Clock.schedule_once(lambda *_: self.fetch())
            Clock.schedule_interval(self.update_time, 1)
            self.update_columns(Window.size)
            Window.bind(size=lambda *_: self.update_columns(Window.size))

    def update_columns(self, size):
        """Adjust number of columns based on window width."""
        width, _ = size
        if width < 800:
            cols = 1
        elif width < 1200:
            cols = 2
        else:
            cols = 3
        grid = self.ids.get("item_grid")
        if grid:
            grid.cols = cols

    def on_leave(self):
        Clock.unschedule(self.update_time)

    def update_time(self, dt):
        import time

        self.current_time = time.strftime("%H:%M:%S")

    def fetch(self):
        self._gen += 1
        gen = int(self._gen)
        if self.view == "rooms":
            self.fetch_rooms_async(gen)
        else:
            self.fetch_lights_async(gen)

    def fetch_rooms_async(self, gen: int):
        if self.loading_items:
            return
        self.loading_items = True

        def work():
            try:
                details = list_rooms_detailed()

                def assign():
                    if gen != self._gen:
                        return
                    grid = self.ids.item_grid
                    grid.clear_widgets()
                    for rid, d in sorted(
                        details.items(), key=lambda kv: kv[1]["name"].lower()
                    ):
                        grid.add_widget(
                            RoomTile(
                                item_id=int(rid),
                                item_name=d["name"],
                                is_on=bool(d["on"]),
                                brightness=int(d["bri"]),
                                supports_color=bool(d["supports_color"]),
                            )
                        )

                Clock.schedule_once(lambda *_: assign())
            except Exception as e:
                Clock.schedule_once(lambda *_: self.show_error(str(e)))
            finally:
                Clock.schedule_once(lambda *_: setattr(self, "loading_items", False))

        import threading

        threading.Thread(target=work, daemon=True).start()

    def fetch_lights_async(self, gen: int):
        if self.loading_items:
            return
        self.loading_items = True

        def work():
            try:
                details = list_lights_detailed()

                def assign():
                    if gen != self._gen:
                        return
                    grid = self.ids.item_grid
                    grid.clear_widgets()
                    for lid, d in sorted(
                        details.items(), key=lambda kv: kv[1]["name"].lower()
                    ):
                        grid.add_widget(
                            LightTile(
                                item_id=int(lid),
                                item_name=d["name"],
                                is_on=bool(d["on"]),
                                brightness=int(d["bri"]),
                                supports_color=bool(d["supports_color"]),
                            )
                        )

                Clock.schedule_once(lambda *_: assign())
            except Exception as e:
                Clock.schedule_once(lambda *_: self.show_error(str(e)))
            finally:
                Clock.schedule_once(lambda *_: setattr(self, "loading_items", False))

        import threading

        threading.Thread(target=work, daemon=True).start()

    def show_error(self, message: str):
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label

        Popup(
            title="Hue Error",
            content=Label(text=message),
            size_hint=(0.7, 0.5),
        ).open()

    def show_message(self, text, duration=2):
        """Display a transient message at the bottom of the screen."""
        status_lbl = self.ids.get("status_lbl")
        if status_lbl:
            status_lbl.text = text

            def clear_message(*_):
                if status_lbl.text == text:
                    status_lbl.text = ""

            Clock.schedule_once(clear_message, duration)

    def open_settings(self):
        self.manager.current = "settings"


class SettingsScreen(MDScreen):
    """Screen for editing Hue bridge settings."""

    bridge_ip = StringProperty("")
    username = StringProperty("")

    def go_back(self, *_):
        self.manager.current = "main"

    def on_pre_enter(self):
        """Load existing settings when entering the screen."""
        try:
            cfg = load_config()
            self.bridge_ip = cfg.get("bridge_ip", "")
            self.username = cfg.get("username", "")
        except Exception as e:
            # If no config yet, leave fields blank
            print(f"Could not load Hue config: {e}")

    def save(self):
        """Save the entered settings to hue_config.json."""
        ip = self.bridge_ip.strip()
        user = self.username.strip()
        if not ip or not user:
            self.ids.status_lbl.text = "Bridge IP and username are required"
            return
        try:
            save_config(ip, user)
            self.ids.status_lbl.text = "Settings saved. Returning…"
            # Small delay before going back
            from kivy.clock import Clock

            Clock.schedule_once(self.go_back, 1.5)
        except Exception as e:
            self.ids.status_lbl.text = f"Error: {e}"


class HueApp(MDApp):
    theme_color = [0.08, 0.08, 0.12, 1]
    on_color = [0.30, 0.50, 0.34, 1]
    off_color = [0.15, 0.16, 0.19, 1]
    
    def show_message(self, text, duration=2):
        """Proxy method so tiles can display messages via the running app."""
        if self.root:
            main_screen = self.root.get_screen("main")
            if main_screen:
                main_screen.show_message(text, duration)

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.primary_hue = "500"

        def on_key(window, key, *_):
            # F11 toggles fullscreen
            if key == 293:
                Window.fullscreen = not Window.fullscreen

        Window.bind(on_key_down=on_key)
        Window.clearcolor = self.theme_color

        kv_path = Path(__file__).with_name("myapp.kv")
        Builder.load_file(str(kv_path))

        sm = ScreenManager()
        sm.add_widget(MainScreen(name="main"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm


if __name__ == "__main__":
    HueApp().run()
