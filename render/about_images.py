"""Grade the About still with the film's look and write responsive sizes.

usage: python about_images.py about.png SITE_DIR
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from post import grade, load16


def main():
    src, site = Path(sys.argv[1]), Path(sys.argv[2])
    a = grade(load16(src))
    a = a * 255.0 + np.random.default_rng(1).uniform(-0.5, 0.5, a.shape)
    im = Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8))
    for w in (800, 1200):
        r = im.resize((w, w * im.height // im.width), Image.LANCZOS)
        base = site / "img" / f"about-{w}"
        r.save(f"{base}.avif", quality=56, speed=4)
        r.save(f"{base}.webp", quality=78, method=6)
        r.save(f"{base}.jpg", quality=80, optimize=True, progressive=True)


if __name__ == "__main__":
    main()
