# MD 信長の野望・全国版 解析

KOEI，1993，MD（512 KB）。日版（表頭 1993.JUN）與美版 Nobunaga's Ambition（1993.SEP）都支援：同一個程式，位址不同。資料和 SFC 版（`~/works/superfamicom-re/zenkoku`）逐欄相同。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 劇本、人物、大名、國、戰場地形、頭像、大地圖 → zenkoku/output/（美版 → zenkoku/output/usa/）
.venv/bin/python zenkoku/export.py [--rom ROM] [--out DIR]

# kaodata 統一格式資料集 nobu2-md（日版）
.venv/bin/python zenkoku/export_kaodata.py --out <kaodata>/data-local/nobu2-md
.venv/bin/python zenkoku/verify_kaodata_export.py --dataset <輸出目錄>

# 模擬器驗證（MAME；加 --rom "roms/Nobunaga's Ambition (USA).zip" 驗美版）
.venv/bin/python zenkoku/verify_scenarios.py   # 4 劇本載入後的 RAM（約 1 分鐘）
.venv/bin/python zenkoku/verify_persons.py     # 自国情報畫面：大名 6 項、國 12 項（約 2 分鐘）
.venv/bin/python zenkoku/verify_faces.py       # 73 張頭像：VRAM、調色盤、截圖（約 30 秒）
.venv/bin/python zenkoku/verify_maps.py        # 4 劇本開局的大地圖 bitmap 與調色盤（約 1 分鐘）
```

ROM 預設讀 `roms/Nobunaga no Yabou - Zenkoku Ban (Japan).zip`，依表頭序號自動判斷日版／美版。依賴：Pillow；openpyxl（可選）；驗證需 `mame`。地圖標註用 macOS 的ヒラギノ角ゴシック，找不到時退回 PIL 預設字型。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼（兩版的位址在 `LAYOUTS`）：文字、劇本、大名、國、頭像、大地圖（含開局上色）、戰場地形 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py`、`verify_kaodata_export.py` | kaodata 資料集 `nobu2-md` 與其驗證 |
| `verify_*.py` | 模擬器驗證（見上） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `scenarios.csv` | 4 劇本：標題、開始年、國數、大名數 |
| `persons.csv` | 68 人：姓名（美版只有一個名字）、登場劇本、頭像碼 |
| `daimyo_scenarios.csv` | 4 劇本的大名（17／53／41／29 筆）：年齢、健康、野心、運、魅力、知力、花紋、領國 |
| `provinces.csv` | 50＋17 國：地方、相鄰、戰場地圖、上色起點 |
| `province_scenarios.csv` | 4 劇本 × 國：大名與 13 項數值、未解的 `$1130` |
| `battle_maps.csv`、`battle_cells.csv` | 50 張戰場的地形統計與每格地形 |
| `zenkoku.xlsx` | 以上各表 |
| `faces/`、`portraits/` | 每人頭像（`031_織田信長.png`）、全部 73 張（068–072 是姫） |
| `map_50.png`、`map_17.png`、`map_scenario1-4.png`、`map_50_labelled.png` | 大地圖：未上色、4 劇本開局、標上國號國名（放大） |

kaodata 資料集 `nobu2-md`（遊戲代碼 NOBU2，平台 MD）：68 人、73 張頭像（5 張姫），沒有讀音。美版頭像和日版完全相同，所以只出日版資料集。

## 進度

- ✓ 劇本 4 個：載入程式與來源表（RAM 完全一致）、開始年、大名數
- ✓ 大名 6 項、國 13 項的欄位意義（情報畫面）；人物 68 人
- ✓ 頭像 73 張；kaodata `nobu2-md`
- ✓ 大地圖：50／17 國 bitmap、開局上色（flood fill＋花紋）
- ✓ 美版：同上全部（共用 `rom.py`）
- 戰場：只有地形表（和 SFC 相同），畫面組成未解
- 未解：見 ROM_FORMAT.md §9

## 驗證結果

| 腳本 | 日版 | 美版 |
|------|------|------|
| `verify_scenarios.py` | 4 劇本載入後 RAM 7474/7474 bytes 相同，大名數、國數相同 | 4 劇本 7470/7470 bytes 相同 |
| `verify_persons.py` | 大名 142/142（年齢＋5 能力）、國 169/169（12 項），含 2 輪自訂值 | 同左 142/142、169/169 |
| `verify_faces.py` | 73/73：VRAM、CRAM line 2、畫面 40×48 逐 pixel | 73/73 |
| `verify_maps.py` | 4 劇本開局 bitmap 19200/19200 bytes、調色盤一致 | 4/4 |
| `verify_kaodata_export.py` | 68/68 人、73/73 張、checksums OK | — |
