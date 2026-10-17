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
Basis = Literal["client_fact", "sourced", "general_knowledge", "assumption"]


# --- shared ---------------------------------------------------------------------------------


class CitationRef(BaseModel):
    ref: str = Field(description="Exactly as the cite attribute in the corpus, e.g. 'S01 p.10', 'S01 Table 1 (p.6)', 'DOCX §3'. 'EXTERNAL' for non-AFS.")
    quote: str | None = Field(default=None, description="Verbatim passage copied from that page (max ~25 words). Mandatory for EXTERNAL.")
    url: str | None = Field(default=None, description="Mandatory for EXTERNAL, else null.")


class Statement(BaseModel):
    text: str
    basis: Basis = Field(
        description="client_fact: stated by the client; sourced: directly supported by the cited AFS page; "
        "general_knowledge: textbook knowledge not in the materials; assumption: assumed for this provisional assessment."
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


# --- stage 3: assessment --------------------------------------------------------------------


class PremiseCheck(BaseModel):
    client_claim: str
    verdict: Literal["supported", "plausible_to_be_tested", "contradicted", "unverifiable"] = Field(
        description="'supported' only if a cited source shows the same application type; otherwise 'plausible_to_be_tested'."
    )
    explanation: list[Statement]


class TableRowDecision(BaseModel):
    table_row: str = Field(description="Shortlisted row as 'method / measurement technique'.")
    decision: Literal["recommended", "alternative", "lab_screening_only", "rejected"]
    reason: str


class RecNote(BaseModel):
    kind: Literal["condition", "why_not_simpler", "combination_trigger", "spectral_range_note"]
    text: str
    basis: Basis
    citations: list[CitationRef] = Field(default_factory=list)


class Recommendation(BaseModel):
    method: str = Field(description="Method or combination, e.g. 'NIR', 'NIR + Raman'.")
    technique_geometry: str
    role: Literal["primary", "alternative", "add_on_if_needed", "not_recommended"]
    simplicity_rank: int = Field(description="1 = simplest sufficient option.")
    cost_complexity: Literal["low", "average", "high"] = Field(description="S01 Table 1 cost rating.")
    spectral_range: str | None = Field(description="Nominal method range in correct units, copied from the sources.")
    rationale: list[Statement]
    notes: list[RecNote] = Field(description="Conditions; why_not_simpler if a simpler option exists; combination_trigger for combinations; spectral_range_note.")
    confidence: Literal["low", "medium", "high"]
    confidence_reason: str


class MeasurementConcept(BaseModel):
    probe_type: str
    geometry: str
    location: str
    fiber_family: str
    fiber_compatible: bool | None = Field(description="null if the link is not yet defined.")
    architecture: Literal["centralized", "iot", "undecided"]
    rationale: list[Statement] = Field(description="Include the fiber compatibility check.")


class Risk(BaseModel):
    type: Literal["technical", "assumption", "evidence_scope"]
    risk: str
    mitigation: str
    basis: Basis
    citations: list[CitationRef] = Field(default_factory=list)


class PlanStep(BaseModel):
    stage: Literal["lab_screening", "method_comparison", "inline_trial", "scale_up"]
    aspect: Literal[
        "samples", "establish", "reference_method", "compare_on", "decision_basis", "location", "interface",
        "verify", "robustness", "cleaning_sterilization", "industry_standards", "few_wavelength_simplification",
    ]
    text: str
    basis: Basis
    citations: list[CitationRef] = Field(default_factory=list)


class FeasibilityPlan(BaseModel):
    objective: str
    methods_screened: list[str]
    methods_compared: list[str] = Field(description="Only as many as needed.")
    steps: list[PlanStep] = Field(
        description="In stage order. lab_screening: samples, establish (range, resolution, ppm vs %). method_comparison: "
        "reference_method (client's lab method), compare_on, decision_basis (agreed with client, no invented numbers). "
        "inline_trial: location, interface, verify. scale_up: robustness, cleaning_sterilization, industry_standards, "
        "few_wavelength_simplification."
    )
    afs_next_path: Literal["A", "B", "C", "undecided"]
    afs_next_path_reason: str


class Assessment(BaseModel):
    decision_status: Literal["provisional_assessment", "insufficient_information", "outside_supported_scope"]
    status_reason: str
    summary_for_expert: str = Field(description="Two or three sentences an AFS expert reads first.")
    constraints: list[Statement]
    key_unknowns: list[str]
    premise_checks: list[PremiseCheck]
    method_table_screening: list[TableRowDecision] = Field(description="One entry for every shortlisted S01 Table 1 row.")
    recommendations: list[Recommendation]
    measurement_concept: MeasurementConcept
    risks: list[Risk]
    assumptions: list[str]
    feasibility_plan: FeasibilityPlan


# --- verification + final record ------------------------------------------------------------


class SourceCheck(BaseModel):
    path: str
    ref: str
    quote: str | None
    status: Literal["verified", "page_only", "quote_not_found", "unknown_source", "external_missing_quote"]
    score: float | None = None


class Flag(BaseModel):
    path: str
    kind: Literal["quote", "number", "unsupported_sourced_claim", "scope", "basis", "table_coverage", "questionnaire"]
    detail: str


class Verification(BaseModel):
    sources: list[SourceCheck] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    revised: bool = False
    flags_before_revision: list[Flag] = Field(default_factory=list)


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
    extraction: ExtractedEnquiry
    pre_analysis: dict
    run_meta: RunMeta
