"""In-memory doubles of `platform.devices.DeviceStore` and `platform.capture_policy.CaptureStore`
for the hermetic device-API tests (`tests/test_device_api.py`).

They apply the SAME pure decisions the Postgres stores apply — `poll_outcome`,
`decide_transition`, `seat_may_register`, the session/device row `device_ctx_from_row` reads —
so the hermetic lane exercises the real state machine and the real routes; the SQL itself is
exercised by `tests/test_device_api_pg.py` against a scratch database.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.platform import capture_policy as P
from genios_engine.platform import devices as D
from genios_engine.platform.auth import hash_key, seat_role
from genios_engine.platform.ids import new_id
from genios_engine.platform.sessions import SessionTokens, mint_access_token


def _now() -> datetime:
    return datetime.now(timezone.utc)


class World:
    """The rows both doubles read and write."""

    def __init__(self) -> None:
        self.orgs: dict[str, dict] = {}
        self.seats: dict[tuple[str, str], dict] = {}
        self.codes: dict[str, dict] = {}              # device_code_hash → row
        self.devices: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.policies: dict[str, dict] = {}
        self.seat_settings: dict[tuple[str, str], dict] = {}
        self.deltas: dict[tuple, dict] = {}
        self.leases: dict[tuple, dict] = {}
        self.presence_writes = 0

    def add_org(self, org_id: str, owner_email: str, plan_status: str = "active") -> None:
        self.orgs[org_id] = {"email": owner_email, "plan_status": plan_status}

    def add_seat(self, org_id: str, seat_id: str, email: str, role: str = "member",
                 active: bool = True) -> None:
        self.seats[(org_id, seat_id)] = {"email": email, "role": role, "active": active}

    def open(self, org_id: str, seat_id: str, device_id: str | None = None) -> SessionTokens:
        seat = self.seats[(org_id, seat_id)]
        role = seat_role(seat["email"], seat["role"], self.orgs[org_id]["email"])
        sid = new_id("ses")
        self.sessions[sid] = {"org_id": org_id, "seat_id": seat_id, "device_id": device_id,
                              "revoked_at": None, "expires_at": _now() + timedelta(days=30)}
        token = mint_access_token(org_id=org_id, seat_id=seat_id, email=seat["email"], role=role,
                                  session_id=sid)
        return SessionTokens(access_token=token, refresh_token="grt_" + sid, session_id=sid,
                             expires_in=3600, refresh_expires_in=86400, org_id=org_id,
                             seat_id=seat_id, email=seat["email"], role=role)

    def code_by_user_code(self, user_code: str) -> dict | None:
        h = hash_key(user_code)
        return next((r for r in self.codes.values() if r["user_code_hash"] == h), None)


class MemoryDeviceStore:
    def __init__(self, world: World) -> None:
        self.w = world

    def issue_code(self, *, device_name, platform, os_version, app_version, requested_ip,
                   now=None) -> D.IssuedCode:
        now = now or _now()
        user_code, device_code = D.new_user_code(), D.new_device_code()
        self.w.codes[hash_key(device_code)] = {
            "user_code_hash": hash_key(user_code), "org_id": None, "seat_id": None,
            "device_id": None, "device_name": device_name, "platform": platform,
            "os_version": os_version, "app_version": app_version, "requested_ip": requested_ip,
            "created_at": now, "expires_at": now + timedelta(seconds=D.CODE_TTL_SECONDS),
            "approved_at": None, "denied_at": None, "consumed_at": None, "last_polled_at": None}
        return D.IssuedCode(device_code=device_code, user_code=user_code)

    def exchange(self, device_code, *, now=None) -> D.Exchange:
        now = now or _now()
        row = self.w.codes.get(hash_key(device_code or ""))
        outcome = D.poll_outcome(row, now)
        if outcome in (D.AUTHORIZATION_PENDING, D.SLOW_DOWN):
            row["last_polled_at"] = now
            return D.Exchange(error=outcome)
        if outcome != D.APPROVED:
            return D.Exchange(error=outcome)
        seat = self.w.seats.get((row["org_id"], row["seat_id"]))
        seat_view = None if seat is None else {
            **seat, "plan_status": self.w.orgs[row["org_id"]]["plan_status"]}
        if not D.seat_may_register(seat_view):
            row["denied_at"] = now
            return D.Exchange(error=D.ACCESS_DENIED)
        self.w.devices.setdefault(row["device_id"], {
            "device_id": row["device_id"], "org_id": row["org_id"], "seat_id": row["seat_id"],
            "device_name": row["device_name"], "platform": row["platform"],
            "os_version": row["os_version"], "app_version": row["app_version"],
            "created_at": now, "last_seen_at": now, "revoked_at": None, "revoked_by": None})
        tokens = self.w.open(row["org_id"], row["seat_id"], device_id=row["device_id"])
        row["consumed_at"] = row["last_polled_at"] = now
        return D.Exchange(tokens=tokens, device_id=row["device_id"],
                          device_name=row["device_name"], platform=row["platform"])

    def get_code(self, user_code):
        return self.w.code_by_user_code(user_code)

    def decide(self, user_code, *, org_id, seat_id, approve, now=None) -> dict:
        row = self.w.code_by_user_code(user_code)
        updates, out = D.decide_transition(row, org_id=org_id, seat_id=seat_id, approve=approve,
                                           now=now or _now())
        if updates:
            row.update(updates)
        return out

    def list_devices(self, org_id, seat_id=None):
        out = []
        for d in self.w.devices.values():
            if d["org_id"] == org_id and (seat_id is None or d["seat_id"] == seat_id):
                seat = self.w.seats.get((org_id, d["seat_id"])) or {}
                out.append({**d, "seat_email": seat.get("email")})
        return out

    def device(self, org_id, device_id):
        d = self.w.devices.get(device_id)
        return dict(d) if d and d["org_id"] == org_id else None

    def revoke(self, org_id, device_id, *, revoked_by) -> bool:
        d = self.w.devices.get(device_id)
        if not d or d["org_id"] != org_id or d["revoked_at"] is not None:
            return False
        now = _now()
        d["revoked_at"], d["revoked_by"] = now, revoked_by
        for s in self.w.sessions.values():
            if s["org_id"] == org_id and s["device_id"] == device_id and s["revoked_at"] is None:
                s["revoked_at"] = now
        for k in [k for k in self.w.leases if k[0] == org_id and k[2] == device_id]:
            del self.w.leases[k]
        return True

    def session_row(self, org_id, session_id):
        s = self.w.sessions.get(session_id)
        if s is None or s["org_id"] != org_id:
            return None
        seat = self.w.seats.get((org_id, s["seat_id"]))
        org = self.w.orgs[org_id]
        dev = self.w.devices.get(s["device_id"]) if s["device_id"] else None
        dev = dev if dev and dev["org_id"] == org_id else None
        return {"seat_id": s["seat_id"], "device_id": s["device_id"],
                "revoked_at": s["revoked_at"], "expires_at": s["expires_at"],
                "seat_active": seat["active"] if seat else None,
                "email": seat["email"] if seat else None, "role": seat["role"] if seat else None,
                "org_email": org["email"], "plan_status": org["plan_status"],
                "device_seat_id": dev["seat_id"] if dev else None,
                "device_revoked_at": dev["revoked_at"] if dev else None,
                "device_exists": dev is not None}


class MemoryCaptureStore:
    def __init__(self, world: World) -> None:
        self.w = world

    def load(self, org_id, seat_id, device_id=None):
        p = self.w.policies.get(org_id)
        s = self.w.seat_settings.get((org_id, seat_id))
        row = {}
        if p:
            row.update({"p_enabled": p["enabled"], "allowed_apps": p["allowed_apps"],
                        "p_blocked_domains": p["blocked_domains"],
                        "generic_web_allowed": p["generic_web_allowed"],
                        "draft_assist_allowed": p["draft_assist_allowed"],
                        "retention_days": p["retention_days"],
                        "moments_display": p.get("moments_display", False)})
        if s:
            row.update({"s_enabled": s["enabled"], "draft_assist": s["draft_assist"],
                        "generic_web": s["generic_web"], "paused_until": s["paused_until"],
                        "blocked_apps": s["blocked_apps"],
                        "s_blocked_domains": s["blocked_domains"]})
        lease = self.w.leases.get((org_id, seat_id, device_id))
        return (P._org_from_row(row or None), P._seat_from_row(row or None),
                dict(lease) if lease else None)

    def catching_up(self, org_id, seat_id):
        return sum(1 for (o, *_), r in self.w.deltas.items()
                   if o == org_id and r.get("seat_id") == seat_id and r.get("status") == "deferred")

    def save_org_policy(self, org_id, changes, *, updated_by):
        p = self.w.policies.setdefault(org_id, {
            "enabled": False, "allowed_apps": list(P.DEFAULT_ALLOWED_APPS), "blocked_domains": [],
            "generic_web_allowed": True, "draft_assist_allowed": False, "retention_days": 90})
        p.update({k: v for k, v in changes.items() if v is not None})
        p["updated_by"] = updated_by

    def save_seat_settings(self, org_id, seat_id, changes):
        s = self.w.seat_settings.setdefault((org_id, seat_id), {
            "enabled": False, "draft_assist": False, "generic_web": True, "paused_until": None,
            "blocked_apps": [], "blocked_domains": []})
        for k, v in changes.items():
            if v is not None or k == "paused_until":
                s[k] = v

    def insert_deltas(self, rows, *, org_id, device_id, now):
        inserted = set()
        for r in rows:
            key = (org_id, device_id, r["session_key"], r["message_watermark"])
            if key not in self.w.deltas:
                self.w.deltas[key] = {**r, "org_id": org_id, "device_id": device_id,
                                      "received_at": now, "status": "held"}
                inserted.add((r["session_key"], r["message_watermark"]))
        if device_id in self.w.devices:
            self.w.devices[device_id]["last_seen_at"] = now
        return inserted

    def write_presence(self, *, org_id, seat_id, device_id, fields, now):
        self.w.presence_writes += 1
        self.w.leases[(org_id, seat_id, device_id)] = {**fields, "updated_at": now}
        if device_id in self.w.devices:
            self.w.devices[device_id]["last_seen_at"] = now
