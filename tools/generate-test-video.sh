#!/usr/bin/env bash
# 解像度 (1080/720/480) × フレームレート (29.97p/59.94p/30p/60p) の全 12 組み合わせを
# 1 本のテスト映像に連結し、それを 4 本に複製して出力する。
#
# 使い方: tools/generate-test-video.sh [出力ディレクトリ] [各セグメント秒数]
#   既定: out/test-video, 3 秒
# 必要: ffmpeg (drawtext 有効)
set -euo pipefail

OUT_DIR="${1:-out/test-video}"
SEG_SEC="${2:-3}"
COPIES=4
SEG_DIR="$OUT_DIR/segments"
MASTER="$OUT_DIR/master.mp4"
FONT="${FONT:-/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf}"

RESOLUTIONS=("1920x1080" "1280x720" "854x480")
FRAMERATES=("30000/1001" "60000/1001" "30" "60")

command -v ffmpeg >/dev/null || { echo "ffmpeg が見つかりません" >&2; exit 1; }
mkdir -p "$SEG_DIR"

label_fps() {
  case "$1" in
    30000/1001) echo "29.97p" ;;
    60000/1001) echo "59.94p" ;;
    *) echo "${1}p" ;;
  esac
}

i=0
for res in "${RESOLUTIONS[@]}"; do
  for fps in "${FRAMERATES[@]}"; do
    i=$((i + 1))
    h="${res#*x}"
    fl="$(label_fps "$fps")"
    seg="$SEG_DIR/$(printf '%02d' "$i")_${h}p_${fl}.mp4"
    echo "[$i/12] ${h}p ${fl} -> $seg"
    # 各セグメントはネイティブ解像度・フレームレートで生成し、
    # 連結用に 1920x1080 へレターボックス配置する (フレームレートは変換しない)。
    ffmpeg -hide_banner -loglevel error -y \
      -f lavfi -i "testsrc2=size=${res}:rate=${fps}:duration=${SEG_SEC}" \
      -f lavfi -i "sine=frequency=1000:sample_rate=48000:duration=${SEG_SEC}" \
      -vf "drawtext=fontfile=${FONT}:text='${h}p ${fl}':fontsize=h/8:fontcolor=white:box=1:boxcolor=black@0.6:x=(w-tw)/2:y=h/10,\
drawtext=fontfile=${FONT}:text='frame %{n}  t=%{pts\:hms}':fontsize=h/16:fontcolor=white:box=1:boxcolor=black@0.6:x=(w-tw)/2:y=h*0.8,\
scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1" \
      -r "$fps" -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p \
      -c:a aac -b:a 128k -shortest "$seg"
  done
done

echo "連結 -> $MASTER"
# フレームレートが混在するため concat フィルタで連結し、タイムスタンプは変換せず VFR のまま保持する。
inputs=()
chain=""
n=0
for res in "${RESOLUTIONS[@]}"; do
  for fps in "${FRAMERATES[@]}"; do
    n=$((n + 1))
    inputs+=(-i "$SEG_DIR/$(printf '%02d' "$n")_${res#*x}p_$(label_fps "$fps").mp4")
    chain+="[$((n - 1)):v][$((n - 1)):a]"
  done
done
ffmpeg -hide_banner -loglevel error -y "${inputs[@]}" \
  -filter_complex "${chain}concat=n=${n}:v=1:a=1[v][a]" -map "[v]" -map "[a]" \
  -fps_mode passthrough -video_track_timescale 120000 \
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -movflags +faststart "$MASTER"

for n in $(seq 1 "$COPIES"); do
  cp "$MASTER" "$OUT_DIR/output-${n}.mp4"
done

echo "完了: $OUT_DIR/output-1..${COPIES}.mp4"
ffprobe -hide_banner -v error -show_entries format=duration -show_entries stream=codec_type,width,height,r_frame_rate \
  -of default=noprint_wrappers=1 "$MASTER"
