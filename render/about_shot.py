"""Still for the About section: biscuits and butter on the banded plate, the mug
behind, slat light across the table. Same set as the hero film.

usage: python about_shot.py OUT.png [samples]
Builds the hero scene via scene.py (rendering no frames), then re-frames.
"""
import runpy
import sys
from pathlib import Path

out = sys.argv[1]
samples = sys.argv[2] if len(sys.argv) > 2 else "128"
sys.argv = ["scene.py", "--out", "/tmp", "--frames", "0:0", "--w", "1200", "--h", "1500", "--samples", samples]
ns = runpy.run_path(str(Path(__file__).with_name("scene.py")))

bpy = ns["bpy"]
PX, PY = ns["PX"], ns["PY"]
ns["set_frame"](40)
cam, target, focus = ns["cam"], ns["target"], ns["focus"]
cam.location = (PX + 0.035, PY - 0.255, 0.165)
target.location = (PX - 0.040, PY + 0.07, 0.035)
focus.location = (PX - 0.028, PY + 0.010, 0.040)
cam.data.lens = 55
cam.data.dof.aperture_fstop = 3.2
scene = bpy.context.scene
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("ABOUT DONE", out)
