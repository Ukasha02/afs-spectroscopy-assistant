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
    conflicts, notes = [], []
    for mentioned in ex.fibers_mentioned:
        for fid in _SILICA_ALIASES.get(mentioned, (mentioned,)):
            if fid not in fibers:
                continue
            for mid in ex.methods_mentioned:
                cov = per_method[mid]["fibers"][fid]
                msg = (
                    f"Client fiber {fibers[fid]['name']} ({fibers[fid]['range_um'][0]}-{fibers[fid]['range_um'][1]} um "
                    f"[{fibers[fid]['src']}]) vs {mid} nominal range {per_method[mid]['nominal_range']}: coverage {cov}"
                )
                if cov == "none":
                    conflicts.append(msg)  # the fiber cannot carry this method at all
                elif cov != "full":
                    notes.append(msg)  # usable for part of the range; state it
    link_unknown = None
    if ex.remote_measurement and not ex.fibers_mentioned:
        link_unknown = "Remote analyzer requested but fiber family and link length are not stated: the link cannot be checked yet."
    elif ex.remote_measurement and not ex.analyzer_distance:
        link_unknown = "Link length / distance to the analyzer is not stated: fiber suitability over that distance cannot be confirmed."
    return {"per_method": per_method, "client_fiber_conflicts": conflicts, "client_fiber_notes": notes, "link_unknown": link_unknown}


def method_id(name: str) -> str | None:
    """Map a free-text method name to a method id (order matters: 'NIR' before 'IR')."""
    n = name.lower()
    for key, mid in (("raman", "RAMAN"), ("fluor", "FLUO"), ("uv", "UVVIS"), ("nir", "NIR"), ("near", "NIR"),
                     ("mir", "MIR"), ("mid", "MIR"), ("ftir", "MIR"), ("atr", "MIR"), ("ir ", "MIR")):
        if key in n:
            return mid
    return None


def fiber_verdict(methods: list[str], ex: ExtractedEnquiry, fc: dict) -> tuple[bool | None, str]:
    """Rule-based fiber check for the recommended methods (S02 p.6 ranges)."""
    facts = load_facts()
    names = {f["id"]: f["name"] for f in facts["fibers"]}
    ids = [m for m in dict.fromkeys(method_id(x) for x in methods) if m]
    if not ids:
        return None, ""
    client = [fid for m in ex.fibers_mentioned for fid in _SILICA_ALIASES.get(m, (m,)) if fid in names]
    parts = []
    if client:
        ok = all(any(fc["per_method"][m]["fibers"][fid] != "none" for fid in client) for m in ids)
        for m in ids:
            parts.append(f"{m}: " + ", ".join(f"{names[f]} {fc['per_method'][m]['fibers'][f]}" for f in client))
        return ok, "Rule check of the stated fiber: " + "; ".join(parts) + "."
    for m in ids:
        full = [names[f] for f, cov in fc["per_method"][m]["fibers"].items() if cov == "full"]
        partial = [names[f] for f, cov in fc["per_method"][m]["fibers"].items() if cov.startswith("partial")]
        parts.append(f"{m} full range: {', '.join(full) or 'no single fiber'}; partial: {', '.join(partial) or '-'}")
    return None, "No fiber link stated. Rule check: " + "; ".join(parts) + "."


def fiber_findings(fc: dict) -> list[str]:
    """Fiber issues the answer MUST raise in its premise check and as a fiber_link risk."""
    return fc["client_fiber_conflicts"] + ([fc["link_unknown"]] if fc["link_unknown"] else [])


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
    fc = fiber_checks(ex)
    findings = fiber_findings(fc)
    required = required_risk_categories(ex)
    if findings and "fiber_link" not in required:
        required.append("fiber_link")
    return {
        "table_shortlist": table_shortlist(ex),
        "fiber_checks": fc,
        "fiber_findings_required_in_premise_check": findings,
        "rule_hints": rule_hints(ex),
        "required_risk_categories": required,
    }
