# Baju Swing — Mathematics

This document is the companion to the `drill_detection/baju_swing/` code. Every
formula below has a matching inline comment in the source. All tunables live in
`config.py` (single source of truth); there are no magic numbers in the logic.

## 1. Drill description

**Baju Swing** is a marching **arm-swing** drill. A cadet stands to attention and
swings the arms in the sagittal plane — one arm forward while the other goes back
(front-back marching swing) — in front of a front-on USB camera. Each *swing
extreme* (the point of maximum reach) is a repetition ("iteration") and is scored
out of 10 on five parameters:

1. **Arms straight** — both elbows near 180°.
2. **Swing spread** — the inter-arm angle at its maximum (near 180°).
3. **Legs straight** — both knees near 180° (attention posture while swinging).
4. **Fist closed** — the four fingers curled into a fist.
5. **Thumb on top** — the thumb folded across the front of the fingers.

## 2. Pipeline & key-frame definition

Two-pass, mirroring `kadam_tal` (peak detection) plus the `salute` IMAGE-mode
hand pass:

- **Pass 1 (pose, VIDEO mode):** every frame (subject to `every_k_frames`) is run
  through MediaPipe Holistic. Per frame we compute the **inter-arm angle** and the
  elbow/knee angles.
- **Key frames:** local maxima of the key-frame signal are the swing extremes
  (§4). The signal depends on the camera view (§10.1): inter-arm angle for the
  side view, fist height for the front view. There is **no fixed frame cap** —
  however many valid peaks exist are all scored. `iteration_count = number of
  key frames`.
- **Pass 2 (hands, IMAGE mode):** Holistic is re-run in IMAGE mode on the selected
  key frames only, because reliable hand landmarks come from the IMAGE runner.
  Fist and thumb are scored from those landmarks.

## 3. Landmarks

- **Pose** (`landmarks.py`, same indices as kadam_tal): shoulders 11/12, elbows
  13/14, wrists 15/16, hips 23/24, knees 25/26, ankles 27/28.
- **Hands** (`hand_analysis.py`, MediaPipe HandLandmark): WRIST 0, THUMB_TIP 4,
  INDEX_MCP 5 / INDEX_PIP 6 / INDEX_TIP 8, MIDDLE_MCP 9 / MIDDLE_PIP 10 /
  MIDDLE_TIP 12, RING_MCP 13 / RING_TIP 16, PINKY_MCP 17 / PINKY_TIP 20.
- **Hand scale** = `|WRIST − MIDDLE_MCP|`, clamped ≥ 1.0. Used to normalise the
  thumb gap so it is view- and size-invariant.

## 4. Inter-arm angle (key-frame signal, §6.1)

Let `shoulder_L, wrist_L, shoulder_R, wrist_R` be pixel coordinates.

```
a_L = wrist_L − shoulder_L          # left arm vector
a_R = wrist_R − shoulder_R          # right arm vector
inter_arm_angle = degrees( arccos( (a_L · a_R) / (|a_L| · |a_R|) ) )
```

The signal `inter_arm_angle(frame)` is smoothed with a moving average of width
`smooth_window`, then local maxima are extracted with the **exact** algorithm
copied from `kadam_tal.peak_detection` (renamed `find_swing_peaks`):

- a sample is a peak if it is strictly greater than both neighbours;
- its **prominence** = `value − max(left_min, right_min)` within `±min_distance`
  frames must be ≥ the prominence threshold;
- peaks closer than `min_peak_distance_frames` are merged, keeping the taller one.

Prominence threshold = `min_peak_prominence_deg` if given, else
`max(5.0, angle_range · min_peak_prominence_ratio)` (degrees).

## 5. Scoring primitives (§6.8, copied verbatim)

`score_by_tolerance(value, target, perfect_tol, fail_tol)` — for target-angle
parameters:

```
error = |value − target|
error ≤ perfect_tol        -> 10
error ≥ fail_tol           -> 0
else                       -> 10 · (1 − (error − perfect_tol)/(fail_tol − perfect_tol))
```

`score_by_max(value, perfect_max, fail_max)` — for "smaller is better" ratios:

```
value ≤ perfect_max        -> 10
value ≥ fail_max           -> 0
else                       -> 10 · (1 − (value − perfect_max)/(fail_max − perfect_max))
```

`NaN` (missing landmarks) always scores 0.

## 6. Parameter scoring

Let `Sp, Sf` denote the difficulty-scaled `(perfect, fail)` thresholds from §7.

- **arms_straight (§6.2):**
  `elbow = angle_at_joint(shoulder, elbow, wrist)` for each side.
  `arms_straight = mean( score_by_tolerance(elbow_L, 180, Sp, Sf),
                          score_by_tolerance(elbow_R, 180, Sp, Sf) )`.
- **swing_spread (§6.3):**
  `swing_spread = score_by_tolerance(inter_arm_angle, 180, Sp, Sf)`.
- **legs_straight (§6.4):**
  `knee = angle_at_joint(hip, knee, ankle)` for each side.
  `legs_straight = mean( score_by_tolerance(knee_L, 180, Sp, Sf),
                          score_by_tolerance(knee_R, 180, Sp, Sf) )`.
