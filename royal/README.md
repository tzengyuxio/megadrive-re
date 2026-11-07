# MD ロイヤルブラッド 解析

KOEI，1992，MD（1 MB，`GM T-76063`，海外名 Gemfire）。資料和 FC 版（`~/works/famicom-re/royal`）相同，頭像是 MD 重畫的。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 劇本、人物、家、領地、部隊、戰場地形、頭像、地圖 → royal/output/
.venv/bin/python royal/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 royal-md
.venv/bin/python royal/export_kaodata.py --out <kaodata>/data-local/royal-md
.venv/bin/python royal/verify_kaodata_export.py --dataset <輸出目錄>

# 模擬器驗證（MAME）
.venv/bin/python royal/verify_scenarios.py   # 4 劇本載入後的 RAM（約 2 分鐘）
.venv/bin/python royal/verify_faces.py       # 91 張頭像：VRAM、CRAM、截圖（--quick 只跑 6 張）
.venv/bin/python royal/verify_map.py         # 主畫面版面、地圖 tile、調色盤、截圖
```

ROM 預設讀 `_original/md/Royal Blood (Japan).zip`。依賴：Pillow；openpyxl（可選）；驗證需 `mame`。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、劇本、家、人物、領地、名稱表、部隊、頭像、主畫面／地圖、戰場地形 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py`、`verify_kaodata_export.py` | kaodata 資料集 `royal-md` 與其驗證 |
| `verify_*.py` | 模擬器驗證（見上） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `scenarios.csv` | 4 劇本：標題、年數差、人物數、家數、支配領地數 |
| `characters.csv` | 4 劇本登場人物（164 筆）：年齢、知武魅、所在、家、身分、一族（推定）、未知欄 |
| `houses.csv` | 4 劇本的家（26 筆）：当主、領地 |
| `provinces.csv` | 4 劇本 × 30 領地：支配家、金食兵、開発、作物、民忠、部隊候補、人物、相鄰、地圖標記格 |
| `units.csv` | 23 種部隊：數值、類別 |
| `battle_maps.csv`、`battle_maps/` | 30 張戰場的地形（示意色塊圖，遊戲的戰場畫面未解） |
| `royal.xlsx` | 以上各表 |
| `faces/`、`advisers/`、`unit_faces/` | 頭像：64 人（`C04_エラン.png`）、4 相談役、23 部隊 |
| `map.png`、`screen_1.png`、`screen_2.png`、`panel.png` | 戰略地圖（含國號）、兩張主畫面版面、空白面板 |

kaodata 資料集 `royal-md`（遊戲代碼 ROYAL，平台 MD）：64 人、91 張頭像（P64–67 group 相談役、P68–90 group 第5部隊 並以部隊名為 name），沒有頭像碼；reading 是片假名名稱轉平假名（同 royal-fc）。

## 進度

| 項目 | 狀態 | 證據 | 說明 |
|------|------|------|------|
| 劇本 4 個（家、人物、領地區塊） | ✅ | emu+cross | `verify_scenarios.py` 載入後 RAM 2134/2134 bytes 相同，資料和 FC 版逐欄相同；ROM_FORMAT §3 |
| 名稱表：人物、領地（相鄰、標記格）、部隊、家名 | ✅ | cross | `export.py` 輸出和 FC 版 CSV 逐欄比對 0 差異；ROM_FORMAT §4 |
| 可選家当主表 | 🟡 | code | 選家畫面程式（`$1EC90` 一帶）讀這張表；ROM_FORMAT §4 |
| 部隊表的數值 | 🟡 | cross | 資料和 FC 版相同，`+11`／`+12` 攻防只是推測；ROM_FORMAT §4 |
| 頭像 91 張（人物 64、相談役 4、部隊 23） | ✅ | emu | `verify_faces.py` 比對 VRAM／CRAM／截圖；ROM_FORMAT §5 |
| kaodata 資料集 `royal-md` | ✅ | checksum | `verify_kaodata_export.py` |
| 主畫面版面與戰略地圖 | ✅ | emu | `verify_map.py` 比對 tile、CRAM、window plane 與截圖；ROM_FORMAT §6 |
| 戰場地形 30 張 | ✅ | cross | 和 FC 版 `0x26A66` 逐 byte 相同；ROM_FORMAT §4 |
| 戰場畫面 | ❌ | | 見「未解」 |

## 未解

- 劇本 header 除年數差外的欄位；家槽旗標（`+3`）（ROM_FORMAT §3、§7）
- 人物 `+10`（一族，推定）、`+11`；姓名表 `+16`（ROM_FORMAT §3.1、§4、§7）
- 領地 `+13..15` 旗標、`+16..18`、`+20..21`，部隊槽末位元組（ROM_FORMAT §3.2、§7）
- 部隊表 `+11`／`+12`（攻防?）、`+16`、`+17`（ROM_FORMAT §4、§7）
- 魔術師（魔術類部隊）與寶石的歸屬、事件資料（ROM_FORMAT §7）
- 戰場畫面的組成，只有地形表（ROM_FORMAT §7）
- 第二張主畫面版面（`0x505B0`）的用途，還沒在遊戲中對到（ROM_FORMAT §6、§7）

## 驗證結果

| 腳本 | 結果 |
|------|------|
| `verify_scenarios.py` | 4 劇本載入後 RAM 各 2134/2134 bytes 相同（另跳過 380 個執行期指標 bytes） |
| `verify_faces.py` | 91/91：VRAM 960 bytes、CRAM line 3、畫面 40×48 逐 pixel（人物 15 的 3 個透明 pixel 不比） |
| `verify_map.py` | VRAM tile 0x378+0x1A1、CRAM line 2 一致；window plane 840/840 格等於版面；地圖 15360/15360 pixel（30 個家旗格以外） |
| `verify_kaodata_export.py` | 64/64 人、91/91 張、checksums OK；kaodata `pnpm verify` 155 checked、0 mismatched |
