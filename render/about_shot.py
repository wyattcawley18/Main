"""Still for the About section: an 85mm close-up of the pint from the hero set.

usage: python about_shot.py OUT.png [samples]
Builds the hero scene via scene.py (rendering no frames), then re-frames.
"""
import runpy
import sys
from pathlib import Path

out = sys.argv[1]
samples = sys.argv[2] if len(sys.argv) > 2 else "160"
sys.argv = ["scene.py", "--out", "/tmp", "--frames", "0:0", "--w", "1200", "--h", "1500", "--samples", samples]
ns = runpy.run_path(str(Path(__file__).with_name("scene.py")))

bpy = ns["bpy"]
GX, GY = ns["GX"], ns["GY"]
ns["set_frame"](36)
cam, target, focus = ns["cam"], ns["target"], ns["focus"]
cam.location = (GX - 0.10, GY - 0.36, 0.205)
target.location = (GX - 0.002, GY, 0.118)
focus.location = (GX - 0.014, GY - 0.034, 0.128)
cam.data.lens = 85
cam.data.dof.aperture_fstop = 2.4
scene = bpy.context.scene
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("ABOUT DONE", out)
