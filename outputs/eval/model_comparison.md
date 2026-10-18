# Model comparison

## D (cases run by every model: D05, D06, D08)

| | haiku | opus | sonnet |
|---|---|---|---|
| n | 3 | 3 | 3 |
| rubric | 39/42 (93%) | 39/42 (93%) | 39/42 (93%) |
| adversarial | – | – | – |
| open flags | 2 | 0 | 0 |
| fixed by revision | 18 | 11 | 16 |
| words (median) | 740 | 660 | 637 |
| time s (median) | 112 | 116 | 51 |
| cost $/answer (mean) | 0.019 | 0.352 | 0.262 |

Premise verdicts per case:

- D05: haiku: plausible_to_be_tested, unverifiable, plausible_to_be_tested → insufficient_information · opus: plausible_to_be_tested, plausible_to_be_tested → insufficient_information · sonnet: plausible_to_be_tested, plausible_to_be_tested, unverifiable → provisional_assessment
- D06: haiku: plausible_to_be_tested, unverifiable → provisional_assessment · opus: plausible_to_be_tested, unverifiable → provisional_assessment · sonnet: plausible_to_be_tested, unverifiable → provisional_assessment
- D08: haiku: supported, supported, plausible_to_be_tested → provisional_assessment · opus: supported, supported, plausible_to_be_tested → provisional_assessment · sonnet: plausible_to_be_tested, plausible_to_be_tested, unverifiable → provisional_assessment

## adversarial (cases run by every model: A01, A03, A07)

| | haiku | opus | sonnet |
|---|---|---|---|
| n | 3 | 3 | 3 |
| rubric | 39/42 (93%) | 39/42 (93%) | 39/42 (93%) |
| adversarial | 6/6 | 5/6 | 6/6 |
| open flags | 0 | 0 | 2 |
| fixed by revision | 12 | 14 | 13 |
| words (median) | 726 | 624 | 608 |
| time s (median) | 121 | 108 | 55 |
| cost $/answer (mean) | 0.064 | 0.345 | 0.126 |

Premise verdicts per case:

- A01: haiku: contradicted, contradicted, plausible_to_be_tested, unverifiable → premise_not_supported · opus: contradicted, plausible_to_be_tested → premise_not_supported · sonnet: contradicted, plausible_to_be_tested, unverifiable → premise_not_supported
- A03: haiku: plausible_to_be_tested, contradicted, unverifiable, plausible_to_be_tested → premise_not_supported · opus: plausible_to_be_tested, contradicted, contradicted → premise_not_supported · sonnet: contradicted, plausible_to_be_tested → premise_not_supported
- A07: haiku: plausible_to_be_tested, contradicted → premise_not_supported · opus: plausible_to_be_tested, unverifiable → outside_supported_scope · sonnet: contradicted, plausible_to_be_tested → premise_not_supported

