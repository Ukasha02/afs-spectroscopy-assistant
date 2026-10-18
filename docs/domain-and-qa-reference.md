# Domain and Q&A reference: AFS Spectroscopy Assistant

## A. What the AFS experts told us (Q&A session, Sat 17 Oct)

The source is our notes and a rough auto-transcript of the session. The expert is the AFS founder. Wording is paraphrased; transcript errors are fixed where obvious (e.g. "hemometric" = chemometric).

### A1. Product expectations
- **An MVP, not a proof of concept.** It should work end to end and be built so it can scale later.
- **It must not hallucinate.** Every technical claim must be traceable to the AFS materials or a quoted external source. When it's unsure, the assistant says so.
- **No external spectral databases and no real-time spectral analysis are required.** The task is to assess the customer enquiry and propose a feasibility path, with citations.
- **The minimum scope is initial solution design for in-line applications.** Predictive or chemometric modelling (e.g. Indirect Hard Modeling) is *nice to have*, not required.

### A2. AFS sees itself as a "process doctor"
- AFS works like a doctor. It asks a few targeted questions (like temperature or blood pressure), diagnoses where the process problem or bottleneck is, and only then suggests a sensor.
- **The assistant should open with a short diagnostic questionnaire: 5–10 questions, not 100.** The shorter the path to understanding the customer's problem, the better.
- Example customer: a brewery with batch-to-batch variation during fermentation that wants fiber-optic probes for real-time monitoring, so they can intervene and get higher quality and yield with fewer mistakes.
- **Customers include researchers and R&D groups**, not only production plants. AFS's path is diagnostics → research system → 1–3 prototypes → licensing to a big manufacturer for volume production.
- **Chemometrics is the last stage.** Process diagnostics come first, and software and models come after you understand the process and have data.

### A3. How to choose methods (core decision logic)
- **"As simple as possible, as complicated as necessary."**
- **If one method answers the customer's need, recommend that one, and the cheaper and simpler option.** Don't upsell. AFS respects the customer's budget and is not a dealer for expensive instruments ("you don't need a Bentley to buy a croissant around the corner").
- **Combine methods only when a single method isn't precise or robust enough.** Then data fusion of physically different methods gives synergy.
- Why combinations work:
  - MIR absorption sees **asymmetric** molecular vibrations and Raman sees **symmetric** ones, so they complement each other.
  - Fluorescence comes from **electron transitions** and MIR from **molecular vibrations**. Because the physics differs, fusing them gives much more information.
- **Proof point (S04):** with a MIR + fluorescence combi probe on chicken tissues, each method alone could only separate one organ from the others, while fused data separated all three. In the end, **just two wavelengths** (one IR, one fluorescence) did as well as or better than two broad-range spectrometers.
- **Goal: find the few key parameters or wavelengths that carry enough information.** Broad-range research systems are for the lab, and simplified few-wavelength sensors are for volume production.
- NIR + Raman: AFS built one of the first NIR/Raman combi probes ("one finger" in a powder like paracetamol). Fusing them is more accurate and robust but costs more. For a single fixed product made in tonnes, you can later reduce it to a couple of wavelengths per method.
- MIR absorption has historically been ~60% of all analysis. Raman is "booming", partly as a fashion. Don't default to Raman because it's trendy.

### A4. What the feasibility plan should contain
- **The expected level is a comparison design and the ideas behind it, not exact sample counts or acceptance numbers.**
- **Typical sequence:**
  1. **Lab first.** Measure a couple of representative samples to establish the relevant **spectral range**, the needed **spectral resolution**, and whether the target is at **ppm level or a relatively large concentration**. This decides the method.
  2. **Compare methods** (only as many as needed; see A3).
  3. **Then move to in-line/in-situ in the real process.** This is AFS's main interest.
  4. **Then scale up:** pilot → production. Production probes must be robust, portable, and meet industry standards (likely GMP; the transcript says "GMA"), and must be **sterilizable for biopharma and food**.
- **Reference analysis usually comes from the customer's existing lab methods**, e.g. a sampling robot plus chromatography or mass spectrometry, as at an AFS partner lab in Berlin.
- **Why in-line matters:** ~80% of the chemical and pharma industry still relies on periodic samples. That's like driving with your eyes closed for 10 seconds at a time, because anything can happen between samples.

