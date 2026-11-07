# MD 信長の野望・覇王伝 解析

KOEI，1993，MD（ROM 表頭 `(C)T-76 1993.DEC`，`GM T-76153 -00`，2 MB，checksum 正確）。3 個劇本（1551、1568、1582 年），人物 Id 0–819（實際 817 人）、110 城、64 國。文字是 Shift-JIS（長宗我部／香宗我部用 3 個外字碼）。資料結構與 SFC 版（`~/works/superfamicom-re/haouden`）相同，只是指標改成 4 bytes、多了對齊用的空 byte；數值與 SFC Rev 1 完全相同。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

Mega-CD 版（1994，多了 1583 年劇本、28 人改用新專屬頭像）見 [docs/MEGACD.md](docs/MEGACD.md)；`cd.py` 讀光碟，沿用 `rom.py` 的解碼器，kaodata 匯出預設把 CD 版的追加併進 `nobu5-md`。

## 指令

```bash
.venv/bin/python haouden/export.py [--rom ROM] [--out DIR]          # → haouden/output/（CSV、XLSX、頭像 PNG），約 2 秒
.venv/bin/python haouden/export_kaodata.py --out <kaodata>/data-local/nobu5-md [--no-cd]
.venv/bin/python haouden/verify_kaodata_export.py --dataset <kaodata>/data-local/nobu5-md
.venv/bin/python haouden/verify_scenarios.py                 # 約 10 秒
.venv/bin/python haouden/verify_faces.py [--quick]           # 約 2 分鐘
.venv/bin/python haouden/verify_cd_faces.py                 # Mega-CD，約 50 秒
.venv/bin/python haouden/verify_cd_scenarios.py             # Mega-CD，約 3 秒
```

- ROM 預設直接讀 `_original/md/Nobunaga no Yabou - Haouden (Japan).zip`，`--rom` 也接受 .md／.bin。
- LZ 解壓用 `lz.py`（遊戲 `$3C36` 的 KOEI LZ，和 MD 三國志III 相同，取自 `san3/lz.py`）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。驗證腳本用 MAME（`tools/mame.py`、`tools/replay.py`）。
- Mega-CD 版讀 `_original/megacd/Nobunaga no Yabou - Haouden (Japan).7z`（`--image`／`--cd` 可換），驗證用 Genesis Plus GX（`tools/gpgx.py`）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：劇本（人物、城、大名）、後登場人物、名稱表、城的地圖位置、合戦與城類表、頭像（專屬＋組合） |
| `cd.py` | Mega-CD 版：`Disc`（`SMAIN.PRG` 的頭像表、`ORGKAO.DAT`、`SAVEDAT1`–`4.DAT` 劇本、`TAIKI.DAT` 後登場人物；組合臉沿用卡帶版） |
| `lz.py` | KOEI LZ 解壓 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `nobu5-md`（348 張專屬頭像＋6 組組合臉；沒有人物用的 27 張標上 `group` 姫／事件人物／不明，有標籤的附 `name`；另含 Mega-CD 版的 28 張頭像與 28 人的「Mega-CD 版」樣貌） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 3 劇本載入後的 RAM 與 ROM 劇本映像逐 byte 比對，再從 RAM 解碼比對 |
| `verify_faces.py` | 927 個頭像碼逐一換進選大名確認畫面，比對遊戲寫進 VRAM 的 tile 與 CRAM 調色盤 |
| `verify_cd_faces.py` | Mega-CD：同上，用 Genesis Plus GX |
| `verify_cd_scenarios.py` | Mega-CD：4 劇本載入後的 RAM 與 `SAVEDAT1`–`4.DAT` 逐 byte 比對 |

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

kaodata 資料集 `nobu5-md`（遊戲代碼 NOBU5）：817 人，321 人用專屬頭像、496 人用組合臉（6 組 × 5 部位 × 5 款，`code` 是遊戲的組合碼）；348 張專屬頭像（含 Mega-CD 版時 376 張，28 人多一個「Mega-CD 版」樣貌，見 docs/MEGACD.md §5；kaodata 已收）。ROM 沒有讀音，所以沒有 `reading`。像素存色號，色盤是 MD 的頭像調色盤（MAME 色階換算）。

## 進度

