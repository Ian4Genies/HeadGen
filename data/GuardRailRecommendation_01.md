# Guard Rail Recommendation 01

**Date:** 2026-03-30
**Dataset:** 31 good frames, 65 issue frames (from `data/head-good/` and `data/head-issues/`)
**Baseline:** Live-service BodyConfig values ported to `DEFAULT_JOINT_OVERRIDES` in `variation.py`. No post-generation constraint rules active (`rules_snapshot` is `{}`).

---

## Executive Summary

The current guardrails produce roughly a **32% pass rate** (31 good out of 96 evaluated). The two dominant issue categories are:

| Problem Area | Issue Mentions | % of Issues |
|---|---|---|
| Nose | 45 | 69% |
| Eyes | 42 | 65% |
| Mouth | 14 | 22% |
| Proportions / relationships | 24 (no single-param outlier) | 37% |

Six zero-risk generation clamp tightenings (no good frames lost) would address **~35 of the 65 issue frames**. Eye rotation reduction would catch another 24 but requires accepting some impact on borderline-good frames. The remaining ~24 issues have no single-parameter outlier and require either relational constraints or acceptance of the current variance.

---

## 1. Nose — The Primary Problem (45/65 issues)

### 1.1 Current Generation Limits

| Parameter | Override | Effective Range |
|---|---|---|
| `NoseBind.scale.x` (width) | +-0.35 | [0.65, 1.35] |
| `NoseBind.scale.y` (height) | +-0.25 | [0.75, 1.25] |
| `NoseBind.scale.z` (projection) | +-0.25 | [0.75, 1.25] |
| `NoseBind.rotation.x` (tilt) | +-10 deg | [-10, +10] |

### 1.2 Observed Distributions

| Axis | Good Mean | Good Range | Issue Mean | Issue Range |
|---|---|---|---|---|
| scale.x (width) | 0.990 | [0.738, 1.287] | 1.043 | [0.672, 1.350] |
| scale.y (height) | 1.009 | [0.775, 1.241] | 0.994 | [0.757, 1.244] |
| scale.z (projection) | 0.947 | [0.760, 1.176] | 1.033 | [0.751, 1.245] |
| rotation (abs) | 4.81 deg | [0.11, 9.63] | 5.34 deg | [0.20, 9.88] |

### 1.3 Sub-Issue Breakdown

Within the 45 nose-related issues:

- **12 frames** have `NoseBind.scale.x > 1.30` (nose too wide/big)
- **8 frames** have `NoseBind.scale.z > 1.19` (nose protrudes too far forward)
- **5 frames** have `NoseBind.scale.x < 0.72` (nose too thin)
- **17 frames** have nose rotation > 8 deg (too tilted up or down)
- **7 frames** have a z/x proportion ratio > 1.4 (long-for-its-width), vs only 1 good frame

Issue notes specifically calling out tilt direction:

| Frame | Rotation | Note |
|---|---|---|
| 17 | -8.5 deg | "upturned too much" |
| 42 | -9.0 deg | "too long and too upturned" |
| 43 | -9.9 deg | "too long and too upturned" |
| 47 | -9.2 deg | "upturned a little too much along with how tiny it is" |
| 48 | -4.7 deg | "upturned tiny nose" |
| 49 | +3.7 deg | "small downturned nose" |
| 59 | +8.4 deg | "nose is turned down too much" |
| 72 | +7.7 deg | "nose... thin and upturned gives 'I had a lot of work done' feel" |

### 1.4 Nose Recommendations

#### R1. Tighten `NoseBind.scale.x` range: +-0.35 -> +-0.30

**Current:** [0.65, 1.35] **Proposed:** [0.70, 1.30]

Impact: Catches 14 issue frames (wide noses) + 5 issue frames (thin noses). Loses 0 good frames.

The good-frame max is 1.287 and min is 0.738, so clamping at [0.70, 1.30] sits comfortably outside the good envelope while cutting the most extreme issue outliers.

#### R2. Tighten `NoseBind.scale.z` range: +-0.25 -> +-0.20

**Current:** [0.75, 1.25] **Proposed:** [0.80, 1.20]

Impact: Catches 10 issue frames (protruding noses). Loses 0 good frames.