### A5. Citations
- **For AFS materials, document + page is enough** (e.g. `S01 p.17`), **as long as that page directly supports the claim.** A quote is helpful but optional.
- **For external sources, both the citation and the quoted passage are required.**

### A6. Evaluation
- No hidden "expected answers" for H01–H06 were confirmed beyond the worked examples (D01, D02) and the rubric. Use the D01/D02 worked answers and the docx's "Common mistakes" section as the quality bar.

### A7. Design implications for us
1. **Two modes, one pipeline:**
   - **Interactive mode (demo / live enquiry):** enquiry → ≤10 prioritized diagnostic questions → user answers (or skips) → recommendation.
   - **One-shot mode (H01–H06 submission):** a single structured answer containing the questions *and* a provisional recommendation that lists its assumptions explicitly.
2. **Order the questions by decision impact.** First ask what could change the method (sample type and optics, target analyte, concentration level ppm vs %), then the setup (temperature, fouling, distance to analyzer, sterilization), then the requirements (accuracy, response time, budget).
3. **Build a simplicity ladder into the recommendation logic:** start with the simplest single method that fits, add a second method only with a stated reason, and always say *why* a combination might be needed and under what condition.
4. **Put budget and cost awareness in the output.** Use the cost and complexity ratings from the method table and never recommend the expensive option without a reason.
5. **Use the feasibility plan template:** lab screening (range, resolution, concentration level) → method comparison against the customer's reference lab method → in-line trial → scale-up notes (robustness, sterilizability, few-wavelength simplification).
6. **Add a premise check and a decision status** to every answer: `provisional assessment` / `insufficient information` / `outside supported scope`.
7. **Make "no hallucination" a feature we demo:** every claim carries a citation, and a self-check step removes or flags any claim without support.

### A8. Second expert session (Sat 17 Oct)
1. **Source priority.** AFS materials come first. General spectroscopy knowledge is allowed only as secondary support. It must always carry the label `basis=general_knowledge`, and it must never be the main justification for a recommendation.
2. **Never estimate missing numbers** (detection limits, concentration ranges, fiber lengths, detector specs). Turn each one into a clarification question, or into something the lab screening must establish. This is enforced in the prompt and in the number check of the verifier.
3. **Questionnaire.** The design is ours. The expert's hint: "understand stakeholders and their pain first, then architect, recommend, check feasibility." Order the questions by decision impact:
   1. Pain or goal: what goes wrong today, and what decision real-time data would drive.
   2. Target analyte and level (ppm vs %).
   3. Sample form and optics (liquid/powder/paste/solid; clear/turbid/opaque).
   4. Process conditions (temperature, pressure, fouling, cleaning or sterilization).
   5. Installation point and distance to the analyzer.
   6. Current reference lab method and its accuracy.
   7. Accuracy, response time, budget.

   Ask at most 5–10 questions, skip anything the enquiry already states, and give each question a fallback assumption to use if it goes unanswered. The fallback must not contain an invented number.

---

## B. Domain primer (plain-language)

### B1. Core idea
Spectroscopy shines light on a material and measures which wavelengths are absorbed, scattered or re-emitted. Molecules have characteristic "fingerprints", so the spectrum reveals composition. **In-line / in-situ** means a fiber-optic probe sits directly in the pipe or reactor and measures continuously, instead of sampling to a lab (**offline**).

### B2. Units
- nm (nanometre); µm (micrometre; 1 µm = 1000 nm); cm⁻¹ (wavenumber).
- **µm = 10 000 / cm⁻¹**, so 4000 cm⁻¹ = 2.5 µm and 400 cm⁻¹ = 25 µm.
- For Raman, state the **laser excitation wavelength (nm)** and the **Raman shift (cm⁻¹)** separately.

### B3. Spectral regions
| Region | Range | Typical use |
|---|---|---|
| UV-Vis | ~190–780 nm | Defined absorbers, colour, optical density / turbidity |
| NIR | 780–2500 nm | Water, fat, protein, powders. Broad overlapping bands, so it needs chemometric calibration |
| MIR | 4000–400 cm⁻¹ (2.5–25 µm) | Strongest, most specific fundamental vibrations. Usually measured by ATR because water absorbs MIR strongly |

