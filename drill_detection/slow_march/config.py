from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drill_detection.report_metadata import ReportMetadata


@dataclass
class PipelineConfig:
    """Single source of truth for every slow-march tunable. No magic numbers in logic."""

    input_path: Path
    output_dir: Path
    every_k_frames: int = 1
    min_detection_confidence: float = 0.5
    save_annotated_frames: bool = True
    save_raw_frames: bool = False

    # --- Key-frame (step-extreme) detection ---
    smooth_window: int = 5
    min_peak_distance_frames: int = 15
    min_peak_prominence_deg: float | None = None  # absolute prominence in degrees; None => derive from ratio
    min_peak_prominence_ratio: float = 0.15  # fraction of signal range used when prominence not given

    # Key-frame signal selection. Several detectors are available; "foot_passing" is the
    # current ACTIVE side-view detector (approved definition):
    #   "foot_passing"       -> ACTIVE (side). The "passing" instant of each pace: BOTH feet
    #                           parallel to the ground (hind grounded flat + front held flat)
    #                           AND the legs close together (small inter-leg split). Selected as
    #                           self-calibrating local minima of a combined cost (each signal is
    #                           normalised to the clip's own range -> no hardcoded degrees, so
    #                           it generalises across person / camera / pace). See
    #                           _find_by_foot_passing in key_frame_detection.py.
    #   "stride"             -> SAVED pipeline. Local maxima of normalised horizontal ankle
    #                           separation (front leg farthest), snapped to the most STATIC
    #                           grounded-foot frame.
    #   "perpendicular_hind" -> stride peaks snapped to the most PERPENDICULAR hind leg;
    #                           rejects steps not within `hind_perpendicular_max_deg` of vertical.
    #   "merged"             -> combined static + perpendicular (accept only if BOTH pass).
    #   "inter_leg_angle"    -> legacy thigh-vector angle maxima (front-view fallback).
    #   "auto"               -> "foot_passing" when view=="side", else "inter_leg_angle".
    #                           (Flip auto's side default in key_frame_detection.py to change
    #                           the active pipeline for everyone.)
    key_frame_signal: str = "auto"
    stride_min_prominence_ratio: float = 0.15   # stride-peak prominence as fraction of signal range (unit-agnostic)
    min_stride_ratio_of_max: float = 0.55       # a key frame's stride must be >= this fraction of the clip's max
                                                # stride, i.e. the front leg is genuinely far forward (rejects
                                                # small local bumps that are not real step extremes)
    hind_static_snap_window: int = 6            # frames each side of a stride peak to search for the planted instant
                                                # (shared by all three detectors as the snap search radius)
    hind_static_snap_separation_tol: float = 0.12  # snap only within this fraction below the peak separation
    hind_static_max_speed_ratio: float = 0.045  # "stride"/"merged" gate: reject a step if the grounded ankle still
                                                # moves faster than this (per-frame horizontal displacement / body
                                                # scale) at the snapped frame

    # --- NEW pipeline "perpendicular_hind" (real-world key frame; ACTIVE for side view) ---
    # The hind (grounded) leg being perpendicular to the ground is MANDATORY. Each stride peak
    # is snapped to the nearby frame where the grounded leg is most plumb (min off-vertical
    # angle), and any step whose hind leg never comes within this many degrees of vertical is
    # rejected. `grounded_vertical_deg` == 0 means the leg is exactly perpendicular.
    hind_perpendicular_max_deg: float = 18.0

    # --- FUTURE pipeline "merged" (ready to enable; combines static + perpendicular) ---------
    # Snap cost = normalised(grounded-foot speed) blended with normalised(off-vertical angle);
    # a step is accepted only if the snapped frame is BOTH static AND perpendicular. Turn on
    # with key_frame_signal="merged" (or --key-frame-signal merged) whenever we want the
    # stricter combined detector. Weights below control the snap blend (need not sum to 1).
    merged_speed_weight: float = 0.5
    merged_perpendicular_weight: float = 0.5

    # --- ACTIVE pipeline "foot_passing" (both feet parallel to ground + legs together) --------
    # Key frames are local minima of a self-calibrating cost combining three per-frame signals,
    # each normalised to the clip's own robust percentile range (NO absolute degree thresholds):
    #   * hind-foot flatness  (sole heel->toe angle to horizontal; 0 == grounded flat)
    #   * front-foot flatness (0 == parallel to ground)
    #   * inter-leg split     (angle between the two hip->ankle leg vectors; small == together)
    # Weights below scale each normalised term in the cost (need not sum to 1). Raising
    # foot_passing_split_weight biases toward feet-together; raising the flatness weights biases
    # toward both-feet-flat.
    foot_passing_hind_flat_weight: float = 1.0
    foot_passing_front_flat_weight: float = 1.0
    foot_passing_split_weight: float = 1.0
    foot_passing_norm_low_pct: float = 5.0    # robust-normalisation lower percentile
    foot_passing_norm_high_pct: float = 95.0  # robust-normalisation upper percentile
    foot_passing_min_prominence_ratio: float = 0.15  # cost-minimum prominence as fraction of cost range
    # (pace spacing reuses min_peak_distance_frames; smoothing reuses smooth_window.)

    # --- Scoring targets (see MATH.md / scoring.py) ---
    target_arm_angle_deg: float = 180.0        # arms straight: elbow ~180 deg
    target_grounded_knee_deg: float = 180.0    # grounded leg straight: knee ~180 deg
    target_grounded_vertical_deg: float = 0.0  # grounded leg perpendicular: 0 deg off vertical
    target_head_yaw_deg: float = 0.0           # look front: yaw ratio ~0 (see scoring, uses ratio not deg)
    target_foot_horizontal_deg: float = 0.0    # raised foot flat: 0 deg off horizontal

    # --- Mandatory raised-foot gate (PRD 6.5) ---
    raised_foot_is_mandatory: bool = True
    raised_foot_pass_threshold: float = 5.0  # raised_foot sub-score below this triggers the gate
    raised_foot_gate_cap: float = 4.0        # frame_total capped to this value when the gate fires

    # --- Difficulty knob 0..5 ---
    difficulty: float = 2.0

    # --- Camera view: "side" (default) or "front" (PRD clarified decision) ---
    # 3 of 4 scored params (raised-foot parallel, grounded-leg perpendicular, inter-leg
    # split) are most reliable from the side; head-yaw ("look front") degrades gracefully
    # in side view and is down-weighted there (see scoring.py head_front handling).
    view: str = "side"

    report_metadata: ReportMetadata | None = None
