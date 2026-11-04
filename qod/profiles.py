"""Yerel QoD servisinin sunduğu QoS profilleri (CAMARA QoS Profiles 1.1.0 biçiminde)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    target_kbps: int
    min_duration_s: int = 5
    max_duration_s: int = 3600

    def to_camara(self) -> dict:
        rate = {"value": self.target_kbps, "unit": "kbps"}
        return {
            "name": self.name,
            "description": f"Video uplink önceliği, {self.target_kbps} kbps",
            "status": "ACTIVE",
            "targetMinUpstreamRate": rate,
            "maxUpstreamRate": rate,
            "minDuration": {"value": self.min_duration_s, "unit": "Seconds"},
            "maxDuration": {"value": self.max_duration_s, "unit": "Seconds"},
            "priority": 10,
        }


PROFILES: dict[str, Profile] = {
    p.name: p for p in (Profile("QOS_VIDEO_M", 1500), Profile("QOS_VIDEO_L", 2500))
}
