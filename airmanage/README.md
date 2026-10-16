# MD エアーマネジメント 大空に賭ける 解析

KOEI，1992，MD（1 MB，`GM T-76083`）。資料表和 SFC 版（`~/works/superfamicom-re/airmanage`）逐值相同（改成 big-endian word、4-byte 指標），頭像大多沿用 SFC 的圖但重新配色（SFC 12 組調色盤 → MD 5 組）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 都市、劇本、距離、機種、製造商、頭像、大地圖 → airmanage/output/
.venv/bin/python airmanage/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 air-md
.venv/bin/python airmanage/export_kaodata.py --out <kaodata>/data-local/air-md
.venv/bin/python airmanage/verify_kaodata_export.py --dataset <輸出目錄>

# 模擬器驗證（MAME）
.venv/bin/python airmanage/verify_scenarios.py   # 2 劇本開始後的 RAM（約 20 秒）
.venv/bin/python airmanage/verify_faces.py       # 33 張頭像：配對、VRAM、CRAM、截圖（--faces 0,8,28 只跑部分）
.venv/bin/python airmanage/verify_maps.py        # 大地圖：tile、調色盤、plane B、城市標記
```

ROM 預設讀 `roms/Air Management - Oozora ni Kakeru (Japan).zip`。依賴：Pillow；openpyxl（可選）；驗證需 `mame`。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：都市、距離、劇本、機種、製造商、頭像、大地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py`、`verify_kaodata_export.py` | kaodata 資料集 `air-md` 與其驗證 |
| `verify_*.py` | 模擬器驗證（見上） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `cities.csv` | 22 都市：名稱（全形／半形）、機場、預設航空公司、類型、地圖座標、初期航線（推測）、未解欄 |
| `scenario_cities.csv` | 2 劇本 × 22 都市：人口、経済力／観光地（含 d–s 等級）、スロット、本社スロット、初期資金（推測） |
| `distances.csv` | 22×22 距離（km） |
| `matrix2.csv` | 22×22 第二張對稱表（未解，SFC 也未解） |
| `aircraft.csv` | 20 機種：座席、航続距離、価格、燃料費、発売／生産終了年、メーカー |
| `makers.csv` | 5 製造商：代表色、頭像、販售機種 |
| `airmanage.xlsx` | 以上各表 |
| `faces/`、`faces.png` | 33 張頭像（部下 8、交渉相手 20、メーカー 5），用遊戲配對的調色盤 |
| `world_map.png`、`world_map_cities.png` | 大地圖；加上 22 都市標記位置與名稱 |

kaodata 資料集 `air-md`（遊戲代碼 AIR，平台 MD，結構同 air-sfc）：沒有角色（遊戲不給人名），33 張頭像全放 portraits（group 部下／交涉對象／廠商，廠商附 ROM 的製造商名），沒有頭像碼；調色盤 5 組 × 16 色（MAME 色階），像素＝組 × 16 ＋ 色。

## 進度

- ✓ 都市 22：名稱、機場、航空公司、類型、地圖座標、距離表
- ✓ 劇本 2（1963、1983）：都市數值、スロット、本社スロット；ROM 表與 RAM 完全一致
- ✓ 機種 20、製造商 5（機種 19 ROM 寫「コンコレド」，照錄）
- ✓ 頭像 33 張與遊戲的配對規則；kaodata `air-md`
- ✓ 大地圖（HQ 選擇畫面、主畫面）與城市標記
- 未解：第二張 22×22 表、初期航線的兩個 byte、本社參數、初期資金（推測）、機種 +16、機體圖、世界座標、文字／字型、模擬邏輯（見 ROM_FORMAT.md §8）

## 驗證結果

| 腳本 | 結果 |
|------|------|
| `verify_scenarios.py` | 2 劇本：RAM 劇本表 220/220 words、都市紀錄 22/22、スロット 22/22、4 家本社スロット 4/4 |
| `verify_faces.py` | 遊戲為 4 部下＋12 交渉相手產生的描述子 16/16 與配對規則一致；33/33 張 VRAM 960 bytes、CRAM line 3、畫面逐 pixel 相同（色 0 透明不比；共 183 格被眼／嘴動畫 tile 蓋住，這些 tile 都出自該種類的動畫檔） |
| `verify_maps.py` | HQ 畫面與主畫面：tile 512/512、CRAM line 1（主畫面閃爍的色 3、4 不比）、plane B 416/416（HQ，上方被框蓋住）與 512/512（主畫面）；HQ 畫面城市標記 sprite 22/22 |
| `verify_kaodata_export.py` | 33/33 張（圖、group、廠商名）、checksums OK；kaodata `pnpm verify` 33 checked、0 mismatched |
