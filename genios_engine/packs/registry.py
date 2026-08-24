from __future__ import annotations

import json

from sqlalchemy import text

from genios_engine.platform.db import get_engine

from .merge import merge_config
from .snapshot import canonical, snapshot_id


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
            # A (pack_id, version) is immutable.  `ON CONFLICT DO NOTHING` alone used to
            # silently accept different bytes under an already-published version, making
            # historical signals impossible to replay honestly.  The post-insert read is
            # safe under concurrency: PostgreSQL waits for the conflicting insert before
            # this SELECT can observe the winning row.
            held = c.execute(text(
                "select manifest, checksum from pack_registry "
                "where pack_id=:p and version=:v for update"),
                {"p": manifest["id"], "v": manifest["version"]}).first()
            held_manifest = held.manifest if isinstance(held.manifest, dict) \
                else json.loads(held.manifest)
            if held.checksum != checksum or canonical(held_manifest) != canonical(manifest):
                raise ValueError(
                    f"immutable pack version mismatch: {manifest['id']}@{manifest['version']}")
        return checksum

    def apply_to_tenant(self, org_id: str, pack_id: str, version: str,
                        state: str = "active") -> None:
        with self._engine.begin() as c:
            c.execute(text(
                "insert into tenant_packs (org_id, pack_id, version, state) "
                "values (:o, :p, :v, :s) on conflict (org_id, pack_id) do update set "
                "lvl3_config=case when tenant_packs.version=excluded.version "
                "then tenant_packs.lvl3_config else '{}'::jsonb end, "
                "version=excluded.version, state=excluded.state, "
                "authority_revision=tenant_packs.authority_revision+1, "
                "updated_at=clock_timestamp()"),
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
                "  authority_revision = authority_revision + 1, "
                "  updated_at = clock_timestamp() "
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

    def persist_effective_snapshot(self, org_id: str, pack_id: str, effective: dict,
                                   *, cause: str) -> str:
        """Persist and verify the exact effective bytes consumed by a reasoning run.

        Runtime-derived overlays (for example a tenant's observed P90 deal value) are part of the
        scoring configuration, not incidental metadata.  Giving those bytes their own snapshot
        prevents a run from claiming provenance from the earlier pre-overlay pack snapshot.
        """
        sid = snapshot_id(effective)
        with self._engine.begin() as c:
            c.execute(text(
                "insert into config_snapshots (snapshot_id, org_id, pack_id, effective, cause) "
                "values (:id, :o, :p, cast(:e as jsonb), :cause) "
                "on conflict do nothing"),
                {"id": sid, "o": org_id, "p": pack_id,
                 "e": json.dumps(effective, default=str), "cause": cause})
            held = c.execute(text(
                "select effective from config_snapshots "
                "where org_id=:o and snapshot_id=:id"),
                {"o": org_id, "id": sid}).first()
            if held is None:
                raise RuntimeError(
                    "tenant config snapshot was not persisted; apply migration "
                    "0025_config_snapshot_tenant_scope.sql")
            held_effective = held.effective if isinstance(held.effective, dict) \
                else json.loads(held.effective)
            if canonical(held_effective) != canonical(effective):
                raise RuntimeError(f"config snapshot hash collision for {org_id}:{sid}")
        return sid

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
                     "templates": manifest.get("templates", {}),   # L5 card templates
                     # The pack's OUTBOUND vocabulary — the fields and observation kinds it
                     # reasons over, and the hints L1 should gate on. sales_v1.py labels this
                     # block "L2 extraction whitelist ... domain vocabulary lives here, not in
                     # the engine", and dropping it here severed that contract: L1's domain
                     # hints stayed a hardcoded 8-keyword regex and L2's extraction prompt a
                     # module constant with no pack parameter, so a sales pack and a support
                     # pack produced byte-identical capture. A rule that reads `deal.status`
                     # while the extractor was never told the name is a dead rule by design.
                     "schema": manifest.get("schema", {}),
                     "capture": manifest.get("capture", {})}
        sid = self.persist_effective_snapshot(org_id, pack_id, effective, cause="pack_apply")
        return effective, sid
