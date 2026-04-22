from __future__ import annotations

import os
import tempfile
from pathlib import Path

import cv2
import numpy as np

import config


def preprocess_frames(frame_paths: list[str]) -> tuple[list[str], str | None]:
    if not config.OCR_PREPROCESS:
        return frame_paths, None

    output_dir = tempfile.mkdtemp(prefix="animetrans_preproc_")
    out_paths: list[str] = []

    for path in frame_paths:
        img = cv2.imread(path)
        if img is None:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        h, w = gray.shape[:2]
        if h < 100:
            gray = cv2.resize(
                gray, None, fx=2, fy=2,
                interpolation=cv2.INTER_CUBIC,
            )

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        fname = Path(path).name
        out_path = os.path.join(output_dir, fname)
        cv2.imwrite(out_path, enhanced)
        out_paths.append(out_path)

    out_paths.sort()
    return out_paths, output_dir
