"""Data contracts for every pipeline stage (PRD §3).

The LLM-facing models (Intake, Assessment) are passed to structured outputs, so they avoid
recursion. Length limits are validated client-side.

Every claim is a `Statement` with a basis label (client_fact | sourced | general_knowledge |
assumption) and inline citations. The verifier checks quotes, numbers and source scope and
writes a report next to the answer.
"""

from typing import Literal

from pydantic import BaseModel, Field

MethodId = Literal["NIR", "MIR", "RAMAN", "FLUO", "UVVIS"]
FiberId = Literal["UV_SILICA", "VISNIR_SILICA", "CIR", "PIR", "HWG", "INF3", "ZRF4", "SILICA_UNSPECIFIED", "OTHER"]
SampleState = Literal[
    "clear_liquid", "turbid_liquid", "opaque_liquid", "paste_or_soft_solid", "powder", "solid", "tissue", "gas", "unknown"
]
Basis = Literal["client_fact", "sourced", "general_knowledge", "assumption", "proposal"]


# --- shared ---------------------------------------------------------------------------------


class CitationRef(BaseModel):
    ref: str = Field(description="Exactly as the cite attribute in the corpus, e.g. 'S01 p.10', 'S01 Table 1 (p.6)', 'DOCX §3'. 'EXTERNAL' for non-AFS.")
    quote: str | None = Field(default=None, description="Verbatim passage copied from that page (max ~25 words). Mandatory for EXTERNAL.")
    url: str | None = Field(default=None, description="Mandatory for EXTERNAL, else null.")


class Statement(BaseModel):
    text: str
    basis: Basis = Field(
        description="client_fact: stated by the client; sourced: directly supported by the cited AFS page; "
        "general_knowledge: textbook knowledge not in the materials; assumption: assumed for this provisional assessment; "
        "proposal: a proposed experiment or action (feasibility plan)."
    )
    citations: list[CitationRef] = Field(default_factory=list, description="Required when basis is sourced.")


# --- stage 1: intake (extraction + diagnostic questionnaire) --------------------------------


class StatedFact(BaseModel):
    fact: str
    enquiry_quote: str = Field(description="Exact words from the enquiry.")


class ClientPremise(BaseModel):
    claim: str = Field(description="A belief, assumption or request of the client that must be checked.")
    enquiry_quote: str


class ExtractedEnquiry(BaseModel):
    summary: str = Field(description="One sentence: what the client wants to know or decide.")
    stated_facts: list[StatedFact]
    targets: list[str] = Field(description="Variables or analytes to monitor, as stated. Empty if undefined.")
    sample_description: str
    sample_state: SampleState
    process_context: Literal["production", "pilot", "research_lab", "clinical_or_medical", "unknown"]
    conditions: list[str] = Field(description="Stated process conditions (temperature, flow, fouling, ...).")
    measurement_location: str | None
    remote_measurement: bool = Field(description="True if the analyzer is away from the measuring point or remote / non-contact measurement is requested.")
    contact_with_sample: Literal["possible", "not_possible", "unknown"]
    analyzer_distance: str | None = Field(description="Stated distance or separation, verbatim.")
    existing_equipment: list[str]
    methods_mentioned: list[MethodId]
    fibers_mentioned: list[FiberId]
    client_premises: list[ClientPremise]
    requested_decision: str
    unknowns: list[str] = Field(description="Decision-relevant information the enquiry does not give.")


QUESTION_TOPICS = (
    "pain_goal", "target_and_level", "sample_form_optics", "process_conditions",
    "installation_distance", "reference_method", "requirements",
)
QuestionTopic = Literal[
    "pain_goal", "target_and_level", "sample_form_optics", "process_conditions",
    "installation_distance", "reference_method", "requirements",
]


class Question(BaseModel):
    id: str = Field(description="Q1, Q2, ... in priority order.")
    topic: QuestionTopic = Field(description="Questions are ordered by topic in this order.")
    question: str
    why: str = Field(description="What the answer decides.")
    assumption_if_unanswered: str = Field(description="Fallback for a provisional answer. No invented numbers.")
    answer: str | None = Field(default=None, description="Leave null. Filled by the client in interactive mode.")


class Intake(BaseModel):
    extraction: ExtractedEnquiry
    questions: list[Question] = Field(min_length=5, max_length=10)


# --- stage 3: assessment (worked-answer recipe, docx §2/§3) ---------------------------------

DecisionStatus = Literal[
    "provisional_assessment", "insufficient_information", "premise_not_supported", "outside_supported_scope"
]
RiskCategory = Literal[
    "calibration_validity", "physical_variation", "no_guaranteed_gain", "nothing_confirmed",
    "fouling_interface", "fiber_link", "evidence_scope", "other",
]
PlanElement = Literal["representative_samples", "lab_screening", "spectra_with_reference", "models_and_validation", "comparison"]
PLAN_REQUIRED = (("representative_samples", "lab_screening"), ("spectra_with_reference",), ("models_and_validation",), ("comparison",))


