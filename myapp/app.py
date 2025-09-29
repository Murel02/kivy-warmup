from pathlib import Path
import threading
import time

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    StringProperty,
)
from kivy.uix.screenmanager import ScreenManager
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen

from .hue import (
    list_lights_detailed_for_room,  # <-- use room-aware lights fetch
    list_rooms_detailed,
    load_config,
    save_config,
    discover_bridges,
)

# Fullscreen for the 7" display
Window.fullscreen = "auto"


# ---------------------------
#        MAIN (ROOMS)
# ---------------------------


class MainScreen(MDScreen):
    current_time = StringProperty("")
    loading_rooms = BooleanProperty(False)

    rooms = ListProperty([])
    PAGE_SIZE = NumericProperty(12)
    rooms_page = NumericProperty(0)
    rooms_page_text = StringProperty("1/1")

    _initialized = BooleanProperty(False)
    _gen_rooms = NumericProperty(0)

    def on_pre_enter(self, *_):
        if not self._initialized:
            self._initialized = True
            Clock.schedule_interval(self.update_time, 1)
            self._tune_for_small_screen()
            Window.bind(size=lambda *_: self._tune_for_small_screen())
            Clock.schedule_once(lambda *_: self.fetch_rooms_async())

    def update_time(self, dt):
        self.current_time = time.strftime("%H:%M:%S")

    def _tune_for_small_screen(self):
        """Bigger room tiles on 800x480 by using fewer columns."""
        W, H = Window.size
        cols = 3 if W >= 760 else 2

        g = self.ids.get("rooms_grid")
        if g:
            per_grid_w = W - dp(8 * 2)  # container padding
            tile_w = (per_grid_w - dp(6) * (cols - 1)) / cols
            # compact height to avoid a big top gap
            tile_h = max(dp(120), min(dp(135), tile_w * 0.7))
            g.cols = cols
            g.col_default_width = tile_w
            g.row_default_height = tile_h

        rows = 2
        self.PAGE_SIZE = cols * rows
        self._refresh_page_label()

    def fetch_rooms_async(self):
        self.loading_rooms = True
        self._gen_rooms += 1
        gen = int(self._gen_rooms)

        def work():
            try:
                details = list_rooms_detailed()  # {id: {...}}
                items = []
                for rid, d in details.items():
                    items.append(
                        {
                            "id": int(rid),
                            "name": d.get("name", f"Room {rid}"),
                            "on": bool(d.get("on", False)),
                            "bri": int(d.get("bri", 0)),
                            "supports_color": bool(d.get("supports_color", False)),
                        }
                    )
                items.sort(key=lambda x: x["name"].lower())

                def assign():
                    if gen != self._gen_rooms:
                        return
                    self.rooms = items
                    self.rooms_page = 0
                    self.update_rooms_view()

                Clock.schedule_once(lambda *_: assign())
            except Exception as e:
                msg = f"Rooms error: {e}"
                Clock.schedule_once(lambda *_: self.show_message(msg, 3))
            finally:
                Clock.schedule_once(lambda *_: setattr(self, "loading_rooms", False))

        threading.Thread(target=work, daemon=True).start()

    def update_rooms_view(self):
        grid = self.ids.get("rooms_grid")
        if not grid:
            return
        grid.clear_widgets()
        start = self.rooms_page * self.PAGE_SIZE
        page = self.rooms[start : start + self.PAGE_SIZE]
        from .ui import RoomTile

        for r in page:
            grid.add_widget(
                RoomTile(
                    item_id=r["id"],
                    item_name=r["name"],
                    is_on=r["on"],
                    brightness=r["bri"],
                    supports_color=r["supports_color"],
                )
            )
        self._refresh_page_label()

    def page_rooms(self, delta: int):
        total_pages = max(1, (len(self.rooms) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.rooms_page = (self.rooms_page + delta) % total_pages
        self.update_rooms_view()

    def _refresh_page_label(self):
        total_pages = max(1, (len(self.rooms) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.rooms_page_text = f"{min(self.rooms_page + 1, total_pages)}/{total_pages}"

    def show_message(self, text, duration=2):
        status_lbl = self.ids.get("status_lbl")
        if not status_lbl:
            return
        status_lbl.text = text

        def clear_message(*_):
            if status_lbl.text == text:
                status_lbl.text = ""

        Clock.schedule_once(clear_message, duration)


# ---------------------------
#     ROOM LIGHTS SCREEN
# ---------------------------


class RoomLightsScreen(MDScreen):
    room_id = NumericProperty(-1)
    room_name = StringProperty("")
    loading = BooleanProperty(False)
    lights = ListProperty([])

    def set_room(self, rid: int, name: str):
        self.room_id = rid
        self.room_name = name

    def on_pre_enter(self, *_):
        self.fetch_lights_async()

    def go_back(self, *_):
        self.manager.current = "main"

    def fetch_lights_async(self):
        if self.room_id < 0:
            return
        self.loading = True

        def work():
            try:
                details = list_lights_detailed_for_room(self.room_id)
                items = []
                for lid, d in details.items():
                    items.append(
                        {
                            "id": int(lid),
                            "name": d.get("name", f"Light {lid}"),
                            "on": bool(d.get("on", False)),
                            "bri": int(d.get("bri", 0)),
                            "supports_color": bool(d.get("supports_color", False)),
                        }
                    )
                items.sort(key=lambda x: x["name"].lower())

                def assign():
                    self.lights = items
                    grid = self.ids.get("lights_grid")
                    if grid:
                        grid.clear_widgets()
                        from .ui import LightTile

                        for l in items:
                            grid.add_widget(
                                LightTile(
                                    item_id=l["id"],
                                    item_name=l["name"],
                                    is_on=l["on"],
                                    brightness=l["bri"],
                                    supports_color=l["supports_color"],
                                )
                            )

                Clock.schedule_once(lambda *_: assign())
            except Exception as e:
                msg = f"Lights error: {e}"
                Clock.schedule_once(
                    lambda *_: setattr(self.ids.status_lbl, "text", msg)
                )
            finally:
                Clock.schedule_once(lambda *_: setattr(self, "loading", False))

        threading.Thread(target=work, daemon=True).start()


# ---------------------------
#        SETTINGS
# ---------------------------


class SettingsScreen(MDScreen):
    bridge_ip = StringProperty("")
    username = StringProperty("")

    def go_back(self, *_):
        self.manager.current = "main"

    def on_pre_enter(self, *_):
        try:
            cfg = load_config()
            self.bridge_ip = cfg.get("bridge_ip", "")
            self.username = cfg.get("username", "")
        except Exception as e:
            print(f"Could not load Hue config: {e}")

    def discover(self) -> None:
        lbl = self.ids.status_lbl
        lbl.text = "Discovering Hue bridges…"
        btn = self.ids.get("btn_discover")
        if btn:
            btn.disabled = True

        def work():
            try:
                ips = discover_bridges(skip_cloud=True)
                if not ips:
                    ips = discover_bridges(skip_cloud=True)

                def assign():
                    if not ips:
                        lbl.text = "No Hue bridges found"
                        return
                    self.bridge_ip = ips[0]
                    lbl.text = "Bridge: " + ", ".join(ips)

                Clock.schedule_once(lambda *_: assign())
            except Exception as e:
                msg = f"Discover error: {e}"
                Clock.schedule_once(lambda *_: setattr(lbl, "text", msg))
            finally:
                if btn:
                    Clock.schedule_once(lambda *_: setattr(btn, "disabled", False))

        threading.Thread(target=work, daemon=True).start()

    def save(self):
        ip = self.bridge_ip.strip()
        user = self.username.strip()
        lbl = self.ids.get("status_lbl")
        if not ip:
            if lbl:
                lbl.text = "Bridge IP is required"
            return

        def work():
            try:
                if not user:
                    from .hue import create_user

                    if lbl:
                        Clock.schedule_once(
                            lambda *_: setattr(
                                lbl, "text", "Pairing… Press link button"
                            )
                        )
                    new_user = create_user(ip)
                    self.username = new_user
                    user_to_save = new_user
                else:
                    user_to_save = user

                save_config(ip, user_to_save)
                if lbl:
                    Clock.schedule_once(
                        lambda *_: setattr(lbl, "text", "Saved. Returning…")
                    )
                Clock.schedule_once(self.go_back, 1.0)
            except Exception as e:
                if lbl:
                    msg = f"Save error: {e}"
                    Clock.schedule_once(lambda *_: setattr(lbl, "text", msg))

        threading.Thread(target=work, daemon=True).start()


# ---------------------------
#           APP
# ---------------------------


class HueApp(MDApp):
    theme_color = [0.08, 0.08, 0.12, 1]
    on_color = [0.30, 0.50, 0.34, 1]
    off_color = [0.15, 0.16, 0.19, 1]

    def show_message(self, text, duration=2):
        if self.root:
            main = self.root.get_screen("main")
            if main:
                main.show_message(text, duration)

    def open_room(self, room_id: int, room_name: str):
        """Called from RoomTile chevron."""
        if not self.root:
            return
        rl = self.root.get_screen("room_lights")
        rl.set_room(room_id, room_name)
        rl.fetch_lights_async()
        self.root.current = "room_lights"

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.primary_hue = "500"

        Window.clearcolor = self.theme_color

        kv_path = Path(__file__).with_name("myapp.kv")
        Builder.load_file(str(kv_path))

        sm = ScreenManager()
        sm.add_widget(MainScreen(name="main"))
        sm.add_widget(RoomLightsScreen(name="room_lights"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm


if __name__ == "__main__":
    HueApp().run()
