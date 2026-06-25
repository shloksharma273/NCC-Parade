# Product Requirements Document (PRD)

## Product Name
Salute Detection from Video using MediaPipe

## Objective
Build a computer vision pipeline that processes videos from the `data/` folder, analyzes each frame using MediaPipe, and returns frames where the distance between the **right-hand forefinger** and **eyebrows** is minimum (strongest salute posture candidates).

## Problem Statement
Manual review of videos to identify salute moments is slow and inconsistent. We need an automated method that can:
- Read local video files.
- Analyze every frame.
- Detect relevant body landmarks (face + hands).
- Score each frame based on geometric proximity between right forefinger and eyebrow region.
- Return the best matching frames for downstream review or model training.

## Scope

### In Scope
- Input videos from `data/` directory.
- Frame-by-frame processing.
- Landmark detection with MediaPipe:
  - Face landmarks (including eyebrow points).
  - Hand landmarks (including right index fingertip).
  - Optional pose landmarks for debugging/validation.
- Per-frame distance computation:
  - Distance between right index fingertip and eyebrow reference point(s).
- Ranking and selecting candidate salute frames.
- Exporting outputs:
  - Frame images.
  - Metadata (frame number, timestamp, distance, confidence).

### Out of Scope (Phase 1)
- Real-time webcam inference.
- Multi-person tracking or identity assignment.
- Full gesture classification beyond salute proximity rule.
- Model training/fine-tuning.
- Cloud deployment/API hosting.

## Users and Use Cases

### Primary User
Developer/analyst building a salute detection dataset and validation workflow.

### Core Use Cases
- Given a video in `data/`, extract top-N frames where right forefinger is closest to eyebrow region.
- Review selected frames visually and verify salute instances.
- Run pipeline on multiple videos and compare outputs.

## Functional Requirements

### FR1: Video Ingestion
- System shall scan `data/` for supported video formats (`.mp4`, `.mov`, `.avi`, configurable).
- System shall process one or multiple input videos per run.

### FR2: Frame Extraction
- System shall decode each video frame-by-frame in temporal order.
- System shall preserve frame index and timestamp for each processed frame.
- System shall support optional frame skipping (`every_k_frames`) for performance tuning.

### FR3: Landmark Detection
- System shall run MediaPipe per frame to detect:
  - Face mesh landmarks.
  - Hand landmarks with left/right handedness.
- System shall identify:
  - Right hand index fingertip landmark.
  - Left and right eyebrow landmark points from face mesh.
- If required landmarks are missing in a frame, frame shall be marked invalid and skipped from scoring.

### FR4: Distance Computation
- System shall compute a normalized Euclidean distance score between:
  - Right index fingertip point.
  - Eyebrow anchor point (or midpoint of selected eyebrow landmarks).
- Distance shall be normalized by a face-scale metric (e.g., inter-eye distance) to improve robustness across depth/zoom.
- Lower score means stronger salute candidate.

### FR5: Candidate Selection
- System shall rank valid frames by ascending normalized distance.
- System shall return:
  - Top-N minimum-distance frames.
  - Optional contiguous-window suppression to avoid near-duplicate adjacent frames.

### FR6: Output Generation
- For each selected frame, system shall save:
  - Annotated frame image (landmarks and measured segment).
  - Raw frame image (optional toggle).
- System shall write a structured output file (`results.json` / `results.csv`) containing:
  - `video_name`
  - `frame_index`
  - `timestamp_ms`
  - `distance_raw`
  - `distance_normalized`
  - `detection_confidence`
  - `output_image_path`

### FR7: CLI Execution
- System shall expose a command-line interface:
  - Input: video path or folder.
  - Config: top-N, frame-skip, confidence threshold, output directory.
  - Output: summary statistics and artifact paths.

## Non-Functional Requirements
- **Accuracy:** At least 90% of top-10 returned frames should visually correspond to salute-like posture on test videos.
- **Performance:** Process 720p video at >= 5 FPS on a standard laptop CPU (no GPU requirement for Phase 1).
- **Reliability:** Pipeline should not crash on occasional detection failures; it should skip invalid frames gracefully.
- **Reproducibility:** Same input/config should produce deterministic ranked outputs.
- **Maintainability:** Modular code split into ingestion, detection, scoring, and export components.

## Technical Design Notes

### Suggested Stack
- Python 3.10+
- OpenCV for video decoding and frame I/O.
- MediaPipe Tasks/Solutions for face + hand landmarks.
- NumPy/Pandas for computation and result management.

### Landmark Mapping (Initial Proposal)
- Right index fingertip: MediaPipe Hand landmark `INDEX_FINGER_TIP`.
- Eyebrow anchor:
  - Option A: midpoint of key right eyebrow landmarks.
  - Option B: minimum distance to any eyebrow landmark among selected set.
- Choose one approach and keep configurable for experiments.

### Distance Formula
- Raw distance: `d = ||p_finger - p_eyebrow||`.
- Normalized distance: `d_norm = d / ||p_left_eye_center - p_right_eye_center||`.

## Data Flow
1. Load video file from `data/`.
2. Iterate through frames.
3. Run MediaPipe detection on frame.
4. Extract right index fingertip + eyebrow landmarks.
5. Compute normalized distance.
6. Store frame metrics.
7. Rank frames by minimum distance.
8. Save top candidates and metadata.

## Configuration
- `input_dir`: default `data/`
- `output_dir`: default `output/`
- `top_n`: default `10`
- `every_k_frames`: default `1`
- `min_detection_confidence`: default `0.5`
- `save_annotated_frames`: default `true`
- `save_raw_frames`: default `false`
- `temporal_nms_window`: default `5` frames

## Acceptance Criteria
- Running the pipeline against `data/front_salute.mp4` and `data/side_salute.mp4` produces:
  - A ranked output file for each video.
  - At least top-10 candidate frame images per video.
  - Metadata with frame index and distance values.
- Top-ranked frames must show right forefinger closest to eyebrow region in visual inspection.
- System handles frames with missing hand/face landmarks without terminating.

## Validation Plan
- Qualitative review:
  - Manually inspect top-N outputs on both sample videos.
- Quantitative checks:
  - Compare distance curve across timeline; minima should align with visible salute gesture.
  - Measure proportion of true salute frames in top-N.
- Failure analysis:
  - Record frames where handedness is misclassified or eyebrows are occluded.

## Risks and Mitigations
- **Handedness confusion:** Cross-check wrist/elbow orientation using pose landmarks when uncertain.
- **Occlusion or motion blur:** Use temporal smoothing across neighboring frames.
- **Camera angle variation:** Use face-normalized distance and configurable eyebrow anchor strategy.
- **Multiple people in frame:** Restrict to highest-confidence face-hand pair in Phase 1.

## Milestones
- **M1:** Baseline pipeline (ingest -> detect -> score -> rank) on single video.
- **M2:** Batch processing for all videos in `data/`.
- **M3:** Output artifacts + CLI options + logging.
- **M4:** Validation report and threshold tuning on sample videos.

## Future Enhancements
- Add explicit salute classifier (sequence model) after candidate frame mining.
- Add temporal gesture segmentation (start/hold/end of salute).
- Support real-time stream processing.
- Build simple UI for visual review.
