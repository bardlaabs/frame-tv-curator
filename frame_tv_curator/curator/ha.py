"""Home Assistant access via the Supervisor proxy."""
import os, json, urllib.request, logging
log = logging.getLogger("ha")
BASE = os.environ.get("HA_URL", "http://supervisor/core/api")
TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN", "")

def _req(method, path, body=None):
    r = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=20) as f:
        t = f.read()
        return json.loads(t) if t else None

def get_state(entity, quiet=False):
    try:
        return _req("GET", f"/states/{entity}")
    except Exception as e:
        if not quiet:
            log.warning("get_state %s: %s", entity, e)
        return None

def states():
    return _req("GET", "/states") or []

def call(domain, service, data):
    return _req("POST", f"/services/{domain}/{service}", data)

def tv_info(entity):
    s = get_state(entity) or {}
    a = s.get("attributes", {})
    return {"state": s.get("state"), "art_mode": a.get("art_mode_status"), "ip": a.get("ip_address")}
