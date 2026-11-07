# MD 三國志II 解析

KOEI，1991 年 10 月，Mega Drive（1 MB）。和 SFC 版スーパー三國志II 是同一套資料：劇本、人物、州、相鄰、戰場的資料表內容相同，只是換成大端序、部分記錄加寬（對照見 ROM_FORMAT.md §9）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python san2/export.py [--rom ROM] [--out DIR]             # → san2/output/（CSV、XLSX、PNG）
.venv/bin/python san2/export_kaodata.py --out <kaodata>/data-local/san2-md
.venv/bin/python san2/verify_kaodata_export.py --dataset <kaodata>/data-local/san2-md   # 約 15 秒
.venv/bin/python san2/verify_scenarios.py                          # 約 5 秒
.venv/bin/python san2/verify_maps.py                               # 約 50 秒
.venv/bin/python san2/verify_text.py                               # 約 5 秒

# 重建漢字碼對照 data/kanji_ext.json（需要 superfamicom-re 的 san2）
.venv/bin/python san2/tools/build_kanji_map.py
```

- ROM 預設直接讀 `_original/md/Sangokushi II (Japan).zip`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。
- 驗證腳本需要 MAME（`tools/mame.py`、`tools/drive.py`、`tools/replay.py`），多個 MAME 平行跑。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：人物、配置、州、相鄰、字型、頭像、大地圖、戰場 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `san2-md`（姓名照 ROM 原文、替代字另給 `nameHistorical`、讀音分姓名） |
| `verify_kaodata_export.py` | 資料集與 ROM、checksums、模擬器畫面三方比對 |
| `verify_scenarios.py` | 6 劇本開局 RAM 與 ROM 解碼比對 |
| `verify_maps.py` | 大地圖與 41 張戰場，和模擬器 VRAM／CRAM 比對 |
| `verify_text.py` | 人名字形，和模擬器畫出的字比對 |
| `tools/session.py` | 遊戲操作序列（劇本、君主選擇、指令畫面、開戰）與跑序列取 dump 的函式 |
| `tools/build_kanji_map.py` | 從 SFC 版的漢字碼對照推出 MD 版的對照，並核對字形 |
| `data/kanji_ext.json` | 漢字碼 → 漢字（外部資料推得，字形已和 SFC 逐點核對） |
| `data/surnames.tsv` | 姓氏讀音（kaodata 讀音分姓名用） |

## 輸出（`san2/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 352 人：[EXT] 姓名、漢字碼、讀音、才智、戰力、號召、義理、人德、野望、相性、親族、生年、登場年、頭像碼 |
| `person_scenarios.csv` | 6 劇本 × 在場人物：身分（君主／武將／在野／未登場）、州、[EXT] 君主、忠誠、兵士、年齡 |
| `provinces.csv` | 6 劇本 × 41 州：勢力、[EXT] 君主、人口、金、兵糧、民忠、土地、治水、馬、信 |
| `adjacency.csv` | 41 州的六角座標、6 方向的鄰州、戰場地形格數 |
| `san2.xlsx` | 以上四張表（需 openpyxl） |
| `faces/`、`portraits/` | 每人頭像（`000_曹操.png`）、專屬頭像 P001–P208 |
| `mob_parts.png`、`mob_parts/` | 組合臉零件總覽與各零件 |
| `map.png` | 大地圖（不含州號與勢力旗） |
| `battle_maps/` | 41 張戰場（01–41） |
| `province_hex.png` | 州的六角格相鄰圖 |
| `china_battle_map(_labeled).png` | 41 張戰場依相鄰關係拼成的全中國戰場 |

CSV 和 SFC 版的匯出逐欄相同（漢字碼欄除外，MD 的字碼不同）。

## 進度

