# Model comparison

## D (cases run by every model: D01, D02, D03, D04, D05, D06, D07, D08)

| | haiku |
|---|---|
| n | 8 |
| rubric | 104/112 (93%) |
| adversarial | – |
| open flags | 2 |
| fixed by revision | 31 |
| words (median) | 613 |
| time s (median) | 100 |
| cost $/answer (mean) | 0.017 |

Premise verdicts per case:

- D01: haiku: plausible_to_be_tested, plausible_to_be_tested → provisional_assessment
- D02: haiku: plausible_to_be_tested, unverifiable → provisional_assessment
- D03: haiku: plausible_to_be_tested, plausible_to_be_tested, plausible_to_be_tested → provisional_assessment
- D04: haiku: supported, plausible_to_be_tested → provisional_assessment
- D05: haiku: plausible_to_be_tested, unverifiable, plausible_to_be_tested → insufficient_information
- D06: haiku: plausible_to_be_tested, unverifiable → provisional_assessment
- D07: haiku: plausible_to_be_tested, unverifiable → provisional_assessment
- D08: haiku: supported, supported, plausible_to_be_tested → provisional_assessment

## adversarial (cases run by every model: A01, A02, A03, A04, A05, A06, A07, A08)

| | haiku |
|---|---|
| n | 8 |
| rubric | 103/112 (92%) |
| adversarial | 16/16 |
| open flags | 2 |
| fixed by revision | 34 |
| words (median) | 655 |
| time s (median) | 102 |
| cost $/answer (mean) | 0.040 |

Premise verdicts per case:

- A01: haiku: contradicted, contradicted, plausible_to_be_tested, unverifiable → premise_not_supported
- A02: haiku: contradicted, unverifiable → insufficient_information
- A03: haiku: plausible_to_be_tested, contradicted, unverifiable, plausible_to_be_tested → premise_not_supported
- A04: haiku: contradicted, unverifiable, unverifiable → premise_not_supported
- A05: haiku: unverifiable, unverifiable → insufficient_information
- A06: haiku: unverifiable, plausible_to_be_tested → outside_supported_scope
- A07: haiku: plausible_to_be_tested, contradicted → premise_not_supported
- A08: haiku: unverifiable, plausible_to_be_tested, unverifiable → provisional_assessment

