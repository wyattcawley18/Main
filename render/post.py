"""Grade rendered frames: bloom pyramid, split-tone, gentle S-curve, vignette.

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


def load16(p):
    a = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)[..., 2::-1].astype(np.float32)
    return a / (65535.0 if a.dtype != np.uint8 and a.max() > 255 else 255.0)


def save16(a, p):
    u = (np.clip(a, 0, 1) * 65535.0 + 0.5).astype(np.uint16)
    cv2.imwrite(str(p), u[..., ::-1])


def bloom(lin):
    h, w, _ = lin.shape
    lum = lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    knee = np.clip((lum - 0.55) / 0.9, 0, None)[..., None] ** 1.6
    bright = lin * np.minimum(knee, 4.0)
    small = bright[::4, ::4]
    out = np.zeros_like(lin)
    for sigma, wgt in ((2.0, 0.10), (7.0, 0.09), (22.0, 0.07)):
        b = np.stack([gaussian_filter(small[..., c], sigma) for c in range(3)], -1)
        b = zoom(b, (h / b.shape[0], w / b.shape[1], 1), order=1)
        out += wgt * b
    # warm halation fringe on the widest lobe
    return out * np.array([1.06, 0.96, 0.84], np.float32)


def grade(a):
    lin = a ** 2.2
    lin = lin + bloom(lin)
    a = np.clip(lin, 0, None) ** (1 / 2.2)
    lum = (a @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
    # split tone: cool haint-blue shadows, warm highlights
    shadow = (1 - np.clip(lum * 2.2, 0, 1)) ** 2
    a = a + shadow * np.array([-0.006, 0.006, 0.020], np.float32)
    high = np.clip((lum - 0.55) * 2.2, 0, 1)
    a = a + high * np.array([0.020, 0.006, -0.018], np.float32)
    # gentle S-curve and lifted blacks
    s = a * a * (3 - 2 * a)
    a = a * 0.72 + s * 0.28
    a = 0.010 + a * 0.985
    # saturation +6%
    lum = (a @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
    a = lum + (a - lum) * 1.06
    # vignette
    h, w, _ = a.shape
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (x - w * 0.56) / (w * 0.5)
    ny = (y - h * 0.48) / (h * 0.5) * (h / w) * 1.6
    r = np.sqrt(nx * nx + ny * ny)
    a = a * (1 - 0.32 * np.clip(r, 0, 1.6) ** 2.4 / 1.6 ** 2.4 * 1.6)[..., None]
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
