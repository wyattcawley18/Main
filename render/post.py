"""Grade rendered frames: morning halation, honey split-tone, soft S-curve, vignette.

usage: python post.py IN_DIR OUT_DIR
Reads 16-bit PNGs written by scene.py and writes graded 16-bit PNGs.
Grain is deliberately not baked in (the site overlays it in CSS) so the
footage stays compressible.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter, zoom

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def load16(p):
    a = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)[..., 2::-1].astype(np.float32)
    return a / (65535.0 if a.dtype != np.uint8 and a.max() > 255 else 255.0)


def save16(a, p):
    u = (np.clip(a, 0, 1) * 65535.0 + 0.5).astype(np.uint16)
    cv2.imwrite(str(p), u[..., ::-1])


def bloom(lin):
    """Sunlight halation: the brightest stripes and steam bleed warm light."""
    h, w, _ = lin.shape
    lum = lin @ LUMA
    knee = np.clip((lum - 0.50) / 0.8, 0, None)[..., None] ** 1.5
    bright = lin * np.minimum(knee, 4.0)
    small = bright[::4, ::4]
    out = np.zeros_like(lin)
    for sigma, wgt in ((2.5, 0.10), (9.0, 0.10), (28.0, 0.08)):
        b = np.stack([gaussian_filter(small[..., c], sigma) for c in range(3)], -1)
        b = zoom(b, (h / b.shape[0], w / b.shape[1], 1), order=1)
        out += wgt * b
    return out * np.array([1.08, 0.95, 0.78], np.float32)


def grade(a, cx=0.57, cy=0.55):
    lin = a ** 2.2
    lin = lin + bloom(lin)
    a = np.clip(lin, 0, None) ** (1 / 2.2)
    lum = (a @ LUMA)[..., None]
    # split tone: neutral-cool shadows, honey highlights
    shadow = (1 - np.clip(lum * 2.4, 0, 1)) ** 2
    a = a + shadow * np.array([-0.004, 0.002, 0.012], np.float32)
    high = np.clip((lum - 0.5) * 2.0, 0, 1)
    a = a + high * np.array([0.024, 0.010, -0.022], np.float32)
    # soft S-curve, lifted blacks like print stock
    s = a * a * (3 - 2 * a)
    a = a * 0.68 + s * 0.32
    a = 0.014 + a * 0.98
    # saturation +8%
    lum = (a @ LUMA)[..., None]
    a = lum + (a - lum) * 1.08
    # vignette around the mug
    h, w, _ = a.shape
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (x - w * cx) / (w * 0.5)
    ny = (y - h * cy) / (h * 0.5) * (h / w) * 1.6
    r = np.sqrt(nx * nx + ny * ny)
    a = a * (1 - 0.30 * np.clip(r, 0, 1.6) ** 2.4 / 1.6 ** 2.4 * 1.6)[..., None]
    return np.clip(a, 0, 1)


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    frames = sorted(src.glob("f*.png"))
    for i, p in enumerate(frames):
        save16(grade(load16(p)), dst / p.name)
        if i % 24 == 0:
            print("graded", p.name, flush=True)


if __name__ == "__main__":
    main()
