"""CAMARA QoD 1.1.0 oturum durum makinesi (ağdan ve HTTP'den bağımsız saf mantık)."""
import uuid
from datetime import datetime, timezone
from typing import Callable

from qod.profiles import PROFILES
from qod.shaper import Shaper

ACTIVE_STATES = ("REQUESTED", "AVAILABLE")


class QodError(Exception):
    status = 400
    code = "INVALID_ARGUMENT"

    def __init__(self, message: str = ""):
        super().__init__(message or self.code)
        self.message = message or self.code


class InvalidArgument(QodError):
    pass


class DurationOutOfRange(QodError):
    code = "QUALITY_ON_DEMAND.DURATION_OUT_OF_RANGE"


class NotFound(QodError):
    status, code = 404, "NOT_FOUND"


class ConflictError(QodError):
    status, code = 409, "CONFLICT"


class ExtensionNotAllowed(QodError):
    status, code = 409, "QUALITY_ON_DEMAND.SESSION_EXTENSION_NOT_ALLOWED"


class MissingIdentifier(QodError):
    status, code = 422, "MISSING_IDENTIFIER"


class UnsupportedIdentifier(QodError):
    status, code = 422, "UNSUPPORTED_IDENTIFIER"


def _rfc3339(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def device_ip(device: dict | None) -> str:
    if not device:
        raise MissingIdentifier("The device cannot be identified.")
    v4 = device.get("ipv4Address") or {}
    ip = v4.get("publicAddress") or v4.get("privateAddress")
    if not ip:
        raise UnsupportedIdentifier("The identifier provided is not supported.")
    return ip


class SessionStore:
    def __init__(self, shaper: Shaper, clock: Callable[[], float], activation_delay_s: float = 1.0):
        self.shaper, self.clock, self.activation_delay_s = shaper, clock, activation_delay_s
        self.on_change: Callable[[dict], None] = lambda s: None
        self._s: dict[str, dict] = {}  # sessionId -> iç kayıt

    # --- dışa açık işlemler -------------------------------------------------
    def create(self, body: dict) -> dict:
        ip = device_ip(body.get("device"))
        server = (body.get("applicationServer") or {}).get("ipv4Address")
        if not server:
            raise InvalidArgument("applicationServer.ipv4Address is required")
        profile = PROFILES.get(body.get("qosProfile", ""))
        if profile is None:
            raise InvalidArgument("Unknown qosProfile")
        duration = body.get("duration")
        if not isinstance(duration, int) or not profile.min_duration_s <= duration <= profile.max_duration_s:
            raise DurationOutOfRange("The requested duration is out of the allowed range for the specific QoS profile")
        if any(r["ip"] == ip and r["qosStatus"] in ACTIVE_STATES for r in self._s.values()):
            raise ConflictError("Conflict with an existing session for the same device.")
        sid = str(uuid.uuid4())
        self._s[sid] = {
            "sessionId": sid, "ip": ip, "server": server, "profile": profile,
            "body": {k: body[k] for k in ("device", "applicationServer", "qosProfile", "sink") if k in body},
            "duration": duration, "qosStatus": "REQUESTED", "statusInfo": None,
            "requested": self.clock(), "started": None, "expires": None,
        }
        return self.get(sid)

    def get(self, sid: str) -> dict:
        r = self._s.get(sid)
        if r is None:
            raise NotFound("The specified resource is not found.")
        out = dict(r["body"])
        out.update(sessionId=sid, duration=r["duration"], qosStatus=r["qosStatus"])
        if r["started"] is not None:
            out["startedAt"] = _rfc3339(r["started"])
            out["expiresAt"] = _rfc3339(r["expires"])
        if r["statusInfo"]:
            out["statusInfo"] = r["statusInfo"]
        return out

    def expires_ts(self, sid: str) -> float | None:
        return self._s[sid]["expires"]

    def delete(self, sid: str) -> None:
        r = self._s.get(sid)
        if r is None:
            raise NotFound("The specified resource is not found.")
        if r["qosStatus"] == "AVAILABLE":
            self._end(r, "DELETE_REQUESTED", self.clock())
        del self._s[sid]

    def extend(self, sid: str, add_s: int) -> dict:
        r = self._s.get(sid)
        if r is None:
            raise NotFound("The specified resource is not found.")
        if r["qosStatus"] != "AVAILABLE":
            raise ExtensionNotAllowed(f"Extending the session duration is not allowed in the current state ({r['qosStatus']}).")
        if not isinstance(add_s, int) or add_s < 1:
            raise InvalidArgument("requestedAdditionalDuration must be a positive integer")
        r["duration"] = min(r["duration"] + add_s, r["profile"].max_duration_s)
        r["expires"] = r["started"] + r["duration"]
        return self.get(sid)

    def by_device(self, ip: str) -> list[dict]:
        return [self.get(sid) for sid, r in self._s.items() if r["ip"] == ip]

    def tick(self, now: float | None = None) -> None:
        now = self.clock() if now is None else now
        for r in list(self._s.values()):
            if r["qosStatus"] == "REQUESTED" and now >= r["requested"] + self.activation_delay_s:
                self.shaper.add_priority(r["sessionId"], r["ip"], r["server"], r["profile"].target_kbps)
                r.update(qosStatus="AVAILABLE", started=now, expires=now + r["duration"])
                self.on_change(self.get(r["sessionId"]))
            elif r["qosStatus"] == "AVAILABLE" and now >= r["expires"]:
                self._end(r, "DURATION_EXPIRED", now)

    # --- iç ------------------------------------------------------------------
    def _end(self, r: dict, reason: str, now: float) -> None:
        self.shaper.remove_priority(r["sessionId"])
        r.update(qosStatus="UNAVAILABLE", statusInfo=reason)
        if reason != "DURATION_EXPIRED":
            r["duration"] = max(1, int(now - r["started"]))
            r["expires"] = now
        self.on_change(self.get(r["sessionId"]))
