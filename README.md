# Salute Detection Pipeline

This project detects salute candidate frames in videos by minimizing the distance between the **right index fingertip** and the **eyebrow anchor** using MediaPipe landmarks.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set drill difficulty in `.env` (or copy from `.env.example`):

```bash
# 0 = lenient, 5 = strict
DIFFICULTY=2
```

You can override per run with `--difficulty 4`.

On first run, the pipeline downloads the MediaPipe `holistic_landmarker.task` model into `models/`.

## Run

Default run (reads videos from `data/` and writes to `output/`):

```bash
python main.py
```

Example with custom options:

```bash
python main.py \
  --input data \
  --output-dir output \
  --top-n 10 \
  --every-k-frames 1 \
  --min-detection-confidence 0.5 \
  --temporal-nms-window 5 \
  --save-raw-frames
```

## Outputs

Per video, the pipeline creates:
- `output/<video_name>/results.json`
- `output/<video_name>/results.csv`
- `output/<video_name>/annotated_frames/` (unless disabled)
- `output/<video_name>/raw_frames/` (optional)

Each result row contains:
- `frame_index`
- `timestamp_ms`
- `distance_raw`
- `distance_normalized`
- `detection_confidence`
- `output_image_path`

## Front salute posture analysis

For front-facing salute videos (filename contains `front`), the pipeline scores the top 5 selected frames on:

1. Right hand fingers and thumb joined
2. Right elbow angle (target: 45°)
3. Feet together (medial shoe contact) and foot angle (target: 30°)
4. Left hand attached to the body

Each check is scored out of 10 with equal weights (0.25 each) for a cumulative `weighted_score` out of 10.

Outputs:
- `output/<video_name>/posture_analysis.csv`
- `output/<video_name>/posture_analysis.json`
- `output/<video_name>/posture_annotated_frames/`

