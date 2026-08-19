# Risk Scoring — Design and Rationale

AutoShield computes two independent risk scores per neighborhood — `parking_risk_score` and `pedestrian_risk_score` — from historical SFPD incident reports. This document specifies the algorithm and records why each design choice was made, including alternatives that were considered and rejected.

---

## Algorithm

For each neighborhood, for each axis (`parking`, `pedestrian`):

```
for each incident i assigned to neighborhood N, where age_i <= 36 months:
    decay_i = exp(-ln(2) * age_i_days / halflife_days[category_i])
    contribution_i = weight[axis][category_i] * decay_i

raw(N, axis)      = sum of contribution_i over all qualifying incidents
density(N, axis)  = raw(N, axis) / area_km2(N)

n = count of qualifying incidents in N
if n < 5:
    shrunk_density = (n / (n + k)) * density(N, axis)
                    + (k / (n + k)) * citywide_mean_density(axis)      # k = 10
else:
    shrunk_density = density(N, axis)

score(N, axis) = percentile_rank(shrunk_density among all neighborhoods) * 100
```

Neighborhoods with `n < 5` qualifying incidents are flagged in the API response (`low_sample: true`) so the frontend can indicate reduced confidence without hiding the score.

### Half-lives (by crime category, not by axis)

| Category | Half-life |
|---|---|
| Motor Vehicle Theft | 9 months |
| Larceny – From Vehicle | 9 months |
| Burglary | 9 months |
| Robbery | 18 months |
| Assault | 18 months |

Hard cutoff at 36 months regardless of category.

### Weight tables

| Category | Parking weight | Pedestrian weight |
|---|---|---|
| Motor Vehicle Theft | 1.0 | 0.1 |
| Larceny – From Vehicle | 1.0 | 0.05 |
| Burglary | 0.3 | 0.2 |
| Robbery | 0.3 | 1.0 |
| Assault | 0.1 | 1.0 |

Weights live in application code (or a config table), not on individual `incidents` rows — this keeps scores recomputable with revised weights without re-ingesting raw data, and keeps the weight table auditable in one place rather than baked into stored data.

---

## Design decisions and rationale

**Weighted sum of severity, not raw incident count.** A flat count treats a broken car window the same as a carjacking. Both SpotCrime's SpotScore ("public-risk weighting") and CAP Index (loss-weighted crime data) use severity-weighted inputs rather than counts for the same reason.

**Two independent axes rather than one blended score.** Parking risk and pedestrian risk are driven by different mechanisms, not different weightings of the same thing. Routine activity theory (crime requires a motivated offender, a suitable target, and the absence of a capable guardian) explains why: an unattended parked car has zero guardianship by definition, so its risk is purely opportunistic/property-driven; a pedestrian has self- and bystander-guardianship, so their risk is driven by confrontation dynamics that don't apply to an unattended object. This mirrors why UCR/NIBRS itself splits violent (Part I person) crime from property crime rather than reporting one aggregate index.

**Non-zero cross-category weights.** Property and violent crime aren't independent signals — elevated robbery activity implies reduced guardianship that's mildly relevant even to parked-car risk, just less directly than an actual vehicle break-in. SpotScore's own methodology reflects the same idea (an occupied burglary is weighted higher than an unoccupied one due to confrontation risk). Hard-zeroing the "off-axis" categories would discard real correlation.

**Exponential decay, half-life tied to category, 36-month cap.** A fixed window (e.g., "only last 90 days") creates a cliff-edge — an incident matters 100% one day and 0% the next. Exponential decay avoids that. The specific constants (9mo property / 18mo violent / 36mo cap) are adopted directly from SpotCrime's published SpotScore methodology rather than invented: violent-crime samples are rarer and need a longer memory to remain statistically meaningful; property crime is common enough that a shorter, more current window is more representative.

**Area normalization (land area, not population or parking supply) — known limitation.** This was the pragmatic v1 choice: neighborhood boundary polygons already exist in the schema, so `ST_Area` requires no new data source, whereas population or parking-supply data would. The tradeoff: land area is a proxy for exposure, not the real thing. A sparse, low-density neighborhood can appear artificially safe on the parking axis simply because its denominator is large relative to how many cars are actually parked there; a dense commercial neighborhood can appear artificially risky on the pedestrian axis because area-normalization doesn't capture how much foot traffic it actually carries. SpotCrime avoids this by normalizing against Census population (with a daytime-population adjustment for commercial areas). Adopting equivalent population/parking-supply normalization is the identified follow-up, deliberately deferred rather than rushed, since it requires integrating a new dataset rather than a formula change.

**Percentile calibration, framed as comparative, not absolute.** A raw weighted-density number has no intrinsic meaning. Percentile-ranking against other SF neighborhoods makes it interpretable, but it also means a neighborhood is always ranked somewhere even if citywide incidents dropped — so scores should be presented in UI copy as relative ("safer than most of the city") rather than as an absolute probability.

