# 映像ソース(生成・再生)

LT86104SX は入力を複製するだけなので、Full HD 映像を作って HDMI で入力する機器が別途必要です。
ここでは「テスト映像の生成」と「その再生機」に必要なものをまとめます。

## 1. テスト映像の生成(PC で行う)

| 必要なもの | 備考 |
|---|---|
| ffmpeg / ffprobe | drawtext(libfreetype)有効ビルド。Ubuntu は `apt install ffmpeg`、Windows は gyan.dev の full ビルド |
| 等幅フォント | 既定は DejaVu Sans Mono Bold。環境変数 `FONT` で変更可 |
| bash | Windows は WSL または Git Bash |
| ディスク約 200 MB | 3 秒セグメントで master 約 30 MB × 5 本 |

```
tools/generate-test-video.sh out/test-video 3
```

生成されるもの:

- `master.mp4`: 1080p / 720p / 480p × 29.97p / 59.94p / 30p / 60p の 12 セグメントを連結した 1 本。キャンバスは 1920x1080、フレームレートは VFR で元の値を保持
- `output-1.mp4` 〜 `output-4.mp4`: master の複製(ファイルとして 4 本必要な場合用)
- `segments/`: 各組み合わせをネイティブ解像度のまま保存した個別ファイル

各フレームに「解像度 fps」ラベル、フレーム番号、タイムコードを焼き込んでいるので、4 出力のコマ落ちや遅延差を目視で確認できます。

### モード切替をネイティブでテストしたい場合

1 本のファイルに複数解像度は入らないため、master は 1080p キャンバスに拡大しています。
HDMI のモード切替(EDID ネゴシエーション、再ロック)をテストしたい場合は `segments/` のファイルを順に再生し、
再生機の出力モードをファイルに追従させます(`tools/play-loop.sh` の `--native` 参照)。

## 2. 再生機(HDMI ソース)の選定

| 候補 | 1080p60 | 59.94p の正確さ | モード切替 | 備考 |
|---|---|---|---|---|
| **Raspberry Pi 4 / 5** | ◎ | ○(KMS で 59.94 Hz 選択可) | ○ | 最小・安価。推奨 |
| ミニ PC(N100 等) | ◎ | ○ | ○ | mpv で安定。ffmpeg で生成も同じ機で可 |
| RK3588 ボード | ◎ | ○ | ○ | 将来 4 画面独立出力に移行するならこれ |
| ESP32-P4 + LT9611 | ×(1080p30 まで) | × | △ | 59.94p/60p が不可のため対象外 |

推奨は Raspberry Pi 4 または 5 です。必要なもの:

| 部品 | 備考 |
|---|---|
| Raspberry Pi 4 (2 GB 以上) または Pi 5 | Pi 5 は H.264 ハードウェアデコードがないが 1080p60 は CPU で足りる |
| microSD 16 GB 以上 | Raspberry Pi OS Lite(64bit) |
| micro HDMI → HDMI ケーブル | LT86104SX の入力へ |
| 5V 3A(Pi4) / 5V 5A(Pi5) 電源 | |
| mpv | `apt install mpv` |

### Raspberry Pi の設定

`/boot/firmware/cmdline.txt` に出力モードを固定します(1080p 59.94 Hz の例)。

```
video=HDMI-A-1:1920x1080@59.94D
```

モードを切り替えてテストする場合は固定せず、`tools/play-loop.sh --native` で mpv に切替させます。

デスクトップ不要のため DRM 直接出力を使います:

```
mpv --vo=drm --drm-connector=HDMI-A-1 --loop-file=inf --fs master.mp4
```

## 3. システム全体

```
[PC: ffmpeg で生成] --master.mp4--> [Raspberry Pi: mpv でループ再生]
                                              | HDMI 1080p
                                        [LT86104SX] ---> HDMI×4
                                              | I2C
                                           [ESP32]
```

## 4. 確認項目

- 4 出力ともフレーム番号が同時に進む(スプリッタの遅延は 1 フレーム未満)
- 29.97p ↔ 59.94p の切替でコマ落ち・テアリングがない(VFR 区間)
- モニタの情報表示で入力モードが 1080p 59.94/60 Hz と表示される
- 1 kHz テスト音が 4 出力すべてで出る