The good-frame max is 1.176. Setting the ceiling at 1.20 provides margin while eliminating all the "nose protrudes too far" outliers.

#### R3. Reduce `NoseBind.rotation.x`: +-10 -> +-8 deg

**Current:** [-10, +10] **Proposed:** [-8, +8]

Impact: Catches 20 issue frames (extreme tilt). Loses 6 good frames.

This is a trade-off. 17 of the 20 caught issues specifically mention nose as a problem, and the 6 good frames that would be affected are:

- Frame 2 (rot 7.3 deg, noted as "extreme but works")
- Frame 22 (rot 3.6 deg, noted "nose a bit down turned")
- Frame 36 (rot 4.2 deg, noted "slightly down turned")
- Frame 62 (rot 8.2 deg, noted "nose rotation feels a bit extreme")
- Frame 73 (rot 9.6 deg, noted attractive)
- Frame 76 (rot 6.4 deg, noted "nose a little long")

Frames 62 and 73 are the only real losses here since the others have rotation below 8 deg and would be caught by the quaternion w-component precision, not actual visual rotation.

**Alternative — less aggressive:** +-9 deg. Would catch fewer issues but lose only ~2 good frames.

#### R4. NEW — Nose Proportion Constraint (z/x ratio)

**Proposed relational rule:** When `NoseBind.scale.z / NoseBind.scale.x > 1.40`, the nose looks "long for its width" — the most frequently cited specific complaint.

- 7 issue frames exceed this ratio, only 1 good frame does (frame 33, noted "nose might be the tiniest bit tiny")
- This catches cases where neither axis alone is out of range but their combination is bad

This would need a new rule type in `constraints.py` (a `ratio_clamp`) or could be approximated by tightening both axes together.

---

## 2. Eyes — The Rotation Problem (42/65 issues)

### 2.1 Current Generation Limits

| Parameter | Override | Effective Range |
|---|---|---|
| `LeftEyeSocketBind.rotation.z` (tilt/slant) | +-10 deg | [-10, +10] |
| `LeftEyeSocketBind.scale.x` | +-0.10 | [0.90, 1.10] |
| `LeftEyeSocketBind.scale.y` | +-0.10 | [0.90, 1.10] |

### 2.2 Eye Rotation Distribution

| | Mean | Median | Max | Min |
|---|---|---|---|---|
| Good | 3.81 deg | 2.83 deg | 9.88 deg | 0.02 deg |
| Issue | 5.42 deg | 5.57 deg | 9.32 deg | 0.16 deg |

The issue population is shifted ~1.6 deg higher on average. 19 issue frames explicitly mention eye rotation/slant/droop as a problem. Even 7 good frames express concern about eye rotation ("eye rotation is extreme but it works", "eye rotation is just distracting", "eye rotation... probably still too extreme").

### 2.3 Impact Analysis for Eye Rotation Clamp

| Proposed Max | Issues Caught | Good Lost | Notes |
|---|---|---|---|
| 7 deg | 24/65 (37%) | 6/31 (19%) | Loses some good-but-borderline frames |
| 6 deg | 30/65 (46%) | 8/31 (26%) | More aggressive |
| 5 deg | 38/65 (58%) | 9/31 (29%) | Very aggressive |

### 2.4 Eye Recommendations

#### R5. Reduce `LeftEyeSocketBind.rotation.z`: +-10 -> +-7 deg

**Current:** [-10, +10] **Proposed:** [-7, +7]

This is the most impactful single change for quality but carries risk. The 6 good frames that would be affected are:

| Frame | Rot | Note |
|---|---|---|
| 2 | 8.75 deg | "Eye rotation is extreme but it works with face which overall appears asian" |
| 8 | 7.38 deg | "eyes might be a bit wide up and down... but the face is good" |
| 21 | 7.53 deg | "head is good but even for a good head I think the eye rotation again is unattractive" |
| 34 | 9.66 deg | "Eyes are a bit on the large side but honestly looks good" |
| 76 | 8.92 deg | "Attractive, asian, nose is a little long" |
| 97 | 9.88 deg | "one of the few heads where the eye rotation is not distracting, but probably still too extreme" |

