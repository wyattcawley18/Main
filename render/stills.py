"""Poster stills for the hero, from graded frame 0 (matches the video's first frame).

usage: python stills.py GRADED_DIR SITE_DIR
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

CROP_X = 866  # keep in sync with encode.sh


def load(p):
    a = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)[..., 2::-1].astype(np.float32)
    a = a / (65535.0 if a.max() > 255 else 255.0)
    rng = np.random.default_rng(0)
    a = a * 255.0 + rng.uniform(-0.5, 0.5, a.shape)  # dither the 16-bit -> 8-bit step
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)[..., :3])


def save_all(im, base):
    im.save(f"{base}.avif", quality=58, speed=4)
    im.save(f"{base}.webp", quality=78, method=6)
    im.save(f"{base}.jpg", quality=80, optimize=True, progressive=True)


def main():
    graded, site = Path(sys.argv[1]), Path(sys.argv[2])
    media = site / "media"
    media.mkdir(parents=True, exist_ok=True)
    f0 = load(graded / "f0000.png")
    save_all(f0, media / "poster-1920")
    save_all(f0.resize((1280, 720), Image.LANCZOS), media / "poster-1280")
    save_all(f0.crop((CROP_X, 0, CROP_X + 608, 1080)), media / "poster-portrait")
    # mid-loop frame: soft backdrop for the visit section, and the OG card source
    f120 = load(graded / "f0120.png")
    f120.resize((960, 540), Image.LANCZOS).filter(ImageFilter.GaussianBlur(3)).save(
        media / "backdrop.jpg", quality=70, optimize=True, progressive=True)
    f120.save(graded.parent / "og-src.jpg", quality=93)


if __name__ == "__main__":
    main()