- **fist (§6.5):** for each finger F ∈ {index, middle, ring, pinky}
  `curl_ratio_F = |TIP_F − WRIST| / |MCP_F − WRIST|`.
  A closed finger folds toward the wrist, so the tip is *nearer* the wrist than
  the knuckle ⇒ small ratio. `fist = mean_F score_by_max(curl_ratio_F, Sp, Sf)`.
  The ratio is a quotient of two lengths, hence inherently scale/view-invariant.
- **thumb (§6.6):**
  `thumb_gap = min(|THUMB_TIP − INDEX_PIP|, |THUMB_TIP − MIDDLE_PIP|) / hand_scale`.
  A thumb folded on top sits close to the finger PIP joints ⇒ small gap.
  `thumb = score_by_max(thumb_gap, Sp, Sf)`.

**Both hands** are scored and **averaged**. If only one hand is detected its
scores are used (single-hand fallback, salute pattern). If **no** hand landmarks
are found, fist and thumb both score **0**.

## 7. Difficulty model (0–5) and tolerance table

`difficulty ∈ [0, 5]` (default 2.0) from `--difficulty` or `.env DIFFICULTY`,
clamped. Every threshold flows through `scaled_tolerances`, a linear interpolation
with `t = difficulty / 5`:

```
perfect(d) = lerp(perfect_easy, perfect_hard, t)
fail(d)    = lerp(fail_easy,    fail_hard,    t)
```

Lower difficulty ⇒ wider tolerances (lenient); higher ⇒ tighter (strict). Bands
live in `config.py`:

| Parameter | Metric | perfect easy→hard | fail easy→hard | Const |
|-----------|--------|-------------------|----------------|-------|
| Arms straight | elbow error vs 180° | 15° → 5° | 45° → 20° | `ELBOW_STRAIGHT_BAND` |
| Swing spread | inter-arm error vs 180° | 20° → 8° | 70° → 35° | `INTER_ARM_BAND` |
| Legs straight | knee error vs 180° | 10° → 4° | 35° → 15° | `KNEE_STRAIGHT_BAND` |
| Fist closed | per-finger curl ratio (max) | 0.55 → 0.35 | 1.05 → 0.85 | `FIST_CURL_BAND` |
| Thumb on top | thumb gap ratio (max) | 0.45 → 0.25 | 1.10 → 0.85 | `THUMB_GAP_BAND` |

The `PipelineConfig` fields `fist_curl_perfect_ratio=0.45`,
`fist_curl_fail_ratio=0.90`, `thumb_on_top_perfect_ratio=0.35`,
`thumb_on_top_fail_ratio=1.00` document the effective hand-ratio thresholds at
the default difficulty (≈2); the bands above are authoritative for scaling.

At low difficulty the elbow band is 15/45, so an elbow of 160–170° (10–20° of
error) still earns partial credit; at high difficulty (5/20) the same elbow
scores 0, matching PRD §2/§6.2.

## 8. Frame total & aggregation (§6.7)

Weights (all 0.20, in `config.WEIGHTS`):

```
frame_total = 0.20·arms_straight + 0.20·swing_spread + 0.20·legs_straight
            + 0.20·fist + 0.20·thumb
```

Summary in `results.json`:

```
iteration_count       = number of key frames (swings)
total_score           = Σ frame_total
max_possible_score    = iteration_count · 10
average_score_per_swing = total_score / iteration_count
```

## 9. Worked examples

**A. Clean swing at difficulty 2** (`t = 0.4`; elbow band → perfect 11°, fail 35°;
inter-arm → perfect 15.2°, fail 56°; knee → perfect 7.6°, fail 27°; fist → perfect
0.47, fail 0.97; thumb → perfect 0.37, fail 1.00):

- elbows 178°/176° → error 2°/4° ≤ 11° → 10, 10 → arms_straight 10.
- inter-arm 172° → error 8° ≤ 15.2° → swing_spread 10.
- knees 179°/180° → legs_straight 10.
- curl ratios ≈ 0.40 each ≤ 0.47 → fist 10.
- thumb gap 0.30 ≤ 0.37 → thumb 10.
- frame_total = 0.2·(10+10+10+10+10) = **10.0/10**.

**B. Bent arms + open hand at difficulty 2:**

- elbows 150°/152° → error 30°/28°, between 11° and 35°:
  score = 10·(1 − (30−11)/(35−11)) = 10·(1 − 19/24) = **2.08**; other 2.92;
  arms_straight ≈ 2.50.
- inter-arm 120° → error 60° ≥ 56° → swing_spread 0.
- knees straight → legs_straight 10.
- open hand, curl ratios ≈ 1.0 ≥ 0.97 → fist 0.
- thumb sticking out, gap ≈ 1.1 ≥ 1.0 → thumb 0.
- frame_total = 0.2·(2.50 + 0 + 10 + 0 + 0) = **2.5/10**.

Lowering the difficulty toward 0 widens every band and raises both totals;
raising it toward 5 tightens them and lowers the totals — satisfying the
monotonicity acceptance criterion.

## 10. Camera view (side vs front)

