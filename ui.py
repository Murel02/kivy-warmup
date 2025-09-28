# ui.py

from kivy.uix.boxlayout import BoxLayout
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.popup import Popup
import threading


class HueTile(BoxLayout):
    """
    Base widget for controlling a Hue light or room.
    Subclasses must override the three _call_api_* methods.
    """

    item_id = NumericProperty(0)
    item_name = StringProperty("")
    is_on = BooleanProperty(False)
    brightness = NumericProperty(0)
    supports_color = BooleanProperty(False)

    _bri_job = None

    def _apply_state_label(self):
        """Update the state and name labels in kv (subclasses may override)."""
        self.ids.state_lbl.text = "ON" if self.is_on else "OFF"
        self.ids.name_lbl.text = self.item_name
        self.ids.color_btn.disabled = not self.supports_color

    # API hooks to be implemented by subclasses
    def _call_api_toggle(self, new_state: bool):
        raise NotImplementedError

    def _call_api_brightness(self, brightness: int):
        raise NotImplementedError

    def _call_api_color(self, hue_deg: float, sat_pct: float):
        raise NotImplementedError

    def toggle(self):
        """Toggle the on/off state."""
        target_state = not self.is_on

        def work():
            try:
                self._call_api_toggle(target_state)
                Clock.schedule_once(lambda *_: self._set_on(target_state))
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup("Hue Error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _set_on(self, on: bool):
        self.is_on = bool(on)
        self._apply_state_label()

    def _popup(self, title: str, text: str):
        Popup(title=title, content=Label(text=text), size_hint=(0.7, 0.5)).open()

    def on_kv_post(self, *_):
        # Called after kv is applied – ensure labels/buttons reflect initial state
        self._apply_state_label()

    def on_slider_change(self, val):
        """Handle slider movement and schedule brightness commit."""
        self.brightness = int(val)
        if self._bri_job:
            self._bri_job.cancel()
        self._bri_job = Clock.schedule_once(lambda dt: self._commit_brightness(), 0.35)

    def on_slider_release(self, instance, touch):
        """Commit brightness immediately on touch release."""
        if instance.collide_point(*touch.pos):
            if self._bri_job:
                self._bri_job.cancel()
            self._commit_brightness()

    def _commit_brightness(self):
        percent = int(self.brightness)

        def work():
            try:
                self._call_api_brightness(percent)
                Clock.schedule_once(lambda *_: self._set_on(percent > 0))
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup("Hue Error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def open_color_picker(self):
        """Show a simple preset colour selection dialog."""
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
            title=f"Color · {self.item_name}", type="custom", content_cls=grid
        )
        dlg["ref"] = dialog
        dialog.open()

    def _commit_color(self, hue_deg, sat_pct):
        def work():
            try:
                self._call_api_color(hue_deg, sat_pct)
                Clock.schedule_once(lambda *_: self._set_on(True))
            except Exception as e:
                Clock.schedule_once(lambda *_: self._popup("Hue Error", str(e)))

        threading.Thread(target=work, daemon=True).start()


from .hue import (
    set_on,
    set_brightness,
    set_color_hs,
    set_room_on,
    set_room_brightness,
    set_room_color_hs,
)


class LightTile(HueTile):
    """Tile widget representing a single light."""

    def _call_api_toggle(self, new_state: bool):
        set_on(int(self.item_id), new_state)

    def _call_api_brightness(self, brightness: int):
        set_brightness(int(self.item_id), brightness)

    def _call_api_color(self, hue_deg: float, sat_pct: float):
        set_color_hs(int(self.item_id), hue_deg, sat_pct)


class RoomTile(HueTile):
    """Tile widget representing a room group."""

    def _call_api_toggle(self, new_state: bool):
        set_room_on(int(self.item_id), new_state)

    def _call_api_brightness(self, brightness: int):
        set_room_brightness(int(self.item_id), brightness)

    def _call_api_color(self, hue_deg: float, sat_pct: float):
        set_room_color_hs(int(self.item_id), hue_deg, sat_pct)
