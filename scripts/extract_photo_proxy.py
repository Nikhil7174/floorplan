"""Pull 2–8 stills from a Stray rgb.mp4 so we can exercise the photo path locally.

These frames are a development proxy, not a substitute for real iPhone stills.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def extract(video: Path, dest: Path, count: int = 6) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if n < 2:
        raise SystemExit(f"No frames in {video}")
    idxs = np.linspace(n * 0.15, n * 0.85, count).astype(int)
    written: list[Path] = []
    for i, idx in enumerate(idxs):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if not ok:
            continue
        path = dest / f"{i:02d}.jpg"
        cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        written.append(path)
    cap.release()
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/raw/single_room_photos/room"))
    parser.add_argument("--count", type=int, default=6)
    args = parser.parse_args()
    paths = extract(args.video, args.out, args.count)
    print(f"Wrote {len(paths)} stills to {args.out}")


if __name__ == "__main__":
    main()
