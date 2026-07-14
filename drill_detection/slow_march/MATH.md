# Slow March — Mathematics of Detection & Scoring

This document is the authoritative reference for every formula and threshold used by the
`drill_detection/slow_march` package. It must stay in sync with `config.py`, `scoring.py`,
`landmarks.py`, `geometry.py`, and `key_frame_detection.py`.

## 1. Drill definition

A slow, controlled parade march. At any instant one leg is **grounded** (planted, vertical,
straight) and the other is **raised** and driven forward. At the extreme of each step a
correct slow march shows:

1. **Arms straight** — elbows ≈ 180°.
2. **Look to the front** — head faces forward, neck upright (not turned/tilted).
3. **Grounded leg perpendicular & straight** — support leg vertical to the ground and knee ≈ 180°.
4. **Raised-leg foot parallel to the ground (MANDATORY)** — the airborne foot held flat.

## 2. Key-frame definition & detection

There is no single key pose. **Every step extreme is a key frame.** A correct slow-march key
frame is the instant where **the front leg is farthest forward AND the hind (grounded) leg is
planted/static** — the classic "leg driven out to the front, held over a firmly planted rear
foot." Simply taking the widest leg split is not enough: the widest-split moment can occur
mid-transition while the rear foot is still sliding. We therefore detect on two conditions
together. The signal used is selected by `key_frame_signal` (`"auto"` ⇒ `"stride"` for
`view="side"`, `"inter_leg_angle"` for `view="front"`).

### 2.1 Stride detector (side view — default)

**Front leg farthest** → normalised horizontal distance between the two ankles:

```
body_scale   = mean( |ankle_L − hip_L|, |ankle_R − hip_R| ), clamped ≥ 1   # camera-distance invariant
stride[i]    = |ankle_L.x − ankle_R.x| / body_scale                        # larger ⇒ legs split wider
```

**Hind leg static** → per-frame horizontal speed of the *grounded* ankle (the grounded leg is
the one with the smaller knee-lift, i.e. the planted rear leg):

```
hind_speed[i] = |grounded_ankle.x[i] − grounded_ankle.x[i−1]| / body_scale   # 0 ⇒ foot planted
```

Detection steps:

1. Smooth `stride` (box filter, `smooth_window`), and lightly smooth `hind_speed`.
2. Find local maxima of `stride` (reusing the verbatim `kadam_tal` prominence / `min_distance`
   machinery; prominence floor = `signal_range · stride_min_prominence_ratio`, unit-agnostic).
3. **Snap** each raw peak to the nearby frame (within `±hind_static_snap_window`, keeping
   `stride ≥ (1 − hind_static_snap_separation_tol)·peak`) that **minimises `hind_speed`** — i.e.
   the moment the rear foot is most planted while the front leg is still (near) farthest.
4. **Front-far-forward gate:** keep only snapped frames with
   `stride ≥ min_stride_ratio_of_max · max(stride)` (default 0.55) — rejects small bumps that
   are not real step extremes.
5. **Hind-static gate:** keep only frames with `hind_speed ≤ hind_static_max_speed_ratio`
   (default 0.045) — rejects mid-transition frames where the rear foot is still moving. (If this
   gate would reject *every* step on an otherwise-valid clip, it is relaxed so detection never
   silently returns zero.)
6. De-duplicate within `min_peak_distance_frames`, keeping the wider-stride frame.

Each key frame records `stride_separation_norm` and `hind_foot_speed_norm` in `results.json`
for transparency (empirically ~0.7–1.0 and ~0.00–0.02 respectively on real footage).

### 2.2 Inter-leg-angle detector (front-view fallback)

When `view="front"` the stride opens toward the camera and horizontal ankle separation is
degenerate, so we fall back to the thigh-vector angle (its local maxima, same peak machinery):

```
v_L = knee_L − hip_L ;  v_R = knee_R − hip_R
inter_leg_angle = angle_between(v_L, v_R) = degrees( arccos( (v_L · v_R) / (|v_L| |v_R|) ) )
```