| 項目 | 狀態 | 證據 | 說明 |
|------|------|------|------|
| 字型 16 × 16、跳脫碼、人名 387 個漢字碼 | ✅ | emu+modified+cross | `verify_text.py` 以 ROM patch 換人名比對 VRAM 字形 388/388，字形與 SFC 387/387 逐點相同；ROM_FORMAT §3 |
| 6 劇本 × 41 州（金、兵糧、人口、勢力、土地、民忠、治水、馬、信） | ✅ | emu+cross | `verify_scenarios.py` 州 41/41 × 6，246 筆與 SFC 逐欄相同；ROM_FORMAT §2 |
| 州相鄰表、大地圖游標格 | ✅ | cross | 與 SFC 版相同；ROM_FORMAT §2、§9 |
| 人物能力、每劇本的勢力、忠誠、兵士 | ✅ | emu+cross | `verify_scenarios.py` 比對 RAM 的人物 24-byte 記錄全部相符；ROM_FORMAT §4 |
| 人物讀音、義理等 4 項、親族、生年、登場年 | ✅ | cross | 與 SFC 版逐 byte 相同（讀音 352/352、配置 352/352）；ROM_FORMAT §4 |
| 頭像：專屬 208 張、組合臉 8 頭型 | ✅ | emu+modified | `verify_kaodata_export.py` 把袁術的頭像碼換成每個碼，比對畫面、VRAM、CRAM 384/384；ROM_FORMAT §6 |
| kaodata 資料集 `san2-md` | ✅ | checksum | `verify_kaodata_export.py` |
| 大地圖（tilemap、tile、調色盤） | ✅ | emu | `verify_maps.py` 開戰選州畫面比對，不符的 55 格是州號／旗子／視窗；ROM_FORMAT §5 |
| 41 張戰場與地形 tile | ✅ | emu+modified+cross | `verify_maps.py` 把每張戰場換進州 20 開戰比對 41/41，內容與 SFC 相同；ROM_FORMAT §7 |
| 選單／訊息文字 | ❌ | | 見「未解」 |
| 佈陣圖、勢力旗、州號位置、道具／事件 | ❌ | | 見「未解」 |

## 未解

- 劇本標頭年之後的 18 bytes、配置表 `+1`（ROM_FORMAT §2、§4.3、§10）
- 選單／訊息文字的編碼與位置：人名的漢字碼已解，假名訊息還沒找到（ROM_FORMAT §3、§10）
- 佈陣 nibble 圖 `0x4705A`：和 SFC／FC 版相同，意義未解（ROM_FORMAT §8、§10）
- 勢力旗的圖與位置表、州號標籤的位置表：州號 tile 在 `0x68CF0`，放置位置未找（ROM_FORMAT §5、§10）
- `0x48698` 起疑似視窗框表，未細看（ROM_FORMAT §8）
- 11 張重繪頭像的來由：MD 版自己的修改，沒有對照（ROM_FORMAT §6、§10）
- 戰爭觀看設定的效果（ROM_FORMAT §10）
- 道具、事件表（ROM_FORMAT §10）

## 驗證

全部在 MAME 跑遊戲本身的程式，和 ROM 解碼獨立比對。

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_text.py` | 君主選擇畫面的 6 個人名換成每個人名用到的碼（ROM patch），比對 VRAM 裡畫出的字形 | 388/388 字形相符（387 碼） |
| `verify_scenarios.py` | 6 劇本選完後的 RAM（州記錄、人物 24-byte 記錄）和 ROM 解碼比對 | 州 41/41 × 6；人物 150/203/210/214/196/183 全部相符 |
| `verify_kaodata_export.py` | 參考渲染器與 ROM 組圖逐 pixel 比對、checksums；模擬器裡把袁術的頭像碼換成每個碼，比對畫面像素、VRAM tile、CRAM | 560/560、OK、384/384（352 個用到的碼＋32 個合成碼） |
| `verify_maps.py` | 開戰選州畫面的大地圖 tilemap／tile／調色盤；41 張戰場逐張換進州 20 開戰，比對 plane、地形 tile 與調色盤 | tilemap 449/504 相符、其餘 55 格是州號／旗子／視窗覆蓋；tile 433/433；調色盤 OK；地形 tile 28/28；戰場 41/41 |
