"""Tez Chal (quick-march) drill detection package.

Key frames are the step extremes of a quick march: the frames where the angle
between the two legs (hip->ankle vectors) is at a LOCAL MAXIMUM, i.e. one leg is
driven forward / knee raised and the other trails, so the legs are maximally
split. Mirrors the slow_march / kadam_tal package layout: extract per-frame
landmarks -> detect key frames (inter-leg-angle maxima) -> annotate + emit
results.json (+ a montage of the detected key frames for quick review).

Scoring/report generation is a deliberate follow-up step (HOOK in pipeline.py);
this first cut lands the key-frame detection and its visualisation.
"""
