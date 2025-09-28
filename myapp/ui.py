# ui.py

from kivy.uix.boxlayout import BoxLayout
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivymd.app import MDApp
from kivy.uix.colorpicker import ColorPicker
import colorsys
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
                Clock.schedule_once(
                    lambda *_: (
                        self._set_on(percent > 0),
                        MDApp.get_running_app().show_message(
                            f"{self.item_name} brightness set to {percent}%"
                        ),
                    )
                )
            except Exception as e:
                Clock.schedule_once(
                    lambda *_: MDApp.get_running_app().show_message(f"Error: {e}")
                )

        threading.Thread(target=work, daemon=True).start()

    def open_color_picker(self):
        """Show a simple preset colour selection popup."""
        if not self.supports_color:
            return

        from kivy.uix.popup import Popup
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.button import Button

        # Preset colours (Hue degrees and saturation percentages)
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

        # Create a grid of buttons
        grid = GridLayout(cols=3, spacing=10, padding=10, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        popup = Popup(
            title=f"Color · {self.item_name}",
            content=grid,
            size_hint=(0.8, 0.6),  # adjust as needed
            auto_dismiss=True,
        )

        def choose_color(h, s):
            def cb(*args):
                popup.dismiss()  # close the popup
                self._commit_color(h, s)  # apply the colour

            return cb

        for label, h, s in presets:
            btn = Button(
                text=label,
                size_hint=(1, None),
                height=40,
                on_release=choose_color(h, s),
            )
            grid.add_widget(btn)
            
        # custom colour button
        def open_custom_picker(*_) -> None:
            cp = ColorPicker()
            layout = BoxLayout(orientation="vertical")
            layout.add_widget(cp)
            btn_box = BoxLayout(size_hint_y=None, height=40, spacing=10, padding=10)
            ok_btn = Button(text="OK")
            cancel_btn = Button(text="Cancel")
            btn_box.add_widget(ok_btn)
            btn_box.add_widget(cancel_btn)
            layout.add_widget(btn_box)
            custom_popup = Popup(
                title=f"Choose colour for {self.item_name}",
                content=layout,
                size_hint=(0.9, 0.9),
                auto_dismiss=False,
            )

            def on_ok(*args) -> None:
                r, g, b = cp.color[:3]
                h, s, _ = colorsys.rgb_to_hsv(r, g, b)
                self._commit_color(h * 360.0, s * 100.0)
                custom_popup.dismiss()

            ok_btn.bind(on_release=on_ok)
            cancel_btn.bind(on_release=lambda *_: custom_popup.dismiss())
            custom_popup.open()

        custom_btn = Button(
            text="Custom",
            size_hint=(1, None),
            height=40,
            on_release=open_custom_picker,
        )
        grid.add_widget(custom_btn)

        popup.open()

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
