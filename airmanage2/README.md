# MD エアーマネジメントII 航空王をめざせ 解析

KOEI，1994，MD（1 MB，`GM T-76143`）。資料表和 SFC 版（`~/works/superfamicom-re/airmanage2`）逐值相同（改成 big-endian word、4-byte 指標），29 張頭像和 SFC 色號逐像素相同但重新配色；地圖 tile 用 KOEI LZ。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 都市、國家、地區、劇本、世界事件、機種、製造商、關聯事業、頭像、地圖 → airmanage2/output/
.venv/bin/python airmanage2/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 air2-md
.venv/bin/python airmanage2/export_kaodata.py --out <kaodata>/data-local/air2-md
.venv/bin/python airmanage2/verify_kaodata_export.py --dataset <輸出目錄>

# 模擬器驗證（MAME）
.venv/bin/python airmanage2/verify_scenarios.py   # 4 劇本開局後的 RAM（約 50 秒）
.venv/bin/python airmanage2/verify_faces.py       # 秘書／職員調色盤規則 + 35 個頭像描述（--faces 0,8,23 只跑部分）
.venv/bin/python airmanage2/verify_maps.py        # 世界地圖、7 張地區地圖、都市標記
```

ROM 預設讀 `roms/Air Management II - Koukuuou o Mezase (Japan).zip`。依賴：Pillow；openpyxl（xlsx）；驗證需 `mame`。LZ 解碼借用 `haouden/lz.py`。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：都市、地區、國家、劇本、世界事件、機種、製造商、頭像與描述規則、地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py`、`verify_kaodata_export.py` | kaodata 資料集 `air2-md` 與其驗證 |
| `verify_*.py` | 模擬器驗證（見上） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `cities.csv` | 89 都市：名稱（全形／半形）、地區、國家（劇本 1）、可否為本社、預設航空公司、地區／世界地圖座標 |
| `scenario_cities.csv` | 4 劇本 × 89 都市：國家與 3 個未解值、第二記錄（未解） |
| `countries.csv` | 57 國：名稱、各劇本的 `$FF9964` 值（未解）、`0x47875`（未解） |
| `areas.csv` | 7 地區：本社都市、其他都市、遮罩、秘書／職員調色盤、國家代表調色盤 |
| `events.csv` | 55 筆世界事件：年、季、對象、內容 |
| `aircraft.csv` | 53 機種：製造商、座席、航續距離、基準價格、燃費、整備性、生產年 |
| `makers.csv` | 12 製造商：頭像描述、販售機種 |
| `businesses.csv` | 15 關聯事業與 5 個類別 |
| `init_tables.csv` | 開局複製的 4 張未解表（原始 bytes） |
| `airmanage2.xlsx` | 以上各表 |
| `faces/`、`faces.png` | 35 個頭像（秘書 7、職員 11、國家代表 5 用歐洲調色盤 26；製造商 12 家各自的描述，bae／ヤコブレフ 的調色盤是空的、畫出來是黑影） |
| `world_map.png`、`world_map_cities.png` | 世界地圖；加上 89 都市位置 |
| `area_maps/area_N.png`、`area_N_cities.png` | 7 張地區地圖；加上都市標記與名稱 |

kaodata 資料集 `air2-md`（遊戲代碼 AIR2，平台 MD，結構同 air2-sfc）：沒有角色（遊戲不給人名），33 張頭像全放 portraits（group 秘書／職員／國家代表／廠商，廠商附 ROM 的製造商名，NFKC 大寫），不收指到空調色盤的 bae／ヤコブレフ；沒有頭像碼；調色盤只收用到的 11 組（MAME 色階），像素＝第幾組 × 16 ＋ 色。

## 進度

- ✓ 都市 89、國家 57、地區 7、關聯事業 15：和 SFC 逐值相同
- ✓ 劇本 4（1955／1970／1985／2000）：都市記錄、第二記錄、開局複製表、世界事件套用；ROM 與 RAM 完全一致
- ✓ 機種 53、製造商 12（和 SFC 逐值相同）
- ✓ 頭像 29 張圖 + 30 組調色盤、秘書／職員調色盤規則（MD 的非洲 12、中東／南美 8，和 SFC 對調）；kaodata `air2-md`
- ✓ 世界地圖、7 張地區地圖、都市標記位置
- 未解：劇本名（圖片）、都市記錄 3 個值、開局複製表、`0x47875`／`0x47C8C`、事件 message、機種旗標、國家代表規則未實測、頭像動畫與副本（見 ROM_FORMAT.md §8）

## 驗證結果

| 腳本 | 結果 |
|------|------|
| `verify_scenarios.py` | 4 劇本：`$FFA6F6` 劇本編號、`$FF1FC4` 開局季數、都市記錄 89/89、第二記錄 89/89、開局複製表 4/4 |
| `verify_faces.py` | 4 家本社搬到 7 個地區（2 輪 8 人）：玩家記錄 +0x23 都在 `Rom.secretary_palettes` 範圍內、秘書描述與它一致、職員 4 名 image 互不重複；35/35 個描述的 VRAM 960 bytes、CRAM、畫面逐像素相同（色 0 透明不比；91 個眨眼／說話 tile 都出自動畫資料） |
| `verify_maps.py` | 世界地圖與 7 張地區地圖：tile 704/704、CRAM 第 1 列、plane B 584/704 格（其餘被訊息框覆寫）、畫面上看得到的地圖像素 100% 相同；地區都市標記 89/89 在 `0x47626` 的位置 |
| `verify_kaodata_export.py` | 33/33 張（圖、group、廠商名）、checksums OK；kaodata `pnpm verify` 33 checked、0 mismatched |
