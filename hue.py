import json, os, requests
from pathlib import Path

CONFIG_PATH = Path("hue_config.json")
_session = requests.Session()  # shared session = less overhead


def save_config(bridge_ip: str, username: str):
    CONFIG_PATH.write_text(json.dumps({"bridge_ip": bridge_ip, "username": username}))


def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    ip = os.getenv("HUE_BRIDGE_IP")
    user = os.getenv("HUE_USERNAME")
    if ip and user:
        return {"bridge_ip": ip, "username": user}
    raise RuntimeError(
        "Hue config missing. Run save_config() or set HUE_BRIDGE_IP/HUE_USERNAME."
    )


def _raise_if_error(resp_json):
    if isinstance(resp_json, list):
        for item in resp_json:
            if isinstance(item, dict) and "error" in item:
                err = item["error"]
                raise RuntimeError(
                    f"Hue error {err.get('type')}: {err.get('description')} ({err.get('address')})"
                )
    return resp_json


def list_lights_detailed():
    """
    Returns {id: {"name": str, "on": bool, "bri": 0-100, "supports_color": bool}} in ONE HTTP call.
    """
    cfg = load_config()
    url = f"http://{cfg['bridge_ip']}/api/{cfg['username']}/lights"
    data = _session.get(url, timeout=4).json()
    _raise_if_error(data)
    out = {}
    for lid, info in data.items():
        st = info.get("state", {})
        on = bool(st.get("on", False))
        bri_raw = st.get("bri", 254)
        bri = (
            int(round(bri_raw * 100 / 254))
            if isinstance(bri_raw, (int, float))
            else (100 if on else 0)
        )
        supports = ("hue" in st) or (st.get("colormode") in ("hs", "xy"))
        out[int(lid)] = {
            "name": info.get("name", f"Light {lid}"),
            "on": on,
            "bri": bri,
            "supports_color": supports,
        }
    return out


# --- Actions: no GETs here, caller provides desired state ---
def set_on(light_id: int, on: bool):
    cfg = load_config()
    url = f"http://{cfg['bridge_ip']}/api/{cfg['username']}/lights/{light_id}/state"
    data = _session.put(url, json={"on": bool(on)}, timeout=4).json()
    _raise_if_error(data)
    return data


def set_brightness(light_id: int, percent: int):
    pct = max(0, min(100, int(percent)))
    bri = max(1, min(254, int(round(pct * 254 / 100))))
    cfg = load_config()
    url = f"http://{cfg['bridge_ip']}/api/{cfg['username']}/lights/{light_id}/state"
    data = _session.put(url, json={"on": True, "bri": bri}, timeout=4).json()
    _raise_if_error(data)
    return data


def set_color_hs(light_id: int, hue_degrees: float, sat_percent: float):
    hue = int(round((hue_degrees % 360) * 65535 / 360.0))
    sat = int(round(max(0, min(100, sat_percent)) * 254 / 100.0))
    cfg = load_config()
    url = f"http://{cfg['bridge_ip']}/api/{cfg['username']}/lights/{light_id}/state"
    data = _session.put(
        url, json={"on": True, "hue": hue, "sat": sat}, timeout=4
    ).json()
    _raise_if_error(data)
    return data


# -------- Rooms (groups) --------
def list_rooms_detailed():
    """
    Returnerer {group_id: {name, on, bri(0-100), supports_color}} for alle 'Room'-grupper.
    Bruger ét HTTP-kald til /groups.
    """
    cfg = load_config()
    url = f"http://{cfg['bridge_ip']}/api/{cfg['username']}/groups"
    data = _session.get(url, timeout=4).json()
    _raise_if_error(data)
    out = {}
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


def set_room_on(group_id: int, on: bool):
    cfg = load_config()
    url = f"http://{cfg['bridge_ip']}/api/{cfg['username']}/groups/{group_id}/action"
    data = _session.put(url, json={"on": bool(on)}, timeout=4).json()
    _raise_if_error(data)
    return data


def set_room_brightness(group_id: int, percent: int):
    pct = max(0, min(100, int(percent)))
    bri = max(1, min(254, int(round(pct * 254 / 100))))
    cfg = load_config()
    url = f"http://{cfg['bridge_ip']}/api/{cfg['username']}/groups/{group_id}/action"
    data = _session.put(url, json={"on": True, "bri": bri}, timeout=4).json()
    _raise_if_error(data)
    return data


def set_room_color_hs(group_id: int, hue_degrees: float, sat_percent: float):
    hue = int(round((hue_degrees % 360) * 65535 / 360.0))
    sat = int(round(max(0, min(100, sat_percent)) * 254 / 100.0))
    cfg = load_config()
    url = f"http://{cfg['bridge_ip']}/api/{cfg['username']}/groups/{group_id}/action"
    data = _session.put(
        url, json={"on": True, "hue": hue, "sat": sat}, timeout=4
    ).json()
    _raise_if_error(data)
    return data
