# Knee Peak Frame Extraction & Scoring

Detect kadam tal peak frames, score posture against ideal form, and export results as JSON.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: tune DIFFICULTY
```

## Run

```bash
python main.py
python main.py --difficulty 4   # stricter scoring
```

## Scoring (each peak frame out of 10)

Each kadam tal (one peak = one kadam tal) is scored on four equal-weight criteria:

| Criterion | Ideal |
|-----------|-------|
| Peak leg knee angle | 90° (thigh to shin) |
| Peak leg foot angle | 90° (shin to foot) |
| Grounded leg | Straight (~180° at knee) |
| Hands | Straight arms (~180° at elbow) |

Score drops as measured angles deviate from ideal. Use `--difficulty` (0–5) or `DIFFICULTY` in `.env` to control tolerance — higher = stricter.

## JSON output

```json
{
  "video_name": "drill.mp4",
  "difficulty": 2.0,
  "summary": {
    "kadam_tal_count": 10,
    "total_score": 67.5,
    "max_possible_score": 100,
    "average_score_per_kadam_tal": 6.75
  },
  "peak_frames": [
    {
      "rank": 1,
      "frame_index": 10,
      "peak_leg": "left",
      "knee_angle_deg": 79.88,
      "foot_angle_deg": 123.07,
      "grounded_knee_angle_deg": 161.15,
      "score": {
        "total": 6.75,
        "peak_knee_angle": 8.2,
        "peak_foot_angle": 5.1,
        "grounded_leg": 7.0,
        "hands": 6.7
      }
    }
  ]
}
```

## Outputs

- `output/<video_name>/results.json`
- `output/<video_name>/peak_frames/` — annotated peak frame images with score overlay
- `output/<video_name>/kadam_tal_report.pdf` — PDF report (auto-generated after analysis)

## PDF report

The PDF report is generated automatically when you run `python main.py`. You can also generate it separately:

```bash
python generate_report.py --results "output/<video_name>/results.json"
```

The report includes:
- Header: **Kadam Tal**, person ID, kadam tal count, average score
- Per-frame table with frame image, individual score, and parameter score breakdown
