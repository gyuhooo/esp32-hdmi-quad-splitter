// 出力モード定義 (MODE パラメータ -> タイミング / ピクセルクロック)
// CEA-861 準拠。480p の 29.97/30 は規格外 (H total を 2 倍にして 27 MHz で 30 Hz を作る) なので
// モニタによっては受け付けない。
//
// MODE  解像度   fps     pixclk[MHz]  Htotal Vtotal  sync極性
//  0    1080p    60      148.5        2200   1125    +
//  1    1080p    59.94   148.352      2200   1125    +
//  2    1080p    30      74.25        2200   1125    +
//  3    1080p    29.97   74.176       2200   1125    +
//  4    720p     60      74.25        1650   750     +
//  5    720p     59.94   74.176       1650   750     +
//  6    720p     30      74.25        3300   750     +   (VIC 62)
//  7    720p     29.97   74.176       3300   750     +
//  8    480p     60      27.027       858    525     -
//  9    480p     59.94   27.0         858    525     -
// 10    480p     30      27.027       1716   525     -   (規格外)
// 11    480p     29.97   27.0         1716   525     -   (規格外)

`ifndef VIDEO_MODES_VH
`define VIDEO_MODES_VH

function integer mode_h_active; input integer m; begin
  mode_h_active = (m < 4) ? 1920 : (m < 8) ? 1280 : 720; end endfunction
function integer mode_h_fp; input integer m; begin
  mode_h_fp = (m < 4) ? 88 : (m < 6) ? 110 : (m < 8) ? 1760 : (m < 10) ? 16 : 874; end endfunction
function integer mode_h_sync; input integer m; begin
  mode_h_sync = (m < 4) ? 44 : (m < 8) ? 40 : 62; end endfunction
function integer mode_h_bp; input integer m; begin
  mode_h_bp = (m < 4) ? 148 : (m < 8) ? 220 : 60; end endfunction
function integer mode_v_active; input integer m; begin
  mode_v_active = (m < 4) ? 1080 : (m < 8) ? 720 : 480; end endfunction
function integer mode_v_fp; input integer m; begin
  mode_v_fp = (m < 4) ? 4 : (m < 8) ? 5 : 9; end endfunction
function integer mode_v_sync; input integer m; begin
  mode_v_sync = (m < 4) ? 5 : (m < 8) ? 5 : 6; end endfunction
function integer mode_v_bp; input integer m; begin
  mode_v_bp = (m < 4) ? 36 : (m < 8) ? 20 : 30; end endfunction
function integer mode_sync_pol; input integer m; begin   // 1 = 正極性
  mode_sync_pol = (m < 8) ? 1 : 0; end endfunction
function integer mode_fps_int; input integer m; begin    // タイムコード用 (29.97 は 30 カウント)
  mode_fps_int = ((m & 2) == 0 && m < 8) ? 60 : (m >= 8 && m < 10) ? 60 : 30; end endfunction
function integer mode_is_1001; input integer m; begin    // 1 = 1/1.001 系 (59.94 / 29.97)
  mode_is_1001 = (m & 1); end endfunction

// ラベル文字列 (16 文字、右をスペースで埋める)
function [8*16-1:0] mode_label; input integer m; begin
  case (m)
    0:  mode_label = "1080p 60        ";
    1:  mode_label = "1080p 59.94     ";
    2:  mode_label = "1080p 30        ";
    3:  mode_label = "1080p 29.97     ";
    4:  mode_label = "720p 60         ";
    5:  mode_label = "720p 59.94      ";
    6:  mode_label = "720p 30         ";
    7:  mode_label = "720p 29.97      ";
    8:  mode_label = "480p 60         ";
    9:  mode_label = "480p 59.94      ";
    10: mode_label = "480p 30         ";
    default: mode_label = "480p 29.97      ";
  endcase end endfunction

// MMCME2_BASE の設定 (入力 100 MHz)。tools で総当たりした値。誤差は 480p60 のみ +1 ppm、他は 0。
//   pixclk = 100 / DIVCLK * MULT_F / DIVIDE_F
function integer mode_mmcm_divclk; input integer m; begin
  mode_mmcm_divclk = (m == 0 || m == 2 || m == 4 || m == 6) ? 4 :
                     (m == 1 || m == 3) ? 7 :
                     (m == 5 || m == 7) ? 6 : 1; end endfunction
function real mode_mmcm_mult; input integer m; begin
  mode_mmcm_mult = (m == 0 || m == 2 || m == 4 || m == 6) ? 37.125 :
                   (m == 1 || m == 3 || m == 5 || m == 7) ? 50.625 :
                   (m == 8 || m == 10) ? 6.25 : 6.75; end endfunction
function real mode_mmcm_div; input integer m; begin
  mode_mmcm_div = (m == 0) ? 6.25 : (m == 1) ? 4.875 :
                  (m == 2 || m == 4 || m == 6) ? 12.5 :
                  (m == 3 || m == 5 || m == 7) ? 11.375 :
                  (m == 8 || m == 10) ? 23.125 : 25.0; end endfunction

`endif
