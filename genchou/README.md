# MD 蒼き狼と白き牝鹿・元朝秘史（Genghis Khan II）解析

KOEI，1993，MD。以**日版**為主：『蒼き狼と白き牝鹿・元朝秘史』（ROM 表頭 `(C)T-76 1993.JAN`，`GM T-76103 -00`，1.25MB，checksum 正確）；美版 *Genghis Khan II: Clan of the Gray Wolf*（`(C)T-76 1993.JUL`，`GM T-76066 -00`，1MB，文字英文）也能用 `--rom` 處理。兩版跑同一套程式，位址與記錄格式不同，`rom.py` 依表頭 `0x180` 的序號選 `Layout`。4 個劇本（1184／1206／1271／1185，第 4 個不在選單），結構和 SFC 版（`~/works/superfamicom-re/genchou/`）幾乎一樣，只是改成 68000 的指標與 big-endian；日版的人物格（26 bytes、姓名 16 bytes）與各劇本的女性表和 SFC 版相同，美版把姓名縮成 13 bytes、女性改成 20 人的共用表。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

Mega-CD 版（1993-09，多了劇本「源平の争乱」與 21 張專屬頭像）見 [docs/MEGACD.md](docs/MEGACD.md)；`cd.py` 把光碟的程式組成副 CPU 映像，沿用 `rom.py` 的解碼器（`LAYOUTS["C"]`），kaodata 匯出預設把 CD 版的追加併進 `genchou-md`。

## 指令

```bash
.venv/bin/python genchou/export.py [--rom ROM] [--out DIR]       # 日版 → genchou/output/、美版 → genchou/output/usa/
.venv/bin/python genchou/export_kaodata.py --out <kaodata>/data-local/genchou-md [--no-cd]
.venv/bin/python genchou/verify_kaodata_export.py --dataset <kaodata>/data-local/genchou-md
.venv/bin/python genchou/verify_scenarios.py [--rom ROM]        # 約 12 秒
.venv/bin/python genchou/verify_faces.py [--rom ROM]            # 約 1.5 分鐘
.venv/bin/python genchou/verify_persons.py [--rom ROM]          # 約 40 秒
.venv/bin/python genchou/verify_countries.py [--rom ROM]        # 約 40 秒
.venv/bin/python genchou/verify_cd_faces.py                     # Mega-CD，約 2.5 分鐘
.venv/bin/python genchou/verify_cd_scenarios.py                 # Mega-CD，約 5 秒
```

- ROM 預設直接讀 `roms/Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).zip`；美版用 `--rom "roms/Genghis Khan II - Clan of the Gray Wolf (USA).zip"`（各腳本都接受）。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。驗證需要 MAME（`tools/mame.py`、`tools/replay.py`），在背景執行不搶 focus。Mega-CD 版讀 `roms/megacd/Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).7z`（`--image`／`--cd` 可換），驗證用 Genesis Plus GX（`tools/gpgx.py --build`，要 Mega-CD 2 v2.00 BIOS）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：版本 `Layout`、文字（日版 SJIS＋半形片假名、美版 ASCII）、劇本（人物、國、王家、家族、子女、女性、地名）、解壓縮、頭像（專屬＋組合） |
| `cd.py` | Mega-CD 版：組副 CPU 映像（`SMAIN.PRG`、`INIT.PRG`、`GH2GRP.DAT` 的頭像格）、頭像碼 → 格 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 統一格式資料集 `genchou-md`（97 張專屬頭像＋56 個組合臉頭；日版另含 Mega-CD 版的 36 張頭像、79 人） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；nameZh 與 `data/name_zh.json` 一致；checksums |
| `data/name_zh.json` | [EXT] kaodata 的 `nameZh`（人物 id → 中文名，null＝無來源）；取自 kaodata 的 genchou-pc98／x68／pc88／fc（kaodata-re 從光榮中文 DOS 版取來、已改正錯字），依日文名對照；アルベルトゥス（113）在 pc98 有兩人，依前後人物取 120 號「阿爾伯特斯」 |
| `verify_scenarios.py` | 4 劇本載入後的 RAM 與 ROM 區塊逐 byte 比對 |
| `verify_faces.py` | 每個頭像碼寫進鐵木真的記錄，比對 VRAM tile、CRAM 調色盤、畫面 pixel |
| `verify_persons.py` | 人物數值寫進鐵木真，讀 情報 → 君主（Info → Ruler）面板 |
| `verify_countries.py` | 國的數值寫進オノン河流域（Onon River），讀主畫面國資訊 |
| `verify_cd_faces.py` | Mega-CD：每個頭像碼寫進鐵木真的記錄，比對 VRAM tile、CRAM、畫面 pixel |
| `verify_cd_scenarios.py` | Mega-CD：5 劇本載入後的 PRG-RAM、開局後的家族區與光碟資料比對 |

