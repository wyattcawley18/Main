#!/usr/bin/env bash
# Encode graded frames into the web deliverables in site/media.
#   encode.sh GRADED_DIR OUT_DIR
# AV1 (10-bit, MP4) for browsers that can decode it, H.264 everywhere else.
# The portrait cut is a native-pixel 9:16 crop around the mug and its steam so
# phones get a sharp frame without decoding a full 1080p stream.
set -euo pipefail
IN=$1
OUT=$2
FPS=24
CROP_X=${CROP_X:-866}
mkdir -p "$OUT"
src=(-y -hide_banner -loglevel error -framerate "$FPS" -start_number 0 -i "$IN/f%04d.png")
if ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libsvtav1; then
  av1=(-c:v libsvtav1 -preset 4 -g 192 -pix_fmt yuv420p10le -svtav1-params tune=0 -movflags +faststart -an)
else
  av1=(-c:v libaom-av1 -cpu-used 4 -row-mt 1 -g 192 -pix_fmt yuv420p10le -movflags +faststart -an)
fi
avc=(-c:v libx264 -preset slower -profile:v high -pix_fmt yuv420p -g 48 -tune film -movflags +faststart -an)

ffmpeg "${src[@]}" "${av1[@]}" -crf 34 "$OUT/hero-1080.av1.mp4"
ffmpeg "${src[@]}" "${avc[@]}" -crf 23 -level 4.1 "$OUT/hero-1080.mp4"
ffmpeg "${src[@]}" -vf "scale=1280:720:flags=lanczos" "${av1[@]}" -crf 35 "$OUT/hero-720.av1.mp4"
ffmpeg "${src[@]}" -vf "scale=1280:720:flags=lanczos" "${avc[@]}" -crf 23 -level 3.1 "$OUT/hero-720.mp4"
ffmpeg "${src[@]}" -vf "crop=608:1080:${CROP_X}:0" "${av1[@]}" -crf 34 "$OUT/hero-portrait.av1.mp4"
ffmpeg "${src[@]}" -vf "crop=608:1080:${CROP_X}:0" "${avc[@]}" -crf 23 -level 4.0 "$OUT/hero-portrait.mp4"

ls -la "$OUT"
