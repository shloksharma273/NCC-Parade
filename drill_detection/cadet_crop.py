"""Crop each frame to the cadet before it goes into MediaPipe.

The cadet often fills only a small part of the frame (a 1920x1080 parade ground
with a figure ~20% of its height). Holistic finds the person on a heavily
downscaled copy of the whole frame, so a small cadet is found less reliably and
an instructor walking past can be tracked instead. Cropping to a padded box
around the cadet lets the detector see them large.

Usage in a pipeline loop::

    tracker = CadetTracker(padding=config.crop_padding, enabled=config.crop_to_cadet)
    view = place_on_canvas(frame_bgr, tracker.box_for(width, height), canvas=(width, height))
    result = holistic.detect_for_video(to_mp_image(view.image), ts)
    uncrop_result(result, view)         # landmarks back in full-frame coordinates
    tracker.update(result.pose_landmarks, width, height)

``uncrop_result`` rewrites the landmarks in place, so everything downstream
(metrics, scoring, annotation on the full-resolution frame) is unchanged.

Holistic requires every image fed to one landmarker to have the same size
(its segmentation smoothing compares consecutive masks, even in IMAGE mode),
while the crop box changes size from frame to frame. So the crop is
letterboxed onto a canvas the size of the original frame: the full-frame
fallback (before the cadet is found) is then exactly the uncropped input, and
a crop is scaled up to fill the frame. ``canvas=None`` returns the bare crop.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np



@dataclass(frozen=True)
class CropBox:
    """Pixel box ``[x0, x1) x [y0, y1)`` inside a ``full_w x full_h`` frame."""

    x0: int
    y0: int
    x1: int
    y1: int
    full_w: int
    full_h: int

    @classmethod
    def full(cls, width: int, height: int) -> "CropBox":
        return cls(0, 0, width, height, width, height)

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    @property
    def is_full(self) -> bool:
        return self.x0 == 0 and self.y0 == 0 and self.x1 == self.full_w and self.y1 == self.full_h

    def crop(self, frame: np.ndarray) -> np.ndarray:
        if self.is_full:
            return frame
        # Contiguous copy: mp.Image rejects strided views.
        return np.ascontiguousarray(frame[self.y0 : self.y1, self.x0 : self.x1])

    def to_dict(self) -> dict:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}


@dataclass(frozen=True)
class CropView:
    """The image actually handed to MediaPipe, and how it maps back to the frame.

    ``image`` holds the crop scaled by ``scale`` and offset by ``(pad_x, pad_y)``
    inside a ``canvas_w x canvas_h`` image.
    """

    image: np.ndarray
    box: CropBox
    scale: float
    pad_x: float
    pad_y: float
    canvas_w: int
    canvas_h: int

    @property
    def is_identity(self) -> bool:
        return self.box.is_full and self.scale == 1.0 and self.pad_x == 0 and self.pad_y == 0


def place_on_canvas(frame: np.ndarray, box: CropBox, canvas: tuple[int, int] | None) -> CropView:
    """Crop ``frame`` to ``box``; with ``canvas=(w, h)`` set, letterbox the crop
    onto a black image of that size (aspect preserved), else return it as is."""
    crop = box.crop(frame)
    if canvas is None or (box.is_full and canvas == (box.full_w, box.full_h)):
        return CropView(crop, box, 1.0, 0.0, 0.0, box.width, box.height)

    canvas_w, canvas_h = canvas
    scale = min(canvas_w / box.width, canvas_h / box.height)
    new_w = max(1, round(box.width * scale))
    new_h = max(1, round(box.height * scale))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(crop, (new_w, new_h), interpolation=interp)
    pad_x, pad_y = (canvas_w - new_w) // 2, (canvas_h - new_h) // 2
    image = np.zeros((canvas_h, canvas_w, frame.shape[2]), dtype=frame.dtype)
    image[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
    return CropView(image, box, scale, float(pad_x), float(pad_y), canvas_w, canvas_h)


def _uncrop_landmarks(landmarks, view: CropView) -> None:
    box = view.box
    for lm in landmarks:
        # canvas-normalised -> canvas px -> crop px -> full-frame px -> full-normalised
        lm.x = ((lm.x * view.canvas_w - view.pad_x) / view.scale + box.x0) / box.full_w
        lm.y = ((lm.y * view.canvas_h - view.pad_y) / view.scale + box.y0) / box.full_h
        # z shares x's scale (normalised by image width).
        if lm.z is not None:
            lm.z = lm.z * view.canvas_w / view.scale / box.full_w


def uncrop_result(result, view: CropView):
    """Map a Holistic result's normalised landmarks from the canvas back to the
    full frame, in place. World landmarks are metric and need no change."""
    if view.is_identity:
        return result
    for name in ("pose_landmarks", "face_landmarks", "left_hand_landmarks", "right_hand_landmarks"):
        landmarks = getattr(result, name, None)
        if landmarks:
            _uncrop_landmarks(landmarks, view)
    return result


def box_from_pose(pose_landmarks, width: int, height: int, padding: float,
                  min_aspect: float = 0.75) -> CropBox | None:
    """Padded box around the pose landmarks (full-frame normalised coords).

    ``padding`` is a fraction of the body height added on every side; limbs
    swing out between frames, so it is deliberately generous. The box is also
    widened to at least ``min_aspect`` x its height so a side-on stride or a
    swinging arm is not clipped.
    """
    if not pose_landmarks:
        return None
    xs = np.array([lm.x for lm in pose_landmarks], dtype=float) * width
    ys = np.array([lm.y for lm in pose_landmarks], dtype=float) * height
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    body_h = max(y1 - y0, 1.0)
    pad = padding * body_h
    x0, x1, y0, y1 = x0 - pad, x1 + pad, y0 - pad, y1 + pad

    min_w = min_aspect * (y1 - y0)
    if x1 - x0 < min_w:
        cx = (x0 + x1) / 2
        x0, x1 = cx - min_w / 2, cx + min_w / 2

    x0, y0 = max(0, int(np.floor(x0))), max(0, int(np.floor(y0)))
    x1, y1 = min(width, int(np.ceil(x1))), min(height, int(np.ceil(y1)))
    if x1 - x0 < 16 or y1 - y0 < 16:
        return None
    return CropBox(x0, y0, x1, y1, width, height)


def pose_at_edge(pose_landmarks, margin: float = 0.02) -> bool:
    """Whether any landmark lies within ``margin`` of (or beyond) the frame edge,
    i.e. the cadet is walking in or out and only partly visible."""
    lo, hi = margin, 1.0 - margin
    return any(not (lo <= lm.x <= hi and lo <= lm.y <= hi) for lm in pose_landmarks)


class CadetTracker:
    """Follows the cadet's box from frame to frame.

    * The full frame is used until the cadet has been found on ``min_hits``
      consecutive frames, so one spurious detection cannot start a bad crop.
    * A crop is not *started* while the pose touches the frame edge (cadet
      walking in, partly visible): that pose is unreliable and a crop built
      from it can cut the cadet off. Once cropping, the box just clamps at the
      border instead: jumping back to the full frame mid-track throws off
      MediaPipe's own tracking, and it then loses the cadet for many frames.
    * Growing edges move out immediately (a kick or arm swing must never be
      clipped); shrinking edges ease in with ``smoothing`` so the crop does not
      jitter, which would also confuse MediaPipe's own frame-to-frame tracking.
    * After ``max_misses`` frames with no pose, fall back to the full frame to
      re-acquire the cadet.
    """

    def __init__(self, padding: float = 0.25, enabled: bool = True,
                 smoothing: float = 0.3, max_misses: int = 3, min_hits: int = 5) -> None:
        self.padding = padding
        self.enabled = enabled
        self.smoothing = smoothing
        self.max_misses = max_misses
        self.min_hits = min_hits
        self._box: CropBox | None = None
        self._misses = 0
        self._hits = 0

    def box_for(self, width: int, height: int) -> CropBox:
        if not self.enabled or self._box is None:
            return CropBox.full(width, height)
        return self._box

    def update(self, pose_landmarks, width: int, height: int) -> CropBox | None:
        """Feed the (full-frame) pose of the frame just processed. Returns the
        tight box for *this* frame, or None when there is no usable pose (none
        found, or the cadet is at the frame edge)."""
        if not self.enabled:
            return None
        target = box_from_pose(pose_landmarks, width, height, self.padding)
        if target is None:
            self._hits = 0
            self._misses += 1
            if self._misses >= self.max_misses:
                self._box = None
            return None
        if self._box is None and pose_at_edge(pose_landmarks):
            self._hits = 0
            return None

        self._misses = 0
        self._hits += 1
        prev = self._box
        if prev is None:
            if self._hits >= self.min_hits:
                self._box = target
            return target

        a = self.smoothing

        def ease(old: int, new: int, grow: bool) -> int:
            return new if grow else int(round(old + a * (new - old)))

        self._box = CropBox(
            ease(prev.x0, target.x0, target.x0 < prev.x0),
            ease(prev.y0, target.y0, target.y0 < prev.y0),
            ease(prev.x1, target.x1, target.x1 > prev.x1),
            ease(prev.y1, target.y1, target.y1 > prev.y1),
            width, height,
        )
        return target


def nearest_box(boxes: dict[int, CropBox], frame_index: int, max_gap: int = 30) -> CropBox | None:
    """The recorded box closest in time to ``frame_index`` (within ``max_gap``)."""
    if not boxes:
        return None
    if frame_index in boxes:
        return boxes[frame_index]
    best = min(boxes, key=lambda i: abs(i - frame_index))
    return boxes[best] if abs(best - frame_index) <= max_gap else None
