# MD ヨーロッパ戦線 解析

KOEI，1993，MD（1 MB，`GM T-76113`，海外名 Operation Europe: Path to Victory 1939–45）。資料和 SFC 版（`~/works/superfamicom-re/europe`）
是同一份，只差 16 位元欄位改 big-endian、補齊到偶數位址；頭像像素也和 SFC 版相同。ROM 結構與各表格式見
[docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 劇本、將領、領袖、經歷、都市、兵器、地圖格、頭像、戰場地形示意 → europe/output/
.venv/bin/python europe/export.py [--rom ROM] [--out DIR]

# kaodata 統一格式資料集 europe-md
.venv/bin/python europe/export_kaodata.py --out <kaodata>/data-local/europe-md
.venv/bin/python europe/verify_kaodata_export.py --dataset <輸出目錄>

# 模擬器驗證（MAME）
.venv/bin/python europe/verify_scenarios.py   # 6 劇本：區塊、地形、格碼詞（約 40 秒；--only N 只跑劇本 N）
.venv/bin/python europe/verify_faces.py       # 120 張頭像：VRAM、CRAM、截圖（約 1 分鐘；--quick 只跑 5 張）
```

ROM 預設讀 `_original/md/Europa Sensen (Japan).zip`。依賴：Pillow；openpyxl（可選）；驗證需 `mame`。LZ 解碼共用 `haouden/lz.py`。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、劇本、將領、領袖、經歷、都市、兵器、頭像（含 100–119 的用途）、戰場地形與格碼 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py`、`verify_kaodata_export.py` | kaodata 資料集 `europe-md` 與其驗證 |
| `verify_*.py` | 模擬器驗證（見上） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `scenarios.csv` | 6 劇本：名稱、日期、地圖、雙方將領數、都市數、區塊位址、header |
| `persons.csv` | 人物 id 0–99（94 將領＋6 領袖）：國籍、能力、登場劇本、經歷 |
| `scenario_generals.csv` | 6 劇本的將領槽（137 筆） |
| `leaders.csv` | 6 領袖 |
| `biographies.csv` | 94 人 × 7 行經歷 |
| `cities.csv` | 6 劇本的都市（94 筆）：座標、地形、弾薬／燃料／食料、耐久、駐軍、陣營 |
| `weapons.csv` | 158 種兵器：國籍、種別（推測）、登場（推測）、AP AT 防 速 射 |
| `map_cells.csv` | 6 張戰場 × 1600 格：地形、高 4 位元、格碼詞（未解） |
| `europe.xlsx` | 以上各表 |
| `portraits/` | 頭像 120 張（`096_アイゼンハワー.png`；100–119 沒有人物） |
| `maps/` | 6 張戰場的地形示意色塊圖（16 px／格），另一張加都市名；遊戲的戰場畫面未解 |

kaodata 資料集 `europe-md`（遊戲代碼 EUROPE，平台 MD）：100 人（id 0–99，name 照 ROM 半形片假名轉全形，reading 轉平假名，同 europe-sfc）、
120 張頭像，沒有頭像碼。沒有人物的 100–119 依畫它們的程式加 group：100／104／105 航空隊（ゲーリング／ホーカー／ツポレフ）、101–103 特殊工作
（マクドナルド／ケンタスキー／ハーゲンダッツ）、106–111 副官（軸心國）、112–117 副官（聯合軍）、118／119 事件人物（マルガレーテ／シスター）；
name 都是 ROM 裡畫在頭像旁的字。

## 進度

| 項目 | 狀態 | 證據 | 說明 |
|------|------|------|------|
| 劇本 6 個（區塊複製） | ✅ | emu | `verify_scenarios.py` 在 `$9E06` 比對 RAM 區塊 9365/9365 bytes；ROM_FORMAT「劇本」 |
| 將領、領袖、經歷、都市、兵器 | ✅ | cross | 和 SFC 版 `rom.py` 逐欄相同；欄位意義沿用 SFC 研究，兵器 +5／+6 是推測；ROM_FORMAT「劇本」「兵器」 |
| 頭像 120 張 | ✅ | emu | `verify_faces.py` 比對 VRAM／CRAM／截圖；ROM_FORMAT「頭像」 |
| 頭像 100–119 的用途 | 🟡 | code | 依畫它們的程式（`$3185A`、`$30E60`、`$1FC90` 等）判定；ROM_FORMAT「頭像」 |
| kaodata 資料集 `europe-md` | ✅ | checksum | `verify_kaodata_export.py` |
| 戰場地形 6 張 | ✅ | emu | `verify_scenarios.py` 在 `$9E4C` 比對地形 1600/1600；ROM_FORMAT「戰場地圖」 |
| 戰場格碼詞 | ✅ | emu | `verify_scenarios.py` 在戰場畫面比對 3200/3200 bytes；ROM_FORMAT「戰場地圖」 |
| 戰場畫面（格碼詞 → tile） | ❌ | | 見「未解」 |
| 歐洲地圖（選單背景） | ❌ | | 見「未解」 |

## 未解

- 戰場格碼詞 → tile／調色盤的組成；格碼詞已在 RAM `$FF6D30` 驗證（ROM_FORMAT「戰場地圖」）
- 歐洲地圖（選單背景）沒做（ROM_FORMAT「未解」）
- 部隊（師団／連隊）結構、勝利條件、劇本 header +5 以後（ROM_FORMAT「劇本」）
- 將領 +12 +13 +14 +19 +21（ROM_FORMAT「將領表」）
- 兵器 +5 登場時期、+6 種別名稱只是推測，+11 +12 +14 未解（ROM_FORMAT「兵器」）
- 都市第二組三值、駐軍槽後 2 bytes、+64 其餘位元（ROM_FORMAT「都市」）
- 地形 high nibble（ROM 裡 0 或 8）；兵器名 `$` `'` 在 MD 畫面上的字形（ROM_FORMAT「戰場地圖」「文字」）
- 副官（頭像 106–117）升任替補指揮官的流程未追（ROM_FORMAT「頭像」）

## 驗證結果

| 腳本／比對 | 結果 |
|------|------|
| `verify_scenarios.py` | 6 劇本：`$9E06` 時 RAM 區塊 9365/9365、`$9E4C` 時地形 1600/1600、戰場畫面 `$9EF4` 時格碼詞 3200/3200 bytes 相同 |
| `verify_faces.py` | 120/120：VRAM 960 bytes、CRAM line 0、畫面 40×48 逐 pixel（共 20381 個透明的色 0 pixel 不比） |
| `verify_kaodata_export.py` | 100/100 人、120/120 張（像素、group、name）、checksums OK；kaodata `pnpm verify` 220 checked、0 mismatched |
| 和 SFC 版 `rom.py` 比對 | 人物 100/100、劇本將領 137/137、都市 94/94（含駐軍）、兵器 158/158、經歷 94/94、頭像像素（色號）120/120 相同；地形只有地圖 1 的 (28,9)、(29,9) 不同（SFC 荒地 → MD 丘陵）；kaodata 人名與 europe-sfc 100/100 相同 |
