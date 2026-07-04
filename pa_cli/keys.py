"""
pa_cli.keys — API key registry + reminder system.

Two-layer design:
  - .env             holds ACTUAL secrets (gitignored, NEVER committed)
  - keys_registry.json  holds METADATA only: service name, env var, tier,
                       expiry date, last-check timestamp, last-used, notes.
                       Safe to commit — no secrets inside.

Usage from CLI:
  pa keys list          # show all keys + status (active / expiring / expired)
  pa keys check [name]  # live probe each key against its API endpoint
  pa keys add <service> <key> --expires YYYY-MM-DD --tier free|paid
  pa keys remind        # print expiry warnings (called automatically at CLI startup)
  pa keys audit         # last-used + last-checked per key

Reminder hook: pa_keys_remind() is invoked by main() before any subcommand.
It scans keys_registry.json + reads actual secret length from os.environ,
prints a single-line warning for any key <= 14 days to expiry (or already
expired). No exception, no exit — just stderr.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import quote
import urllib.request as ur
import urllib.error


REGISTRY_PATH = Path(__file__).parent.parent / "keys_registry.json"
ENV_PATH = Path(__file__).parent.parent / ".env"


def load_env_into_environ() -> int:
    """Parse .env file (KEY=VALUE per line) and set into os.environ if not
    already set. Does NOT override existing os.environ values.

    Returns count of env vars loaded.
    """
    if not ENV_PATH.exists():
        return 0
    count = 0
    try:
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$', line)
            if not m:
                continue
            key, value = m.group(1), m.group(2).strip()
            # Strip optional surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            if key not in os.environ:
                os.environ[key] = value
                count += 1
    except Exception:
        pass
    return count


# Default registry — committed as the canonical map of which keys
# this project knows about. Each entry is a "known slot"; actual presence
# depends on whether os.environ has the corresponding *_API_KEY env var.
DEFAULT_REGISTRY = {
    "openalex": {
        "name": "OpenAlex",
        "env_var": "OPENALEX_API_KEY",
        "service_url": "https://api.openalex.org/works?search=ai+literacy",
        "tier": "free",
        "expires": None,
        "notes": "OpenAlex API key for higher rate limit (1 RPS dedicated). Free tier, no expiry reported.",
        "last_checked": None,
        "last_used": None,
    },
    "semanticscholar": {
        "name": "Semantic Scholar",
        "env_var": "S2_API_KEY",
        "service_url": "https://api.semanticscholar.org/graph/v1/paper/search?query=test&limit=1",
        "tier": "free",
        "expires": None,
        "notes": "S2 API key for higher rate limit. Free tier, no expiry reported.",
        "last_checked": None,
        "last_used": None,
    },
    "core": {
        "name": "CORE.ac.uk",
        "env_var": "CORE_API_KEY",
        "service_url": "https://api.core.ac.uk/v3/search/works?q=test&limit=1",
        "tier": "free",
        "expires": None,
        "notes": "CORE v3 API key for higher rate limit. Free tier, no expiry reported.",
        "last_checked": None,
        "last_used": None,
    },
    "unpaywall": {
        "name": "Unpaywall",
        "env_var": "UNPAYWALL_EMAIL",
        "service_url": "https://api.unpaywall.org/v2/10.1038/nature12373?email={email}",
        "tier": "free",
        "expires": None,
        "notes": "Unpaywall uses a registered email instead of an API key. Free, no expiry.",
        "last_checked": None,
        "last_used": None,
    },
}


# =============== Registry I/O ===============

def load_registry() -> Dict[str, Any]:
    """Load keys_registry.json, fall back to DEFAULT_REGISTRY if missing."""
    if not REGISTRY_PATH.exists():
        return dict(DEFAULT_REGISTRY)
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_REGISTRY)


def save_registry(registry: Dict[str, Any]) -> str:
    """Write registry to disk (atomic write)."""
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    return str(REGISTRY_PATH)


def init_registry() -> str:
    """Create keys_registry.json from DEFAULT_REGISTRY if not present."""
    if not REGISTRY_PATH.exists():
        return save_registry(DEFAULT_REGISTRY)
    return str(REGISTRY_PATH)


# =============== Status computation ===============

def compute_status(svc: Dict[str, Any], env_value: Optional[str]) -> Dict[str, str]:
    """Return {status, days_to_expiry, hint} for one service."""
    if not env_value:
        return {"status": "missing", "days_to_expiry": "n/a",
                "hint": f"Set {svc['env_var']} in .env"}
    expires = svc.get("expires")
    if not expires:
        return {"status": "active", "days_to_expiry": "no-expiry",
                "hint": "no expiry set"}
    try:
        exp_date = date.fromisoformat(expires)
        days = (exp_date - date.today()).days
    except Exception:
        return {"status": "active", "days_to_expiry": "invalid-date",
                "hint": f"could not parse expires={expires!r}"}
    if days < 0:
        return {"status": "expired", "days_to_expiry": str(days),
                "hint": f"expired {-days} days ago, rotate now"}
    if days <= 1:
        return {"status": "expiring-today", "days_to_expiry": str(days),
                "hint": "expires within 24h, rotate today"}
    if days <= 7:
        return {"status": "expiring-week", "days_to_expiry": str(days),
                "hint": f"expires in {days} days, schedule rotation"}
    if days <= 14:
        return {"status": "expiring-soon", "days_to_expiry": str(days),
                "hint": f"expires in {days} days, plan rotation"}
    return {"status": "active", "days_to_expiry": str(days),
            "hint": f"expires in {days} days"}


# =============== List / audit ===============

def cmd_list() -> List[Dict[str, Any]]:
    """Return table rows for `pa keys list`."""
    reg = load_registry()
    rows = []
    for sid, svc in reg.items():
        env_value = os.environ.get(svc["env_var"])
        status = compute_status(svc, env_value)
        rows.append({
            "id": sid,
            "name": svc.get("name", sid),
            "env_var": svc["env_var"],
            "tier": svc.get("tier", "?"),
            "expires": svc.get("expires") or "(none)",
            "present": bool(env_value),
            "key_length": len(env_value) if env_value else 0,
            "status": status["status"],
            "days_to_expiry": status["days_to_expiry"],
            "hint": status["hint"],
            "last_checked": svc.get("last_checked"),
            "last_used": svc.get("last_used"),
            "notes": svc.get("notes", ""),
        })
    return rows


def cmd_audit() -> Dict[str, Any]:
    """Return audit summary: never-used, never-checked, etc."""
    rows = cmd_list()
    return {
        "total": len(rows),
        "active": sum(1 for r in rows if r["status"] == "active"),
        "expiring_soon": sum(1 for r in rows if "expiring" in r["status"]),
        "expired": sum(1 for r in rows if r["status"] == "expired"),
        "missing": sum(1 for r in rows if r["status"] == "missing"),
        "never_checked": [r["id"] for r in rows if not r["last_checked"]],
        "never_used": [r["id"] for r in rows if not r["last_used"]],
        "rows": rows,
    }


# =============== Check (live probe) ===============

def _probe(url: str, headers: dict = None, timeout: int = 15) -> tuple:
    """GET, return (status_code, response_snippet)."""
    h = {"User-Agent": "paper-agent/3.2 keys-check"}
    if headers:
        h.update(headers)
    req = ur.Request(url, headers=h)
    try:
        with ur.urlopen(req, timeout=timeout) as r:
            body = r.read()[:300].decode("utf-8", errors="ignore")
            return r.status, body[:200]
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read()[:200].decode("utf-8", errors="ignore")
        except Exception:
            return e.code, ""
    except Exception as e:
        return 0, str(e)[:200]


def cmd_check(service_id: Optional[str] = None) -> Dict[str, Any]:
    """Live probe each key (or one specific). Updates last_checked timestamp."""
    reg = load_registry()
    target = reg if service_id is None else {service_id: reg.get(service_id, {})}
    if not target:
        return {"error": f"unknown service: {service_id}",
                "available": list(reg.keys())}
    results = {}
    for sid, svc in target.items():
        env_value = os.environ.get(svc["env_var"])
        if not env_value:
            results[sid] = {"status": "missing",
                            "hint": f"set {svc['env_var']} in .env"}
            continue
        # Build probe URL with the key inline
        url = svc["service_url"]
        headers = {}
        if svc["env_var"] == "OPENALEX_API_KEY":
            url = url + "&api_key=" + quote(env_value)
        elif svc["env_var"] == "S2_API_KEY":
            headers["x-api-key"] = env_value
        elif svc["env_var"] == "CORE_API_KEY":
            headers["Authorization"] = f"Bearer {env_value}"
        elif svc["env_var"] == "UNPAYWALL_EMAIL":
            url = url.replace("{email}", quote(env_value))
        status_code, snippet = _probe(url, headers=headers)
        ok = status_code == 200
        results[sid] = {
            "status": "ok" if ok else f"http-{status_code}",
            "http_status": status_code,
            "snippet": snippet[:120],
            "env_var": svc["env_var"],
        }
        # Update last_checked timestamp
        svc["last_checked"] = datetime.now().isoformat(timespec="seconds")
    save_registry(reg)
    return results


# =============== Add / rotate ===============

def cmd_add(service_id: str, key_value: str, expires: Optional[str] = None,
            tier: str = "free", notes: Optional[str] = None) -> Dict[str, Any]:
    """Add a key to .env + update registry.

    Does NOT validate the key. Caller should run `pa keys check` after.
    Does NOT rotate or delete existing key — caller is responsible for .env.
    """
    reg = load_registry()
    if service_id not in reg:
        reg[service_id] = {
            "name": service_id,
            "env_var": f"{service_id.upper()}_API_KEY",
            "service_url": "",
            "tier": tier,
            "expires": expires,
            "notes": notes or "",
            "last_checked": None,
            "last_used": None,
        }
    else:
        if expires:
            reg[service_id]["expires"] = expires
        if tier:
            reg[service_id]["tier"] = tier
        if notes:
            reg[service_id]["notes"] = notes
    reg[service_id]["last_checked"] = datetime.now().isoformat(timespec="seconds")
    save_registry(reg)

    # Also write/update .env
    env_var = reg[service_id]["env_var"]
    env_path = REGISTRY_PATH.parent / ".env"
    env_lines = []
    if env_path.exists():
        env_lines = env_path.read_text(encoding="utf-8").splitlines()
    # Remove existing line for this key
    env_lines = [l for l in env_lines if not l.startswith(f"{env_var}=")]
    env_lines.append(f"{env_var}={key_value}")
    env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    # Mirror to current process env so subsequent commands see it
    os.environ[env_var] = key_value

    return {"service_id": service_id, "env_var": env_var,
            "registry_path": str(REGISTRY_PATH),
            "env_path": str(env_path),
            "expires": expires, "tier": tier}


# =============== Reminder hook ===============

def cmd_remind(quiet: bool = False) -> Dict[str, Any]:
    """Scan registry + return all warnings; used by main() at startup."""
    rows = cmd_list()
    warnings = []
    for r in rows:
        s = r["status"]
        if s in ("expired", "expiring-today", "expiring-week", "expiring-soon",
                 "missing"):
            warnings.append({
                "id": r["id"],
                "name": r["name"],
                "env_var": r["env_var"],
                "status": s,
                "expires": r["expires"],
                "days_to_expiry": r["days_to_expiry"],
                "hint": r["hint"],
                "reminder_message": _format_reminder(r),
            })
    if not quiet and warnings:
        for w in warnings:
            sys.stderr.write("[pa-keys] " + w["reminder_message"] + "\n")
    return {"warnings": warnings, "checked_at": datetime.now().isoformat(timespec="seconds")}


def _format_reminder(r: Dict[str, Any]) -> str:
    """Human-readable reminder line."""
    s = r["status"]
    name = r["name"]
    env_var = r["env_var"]
    if s == "missing":
        return f"⚠  {name}: {env_var} not set in .env (run `pa keys add {r['id']} <key>`)"
    if s == "expired":
        return f"❌  {name}: EXPIRED ({r['days_to_expiry']} days ago) — rotate now → `pa keys add {r['id']} <new_key>`"
    if s == "expiring-today":
        return f"🚨  {name}: EXPIRES TODAY — rotate immediately → `pa keys add {r['id']} <new_key>`"
    if s == "expiring-week":
        return f"⚠  {name}: expires in {r['days_to_expiry']} days — schedule rotation → `pa keys add {r['id']} <new_key>`"
    if s == "expiring-soon":
        return f"⏰  {name}: expires in {r['days_to_expiry']} days (within 14-day window) — plan rotation"
    return f"?  {name}: {s}"


def write_alerts_to_state(alerts_path: Optional[Path] = None) -> str:
    """Write current reminders to mavis state file (cross-session alerts)."""
    alerts = cmd_remind(quiet=True)
    if alerts_path is None:
        alerts_path = Path(os.environ.get("MAVIS_DATA_DIR", str(Path.home() / ".mavis"))) \
            / "state" / "api_key_alerts.json"
    alerts_path.parent.mkdir(parents=True, exist_ok=True)
    alerts_path.write_text(json.dumps(alerts, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    return str(alerts_path)