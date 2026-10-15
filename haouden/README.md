# MD 信長の野望・覇王伝 解析

KOEI，1993，MD（ROM 表頭 `(C)T-76 1993.DEC`，`GM T-76153 -00`，2 MB，checksum 正確）。3 個劇本（1551、1568、1582 年），人物 Id 0–819（實際 817 人）、110 城、64 國。文字是 Shift-JIS（長宗我部／香宗我部用 3 個外字碼）。資料結構與 SFC 版（`~/works/superfamicom-re/haouden`）相同，只是指標改成 4 bytes、多了對齊用的空 byte；數值與 SFC Rev 1 完全相同。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python haouden/export.py [--rom ROM] [--out DIR]          # → haouden/output/（CSV、XLSX、頭像 PNG），約 2 秒
.venv/bin/python haouden/export_kaodata.py --out <kaodata>/data-local/nobu5-md
.venv/bin/python haouden/verify_kaodata_export.py --dataset <kaodata>/data-local/nobu5-md
.venv/bin/python haouden/verify_scenarios.py                 # 約 10 秒
.venv/bin/python haouden/verify_faces.py [--quick]           # 約 2 分鐘
```

- ROM 預設直接讀 `roms/Nobunaga no Yabou - Haouden (Japan).zip`，`--rom` 也接受 .md／.bin。
- LZ 解壓用 `lz.py`（遊戲 `$3C36` 的 KOEI LZ，和 MD 三國志III 相同，取自 `san3/lz.py`）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。驗證腳本用 MAME（`tools/mame.py`、`tools/replay.py`）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：劇本（人物、城、大名）、後登場人物、名稱表、城的地圖位置、合戦與城類表、頭像（專屬＋組合） |
| `lz.py` | KOEI LZ 解壓 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `nobu5-md`（348 張專屬頭像＋6 組組合臉；沒有人物用的 27 張標上 `group` 姫／事件人物／不明，有標籤的附 `name`） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 3 劇本載入後的 RAM 與 ROM 劇本映像逐 byte 比對，再從 RAM 解碼比對 |
| `verify_faces.py` | 927 個頭像碼逐一換進選大名確認畫面，比對遊戲寫進 VRAM 的 tile 與 CRAM 調色盤 |

## 輸出（`haouden/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 817 人（Id 0–819，139、140、456 未用）：姓名（含改名後的其他名）、生年、政治 戦闘 智謀 采配 野望、初登場、登場劇本、頭像碼與來源 |
| `person_scenarios.csv` | 3 劇本開局的人物（412／459／413）：RAM 位址、年齢、能力、忠誠、知行、身分（大名／城主／家臣）、所在城、大名家、未解欄位 |
| `future_persons.csv` | 3 劇本之後才登場的人物（283／133／59）：登場年、登場城、能力、未解欄位 |
| `castles.csv` | 3 劇本 × 110 城：國、大名家、城主、武將數、本城旗標（推測）、規模、防、貫、人、商、練、治、兵、銭、糧、鉄砲、馬、大地圖位置（格）、無城戰場的城類、未解欄位 |
| `daimyo.csv` | 3 劇本的大名（48／43／27）：當主、所轄城、貢献、家紋（推測）、未解欄位 |
| `provinces.csv`、`titles.csv`、`treasures.csv`、`princesses.csv`、`terrains.csv` | 64 國、226 官位、120 家宝、93 姫、15 種地形的名稱 |
| `historic_battles.csv` | 15 場合戦與對應的城 |
| `haouden.xlsx` | 以上各表（需 openpyxl） |
| `faces/` | 927 個頭像碼的頭像（`048_龍造寺隆信.png`，40×48，組合臉已組好；人物 Id = 頭像碼） |

kaodata 資料集 `nobu5-md`（遊戲代碼 NOBU5）：817 人，321 人用專屬頭像、496 人用組合臉（6 組 × 5 部位 × 5 款，`code` 是遊戲的組合碼）；348 張專屬頭像。ROM 沒有讀音，所以沒有 `reading`。像素存色號，色盤是 MD 的頭像調色盤（MAME 色階換算）。

## 進度

- ✓ 劇本載入程式 `$1E2EE`：劇本映像（0x6F3A bytes → `$FF001A`）＋共用區（0x522 bytes → `$FF6F54`）＋1582 年的 2 byte 修正
- ✓ 人物 44 bytes、城 42 bytes、大名 42 bytes、後登場人物 30 bytes；欄位對應 SFC 版（城名其實是 4 字，見 ROM_FORMAT.md §4.1）
- ✓ 名稱表：國 64、官位 226、家宝 120、合戦 15、能力名 8、姫 93、地形 15；長宗我部／香宗我部外字
- ✓ 城的大地圖位置、合戦對應城、城類（程式參照點已確認，資料與 SFC 相同）
- ✓ 頭像：專屬 348 張＋組合臉 6 組；頭像碼 0–0x3A0（0x398、0x399 遊戲不處理）；kaodata `nobu5-md`
- 未做：大地圖、戰場地圖圖像；字型（文字是 Shift-JIS，不需要字表）
- 未解：見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md) §8

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 選劇本後（人數畫面）RAM `$FF001A–$FF7475` 與 `Rom.ram_image` 逐 byte 比對；再從 RAM 解碼人物、城、大名 | 3 劇本各 29788/29788 bytes 相同；人物 412/412、459/459、413/413，城 110/110 × 3，大名 48/48、43/43、27/27；9 秒 |
| `verify_faces.py` | 1551、1 人、選大名畫面（游標在龍造寺隆信）存 savestate；把他的人物 Id（`$FF0D0E`）換成每個頭像碼後按 C，比對確認框寫到 VRAM `$4000` 的 960 bytes 與 CRAM 第 1 列；未改動時 = 頭像碼 0x30 | 未改動 OK；專屬頭像 348/348、組合臉 579/579、調色盤 NG 0、ALL OK；122 秒 |
| `verify_kaodata_export.py` | 參考渲染器與 `Rom.face_pixels` 逐 pixel 比對、checksums | 人物 817/817、專屬頭像 348/348、checksums OK |

另外和 SFC 版的解碼（`~/works/superfamicom-re/haouden/rom.py`）逐欄比對：3 劇本的人物、城、大名、後登場人物所有已知欄位都相同，人物 +29（SFC +27）與 SFC **Rev 1** 相同（與 Rev 0 有 34 人不同）；姓名只有字形差異（蛎崎／蠣崎、尭煕／尭熙、頴娃／穎娃）。MD 版畫面上的欄位意義沒有另外逐一截圖對照。
