"""Tez Chal (quick-march) drill detection package.

Key frames are the step extremes of a quick march: the frames where the angle
between the two legs (hip->ankle vectors) is at a LOCAL MAXIMUM, i.e. one leg is
driven forward / knee raised and the other trails, so the legs are maximally
split. Mirrors the slow_march / kadam_tal package layout: extract per-frame
landmarks -> detect key frames (inter-leg-angle maxima) -> annotate + emit
results.json (+ a montage of the detected key frames for quick review).

Each key frame is scored /10 on three parameters, each held ideally ALWAYS and
graded by how far the pose deviates:
  1. arms_straight -> both elbows ~180 deg
  2. legs_straight -> both knees  ~180 deg
  3. fist_closed   -> fingers curled toward the wrist (IMAGE-mode hand pass)
The frame total is their equal-weighted mean; the overall score is the average
across key frames. A PDF report (grade banner + per-key-frame breakdown) is
emitted alongside results.json, mirroring slow_march / kadam_tal.
"""
