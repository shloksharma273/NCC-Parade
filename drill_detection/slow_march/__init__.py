"""Slow March (slow-parade march) drill detection package.

Detects every step extreme (local maximum of the inter-leg angle) in a slow-march
clip, scores each key frame /10 on four drill parameters (arms straight, look front,
grounded leg perpendicular & straight, raised foot parallel — mandatory), and emits a
results.json + annotated key frames + PDF report. Mirrors the kadam_tal package.
"""