**`iteration_count` = number of accepted key frames.** Only valid key frames count. This is a
first-class output in `results.json` (`summary.iteration_count`), the analyzer response, and
the PDF.

## 3. Per-frame geometry (`geometry.py` / `landmarks.py`)

| Quantity | Formula | Ideal |
|---|---|---|
| `angle_at_joint(a,b,c)` | `degrees(arccos( (a−b)·(c−b) / (\|a−b\|\|c−b\|) ))` | — |
| `angle_between(v1,v2)` | `degrees(arccos( (v1·v2)/(\|v1\|\|v2\|) ))` | — |
| `angle_to_vertical(v)` | `degrees(arccos( \|v_y\| / \|v\| ))` | 0° = vertical |
| `angle_to_horizontal(v)` | `degrees(arcsin( \|v_y\| / \|v\| ))` | 0° = flat |

Grounded vs raised leg uses the kadam_tal knee-lift convention
`knee_lift_px = hip_y − knee_y` (larger ⇒ knee raised higher). **Grounded = smaller knee-lift**
(planted, lower on screen); **raised = the other**.

## 4. Scoring primitives (copied verbatim; self-contained)

- `score_by_tolerance(value, target, perfect_tol, fail_tol)` — from `kadam_tal/scoring.py`.
  Returns 10 when `|value−target| ≤ perfect_tol`, 0 when `≥ fail_tol`, linear between.
- `score_by_max(value, perfect_max, fail_max)` — from `salute/geometry.py`.
  Returns 10 when `value ≤ perfect_max`, 0 when `≥ fail_max`, linear between.

## 5. Parameter scores (each /10)

### 5.1 Arms straight (`hands`)
```
left_arm  = score_by_tolerance(left_elbow_angle,  180, perfect, fail)
right_arm = score_by_tolerance(right_elbow_angle, 180, perfect, fail)
hands     = mean(left_arm, right_arm)          # elbow = angle_at_joint(shoulder, elbow, wrist)
```

### 5.2 Look to the front (`head_front`) — two sub-checks
```
yaw_ratio  = (nose_x − shoulder_mid_x) / shoulder_width          # ≈ 0 facing front
yaw_score  = score_by_max(|yaw_ratio|, perfect_max, fail_max)
head_tilt  = angle_to_vertical(nose − shoulder_mid)              # ≈ 0 upright
tilt_score = score_by_tolerance(head_tilt, 0, perfect, fail)
head_front = yaw_w · yaw_score + (1 − yaw_w) · tilt_score
```
`yaw_w = 0.25` in **side** view (yaw unreliable — down-weighted, formula kept intact),
`0.5` in **front** view. v1 uses the pose-nose approximation; a hook to swap in Holistic
face-landmark yaw is marked in `landmarks.py`.

**Front vs hind leg (side view).** The two leg-based parameters below score specific legs,
so the front (driven-forward) and hind (rear, planted) legs must be identified correctly.
This is done by **horizontal foot position**, NOT knee height: the marching direction is
taken from the toes (`foot_index` sits ahead of `heel`), aggregated over the clip, and the
**front leg is the one whose ankle is farther in that direction** (`assign_leg_roles_by_position`).
A knee-lift heuristic mislabels the driven-forward leg when its knee sits low, which put the
foot-parallel check on the wrong foot on ~6/8 real key frames. `grounded_leg` = hind (planted);
`raised_leg` = front (driven).

### 5.3 Grounded (HIND) leg perpendicular & straight (`grounded_leg`) — two sub-checks
```
grounded_knee = score_by_tolerance(grounded_knee_angle, 180, perfect, fail)  # angle_at_joint(hip,knee,ankle)
grounded_vert = score_by_tolerance(grounded_vertical,     0, perfect, fail)  # angle_to_vertical(ankle − hip)
grounded_leg  = mean(grounded_knee, grounded_vert)
```