## 輸出（`genchou/output/`，美版在 `genchou/output/usa/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 4 劇本的人物（47／72／69／70）：王家、所在國、身分、體力／上限、戦闘 政治 魅力 指揮（E–A）、年齢、文化（推測）、頭像碼 |
| `family.csv` | 各劇本可選王家的家族區人物（共 90 筆） |
| `children.csv` | 家族區的子女（25 筆；名字，姓名後的 bytes 原樣，最後 2 bytes 是頭像碼） |
| `women.csv` | 日版：4 劇本各自的女性（14／32／23／23）；美版：共用的 20 人。所在國、頭像碼、未解欄位 |
| `countries.csv` | 4 劇本 × 國（14／33／33／33）：王家、相鄰、金、食糧、人口、住民配分、畫面值 +21..+23、部隊（推測）、未解欄位 |
| `houses.csv` | 4 劇本的王家（13／29／23／30）：國王、第一個國、后妃（美版）、文化（推測） |
| `places.csv` | 蒙古 14 地域＋世界 33 國：名稱、大地圖標籤位置 |
| `genchou.xlsx` | 以上各表（需 openpyxl） |
| `portraits/P###.png` | 專屬頭像 0–96（57 起是女性） |
| `faces/` | 每個人物（姓名＋頭像碼）與女性的頭像（`0000_テムジン.png`、`w00_ボルテ.png`；日版 383 張、美版 333 張） |
| `heads.png` | 56 個組合臉頭（每頭：5 部位全用版本 0、全用版本 1，2 倍） |
| `genchou-md/` | `export_kaodata.py --out genchou/output/genchou-md` 的輸出（自行指定時才有） |

## kaodata 資料集（`genchou-md`，遊戲代碼 GENCHOU，平台 MD）

預設用日版（kaodata 的其他版本都是日版）：405 人（男 310、女 73 為 1000 起、家族區子女 22 為 2000 起，比照其他 genchou 資料集），99 人用專屬頭像、306 人用組合臉；97 張專屬頭像（全部有人用，沒有 `group`）、56 個組合臉頭。

- `name` 照 ROM 原文（半形片假名轉全形）；`reading` 比照 `genchou-sfc`：只有片假名的名字轉成平假名（`・` 換空白），含漢字的名字不給；`nameZh` 取自 `data/name_zh.json`（400 人；MD 獨有的子女 2002、2016、2017、2019、2021 沒有中文版來源，不給）；美版不給 `nameZh`。
- 同名同頭像碼的人物合併；同名不同碼的組合臉變體 label 為「<地區>(推測)／男 N」「／女 N」。
- 和 `genchou-sfc` 對照：id 0–247（男）與 1000–1072（女）的 name、reading、頭像碼／專屬頭像編號全部一致（321/321）；MD 日版多了 id 248–309（劇本 1–4 家族區裡的 62 人，如ビルゲ・ベキ、和田義盛、ルイ8世）與 2000–2021 的子女。專屬頭像 97/97、組合臉 234/234（以碼比對）的 pixel 和 SFC 相同（色盤不同）；`parts` 只有 slot 順序不同（MD 是疊圖順序：上部、下部、眼、鼻、口）。
- Mega-CD 版（日版預設含，`--no-cd` 不含）：依 kaodata 的 `addedIn: "CD"` 規格，新增頭像 97–117（21 張）＋118–132（15 張 CD 預先合成、和卡帶版部位差 1 tile 的合成臉）；卡帶版沒有的 79 人接在各區段之後（男 310–370、女 1073–1083、子女 2022–2028），沒有 `nameZh`；CD 版臉不同的 16 個卡帶人物保留卡帶版的臉、CD 的臉放 `expressions`（「Mega-CD 版」）。共 484 人、133 張頭像。尚未交給 kaodata。
- 美版（`--rom` 美版）：355 人（男 313、女 20、子女 22），英文名沒有 `reading`；沒人用的 20 張女性頭像標 `group: 女性`、不給 `name`。
- 色盤是 palette line 1 的 16 色（MAME 色階）。組合臉的 slot 順序是遊戲的疊圖順序，眼鼻口會蓋住上部／下部的格子。