**Empirical Bayes shrinkage for low-sample neighborhoods, rather than a hard display floor.** A neighborhood with 2 qualifying incidents doesn't have a statistically meaningful rate — treating it as a stable estimate would be false precision. Rather than suppressing the score outright below a threshold (a binary cliff), shrinkage pulls low-sample estimates toward the citywide mean, weighted by how little data is available, producing a smooth, more honest estimate. This is the same principle behind SpotCrime's spatial smoothing (borrowing signal from 8–24 nearby blocks), applied in its simplest form. Neighborhoods below the sample threshold are still flagged (`low_sample: true`) for UI transparency.

**No demographic, income, or socioeconomic inputs, at all.** This is the primary bias mitigation in the whole design. CAP Index's model deliberately incorporates over 100 demographic/socioeconomic variables. The well-documented failure mode in predictive-policing systems is rarely an explicit racial input — it's proxy variables (zip code, income, housing type) that correlate closely enough with protected characteristics to reproduce discrimination without ever naming it. Restricting inputs to incident data and geometry removes that channel by construction.

**Descriptive, not predictive; no connection to enforcement.** The most severe documented harms in this space stem from systems that train on policing/arrest data and then direct future enforcement — a feedback loop where more policing produces more recorded incidents, which the system reads as more crime, which sends more policing. This system only visualizes already-reported historical incidents for a private decision (where to park or walk), with no link to patrol allocation or individual flagging — structurally outside that loop.

**Weight table and methodology are user-visible, not hidden in code.** Severity weights are an inherent value judgment; there's no bias-free ground-truth number for "how much worse is an assault than a car break-in." Making the weight table inspectable in-product (not just in this doc) lets a user disagree with a specific, named number instead of an opaque score.

---

## Alternatives considered and rejected

- **Raw incident count.** No severity distinction, no time decay — actively misleading (many minor incidents could outrank fewer severe ones).
- **Full CAP-Index-style multi-factor demographic model.** Introduces the proxy-variable bias risk described above; disproportionate complexity for the value added here.
- **ML-based predictive forecasting** (e.g., kernel-density prediction of future crime). Predictive framing is precisely what invites the feedback-loop failure mode, even without an enforcement connection. A descriptive score of historical incidents is simpler to reason about and audit. Worth revisiting as an explicitly-labeled experimental feature later, not as the default.
- **Sentencing-derived severity weights** (Cambridge Crime Harm Index style — weights derived from recommended custodial sentence length rather than hand-picked). More externally defensible, but disproportionate for a five-category taxonomy; a small, documented, hand-tuned table is proportionate here. Worth revisiting if the category set is broadened.
- **Hard minimum-incident-count floor** for low-sample neighborhoods. Superseded by empirical Bayes shrinkage (see above) — strictly better for barely more implementation cost.

---

## Known limitations

- Reported-incident data is not the same as actual-incident data; reporting rates vary by neighborhood and are trending down across both property and violent crime categories, per current research on police trust and crime reporting.
- Land-area normalization is a proxy for exposure (car-hours, pedestrian-hours), not the real thing, and the mismatch differs in direction between the two axes.
- Neighborhood boundaries (SF Realtor Neighborhoods) are marketing-drawn units, not neutral administrative geography — a known statistical issue (the Modifiable Areal Unit Problem): results can shift depending on which boundary set is used, independent of the underlying data.
- The decay half-life asymmetry (9 vs. 18 months) is a deliberate statistical tradeoff: violent-crime history remains visible in the score twice as long as property-crime history.
- Severity weights are a documented, transparent value judgment — not an empirically derived ground truth.

---

## References

- [How SpotScore Is Calculated: A Methodological Walkthrough of Block-Level Safety Ratings](https://spotcrime.io/blog/spotscore-methodology-block-level-safety-ratings)
- [The CAP Index Scoring System](https://capindex.com/CAP-Index-Scoring-System/)
- [Predictive policing algorithms are racist. They need to be dismantled. — MIT Technology Review](https://www.technologyreview.com/2020/07/17/1005396/predictive-policing-algorithms-racist-dismantled-machine-learning-bias-criminal-justice/)
- [Declining Trends in Crime Reporting and Victims' Trust of Police in the United States and Major Metropolitan Areas in the 21st Century (Xie, Ortiz Solis, Chauhan, 2024)](https://journals.sagepub.com/doi/10.1177/10439862231190212)
- [Routine Activities Theory: Definition & Examples](https://www.simplypsychology.org/routine-activities-theory.html)
- [Modifiable Areal Unit Problem — Wikipedia](https://en.wikipedia.org/wiki/Modifiable_areal_unit_problem)
- [MAUP - Modifiable Areal Unit Problem — GIS Geography](https://gisgeography.com/maup-modifiable-areal-unit-problem/)