class PremiseCheck(BaseModel):
    client_claim: str
    verdict: Literal["supported", "plausible_to_be_tested", "contradicted", "unverifiable"] = Field(
        description="'supported' only if a cited source shows the same application type; otherwise 'plausible_to_be_tested'."
    )
    explanation: list[Statement]


class ReportQuestion(BaseModel):
    question: str = Field(description="Compound question bundling related unknowns. One sentence.")
    covers: Literal["measured", "reference", "variation", "requirements", "context"]


class TableRowDecision(BaseModel):
    table_row: str = Field(description="Shortlisted row as 'method / measurement technique'.")
    decision: Literal["recommended", "alternative", "lab_screening_only", "rejected"]
    reason: str


class Recommendation(BaseModel):
    method: str
    geometry: str
    role: Literal["primary", "comparison", "combination", "alternative", "not_recommended"]
    simplicity_rank: int = Field(description="1 = simplest sufficient option.")
    cost_complexity: Literal["low", "average", "high"] = Field(description="S01 Table 1 cost rating.")
    reason: Statement = Field(description="One sentence: why, citing the application example that supports it for this sample type.")
    caveat: Statement = Field(description="One sentence: the key condition or caveat, cited. For a combination: only after each method is assessed alone; a hypothesis to test.")
    confidence: Literal["low", "medium", "high"]
    confidence_reason: str


class ConceptItem(BaseModel):
    aspect: Literal["interface", "location", "fiber_link"]
    text: str
    basis: Basis
    citations: list[CitationRef] = Field(default_factory=list)


class MeasurementConcept(BaseModel):
    items: list[ConceptItem] = Field(description="One interface per candidate (from S01 Table 1), the location, the fiber link.")
    fiber_family: str
    fiber_compatible: bool | None = Field(description="null if the link is not yet defined.")
    architecture: Literal["centralized", "iot", "undecided"]
    needs_afs_confirmation: list[str] = Field(description="e.g. probe type, installation, optical configuration.")


class SpectralRangeEntry(BaseModel):
    method: str
    nominal_range: str = Field(description="Nominal method range in correct units, copied from the cited page.")
    citation: CitationRef
    note: str | None = Field(description="For Raman: excitation wavelength separately from the Raman shift. Otherwise null.")


class Risk(BaseModel):
    category: RiskCategory
    text: str = Field(description="One short sentence.")
    basis: Basis
    citations: list[CitationRef] = Field(default_factory=list)


class PlanStep(BaseModel):
    element: PlanElement
    text: str = Field(description="One or two sentences.")
    basis: Basis = Field(description="'proposal' for experiment steps.")
    citations: list[CitationRef] = Field(default_factory=list)


class FeasibilityPlan(BaseModel):
    steps: list[PlanStep] = Field(
        description="4 steps in order: representative_samples (or lab_screening when information is insufficient), "
        "spectra_with_reference, models_and_validation, comparison."
    )
    afs_next_path: Literal["A", "B", "C", "undecided"]
    afs_next_path_reason: str


class Assessment(BaseModel):
    decision_status: DecisionStatus
    status_reason: str = Field(description="One line.")
    requirements_stated: list[str] = Field(description="Only what the client said; compact, no interpretation.")
    key_unknowns: list[str] = Field(description="Compact list.")
    premise_checks: list[PremiseCheck]
    report_questions: list[ReportQuestion] = Field(description="4-6 prioritised compound questions, ordered measured, reference, variation, requirements, context.")
    recommendations: list[Recommendation]
    method_table_screening: list[TableRowDecision] = Field(description="One entry for every shortlisted S01 Table 1 row.")
    measurement_concept: MeasurementConcept
    spectral_ranges: list[SpectralRangeEntry]
    risks: list[Risk] = Field(description="About 4 short items; include every required standard category.")
    assumptions: list[str]
    feasibility_plan: FeasibilityPlan
    decision_basis: Statement = Field(description="Acceptance criteria agreed with the client before the test; simplest configuration that meets them on independent material.")


# --- verification + final record ------------------------------------------------------------


class SourceCheck(BaseModel):
    path: str
    ref: str
    quote: str | None
    status: Literal["verified", "page_only", "quote_not_found", "unknown_source", "external_missing_quote"]
    score: float | None = None


class Flag(BaseModel):
    path: str
    kind: Literal["quote", "number", "unsupported_sourced_claim", "scope", "basis", "table_coverage", "questionnaire", "context", "rubric"]
    detail: str


class Verification(BaseModel):
    sources: list[SourceCheck] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    revised: bool = False
    flags_before_revision: list[Flag] = Field(default_factory=list)


class RubricItem(BaseModel):
    check: str
    passed: bool
    detail: str = ""


class RunMeta(BaseModel):
    pipeline_version: str
    calls: list[dict]
    prompt_hash: str
    git_commit: str
    timestamp: str
    duration_s: float


class CaseResult(BaseModel):
    case_id: str
    mode: Literal["one_shot", "interactive"]
    enquiry: str
    facts_stated: list[StatedFact]
    clarification_questions: list[Question]
    assessment: Assessment
    verification: Verification
    rubric: list[RubricItem] = Field(default_factory=list)
    extraction: ExtractedEnquiry
    pre_analysis: dict
    run_meta: RunMeta