## 進度

- ✓ 日版／美版兩套 `Layout`（依序號判斷）
- ✓ 解壓縮（日 `$8D90`／美 `$33F0`，位元串流 LZ，`rom.decompress`）
- ✓ 4 劇本：區塊 A／B、家族區、地名與標籤位置的載入（日 `$276FC`／美 `$26250`）；劇本 4 的格 69 由載入程式清空
- ✓ 人物：姓名（日版 SJIS＋`ESC K` 半形片假名；美版含羅馬數字字形）、王家、所在、體力、戦闘 政治 魅力 指揮、年齢、頭像碼；身分 3 = 國王
- ✓ 國：相鄰、金、食糧、人口、畫面上的三個數值
- ✓ 王家：名稱、第一個國、國王、后妃（美版）；女性：姓名、所在、頭像碼（日版在區塊 B、各劇本一份）；家族區（8 人＋子女名字）
- ✓ 頭像：專屬 97 張（壓縮）＋組合臉 56 頭（5 部位 × 2 版本，未壓縮）；kaodata 資料集 `genchou-md`
- ✓ Mega-CD 版：5 劇本、頭像（含預先合成的 1,792 格），模擬器驗證，kaodata 匯出（未交）
- … 未解：見 ROM_FORMAT.md §7（子女格式、國與女性的多個欄位、大地圖、戰場、兵科等主檔表都還沒做）

## 驗證

| 腳本 | 內容 | 日版 | 美版 |
|------|------|------|------|
| `verify_scenarios.py` | 選單選劇本 1–3（劇本 4 在載入程式入口把 D2 改成 3），在載入程式返回處 dump RAM，比對區塊 A／B、家族區、地名、標籤 x／y；再用同一套解碼器解 RAM（人物、國、王家、日版女性） | 4 劇本全部 5476、1363、676、528、33、33 bytes 一致 | 4 劇本全部 5522、637、624、495、33、33 bytes 一致 |
| `verify_faces.py` | 標題畫面存檔；把頭像碼寫進劇本 1 鐵木真的 ROM 記錄後開新遊戲，比對選單畫面 VRAM tile `$200` 起 960 bytes、CRAM palette line 1、截圖的 40×48 pixel | 403/403（專屬 97、組合臉碼 306：人物、家族、子女、女性用到的全部） | 370/370（專屬 97、組合臉碼 273） |
| `verify_persons.py` | 人物的體力、能力、年齢寫進鐵木真，讀 情報 → 君主 面板（日版面板比美版左移 2 格，數字用 8×16 字型 `FONT_J`） | 346/346 種數值組合 | 346/346 |
| `verify_countries.py` | 國的 +10..+15、+21..+23 寫進第一個國，讀第一回合主畫面國資訊 | 113/113 | 113/113 |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `rom.face_tiles`（CD 版的頭像與 `cd.face_tiles`）逐 pixel 比對、nameZh、checksums | 含 CD：484/484 人、133/133 張、nameZh 484/484、OK（`--no-cd`：405/405、97/97） | 355/355 人、97/97 張、無 nameZh、OK |
| `verify_cd_faces.py`／`verify_cd_scenarios.py` | Mega-CD 版，見 docs/MEGACD.md §4 | 481/481；5 劇本一致 | — |

日版標題畫面要等到第 1600 幀左右才收 Start（美版 1100）。女性頭像碼加 `0x39` 才是專屬頭像編號，這是從女性頭像程式（日 `$7AE6`／美 `$77CC`）讀出來的；`verify_faces.py` 驗的是頭像表本身（男性路徑用碼 0–0x60 叫出全部 97 張），沒有另外在后妃畫面驗女性路徑。