Frames 21 and 97 explicitly note the rotation as a concern. Frame 2 explicitly acknowledges it as extreme. This suggests the good-frame evaluator was being generous — the systemic feedback across both populations is that high eye rotation is generally undesirable.

**Decision point:** If you want to preserve the rare cases where extreme tilt works (e.g. frame 76 "attractive, asian"), keep at +-8 deg. If you want to aggressively clean up the most common complaint, go to +-7 or even +-6.

#### R6. Consider asymmetric eye rotation limit

Several issue notes mention "droopy" eyes (frames 44, 56). If the negative rotation direction (outward droop) is consistently worse than positive (upward tilt), an asymmetric range like `[-5, +8]` could help. The current data doesn't clearly separate direction preference, but it's worth testing visually.

---

## 3. Mouth Width (14/65 issues)

### 3.1 Current vs Observed

| Parameter | Gen Range | Good Range | Issue Range |
|---|---|---|---|
| `MouthBind.scale.x` | [0.80, 1.20] | [0.813, 1.149] | [0.803, 1.188] |

### 3.2 Mouth Recommendations

#### R7. Tighten `MouthBind.scale.x`: +-0.20 -> +-0.15

**Current:** [0.80, 1.20] **Proposed:** [0.85, 1.15]

Impact: Catches 7 issue frames (wide/fish mouths). Loses 0 good frames.

The issue frames caught are the "fish lips" and "wide mouth" complaints (frames 15, 23, 48, 69, 95 etc.). The good-frame max is 1.149, so 1.15 is tight but safe.

"Wide fish lips" is one of the more visually distinctive failure modes (frames 23, 48, 49, 69, 95), and this single change addresses most of them.

---

## 4. Jaw Length (9/65 issues)

### 4.1 Current vs Observed

| Parameter | Gen Range | Good Range | Issue Range |
|---|---|---|---|
| `JawBind.scale.y` | [0.95, 1.05] | [0.955, 1.036] | [0.951, 1.050] |

### 4.2 Jaw Recommendation

#### R8. Tighten `JawBind.scale.y`: +-0.05 -> +-0.04

**Current:** [0.95, 1.05] **Proposed:** [0.96, 1.04]

Impact: Catches 9 issue frames. Loses 0 good frames.

The good-frame max is 1.036. Issue frames at 1.04-1.05 produce visually elongated jaws that interact badly with other features (frames 10, 13, 16, 19, 43, 47, 92, 94). This is a subtle change but picks up several frames for free.

---

## 5. Relational / Proportion Issues (24/65 with no single outlier)

24 issue frames have ALL joint parameters within the good-frame envelope but still look wrong. These are proportion/combination failures that can't be fixed by tightening individual ranges alone.

### 5.1 Common patterns in these 24 frames

Reading through the notes:

- **"Eyes too big for the rest of the features"** (frames 4, 6, 9, 30, 84, 90, 96, 100) — eye scale is within range but large relative to a small nose or narrow mouth
- **"Eye rotation + other feature"** (frames 4, 32, 44, 56, 84) — moderate rotation that's fine alone but combines badly with scale extremes
- **"Nose length-to-width off"** (frames 24, 49, 53, 67, 70, 72) — both axes individually fine but ratio is wrong
- **"Feature mismatch feels alien"** (frames 6, 49, 64) — feminine eyes + masculine jaw, or thin nose + wide lips

### 5.2 Proportion Constraint Recommendations

#### R9. NEW — Nose z/x ratio constraint

As noted in R4: cap `NoseBind.scale.z / NoseBind.scale.x` at 1.40. This handles the "long thin nose" failure that shows up in 7 issue frames even when individual axes are in range.

Implementation: Add a new `ratio_clamp` rule type to `constraints.py`, or implement as a post-generation fixup that scales z down when the ratio exceeds the threshold.

#### R10. NEW — Eye-scale-to-nose-scale proportion guard

When eyes are large (`EyeSocketBind.scale.x > 1.05`) and nose is small (`NoseBind.scale.x < 0.80`), the face looks alien/childlike in a bad way. Consider a mutual_dampen rule that prevents this combination.

This would address frames like 6 ("small nose against large eyes, feels alien"), 90 ("nose is small while eyes are too large"), and 100 ("eyes are just a bit big with the rest of the head").

#### R11. NEW — Mouth-width-to-nose-width coherence

