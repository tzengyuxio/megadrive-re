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

- ROM 預設直接讀 `roms/Sangokushi II (Japan).zip`。
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

- ✓ 字型（16 × 16，含跳脫碼）與人名 387 個漢字碼
- ✓ 人物 352 人：讀音、7 項能力、親族、生年、頭像碼；每劇本的所在州、身分、忠誠、初期兵士、登場年
- ✓ 6 劇本 × 41 州：金、兵糧、人口、勢力、土地、民忠、治水、馬、信；州相鄰表
- ✓ 頭像：專屬 208 張（11 張和 SFC 不同）、組合臉（8 頭型 × 5 區域 × 4 記錄，4 組調色盤）；kaodata 資料集 `san2-md`
- ✓ 大地圖（ROM 的 tilemap ＋ tile）
- ✓ 41 張戰場（13 × 12 六角格，7 種地形）與全中國拼接
- … 未解：劇本標頭後 18 bytes、選單／訊息文字、佈陣圖、勢力旗與州號位置、道具／事件（ROM_FORMAT.md §10）

## 驗證

全部在 MAME 跑遊戲本身的程式，和 ROM 解碼獨立比對。

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_text.py` | 君主選擇畫面的 6 個人名換成每個人名用到的碼（ROM patch），比對 VRAM 裡畫出的字形 | 388/388 字形相符（387 碼） |
| `verify_scenarios.py` | 6 劇本選完後的 RAM（州記錄、人物 24-byte 記錄）和 ROM 解碼比對 | 州 41/41 × 6；人物 150/203/210/214/196/183 全部相符 |
| `verify_kaodata_export.py` | 參考渲染器與 ROM 組圖逐 pixel 比對、checksums；模擬器裡把袁術的頭像碼換成每個碼，比對畫面像素、VRAM tile、CRAM | 560/560、OK、384/384（352 個用到的碼＋32 個合成碼） |
| `verify_maps.py` | 開戰選州畫面的大地圖 tilemap／tile／調色盤；41 張戰場逐張換進州 20 開戰，比對 plane、地形 tile 與調色盤 | tilemap 449/504 相符、其餘 55 格是州號／旗子／視窗覆蓋；tile 433/433；調色盤 OK；地形 tile 28/28；戰場 41/41 |
