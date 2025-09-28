"""
Hue API wrapper for controlling Philips Hue lights and rooms.

Functions:
    save_config(bridge_ip: str, username: str) -> None
    load_config() -> Dict[str, str]
    list_lights_detailed() -> Dict[int, Dict[str, Any]]
    set_on(light_id: int, on: bool) -> Any
    set_brightness(light_id: int, percent: int) -> Any
    set_color_hs(light_id: int, hue_degrees: float, sat_percent: float) -> Any
    list_rooms_detailed() -> Dict[int, Dict[str, Any]]
    set_room_on(group_id: int, on: bool) -> Any
    set_room_brightness(group_id: int, percent: int) -> Any
    set_room_color_hs(group_id: int, hue_degrees: float, sat_percent: float) -> Any
"""

import json
import os
from pathlib import Path
import requests
from typing import Dict, Any, List

CONFIG_PATH = Path("hue_config.json")
_session = requests.Session()


def save_config(bridge_ip: str, username: str) -> None:
    """Persist the Hue bridge IP and username to a local JSON file."""
    CONFIG_PATH.write_text(json.dumps({"bridge_ip": bridge_ip, "username": username}))


def load_config() -> Dict[str, str]:
    """
    Load the Hue bridge IP and username from `hue_config.json` if present,
    otherwise from environment variables HUE_BRIDGE_IP and HUE_USERNAME.

    Raises:
        RuntimeError: if neither source provides a valid configuration.
    """
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    ip = os.getenv("HUE_BRIDGE_IP")
    user = os.getenv("HUE_USERNAME")
    if ip and user:
        return {"bridge_ip": ip, "username": user}
    raise RuntimeError(
        "Hue configuration missing; run save_config() or set HUE_BRIDGE_IP/HUE_USERNAME"
    )


def _raise_if_error(resp_json: Any) -> Any:
    """Raise RuntimeError if the Hue API returned an error."""
    if isinstance(resp_json, list):
        for item in resp_json:
            if isinstance(item, dict) and "error" in item:
                err = item["error"]
                raise RuntimeError(
                    f"Hue error {err.get('type')}: {err.get('description')} ({err.get('address')})"
                )
    return resp_json


def _api_url(*parts) -> str:
    """Construct a Hue API URL from a sequence of path parts."""
    cfg = load_config()
    return f"http://{cfg['bridge_ip']}/api/{cfg['username']}/{'/'.join(str(p) for p in parts)}"


def list_lights_detailed() -> Dict[int, Dict[str, Any]]:
    """Return {id: {name, on, bri, supports_color}} for all lights."""
    data = _session.get(_api_url("lights"), timeout=4).json()
    _raise_if_error(data)
    out: Dict[int, Dict[str, Any]] = {}
    for lid, info in data.items():
        state = info.get("state", {})
        on = bool(state.get("on", False))
        bri_raw = state.get("bri", 254)
        bri = (
            int(round(bri_raw * 100 / 254))
            if isinstance(bri_raw, (int, float))
            else (100 if on else 0)
        )
        supports = ("hue" in state) or (state.get("colormode") in ("hs", "xy"))
        out[int(lid)] = {
            "name": info.get("name", f"Light {lid}"),
            "on": on,
            "bri": bri,
            "supports_color": supports,
        }
    return out


def set_on(light_id: int, on: bool) -> Any:
    """Turn a light on or off."""
    data = _session.put(
        _api_url("lights", light_id, "state"), json={"on": bool(on)}, timeout=4
    ).json()
    return _raise_if_error(data)


def set_brightness(light_id: int, percent: int) -> Any:
    """Set brightness for a light (0–100%). Zero brightness is treated as off."""
    pct = max(0, min(100, int(percent)))
    bri = max(1, min(254, int(round(pct * 254 / 100))))
    data = _session.put(
        _api_url("lights", light_id, "state"), json={"on": True, "bri": bri}, timeout=4
    ).json()
    return _raise_if_error(data)


def set_color_hs(light_id: int, hue_degrees: float, sat_percent: float) -> Any:
    """Set hue (degrees 0–359) and saturation (0–100%) for a light."""
    hue = int(round((hue_degrees % 360) * 65535 / 360.0))
    sat = int(round(max(0, min(100, sat_percent)) * 254 / 100.0))
    data = _session.put(
        _api_url("lights", light_id, "state"),
        json={"on": True, "hue": hue, "sat": sat},
        timeout=4,
    ).json()
    return _raise_if_error(data)


def list_rooms_detailed() -> Dict[int, Dict[str, Any]]:
    """Return {group_id: {name, on, bri, supports_color}} for all room groups."""
    data = _session.get(_api_url("groups"), timeout=4).json()
    _raise_if_error(data)
    out: Dict[int, Dict[str, Any]] = {}
    for gid, info in data.items():
        if info.get("type") != "Room":
            continue
        act = info.get("action", {})
        on = bool(act.get("on", False))
        bri_raw = act.get("bri", 254)
        bri = (
            int(round(bri_raw * 100 / 254))
            if isinstance(bri_raw, (int, float))
            else (100 if on else 0)
        )
        supports = ("hue" in act) or (act.get("colormode") in ("hs", "xy"))
        out[int(gid)] = {
            "name": info.get("name", f"Room {gid}"),
            "on": on,
            "bri": bri,
            "supports_color": supports,
        }
    return out


def set_room_on(group_id: int, on: bool) -> Any:
    """Turn a room group on or off."""
    data = _session.put(
        _api_url("groups", group_id, "action"), json={"on": bool(on)}, timeout=4
    ).json()
    return _raise_if_error(data)


def set_room_brightness(group_id: int, percent: int) -> Any:
    """Set brightness for a room group (0–100%)."""
    pct = max(0, min(100, int(percent)))
    bri = max(1, min(254, int(round(pct * 254 / 100))))
    data = _session.put(
        _api_url("groups", group_id, "action"), json={"on": True, "bri": bri}, timeout=4
    ).json()
    return _raise_if_error(data)


def set_room_color_hs(group_id: int, hue_degrees: float, sat_percent: float) -> Any:
    """Set hue and saturation for a room group."""
    hue = int(round((hue_degrees % 360) * 65535 / 360.0))
    sat = int(round(max(0, min(100, sat_percent)) * 254 / 100.0))
    data = _session.put(
        _api_url("groups", group_id, "action"),
        json={"on": True, "hue": hue, "sat": sat},
        timeout=4,
    ).json()
    return _raise_if_error(data)

def discover_bridges() -> List[str]:
    """
    Discover Hue bridges on the local network using the Phillips Hue discovery service.
    """
    try:
        resp = _session.get("https://discovery.meethue.com", timeout=5)
        data = resp.json()
        if isinstance (data, list):
            return [
                item.get("internalipaddress")
                for item in data
                if isinstance(item, dict) and item.get("internalipaddress")
            ]
        return []
    except Exception as e:
        raise RuntimeError(f"Bridge discovery failed: {e}") from e