### 5.4 FRONT-leg foot parallel to ground (`raised_foot`) — MANDATORY
Scored on the **front (driven-forward) leg only** — the front foot is held flat/parallel.
The hind foot lifting at the heel is normal and is deliberately NOT scored for flatness.
```
f              = foot_index − heel        (FRONT leg)
foot_horizontal = angle_to_horizontal(f)  = degrees(arcsin(|f_y|/|f|))   # 0° when flat
raised_foot    = score_by_tolerance(foot_horizontal, 0, perfect, fail)
```

### 5.5 Frame total & mandatory gate (PRD §6.6 / §6.5)
```
weights = { hands: 0.25, head_front: 0.25, grounded_leg: 0.25, raised_foot: 0.25 }
frame_total = Σ(param · weight)                                  # pre-gate

# MANDATORY raised-foot gate — caps, does NOT zero:
if raised_foot_is_mandatory and raised_foot < raised_foot_pass_threshold (5.0):
    frame_total = min(frame_total, raised_foot_gate_cap (4.0))
```

### 5.6 Aggregation (`results.json.summary`)
```
iteration_count       = number of key frames
total_score           = Σ frame_total over key frames
max_possible_score    = iteration_count · 10
average_score_per_step = total_score / iteration_count
```

## 6. Difficulty scaling (0–5, default 2.0)

Reuses `scaled_tolerances(difficulty, perfect_easy, perfect_hard, fail_easy, fail_hard)`
verbatim from kadam_tal. With `t = difficulty / 5`:
`perfect = lerp(perfect_easy, perfect_hard, t)`, `fail = lerp(fail_easy, fail_hard, t)`.
Lower difficulty ⇒ wider (lenient) bands; higher ⇒ tighter (strict) — so lowering
`--difficulty` measurably raises scores and raising it lowers them.

| Parameter | perfect easy→hard | fail easy→hard |
|---|---|---|
| Arms (elbow vs 180°) | 8 → 3 | 45 → 18 |
| Head yaw ratio (max) | 0.20 → 0.06 | 0.55 → 0.30 |
| Head tilt (vs 0°) | 8 → 3 | 35 → 15 |
| Grounded knee (vs 180°) | 6 → 2 | 35 → 12 |
| Grounded vertical (vs 0°) | 8 → 3 | 35 → 15 |
| Raised foot horizontal (vs 0°) | 6 → 3 | 30 → 12 |

## 7. Worked examples (difficulty = 2.0 ⇒ t = 0.4)

Interpolated bands at t=0.4: arms perfect 6.0 / fail 34.2; head-yaw perfect_max 0.144 /
fail_max 0.45; head-tilt perfect 6.0 / fail 27.0; grounded-knee perfect 4.4 / fail 25.8;
grounded-vertical perfect 6.0 / fail 27.0; raised-foot perfect 4.8 / fail 22.8.

### 7.1 A good step (side view)
- Elbows 178°/179° ⇒ errors 2°/1° ≤ 6.0 ⇒ arms = 10 ⇒ `hands = 10`.
- `yaw_ratio = 0.05` ⇒ ≤ 0.144 ⇒ yaw = 10; `head_tilt = 4°` ≤ 6.0 ⇒ tilt = 10 ⇒ `head_front = 10`.
- Grounded knee 179° (err 1° ≤ 4.4 ⇒ 10); grounded vertical 3° ≤ 6.0 ⇒ 10 ⇒ `grounded_leg = 10`.
- Raised foot horizontal 3° ≤ 4.8 ⇒ `raised_foot = 10` (≥ 5.0 ⇒ no gate).
- `frame_total = 0.25·(10+10+10+10) = 10.0`.

### 7.2 A step failing the mandatory foot gate
- Same as above except raised foot horizontal = **35°** (foot pointed, not flat).
  35 ≥ fail 22.8 ⇒ `raised_foot = 0.0`.
- `frame_total_pre_gate = 0.25·(10+10+10+0) = 7.5`.
- `raised_foot (0.0) < pass_threshold (5.0)` ⇒ gate fires ⇒
  `frame_total = min(7.5, 4.0) = 4.0`. The otherwise-strong step is capped at **4.0/10**.
