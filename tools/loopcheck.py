"""Seam and flicker check for the hero loop.

usage: python loopcheck.py video.mp4
Prints mean absolute frame-to-frame difference (0-255 scale) for every step,
including the wrap from the last frame back to the first. A seamless loop has
a wrap difference in line with its neighbours; flicker shows up as spikes.
"""
import subprocess
import sys

import numpy as np

path = sys.argv[1]
w, h = 480, 270
raw = subprocess.run(
    ["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
    check=True, capture_output=True,
).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
n = len(frames)
d = np.array([np.abs(frames[(i + 1) % n] - frames[i]).mean() for i in range(n)])
inner = d[:-1]
print(f"frames={n} mean_step={inner.mean():.3f} p95={np.percentile(inner, 95):.3f} max={inner.max():.3f} (at {inner.argmax()})")
print(f"wrap {n - 1}->0 = {d[-1]:.3f}  ({d[-1] / inner.mean():.2f}x mean step)")
spikes = np.where(inner > inner.mean() + 4 * inner.std())[0]
print("spikes:", spikes.tolist()[:20])
