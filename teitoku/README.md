# MD 提督の決断 解析

KOEI，1992，MD（1 MB，T-76073）。程式是 SFC 版（`~/works/superfamicom-re/teitoku`）的 68000 移植：字型、文字編碼、表格欄位都和 SFC 一一對應，劇本資料幾乎完全相同。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 劇本、艦船、基地、艦隊、提督、他國、頭像、世界地圖、字型 → teitoku/output/
.venv/bin/python teitoku/export.py [--rom ROM] [--out DIR]

# kaodata 統一格式資料集 tk-md
.venv/bin/python teitoku/export_kaodata.py --out <kaodata>/data-local/tk-md
.venv/bin/python teitoku/verify_kaodata_export.py --dataset <輸出目錄>

# 模擬器驗證（MAME）
.venv/bin/python teitoku/verify_scenarios.py   # 9 劇本載入後的 RAM（約 1 分鐘）
.venv/bin/python teitoku/verify_faces.py       # 54 張頭像：VRAM、CRAM、截圖（約 30 秒）
.venv/bin/python teitoku/verify_maps.py        # 世界地圖：tile、tilemap、CRAM、截圖（約 10 秒）
```

ROM 預設讀 `roms/Teitoku no Ketsudan (Japan).zip`。依賴：Pillow；openpyxl（可選）；驗證需 `mame`。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、劇本（初始化資料＋差分）、艦船、基地、艦隊、陣營、提督、他國、頭像、世界地圖 |
| `data/charset.txt` | 字表（和 superfamicom-re 的 SFC 版相同） |
| `export.py` | 匯出 CSV（UTF-8 BOM）／XLSX／PNG |
| `export_kaodata.py`、`verify_kaodata_export.py` | kaodata 資料集 `tk-md` 與其驗證 |
| `verify_*.py` | 模擬器驗證（見上） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `scenarios.csv` | 9 劇本：標題、日期、開始經過月數 |
| `ship_types.csv` | 14 種艦種名 |
| `ships.csv`、`ship_scenarios.csv` | 270 艘的固定欄位（艦名、讀音、艦種、艦級、性能、完成月）；9 劇本 × 270 的狀態（所屬艦隊、建造中、沉沒、搭載機、兵員、未解欄位） |
| `bases.csv`、`base_scenarios.csv` | 50 基地的代號、名稱、座標；9 劇本 × 50 的所屬、司令部、資源、飛機、燃料等（附原始 bytes） |
| `fleets.csv` | 9 劇本的艦隊：位置、基地、司令官、旗艦、艦船、燃料、士気 |
| `admirals.csv`、`admiral_scenarios.csv` | 40 名提督；各劇本的指揮艦隊、不登場旗標 |
| `countries.csv`、`sides.csv` | 9 劇本 × 13 國的同盟與態度；兩陣營的司令部 |
| `teitoku.xlsx` | 以上各表 |
| `faces/` | 54 張頭像（`15_山本五十六.png`、`40_陸軍.png` ⋯） |
| `world_map.png` | 世界地圖 256 × 128 |
| `font.png` | 1036 字 |

kaodata 資料集 `tk-md`（遊戲代碼 TK，平台 MD）：40 名提督、54 張頭像（14 張無名人物依服裝分組：陸軍／海軍／飛行員），沒有讀音、沒有頭像碼；調色盤是全部頭像用到的 49 色（MAME 色階）。名字去掉 ROM 裡的對齊空白，和 `tk-sfc` 一致。

## 進度

- ✓ 文字：字型、編碼（同 SFC）
- ✓ 劇本 9 個：初始化資料、未壓縮差分、載入流程（RAM 完全一致）
- ✓ 艦船、基地、艦隊、陣營、提督、他國的表格；欄位意義沿用 SFC 的研究
- ✓ 頭像 54 張；kaodata `tk-md`
- ✓ 世界地圖
- 未解：大地圖（作戦移動用的區塊圖）、艦船圖／場景圖、戰鬥畫面、各表部分欄位（見 ROM_FORMAT.md §11）

## 驗證結果

| 腳本 | 結果 |
|------|------|
| `verify_scenarios.py` | 9/9 劇本載入後 RAM `$0060–$3FE8` 16265/16265 bytes 相同 |
| `verify_faces.py` | 54/54：VRAM `$7800`、CRAM 第 3 列、畫面 40 × 48 逐 pixel（103668 個非透明 pixel） |
| `verify_maps.py` | tile 320 個、tilemap（plane B 第 39 列）、CRAM 第 2 列一致；畫面 9472/9472 個地圖 pixel 相同（文字底下的不比） |
| `verify_kaodata_export.py` | 54/54 張、40/40 人、分組、checksums OK；kaodata `pnpm verify` 94 checked, 0 mismatched |
