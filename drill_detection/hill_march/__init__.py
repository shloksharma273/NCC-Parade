"""Hill March drill detection package.

Key frames are the kicks of a hill march: the frames where the KICK ANGLE is at a
LOCAL MAXIMUM. The kick angle is how far the kicked leg is raised from vertical,
derived from how high its ankle rises (vertical image distances are not
foreshortened, so it reads the same from the front and the side), and ties
directly to parameter 1 below. Mirrors the slow_march / kadam_tal package layout:
extract per-frame landmarks -> detect key frames (kick peaks) -> score + annotate ->
emit results.json + annotated key frames + montage + PDF report.

Each key frame is scored /10 on four parameters, graded by deviation from the ideal:
  1. legs_apart  -> kick angle should be MORE than ~60 deg (score_by_min)
  2. arms        -> arms straight (elbows ~180 deg) AND close to the body (small
                    shoulder abduction toward the torso); front view scores
                    "close to body" only
  3. legs_straight -> both knees ~180 deg
  4. head_straight -> head upright and facing front
The frame total is their equal-weighted mean; overall = average across key frames.
"""
