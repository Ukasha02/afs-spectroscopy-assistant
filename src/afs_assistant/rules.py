"""Deterministic pre-analysis (PRD §5 step 3). Pure Python, driven by kb/facts.yaml and the
method table. Nothing here is specific to any case: it only reacts to the extracted fields.

Outputs:
  table_shortlist   S01 Table 1 rows that fit the sample, ordered by cost (simplicity ladder)
  fiber_checks      which fiber families transmit each method's nominal range; conflicts with
                    fibers the client already has
  rule_hints        general rules whose trigger matches the extracted enquiry
"""

from afs_assistant.kb.load import load_chunks, load_facts
from afs_assistant.schema import ExtractedEnquiry

_COST_ORDER = {"low": 0, "average": 1, "high": 2}
_LAB_ONLY = ("cuvette", "integrating sphere", "sample layer")
_AT_DISTANCE = ("surface at a distance", "probe, lens")
_SILICA_ALIASES = {"SILICA_UNSPECIFIED": ("UV_SILICA", "VISNIR_SILICA")}


def _table_rows() -> list[dict]:
    rows = []
    for c in load_chunks():
        if c.source != "TABLE" or c.id == "TABLE:notes":
            continue
        fields = dict(part.split(": ", 1) for part in c.text.split("; ") if ": " in part)
        fields["row_id"] = c.id
        fields["label"] = f"{fields['method']} / {fields['measurement_technique']}"
        rows.append(fields)
    return rows


def table_shortlist(ex: ExtractedEnquiry) -> list[dict]:
    allowed = set(load_facts()["sample_state_map"].get(ex.sample_state, []))
    shortlist = []
    for row in _table_rows():
        sample_types = {s.strip() for s in row["sample_type"].split(",")}
        technique = row["measurement_technique"].lower()
        if ex.sample_state != "unknown" and not (sample_types & allowed):
            continue
        notes = []
        if any(k in technique for k in _LAB_ONLY):
            notes.append("lab/offline technique: use for lab screening, not in-line")
        if any(k in technique for k in _AT_DISTANCE):
            notes.append("non-contact measurement at a distance")
            if not (ex.remote_measurement or ex.contact_with_sample == "not_possible"):
                notes.append("only relevant if contact is a problem")
        if ex.sample_state == "unknown":
            notes.append("sample state unknown: all rows kept")
        shortlist.append(
            {
                "row": row["label"],
                "cite": "S01 Table 1 (p.6)",
                "sample_type": row["sample_type"],
                "optical_path_or_depth": row["optical_path_or_depth"],
                "sensitivity": row["sensitivity"],
                "selectivity": row["selectivity"],
                "cost": row["cost"],
                "notes": notes,
            }
        )
    shortlist.sort(key=lambda r: (_COST_ORDER.get(r["cost"], 3), "lab/offline" in " ".join(r["notes"])))
    return shortlist


def _coverage(method_range: list[float], fiber_range: list[float]) -> str:
    lo, hi = max(method_range[0], fiber_range[0]), min(method_range[1], fiber_range[1])
    if lo >= hi:
        return "none"
    if fiber_range[0] <= method_range[0] and fiber_range[1] >= method_range[1]:
        return "full"
    return f"partial ({lo:g}-{hi:g} um of {method_range[0]:g}-{method_range[1]:g} um)"


def fiber_checks(ex: ExtractedEnquiry) -> dict:
    facts = load_facts()
    fibers = {f["id"]: f for f in facts["fibers"]}
    per_method = {}
    for m in facts["methods"]:
        per_method[m["id"]] = {
            "nominal_range": f"{m['range_display']} [{m['range_src']}]",
            "fibers": {fid: _coverage(m["range_um"], f["range_um"]) for fid, f in fibers.items()},
        }
    conflicts = []
    for mentioned in ex.fibers_mentioned:
        for fid in _SILICA_ALIASES.get(mentioned, (mentioned,)):
            if fid not in fibers:
                continue
            for mid in ex.methods_mentioned:
                cov = per_method[mid]["fibers"][fid]
                if cov != "full":
                    conflicts.append(
                        f"Client fiber {fibers[fid]['name']} ({fibers[fid]['range_um'][0]}-{fibers[fid]['range_um'][1]} um "
                        f"[{fibers[fid]['src']}]) vs {mid} nominal range {per_method[mid]['nominal_range']}: coverage {cov}"
                    )
    return {"per_method": per_method, "client_fiber_conflicts": conflicts}


def rule_hints(ex: ExtractedEnquiry) -> list[str]:
    hits = {"do_not_invent", "nominal_range_not_instrument_range"}
    if "FLUO" in ex.methods_mentioned:
        hits |= {"fluorescence_needs_fluorophore", "sensitivity_not_selectivity"}
    if "RAMAN" in ex.methods_mentioned:
        hits.add("raman_fluorescence_background")
    if len(ex.methods_mentioned) > 1:
        hits.add("combination_is_hypothesis")
    if ex.fibers_mentioned or ex.remote_measurement or "MIR" in ex.methods_mentioned:
        hits |= {"fiber_limits_wavelength", "remote_measurement_nir_silica"}
    if ex.process_context == "clinical_or_medical":
        hits.add("evidence_scope")
    if ex.sample_state in ("tissue", "powder"):
        hits.add("same_spot_for_heterogeneous")
    if ex.sample_state == "unknown" or not ex.targets:
        hits.add("insufficient_information_is_valid")
    if ex.sample_state in ("clear_liquid", "turbid_liquid", "opaque_liquid"):
        hits.add("geometry_follows_optics")
    rules = {r["id"]: r for r in load_facts()["rules"]}
    return [f"{rid}: {rules[rid]['statement']} [{rules[rid]['src']}]" for rid in rules if rid in hits]


def required_risk_categories(ex: ExtractedEnquiry) -> list[str]:
    """Standard risk categories every answer must cover when they apply (worked-answer recipe).
    Decided here, not by the model, so they do not vary between runs."""
    required = ["no_guaranteed_gain", "nothing_confirmed"]  # nothing is measured at this stage
    if ex.targets:  # a quantity is to be monitored -> a calibration will be built
        required.insert(0, "calibration_validity")
    if ex.sample_state not in ("unknown", "gas"):  # real samples vary physically
        required.insert(1 if ex.targets else 0, "physical_variation")
    if ex.fibers_mentioned or ex.remote_measurement:
        required.append("fiber_link")
    if ex.process_context == "clinical_or_medical":
        required.append("evidence_scope")
    return required


def pre_analysis(ex: ExtractedEnquiry) -> dict:
    return {
        "table_shortlist": table_shortlist(ex),
        "fiber_checks": fiber_checks(ex),
        "rule_hints": rule_hints(ex),
        "required_risk_categories": required_risk_categories(ex),
    }
