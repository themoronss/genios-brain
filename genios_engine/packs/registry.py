from __future__ import annotations

import json

from sqlalchemy import text

from genios_engine.platform.db import get_engine

from .merge import merge_config
from .snapshot import snapshot_id


class PackRegistry:
    """D0 Registry Keeper + D3/D4 orchestration. Registers immutable pack versions, applies
    them per tenant, and produces the effective config (+ persisted snapshot) that L3 runs."""

    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def register(self, manifest: dict) -> str:
        checksum = snapshot_id(manifest)                 # content address
        with self._engine.begin() as c:
            c.execute(text(
                "insert into pack_registry (pack_id, version, manifest, checksum) "
                "values (:p, :v, cast(:m as jsonb), :cs) on conflict (pack_id, version) "
                "do nothing"),
                {"p": manifest["id"], "v": manifest["version"],
                 "m": json.dumps(manifest, default=str), "cs": checksum})
        return checksum

    def apply_to_tenant(self, org_id: str, pack_id: str, version: str,
                        state: str = "active") -> None:
        with self._engine.begin() as c:
            c.execute(text(
                "insert into tenant_packs (org_id, pack_id, version, state) "
                "values (:o, :p, :v, :s) on conflict (org_id, pack_id) do update set "
                "version=excluded.version, state=excluded.state, updated_at=now()"),
                {"o": org_id, "p": pack_id, "v": version, "s": state})

    def write_lvl3_offset(self, org_id: str, pack_id: str, rule_id: str, offset: int) -> bool:
        """L6 F4 — the ONLY calibration write path: set a per-rule score offset in lvl3_config,
        which the L4 merge overlays. Law 5: if the rule-offsets path is PINNED, reject + return
        False (the calibrator gets no private door). Bounded value is the caller's responsibility.

        ONE atomic statement, pin-guard in the WHERE. The old shape (read whole blob → mutate in
        Python → write whole blob) meant two concurrent calibration runs both read the same blob
        and the second write silently discarded the first — losing offsets for rules it never
        touched, i.e. corrupting tenant config, not just double-stepping one nudge."""
        with self._engine.begin() as c:
            res = c.execute(text(
                "update tenant_packs set lvl3_config = jsonb_set("
                "  jsonb_set(coalesce(lvl3_config, '{}'::jsonb), '{scoring_defaults}',"
                "            coalesce(lvl3_config->'scoring_defaults', '{}'::jsonb), true),"
                "  '{scoring_defaults,rule_offsets}',"
                "  coalesce(lvl3_config->'scoring_defaults'->'rule_offsets', '{}'::jsonb)"
                "    || jsonb_build_object(cast(:r as text), cast(:v as int)), true),"
                "  updated_at = now() "
                "where org_id=:o and pack_id=:p "
                "and not exists ("
                "  select 1 from jsonb_array_elements_text(coalesce(pins, '[]'::jsonb)) pe "
                "  where pe like 'scoring_defaults.rule_offsets%')"),
                {"r": rule_id, "v": int(offset), "o": org_id, "p": pack_id})
        return res.rowcount == 1                     # 0 → no such tenant pack, or pinned

    def _manifest(self, c, pack_id, version) -> dict | None:
        r = c.execute(text("select manifest from pack_registry where pack_id=:p and version=:v"),
                      {"p": pack_id, "v": version}).first()
        if r is None:
            return None
        return r.manifest if isinstance(r.manifest, dict) else json.loads(r.manifest)

    def effective(self, org_id: str, pack_id: str = "sales") -> tuple[dict | None, str | None]:
        """Merge LVL1/2/3 → effective config, persist the snapshot, return (config, id).
        None if the tenant has no pack applied (then L3 does nothing — no domain hardcoded)."""
        with self._engine.connect() as c:
            tp = c.execute(text("select version, lvl2_config, lvl3_config, pins, state "
                                "from tenant_packs where org_id=:o and pack_id=:p"),
                           {"o": org_id, "p": pack_id}).first()
            if tp is None or tp.state == "disabled":
                return None, None
            manifest = self._manifest(c, pack_id, tp.version)
        if manifest is None:
            return None, None
        lvl2 = tp.lvl2_config if isinstance(tp.lvl2_config, dict) else json.loads(tp.lvl2_config or "{}")
        lvl3 = tp.lvl3_config if isinstance(tp.lvl3_config, dict) else json.loads(tp.lvl3_config or "{}")
        pins = tp.pins if isinstance(tp.pins, list) else json.loads(tp.pins or "[]")
        eff_scoring = merge_config(manifest["scoring_defaults"],
                                   lvl2.get("scoring_defaults", {}),
                                   lvl3.get("scoring_defaults", {}), pins)
        effective = {"pack_id": pack_id, "version": tp.version, "state": tp.state,
                     "scoring": eff_scoring, "rules": manifest["rules"],
                     "plays": manifest.get("plays", {}),
                     "templates": manifest.get("templates", {})}   # L5 card templates
        sid = snapshot_id(effective)
        with self._engine.begin() as c:
            c.execute(text(
                "insert into config_snapshots (snapshot_id, org_id, pack_id, effective, cause) "
                "values (:id, :o, :p, cast(:e as jsonb), 'pack_apply') "
                "on conflict (snapshot_id) do nothing"),
                {"id": sid, "o": org_id, "p": pack_id,
                 "e": json.dumps(effective, default=str)})
        return effective, sid
