"""Hill March drill detection package.

Key frames are the step extremes of a hill march: the frames where the SEPARATION
between the two legs is at a LOCAL MAXIMUM (measured as the angle between the two
hip->ankle leg vectors, which is scale-invariant and ties directly to parameter 1
below). Mirrors the slow_march / kadam_tal package layout: extract per-frame
landmarks -> detect key frames (max inter-leg separation) -> score + annotate ->
emit results.json + annotated key frames + montage + PDF report.

Each key frame is scored /10 on four parameters, graded by deviation from the ideal:
  1. legs_apart  -> angle between the legs should be MORE than ~70 deg (score_by_min)
  2. arms        -> arms straight (elbows ~180 deg) AND close to the body (small
                    shoulder abduction toward the torso)
  3. legs_straight -> both knees ~180 deg
  4. head_straight -> head upright and facing front
The frame total is their equal-weighted mean; overall = average across key frames.
"""
