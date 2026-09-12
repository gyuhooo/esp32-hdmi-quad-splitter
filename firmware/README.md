# firmware

ESP-IDF(v5.x)向けの雛形。以下を行います。

1. LT86104SX をリセット
2. I2C バスをスキャンしてデバイスを列挙
3. 見つかったアドレスに対して `lt86104_init()` を呼ぶ(初期化テーブルは空。データシート入手後に `lt86104.c` の `INIT_TABLE` を埋める)

```
idf.py set-target esp32
idf.py build flash monitor
```

ピン割り当ては `main/lt86104.h` で変更できます。
