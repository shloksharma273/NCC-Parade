"""Baju Swing drill detection.

Detects arm-swing extremes (front-back marching swing) as key frames and scores
each swing on arm straightness, swing spread, leg straightness, fist closure and
thumb-on-top. Mirrors the kadam_tal peak-detection pipeline and reuses the salute
IMAGE-mode Holistic pass for hand landmarks. See MATH.md for the full mathematics.
"""
