"""Data contracts for every pipeline stage (PRD §3).

The LLM-facing models (ExtractedEnquiry, Questionnaire, Assessment) are passed to structured
outputs, so they avoid recursion. Length limits are validated client-side by the SDK.
Citations are attached inline to each claim; the verifier checks them and builds the source list.
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
    ref: str = Field(
        description="Source and page exactly as in the corpus, e.g. 'S01 p.10', 'S01 Table 1 (p.6)', 'S02 p.13', "
        "'DOCX §3'. Use 'EXTERNAL' only for a non-AFS source."
    )
    quote: str | None = Field(
        default=None,
        description="Short verbatim passage (max ~25 words) from that page that supports the claim. "
        "Optional for AFS sources, mandatory for EXTERNAL.",
    )
    url: str | None = Field(default=None, description="Mandatory for EXTERNAL sources, otherwise null.")


class Statement(BaseModel):
    text: str
    basis: Basis = Field(
        description="client_fact = stated in the enquiry or answered by the client; sourced = supported by the "
        "cited AFS page; general_knowledge = textbook knowledge not in the materials (label it); "
        "assumption = not known, assumed for this provisional assessment."
    )
    citations: list[CitationRef] = Field(default_factory=list)


# --- stage 1: extraction --------------------------------------------------------------------


class StatedFact(BaseModel):
    fact: str
    enquiry_quote: str = Field(description="The exact words from the enquiry that state this fact.")


class ClientPremise(BaseModel):
    claim: str = Field(description="A belief, assumption or request of the client that the assessment must check.")
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
    analyzer_distance: str | None = Field(description="Stated distance or separation between analyzer and probe.")
    existing_equipment: list[str]
    methods_mentioned: list[MethodId]
    fibers_mentioned: list[FiberId]
    client_premises: list[ClientPremise]
    requested_decision: str = Field(description="What the client asks the assistant to decide or approve.")
    unknowns: list[str] = Field(description="Decision-relevant information the enquiry does not give.")


# --- stage 2: diagnostic questionnaire ------------------------------------------------------


class Question(BaseModel):
    id: str = Field(description="Q1, Q2, ... in priority order.")
    question: str
    why: str = Field(description="What the answer decides.")
    impact: Literal["method", "setup", "requirements"]
    assumption_if_unanswered: str = Field(description="The assumption the provisional assessment will use.")
    answer: str | None = Field(default=None, description="Filled only in interactive mode by the user.")


class Questionnaire(BaseModel):
    questions: list[Question] = Field(min_length=5, max_length=10)


# --- stage 4: assessment --------------------------------------------------------------------


class PremiseCheck(BaseModel):
    client_claim: str
    verdict: Literal["supported", "contradicted", "unverifiable"]
    explanation: list[Statement]


class SpectralRange(BaseModel):
    value: str = Field(description="Range in correct units, e.g. '780-2500 nm' or '4000-400 cm-1'.")
    note: str = Field(description="State that this is a nominal method range, or what limits the usable range.")


class Recommendation(BaseModel):
    method: str = Field(description="Method or combination, e.g. 'NIR', 'NIR + Raman'.")
    technique_geometry: str = Field(description="Probe / geometry, e.g. 'diffuse reflection probe'.")
    role: Literal["primary", "alternative", "add_on_if_needed", "not_recommended"]
    simplicity_rank: int = Field(description="1 = simplest sufficient option.")
    cost_complexity: Literal["low", "average", "high"] = Field(description="From the S01 Table 1 cost rating.")
    rationale: list[Statement]
    why_not_simpler: str | None = Field(description="Required if a simpler option exists in the shortlist.")
    combination_trigger: str | None = Field(
        description="Required for combinations: the condition under which one method would not be precise or robust enough."
    )
    conditions: list[str] = Field(description="Conditions under which this recommendation holds.")
    spectral_range: SpectralRange | None
    confidence: Literal["low", "medium", "high"]
    confidence_reason: str


class FiberLink(BaseModel):
    family: str
    compatible: bool | None = Field(description="null if the link is not yet defined.")
    check_note: str


class MeasurementConcept(BaseModel):
    probe_type: str
    geometry: str
    location: str
    fiber_link: FiberLink
    architecture: Literal["centralized", "iot", "undecided"]
    rationale: list[Statement]


class Risk(BaseModel):
    risk: str
    type: Literal["technical", "assumption", "evidence_scope"]
    mitigation: str
    citations: list[CitationRef] = Field(default_factory=list)


class LabScreening(BaseModel):
    samples: str
    establish: list[str] = Field(description="Spectral range, spectral resolution, concentration level (ppm vs %), ...")
    methods_screened: list[str]


class MethodComparison(BaseModel):
    methods: list[str] = Field(description="Only as many methods as needed.")
    reference_method: str = Field(description="The customer's existing lab method, or what must be agreed.")
    compare_on: list[str]
    decision_basis: str = Field(description="Criteria to agree with the client. Never invent numerical targets.")


class InlineTrial(BaseModel):
    location: str
    interface: str
    what_to_verify: list[str]


class ScaleUp(BaseModel):
    robustness: str
    cleaning_sterilization: str
    industry_standards: str
    few_wavelength_simplification: str


class FeasibilityPlan(BaseModel):
    objective: str
    lab_screening: LabScreening
    method_comparison: MethodComparison
    inline_trial: InlineTrial
    scale_up: ScaleUp
    afs_next_path: Literal["A", "B", "C", "undecided"]
    afs_next_path_reason: str


class Assessment(BaseModel):
    decision_status: Literal["provisional_assessment", "insufficient_information", "outside_supported_scope"]
    status_reason: str
    summary_for_expert: str = Field(description="Two or three sentences an AFS expert can read first.")
    constraints: list[str]
    key_unknowns: list[str]
    premise_checks: list[PremiseCheck]
    recommendations: list[Recommendation]
    measurement_concept: MeasurementConcept
    risks: list[Risk]
    assumptions: list[str]
    feasibility_plan: FeasibilityPlan


# --- final record ---------------------------------------------------------------------------


class SourceCheck(BaseModel):
    ref: str
    quote: str | None
    url: str | None
    support_check: Literal["verified", "page_only", "unverified", "unknown_source"]
    detail: str


class Verification(BaseModel):
    sources: list[SourceCheck] = Field(default_factory=list)
    unsupported_claims_removed: list[str] = Field(default_factory=list)
    flagged: list[str] = Field(default_factory=list)
    unsupported_numbers: list[str] = Field(default_factory=list)
    critic_issues: list[str] = Field(default_factory=list)
    revised: bool = False


class RunMeta(BaseModel):
    model: str
    effort: str
    provider: str
    prompt_hash: str
    git_commit: str
    timestamp: str
    duration_s: float
    usage: dict[str, int] = Field(default_factory=dict)


class CaseResult(BaseModel):
    case_id: str
    mode: Literal["one_shot", "interactive"]
    enquiry: str
    extraction: ExtractedEnquiry
    questionnaire: Questionnaire
    pre_analysis: dict
    assessment: Assessment
    verification: Verification
    run_meta: RunMeta