### B4. Methods
| Method | Physics | Strengths | Weaknesses |
|---|---|---|---|
| **MIR / FTIR** | Absorption by (asymmetric) molecular vibrations | High selectivity, sharp fingerprints | Short path (ATR sees 1–6 µm), needs special IR fibers, contact/fouling |
| **NIR** | Overtone/combination vibration absorption | Deep penetration; good for powders and opaque media; robust silica fibers | Average selectivity; matrix-specific calibration; sensitive to physical variation (particle size, temperature, scattering) |
| **Raman** | Inelastic laser scattering ((symmetric) vibrations) | High selectivity; works through glass; little water interference | Weak signal; **fluorescence background** can swamp it; high cost |
| **Fluorescence** | Electron transitions; re-emission at longer wavelength | Very high **sensitivity** | Low **selectivity**; only works for a defined fluorescent species or justified marker |
| **UV-Vis** | Electronic absorption | Cheap, sensitive | Low selectivity in mixtures; optical density ≠ viable cell count |

- **Sensitivity** means it can detect small amounts. **Selectivity** means it can distinguish the target from everything else. They are not the same thing.

### B5. Measurement geometries (probe types)
- **ATR (attenuated total reflection):** light reflects inside a crystal (e.g. diamond) in contact with the sample and probes only ~µm deep. For liquids, pastes and soft solids. Risks: contact, fouling, chemical compatibility.
- **Transmission:** light passes through the sample. For clear liquids.
- **Transflection:** through the sample, off a mirror, and back. For clear or slightly turbid liquids.
- **Diffuse reflection:** light scatters in the sample and returns. For powders and opaque or scattering media.
- **Cuvette:** a lab sample holder. **Integrating sphere:** a lab accessory for scattering solids.
- **Combi-probe:** two methods measured at the **same spot** (e.g. MIR-ATR + fluorescence, NIR + Raman).
- **Rule of thumb:** clear liquid → transmission or transflection; opaque or powder → diffuse reflection; strongly absorbing liquid or paste with a need for specificity → MIR-ATR.

### B6. Fibers (a hard physical constraint)
| Fiber | Transmits |
|---|---|
| UV-Vis silica | 190–1200 nm |
| Vis-NIR silica | 350–2400 nm |
| Chalcogenide (CIR) | 1.1–6.5 µm |
| Polycrystalline IR (PIR) | 3–17 µm |
| Hollow glass waveguide (HWG) | 2–18 µm |
| Indium fluoride | 0.3–5.5 µm |
| Zirconium fluoride | 0.3–4.5 µm |

**Silica cannot carry MIR.** MIR needs CIR, PIR or HWG fibers, which are typically shorter and more delicate, so the analyzer-to-probe distance is limited. (Source: S02 p.6; verify exact values against the figure.)

**Two architectures:**
- **Centralized analyzer** with a multiplexer and long fibers: higher accuracy.
- **Distributed IoT spectral sensors:** lower installation cost.

### B7. Data and modelling terms
- **Reference measurement / lab assay:** the trusted, slow lab value (e.g. chromatography) used to calibrate and validate.
- **Chemometrics:** mathematical models that map spectra to composition, e.g. **PCA** (unsupervised, for exploration and classification) and **PLS** (partial least squares regression). Think of it as supervised ML on spectra.
- **Calibration:** a trained chemometric model. It is **matrix-specific**, so it breaks when the formulation or matrix changes.
- **Matrix:** everything in the sample other than the target analyte.
- **Validation on held-out batches or runs:** the equivalent of a test set.
- **Data fusion:** combining spectra from two methods into one model.
- **Indirect Hard Modeling (IHM):** a model of spectra built from pure-component spectra. Optional / nice to have.
- **Feasibility study:** a small first experiment answering "can this work?" before anyone buys equipment.

### B8. Industry vocabulary in the scenarios
- **API:** active pharmaceutical ingredient. **Excipients:** inactive filler/binder powders. **Feed frame:** the tablet-press part that feeds powder into the dies.
- **Whey:** a relatively clear dairy liquid (can turn turbid). **Milk concentrate:** opaque and thick.
- **Fermentation / bioprocess / cell culture:** microbes or cells growing in a tank.
  - **Biomass:** cell amount. **Viable biomass:** living cells only; optical density can't distinguish living from dead.
- **Hot melt extrusion:** a molten polymer pushed through an extruder. Hot, and prone to probe fouling.
- **In vitro:** lab samples. **In vivo:** a living patient. A small in-vitro study is a proof of concept, **not** clinical readiness.
- **ppm vs %:** trace versus bulk concentration. This strongly affects method choice, so ask about it early.