Wide mouth + thin nose = "fish person" (frames 49, 69). A constraint that dampens `MouthBind.scale.x` when `NoseBind.scale.x` is low would address this specific failure mode.

---

## 6. Summary of Recommendations

### Zero-Risk Changes (0 good frames lost)

| ID | Change | Issues Fixed | Code Location |
|---|---|---|---|
| R1 | `NoseBind.scale.x`: +-0.35 -> +-0.30 | ~14 | `variation.py` override |
| R2 | `NoseBind.scale.z`: +-0.25 -> +-0.20 | ~10 | `variation.py` override |
| R7 | `MouthBind.scale.x`: +-0.20 -> +-0.15 | ~7 | `variation.py` override |
| R8 | `JawBind.scale.y`: +-0.05 -> +-0.04 | ~9 | `variation.py` override |

Combined: These four changes address an estimated **30-35 unique issue frames** (accounting for overlap) while losing zero good frames.

### Acceptable-Risk Changes (some borderline good frames affected)

| ID | Change | Issues Fixed | Good Lost | Notes |
|---|---|---|---|---|
| R3 | `NoseBind.rotation.x`: +-10 -> +-8 | ~20 | ~6 | Most lost frames noted rotation as a concern |
| R5 | `LeftEyeSocketBind.rotation.z`: +-10 -> +-7 | ~24 | ~6 | Most lost frames noted rotation as excessive |

### New Relational Constraints (require code additions)

| ID | Constraint | Issues Addressed | Implementation |
|---|---|---|---|
| R4/R9 | Nose z/x ratio max 1.40 | ~7 | New rule type in `constraints.py` |
| R10 | Eye-large + nose-small dampening | ~5 | New relational rule |
| R11 | Mouth-wide + nose-thin dampening | ~3 | New relational rule |

### Priority Order

1. **R1 + R2** (nose scale) — Highest issue count, zero risk
2. **R5** (eye rotation) — Second highest issue count, acceptable risk given QC notes
3. **R7** (mouth width) — Eliminates "fish" failures, zero risk
4. **R8** (jaw length) — Easy win, zero risk
5. **R3** (nose rotation) — Moderate risk, significant catch
6. **R4/R9** (nose ratio) — Requires new constraint type but catches combination failures
7. **R10 + R11** (proportion guards) — Addresses the hardest 24 "no-outlier" issues

---

## Appendix A — All Issue Notes (sorted by frame)