| 項目 | 狀態 | 證據 | 說明 |
|------|------|------|------|
| 劇本載入（劇本映像＋共用區＋1582 年的修正） | ✅ | emu | `verify_scenarios.py` 3 劇本 RAM 各 29788 bytes 與 `Rom.ram_image` 相同；ROM_FORMAT §4 |
| 人物、城、大名的欄位 | ✅ | emu+cross | 從 RAM 解碼一致，欄位意義與 SFC 版（Rev 1）解碼逐欄相同，MD 畫面沒有另外截圖；ROM_FORMAT §4.1–4.3 |
| 後登場人物 | 🟡 | cross | 格式與資料和 SFC 版相同，沒有在模擬器裡等到登場；ROM_FORMAT §4.4 |
| 名稱表（國、官位、家宝、合戦、能力名、姫、地形）與外字 | ✅ | cross | 內容與 SFC 版相同；ROM_FORMAT §3 |
| 城的大地圖位置、合戦對應城、城類 | ✅ | code+cross | 程式參照點已確認，資料與 SFC 版逐 byte 相同；ROM_FORMAT §5 |
| 頭像：專屬 348 張＋組合臉 6 組（頭像碼 927 個） | ✅ | emu+modified | `verify_faces.py` 把龍造寺隆信的人物 Id 換成每個頭像碼，比對 VRAM 與 CRAM；ROM_FORMAT §6 |
| 沒有人物用的頭像的歸屬（姫、事件人物） | 🟡 | code | 依 `$7056` 的呼叫處與同畫面的標籤判定，仍有 11 張不明；ROM_FORMAT §6 |
| kaodata 資料集 `nobu5-md` | ✅ | checksum | `verify_kaodata_export.py` |
| 大地圖、戰場地圖圖像 | ❌ | | 見「未解」 |
| Mega-CD 版：4 劇本（含 1583 年） | ✅ | emu | `verify_cd_scenarios.py` PRG-RAM 與 `SAVEDAT1`–`4.DAT` 29814 bytes 一致；MEGACD §3 |
| Mega-CD 版：頭像（新增 28 張） | ✅ | emu+modified | `verify_cd_faces.py` 把每個 face id 寫進龍造寺隆信的記錄，專屬 376/376、組合 551/551；MEGACD §2 |
| Mega-CD 版：後登場人物（`TAIKI.DAT`） | 🟡 | cross | 前 3 串與卡帶版逐筆相同，沒有在模擬器裡驗證；MEGACD §4 |
| Mega-CD 版：1583 年劇本的城、大名 | ❌ | | 見「未解」 |
| Mega-CD 版：kaodata 併入 `nobu5-md` | ✅ | checksum | `verify_kaodata_export.py`（含 CD 頭像 376/376）；MEGACD §5 |
| Mega-CD 版：其他光碟檔案（開場、戰場、事件等） | ❌ | | 見「未解」 |

## 未解

- 劇本開頭區 `$FF001A–$FF01BB`、misc 區 `$FF6DD0–$FF6F53`、共用區的內容（ROM_FORMAT §4、§8）
- 人物 +24–27、+29、+30、+32 高 4 位元、+38–40、+42–43（ROM_FORMAT §4.2、§8）
- 大名 +4、+5–35（推測關係）、+37–39、+40（家紋，推測）（ROM_FORMAT §4.3、§8）
- 城 +0–3、+16、+26、+41；本城旗標（推測）（ROM_FORMAT §4.1、§8）
- 後登場人物 +1、+2、+24、+25、+28、+29；沒有在模擬器裡等到登場（ROM_FORMAT §4.4、§8）
- 頭像 151、152、327–329、331–335、338 的用途：沒有人物用，ROM 裡找不到以常數指定的地方（ROM_FORMAT §6）
- 大地圖（tilemap、tile、調色盤）與戰場地圖，尚未找（ROM_FORMAT §8）
- 字型在 ROM 中的位置（文字是 Shift-JIS，不需要，未找）（ROM_FORMAT §8）
- Mega-CD 版：1583 年劇本的城、大名沒有整理（`export.py` 只處理卡帶版）；`TAIKI.DAT` 沒有在模擬器裡驗證（MEGACD §4、§6）
- Mega-CD 版：光碟上其他檔案（開場、戰場、事件等）（MEGACD §1、§6）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 選劇本後（人數畫面）RAM `$FF001A–$FF7475` 與 `Rom.ram_image` 逐 byte 比對；再從 RAM 解碼人物、城、大名 | 3 劇本各 29788/29788 bytes 相同；人物 412/412、459/459、413/413，城 110/110 × 3，大名 48/48、43/43、27/27；9 秒 |
| `verify_faces.py` | 1551、1 人、選大名畫面（游標在龍造寺隆信）存 savestate；把他的人物 Id（`$FF0D0E`）換成每個頭像碼後按 C，比對確認框寫到 VRAM `$4000` 的 960 bytes 與 CRAM 第 1 列；未改動時 = 頭像碼 0x30 | 未改動 OK；專屬頭像 348/348、組合臉 579/579、調色盤 NG 0、ALL OK；122 秒 |
| `verify_kaodata_export.py` | 參考渲染器與 `Rom.face_pixels` 逐 pixel 比對、checksums | 人物 817/817、專屬頭像 348/348、checksums OK；含 CD：頭像 376/376、樣貌 28 |
| `verify_cd_faces.py`／`verify_cd_scenarios.py` | Mega-CD 版，見 docs/MEGACD.md §4 | 專屬 376/376、組合 551/551；4 劇本 29814 bytes 一致 |

另外和 SFC 版的解碼（`~/works/superfamicom-re/haouden/rom.py`）逐欄比對：3 劇本的人物、城、大名、後登場人物所有已知欄位都相同，人物 +29（SFC +27）與 SFC **Rev 1** 相同（與 Rev 0 有 34 人不同）；姓名只有字形差異（蛎崎／蠣崎、尭煕／尭熙、頴娃／穎娃）。MD 版畫面上的欄位意義沒有另外逐一截圖對照。
