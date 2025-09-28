# ---- fullscreen via .env ----
import os
from kivy.config import Config

fs = os.getenv("KIVY_WINDOW_FULLSCREEN")
if fs:
    Config.set("graphics", "fullscreen", fs)

from kivy.core.window import Window


def _parse_fullscreen(v: str):
    v = v.strip().lower()
    if v in ("auto", "borderless"):
        return v
    return v in ("1", "true", "yes", "on")


if fs:
    Window.fullscreen = _parse_fullscreen(fs)
# ---- end fullscreen via .env ----

import time, threading
from kivy.clock import Clock
from kivy.properties import (
    BooleanProperty,
    NumericProperty,
    StringProperty,
    ListProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.button import MDButton


from hue import (
    list_lights_detailed,
    set_on,
    set_brightness,
    set_color_hs,
    list_rooms_detailed,
    set_room_on,
    set_room_brightness,
    set_room_color_hs,
)


# --------- LightTile ----------
class LightTile(BoxLayout):
    light_id = NumericProperty(0)
    light_name = StringProperty("")
    is_on = BooleanProperty(False)
    brightness = NumericProperty(0)
    supports_color = BooleanProperty(False)

    _bri_job = None

    def on_kv_post(self, *_):
        self.ids.name_lbl.text = self.light_name
        self._apply_state_label()
        self.ids.color_btn.disabled = not self.supports_color

    def _apply_state_label(self):
        self.ids.state_lbl.text = "ON" if self.is_on else "OFF"

    def toggle(self):
        lid = int(self.light_id)
        next_state = not self.is_on

        def work():
            try:
                set_on(lid, next_state)
                Clock.schedule_once(lambda *_: self._set_on(next_state))
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup("Hue Error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _set_on(self, on):
        self.is_on = bool(on)
        self._apply_state_label()

    def _popup(self, title, text):
        Popup(title=title, content=Label(text=text), size_hint=(0.7, 0.5)).open()

    def on_slider_change(self, val):
        self.brightness = int(val)
        if self._bri_job:
            self._bri_job.cancel()
        self._bri_job = Clock.schedule_once(lambda dt: self._commit_brightness(), 0.35)

    def on_slider_release(self, instance, touch):
        if instance.collide_point(*touch.pos):
            if self._bri_job:
                self._bri_job.cancel()
            self._commit_brightness()

    def _commit_brightness(self):
        lid = int(self.light_id)
        pct = int(self.brightness)

        def work():
            try:
                set_brightness(lid, pct)
                Clock.schedule_once(lambda *_: self._set_on(pct > 0))
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup("Hue Error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def open_color_picker(self):
        if not self.supports_color:
            return
        # Quick preset-dialog (billig og hurtig)
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.gridlayout import MDGridLayout
        from kivymd.uix.button import MDRaisedButton

        presets = [
            ("Warm", 30, 90),
            ("Neutral", 45, 40),
            ("Cool", 200, 60),
            ("Blue", 220, 80),
            ("Purple", 280, 85),
            ("Green", 110, 80),
            ("Red", 0, 90),
            ("Yellow", 55, 95),
        ]
        grid = MDGridLayout(cols=3, padding="8dp", spacing="8dp", adaptive_height=True)
        dlg = {"ref": None}

        def choose(h, s):
            def cb(*_):
                self._commit_color(h, s)
                if dlg["ref"]:
                    dlg["ref"].dismiss()

            return cb

        for label, h, s in presets:
            btn = MDRaisedButton(text=label, on_release=choose(h, s))
            grid.add_widget(btn)

        dialog = MDDialog(
            title=f"Color · {self.light_name}", type="custom", content_cls=grid
        )
        dlg["ref"] = dialog
        dialog.open()

    def _commit_color(self, hue_deg, sat_pct):
        lid = int(self.light_id)

        def work():
            try:
                set_color_hs(lid, hue_deg, sat_pct)
                Clock.schedule_once(lambda *_: self._set_on(True))
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup("Hue Error", str(e)))

        threading.Thread(target=work, daemon=True).start()


# --------- RoomTile ----------
class RoomTile(BoxLayout):
    room_id = NumericProperty(0)
    room_name = StringProperty("")
    is_on = BooleanProperty(False)
    brightness = NumericProperty(0)
    supports_color = BooleanProperty(False)

    _bri_job = None

    def on_kv_post(self, *_):
        self.ids.name_lbl.text = self.room_name
        self.ids.state_lbl.text = "ON" if self.is_on else "OFF"
        self.ids.color_btn.disabled = not self.supports_color

    def _apply_state_label(self):
        self.ids.state_lbl.text = "ON" if self.is_on else "OFF"

    def toggle(self):
        gid = int(self.room_id)
        next_state = not self.is_on

        def work():
            try:
                set_room_on(gid, next_state)
                Clock.schedule_once(lambda *_: self._set_on(next_state))
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup("Hue Error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _set_on(self, on):
        self.is_on = bool(on)
        self._apply_state_label()

    def _popup(self, title, text):
        Popup(title=title, content=Label(text=text), size_hint=(0.7, 0.5)).open()

    def on_slider_change(self, val):
        self.brightness = int(val)
        if self._bri_job:
            self._bri_job.cancel()
        self._bri_job = Clock.schedule_once(lambda dt: self._commit_brightness(), 0.35)

    def on_slider_release(self, instance, touch):
        if instance.collide_point(*touch.pos):
            if self._bri_job:
                self._bri_job.cancel()
            self._commit_brightness()

    def _commit_brightness(self):
        gid = int(self.room_id)
        pct = int(self.brightness)

        def work():
            try:
                set_room_brightness(gid, pct)
                Clock.schedule_once(lambda *_: self._set_on(pct > 0))
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup("Hue Error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def open_color_picker(self):
        if not self.supports_color:
            return
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.gridlayout import MDGridLayout
        from kivymd.uix.button import MDRaisedButton

        presets = [
            ("Warm", 30, 90),
            ("Neutral", 45, 40),
            ("Cool", 200, 60),
            ("Blue", 220, 80),
            ("Purple", 280, 85),
            ("Green", 110, 80),
            ("Red", 0, 90),
            ("Yellow", 55, 95),
        ]
        grid = MDGridLayout(cols=3, padding="8dp", spacing="8dp", adaptive_height=True)
        dlg = {"ref": None}

        def choose(h, s):
            def cb(*_):
                self._commit_color(h, s)
                if dlg["ref"]:
                    dlg["ref"].dismiss()

            return cb

        for label, h, s in presets:
            btn = MDRaisedButton(text=label, on_release=choose(h, s))
            grid.add_widget(btn)

        dialog = MDDialog(
            title=f"Color · {self.room_name}", type="custom", content_cls=grid
        )
        dlg["ref"] = dialog
        dialog.open()

    def _commit_color(self, hue_deg, sat_pct):
        gid = int(self.room_id)

        def work():
            try:
                set_room_color_hs(gid, hue_deg, sat_pct)
                Clock.schedule_once(lambda *_: self._set_on(True))
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup("Hue Error", str(e)))

        threading.Thread(target=work, daemon=True).start()


# --------- Screens ----------
class MainScreen(MDScreen):
    current_time = StringProperty("")
    loading_lights = BooleanProperty(False)
    view = StringProperty("rooms")  # "rooms" / "lights"

    _gen = NumericProperty(0)  # øger hver gang vi starter en fetch
    _inited = BooleanProperty(False)

    def switch_view(self, which):
        self.view = which
        self.fetch()

    def on_pre_enter(self):
        if not self._inited:
            self._inited = True
            Clock.schedule_once(lambda *_: self.fetch())
            Clock.schedule_interval(self.update_time, 1)

    def on_leave(self):
        Clock.unschedule(self.update_time)

    def update_time(self, dt):
        self.current_time = time.strftime("%H:%M:%S")

    def fetch(self):
        self._gen += 1
        gen = int(self._gen)
        if self.view == "rooms":
            self.fetch_rooms_async(gen)
        else:
            self.fetch_lights_async(gen)

    def fetch_rooms_async(self, gen):
        if self.loading_lights:
            return
        self.loading_lights = True

        def work():
            try:
                details = list_rooms_detailed()

                def assign():
                    # skip hvis en nyere fetch er startet
                    if gen != self._gen:
                        return
                    grid = self.ids.item_grid
                    grid.clear_widgets()
                    for gid, d in sorted(
                        details.items(), key=lambda kv: kv[1]["name"].lower()
                    ):
                        grid.add_widget(
                            RoomTile(
                                room_id=int(gid),
                                room_name=d["name"],
                                is_on=bool(d["on"]),
                                brightness=int(d["bri"]),
                                supports_color=bool(d["supports_color"]),
                            )
                        )

                Clock.schedule_once(lambda *_: assign())
            except Exception as e:
                Clock.schedule_once(
                    lambda *_: Popup(
                        title="Hue Error",
                        content=Label(text=str(e)),
                        size_hint=(0.7, 0.5),
                    ).open()
                )
            finally:
                Clock.schedule_once(lambda *_: setattr(self, "loading_lights", False))

        threading.Thread(target=work, daemon=True).start()


    def fetch_lights_async(self, gen):
        if self.loading_lights:
            return
        self.loading_lights = True

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
                                light_id=int(lid),
                                light_name=d["name"],
                                is_on=bool(d["on"]),
                                brightness=int(d["bri"]),
                                supports_color=bool(d["supports_color"]),
                            )
                        )

                Clock.schedule_once(lambda *_: assign())
            except Exception as e:
                Clock.schedule_once(
                    lambda *_: Popup(
                        title="Hue Error", content=Label(text=str(e)), size_hint=(0.7, 0.5)
                    ).open()
                )
            finally:
                Clock.schedule_once(lambda *_: setattr(self, "loading_lights", False))

        threading.Thread(target=work, daemon=True).start()


class SettingsScreen(MDScreen):
    pass


from pathlib import Path
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager


class MyApp(MDApp):
    theme_color = ListProperty([0.08, 0.08, 0.12, 1])
    on_color = ListProperty([0.30, 0.50, 0.34, 1])
    off_color = ListProperty([0.15, 0.16, 0.19, 1])

    def build(self):
        # Material theme
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        self.theme_cls.primary_hue = "500"

        # F11 toggler fullscreen
        def on_key(window, key, *_):
            if key == 293:
                Window.fullscreen = not Window.fullscreen

        Window.bind(on_key_down=on_key)

        Window.clearcolor = self.theme_color
        self.bind(
            theme_color=lambda *_: setattr(Window, "clearcolor", self.theme_color)
        )


        # Byg root
        sm = ScreenManager()
        ms = MainScreen(name="main")
        print("MainScreen created:", ms)
        sm.add_widget(ms)
        sm.add_widget(SettingsScreen(name="settings"))
        return sm


if __name__ == "__main__":
    MyApp().run()
