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

ROM 預設讀 `roms/Europa Sensen (Japan).zip`。依賴：Pillow；openpyxl（可選）；驗證需 `mame`。LZ 解碼共用 `haouden/lz.py`。

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

- ✓ 劇本 6 個：區塊與 RAM 完全一致；將領、領袖、經歷、都市、兵器（欄位沿用 SFC 研究，資料逐欄相同）
- ✓ 頭像 120 張，含 100–119 的用途；kaodata `europe-md`
- ✓ 戰場地形與格碼詞（RAM 驗證）
- 戰場畫面（格碼詞 → tile）、歐洲地圖（選單背景）未做
- 未解：見 ROM_FORMAT.md「未解」

## 驗證結果

| 腳本／比對 | 結果 |
|------|------|
| `verify_scenarios.py` | 6 劇本：`$9E06` 時 RAM 區塊 9365/9365、`$9E4C` 時地形 1600/1600、戰場畫面 `$9EF4` 時格碼詞 3200/3200 bytes 相同 |
| `verify_faces.py` | 120/120：VRAM 960 bytes、CRAM line 0、畫面 40×48 逐 pixel（共 20381 個透明的色 0 pixel 不比） |
| `verify_kaodata_export.py` | 100/100 人、120/120 張（像素、group、name）、checksums OK；kaodata `pnpm verify` 220 checked、0 mismatched |
| 和 SFC 版 `rom.py` 比對 | 人物 100/100、劇本將領 137/137、都市 94/94（含駐軍）、兵器 158/158、經歷 94/94、頭像像素（色號）120/120 相同；地形只有地圖 1 的 (28,9)、(29,9) 不同（SFC 荒地 → MD 丘陵）；kaodata 人名與 europe-sfc 100/100 相同 |