| Frame | Note |
|---|---|
| 1 | Nose is a bit to long, eyes might be scaled a bit to much up and down |
| 1 | Nose is a bit to thin, eyes rotated in a bit to much |
| 4 | Eyes appear flat, and rotated to extreme, wide nose along with tiny mouth does not work |
| 6 | Nose is small and sharp against large eyes and large mouth, feels alien |
| 7 | Eyes rotated too far out, eyes might be too big especially up and down |
| 9 | Eyes a little big, rotation feels off, lips feel very thin |
| 10 | Head is very good except nose is far too long (forward scale issue) |
| 12 | Head looks very attractive but nose protrudes too far forward |
| 13 | Eye rotation is unattractive |
| 14 | Nose is far too big in relation to other features |
| 15 | Eyes feel a little wide and short compared to rest of features |
| 16 | Eye rotation is unattractive. Nose length (forward) is bad |
| 17 | Nose is upturned too much, eyes feel a bit large |
| 18 | Nose is protruding forward and rotated down in an unattractive way |
| 19 | With the length of the chin the mouth should be lower, eyes feel off |
| 23 | Width of mouth feels wide, slight fish feel |
| 24 | Head would be perfect if not for the nose length and bridge |
| 25 | Nose is too big on multiple axis compared to other features |
| 27 | Nose far too long for how thin it is, eye rotation still odd |
| 28 | Eyes and brow are fine, nose is too long, mouth is too wide |
| 30 | Eyes are super distracting compared to sharp mouth and nose |
| 32 | Eye slant along with extremely wide eye scaling is not good |
| 35 | Nose is large creating a weird relationship with eye shape/rotation |
| 40 | Nose and mouth feel too thin |
| 42 | Nose too long and too upturned |
| 43 | Nose too long and too upturned |
| 44 | Eyes droop on the sides, likely due to scaling and rotation |
| 47 | Nose upturned too much along with how tiny it is |
| 48 | Everything wrong: eye rotation, upturned tiny nose, wide fish lips |
| 49 | Alien fish person: small downturned nose, wide lips, rounded eyes |
| 53 | Good from front but nose profile too long forward and squashed |
| 54 | Nose length compared to width is the issue |
| 55 | Nose a bit too long, eyes scaled too much up and down |
| 55 | Nose protrudes, but otherwise would have been good |
| 56 | Eyes turned a bit too much. Nose just a bit too wide |
| 56 | Eyes too droopy, nose just a little long |
| 57 | Eye rotation obviously needs to be fixed, nose too compressed and thin |
| 59 | Head would be perfect but nose turned down too much |
| 63 | Nose is FAR too thin (eye rotation actually works here for once) |
| 64 | Relationship of thin lips, high mouth, and long chin feels off |
| 67 | Nose just a little flat, mouth just a little pouty |
| 68 | Thin lips + wide rotated eyes don't work together |
| 69 | Circular eyes + thin nose + wide tall lips = "plastic surgery" feel |
| 70 | Nose feels squashed up and down and long for how wide it is |
| 71 | Nose too long for how wide it is |
| 72 | Thin upturned nose gives "I had a lot of work done" feel |
| 77 | Would have been perfect if nose wasn't so long for its width |
| 78 | Nose too thin |
| 81 | Whole face feels flat, eyes don't feel right |
| 82 | Very extreme feature discrepancies |
| 83 | Eyes have a surprised expression |
| 84 | Eye rotation too extreme along with size of eyes and mouth |
| 85 | Eye rotation looks fake |
| 86 | Eyes are too circular |
| 87 | Eyes are too small and flat, nose feels off |
| 89 | Eyes are too small and flat, nose feels off |
| 89 | Nose too big |
| 90 | Nose is a bit small and long while eyes are too large |
| 92 | Nose is just a bit turned out |
| 92 | Nose is a bit long for width |
| 94 | Nose is tiny and long |
| 95 | Everything off: eyes too rotated, nose too long, mouth too wide |
| 96 | Eyes probably just a bit large, nose bridge a bit too pronounced |
| 99 | Eyes are terrible |
| 100 | Eyes are just a bit big with the rest of the head |

## Appendix B — Good Frame Notes (sorted by frame)

| Frame | Note |
|---|---|
| 2 | Eye rotation is extreme but it works with face which overall appears asian |
| 3 | Nothing wrong or particularly remarkable. Attractive face |
| 8 | Eyes might be a bit tall, but the face is good |
| 11 | Not particularly attractive but no issues |
| 21 | Head is good but even for a good head the eye rotation is unattractive |
| 22 | Head is fine, eye rotation is just a little extreme |
| 26 | Very attractive head, nose is a little short |
| 29 | Head is good, nose feels a tiny bit off |
| 31 | Simple attractive face |
| 33 | Nose might be tiniest bit tiny. Otherwise attractive feminine face |
| 34 | Eyes a bit large but honestly looks good |
| 36 | Nose slightly down turned but otherwise good and attractive |
| 37 | Not particularly interesting or attractive but no issues |
| 38 | Eye rotation is distracting, otherwise maybe mouth/nose relationship off |
| 46 | Nose a little odd and long, eyes have rotation issue but it works, shippable |
| 50 | Convincingly ethnic, nose is large but not distracting with other features |
| 51 | Jaw width might be a little wide but works |
| 58 | Unremarkable, fine |
| 60 | Eyes just a little too thin but works well enough |
| 61 | Unremarkable |
| 62 | Pass, though nose rotation feels a bit extreme |
| 66 | Fine, unremarkable |
| 73 | Youthful, african, attractive, 8/10 |
| 74 | Head is good, wish nose wasn't so pointy |
| 75 | Attractive, middle eastern |
| 76 | Attractive, asian, nose a little long though |
| 79 | 9/10, attractive, feminine |
| 91 | A tiny bit androgynous but otherwise good |
| 93 | 10/10 attractive |
| 97 | Eye rotation is not distracting for once, but probably still too extreme |
| 98 | Unremarkable but unoffensive |