The drill can be filmed **side-on** or **front-on**; the UI lets the user pick,
and `PipelineConfig.view ∈ {"side", "front"}` (default `"side"`) selects the
mode. The front view is scored on a **different parameter set** (§10.4):
`arms_straight` is dropped, and the **key-frame signal**, **swing spread** and
**fist** metrics are redefined for the head-on camera. `legs_straight` and
`thumb` are computed identically to the side view.

| Parameter | Side view | Front view |
|-----------|-----------|------------|
| key-frame signal | inter-arm angle (§4) | higher fist height (§10.1) |
| swing_spread | inter-arm angle vs 180° (§6.3) | fist height above hip, proportional (§10.2) |
| fist | finger curl toward wrist (§6.5) | fingers-together via midpoints (§10.3) |
| arms_straight | elbows vs 180° (§6.2) | **dropped** |
| legs_straight / thumb | §6.4 / §6.6 | identical |

### 10.1 Key-frame signal (`signals.py`)

The peak finder (`find_swing_peaks`, §4) is view-agnostic: it takes any 1-D
signal index-aligned with the frame metrics and returns its local maxima. The
signal is built per view:

- **Side view:** `inter_arm_angle(frame)` in degrees (§4). Prominence floor
  `min_peak_prominence_floor_side = 5.0` (degrees).
- **Front view:** height of the **higher** of the two fists above the hip line,
  normalised by shoulder width (so the threshold is scale-invariant):

  ```
  shoulder_width = max(|shoulder_L − shoulder_R|, 1)
  hip_y          = (hip_L.y + hip_R.y) / 2
  height_H       = (hip_y − wrist_H.y) / shoulder_width      # H ∈ {L, R}
  signal(frame)  = max(height_L, height_R)                   # "higher of two"
  ```

  Image `y` grows downward, so the subtraction makes a raised fist a local
  **maximum**, matching the side-view convention. Prominence floor
  `min_peak_prominence_floor_front = 0.08` (shoulder-width units).

  With alternating arms, whichever fist is up dominates the max, so each
  up-swing of either arm registers as one peak (one key frame).

### 10.2 Swing spread — front view (`landmarks.py`, `scoring.py`)

Side view scores swing spread from the inter-arm angle (§6.3). Front view scores
**how high the raised fist is** — the same `fist_height` used for the key-frame
signal (§10.1), which is the height of the higher fist above the hip line in
shoulder-width units. Scoring is **proportional** (higher fist → more marks):

```
fist_height  = max(hip_y − wrist_L.y, hip_y − wrist_R.y) / shoulder_width
full         = scaled_value(difficulty, FIST_HEIGHT_FULL_BAND)   # easy→hard
swing_spread = 0                       if fist_height ≤ 0
             = 10 · min(fist_height / full, 1)                   otherwise
```

`FIST_HEIGHT_FULL_BAND = (2.6, 3.2)` shoulder-widths (easy → hard) is the
"max arm reach" at which the score saturates to 10 — TUNABLE dev values
calibrated to the reference clip (fist heights ran 2.3–3.1 sw above the hip);
higher difficulty demands a higher fist for full marks. A fist at or below the
hip scores 0; it rises linearly to 10 as the fist approaches full reach.

**Why fist height, not the two-hand distance:** the drill is an *alternating*
swing, so at the "fist highest" key frame one arm is up and the other is
down/back. The **hand** landmarker misses the down/back hand almost every time
(empirically 1 of 17 key frames on the reference clip had both hands). Fist
height uses only the **pose** wrists (reliably tracked every frame) and only the
*raised* one matters, so it is always defined. The raw `fist_height_norm` is
written to `results.json` per key frame for calibration.

### 10.3 Fist — front view (`hand_analysis.py`)

Side view scores the fist from finger curl toward the wrist (§6.5). Head-on, a
closed fist shows its knuckle face, so front view instead scores **fingers
held together**, using the four finger **midpoints** (PIP joints, indices 6/10/
14/18 — the visible middle segment of a front-on fist):

```
centroid = mean(PIP_index, PIP_middle, PIP_ring, PIP_pinky)
spread   = mean_F |PIP_F − centroid| / hand_scale        # F ∈ 4 fingers
fist     = score_by_max(spread, Sp, Sf)
```

Fingers together ⇒ small spread ⇒ high score. `(Sp, Sf)` are the difficulty-
scaled `FINGER_TOGETHER_BAND` (perfect 0.35→0.20, fail 0.80→0.55, midpoint-
spread ratio). Uses whichever hand(s) are detected (the *raised* fist almost
always is); no hand ⇒ fist scores 0. The raw `fingers_together_spread` is
written to `results.json`.

### 10.4 Front-view parameters & weights (`config.FRONT_WEIGHTS`)

Front view drops `arms_straight` and emphasises the swing height:

```
frame_total = 0.40·swing_spread + 0.20·legs_straight + 0.20·fist + 0.20·thumb
```

`FrameScore.arms_straight` is `None` on the front view and is omitted from
`results.json`, the annotated overlay, and the PDF/summary parameter tables.
Aggregation (§8) is otherwise unchanged.
