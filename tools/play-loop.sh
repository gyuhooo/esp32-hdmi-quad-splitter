#!/usr/bin/env bash
# 再生機 (Raspberry Pi / Linux ミニ PC) でテスト映像を HDMI へループ出力する。
#
# 使い方:
#   tools/play-loop.sh <master.mp4>            # 固定モードで連結済み映像をループ
#   tools/play-loop.sh --native <segmentsディレクトリ>  # セグメントごとに出力モードを切替してループ
# 環境変数:
#   CONNECTOR=HDMI-A-1  (drm コネクタ名。`modetest -c` で確認)
# 必要: mpv (drm 出力対応)
set -euo pipefail

CONNECTOR="${CONNECTOR:-HDMI-A-1}"
command -v mpv >/dev/null || { echo "mpv が見つかりません" >&2; exit 1; }

if [[ "${1:-}" == "--native" ]]; then
  dir="${2:?segments ディレクトリを指定}"
  while true; do
    for f in "$dir"/*.mp4; do
      # ファイル名例: 05_720p_29.97p.mp4 -> 高さ 720, fps 29.97
      base="$(basename "$f" .mp4)"
      h="${base#*_}"; h="${h%%p_*}"
      fps="${base##*_}"; fps="${fps%p}"
      case "$h" in
        1080) mode="1920x1080@${fps}" ;;
        720)  mode="1280x720@${fps}" ;;
        480)  mode="720x480@${fps}" ;;
        *)    mode="preferred" ;;
      esac
      echo "play $f mode=$mode"
      mpv --really-quiet --vo=drm --drm-connector="$CONNECTOR" --drm-mode="$mode" \
          --fs --audio-device=auto "$f" || true
    done
  done
fi

file="${1:?master.mp4 を指定}"
exec mpv --really-quiet --vo=drm --drm-connector="$CONNECTOR" \
     --loop-file=inf --fs --audio-device=auto "$file"
