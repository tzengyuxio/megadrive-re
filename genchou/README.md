# MD Genghis Khan II: Clan of the Gray Wolf 解析

KOEI，1993，MD（美版，ROM 表頭 `(C)T-76 1993.JUL`，`GM T-76066 -00`，1MB，checksum 正確）。即『蒼き狼と白き牝鹿・元朝秘史』，MD 只有美版，文字是英文。4 個劇本（1184／1206／1271／1185，第 4 個不在選單），結構和 SFC 版（`~/works/superfamicom-re/genchou/`）幾乎一樣，只是改成 68000 的指標與 big-endian。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python genchou/export.py [--rom ROM] [--out DIR]       # → genchou/output/（CSV、XLSX、PNG）
.venv/bin/python genchou/export_kaodata.py --out <kaodata>/data-local/genchou-md
.venv/bin/python genchou/verify_kaodata_export.py --dataset <kaodata>/data-local/genchou-md
.venv/bin/python genchou/verify_scenarios.py                    # 約 12 秒
.venv/bin/python genchou/verify_faces.py                        # 約 1.5 分鐘
.venv/bin/python genchou/verify_persons.py                      # 約 40 秒
.venv/bin/python genchou/verify_countries.py                    # 約 40 秒
```

- ROM 預設直接讀 `roms/Genghis Khan II - Clan of the Gray Wolf (USA).zip`。
- 依賴：Pillow；openpyxl（可選，匯出 .xlsx）。驗證需要 MAME（`tools/mame.py`、`tools/replay.py`），在背景執行不搶 focus。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、劇本（人物、國、王家、家族、子女、女性、地名）、解壓縮（`$33F0`）、頭像（專屬＋組合） |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 統一格式資料集 `genchou-md`（97 張專屬頭像＋56 個組合臉頭） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 4 劇本載入後的 RAM 與 ROM 區塊逐 byte 比對 |
| `verify_faces.py` | 每個頭像碼寫進鐵木真的記錄，比對 VRAM tile、CRAM 調色盤、畫面 pixel |
| `verify_persons.py` | 人物數值寫進鐵木真，讀 Info → Ruler 面板 |
| `verify_countries.py` | 國的數值寫進 Onon River，讀主畫面國資訊 |

## 輸出（`genchou/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 4 劇本的人物（47／72／69／70）：王家、所在國、身分、體力／上限、戦闘 政治 魅力 指揮（E–A）、年齢、文化（推測）、頭像碼 |
| `family.csv` | 各劇本可選王家的家族區人物（共 90 筆） |
| `children.csv` | 家族區的子女（25 筆；名字，其餘 7 bytes 原樣） |
| `women.csv` | 女性 20 人：所在國、頭像碼、未解欄位 |
| `countries.csv` | 4 劇本 × 國（14／33／33／33）：王家、相鄰、金、食糧、人口、住民配分、畫面值 +21..+23、部隊（推測）、未解欄位 |
| `houses.csv` | 4 劇本的王家（13／29／23／30）：國王、第一個國、后妃、+34（推測為文化） |
| `places.csv` | 蒙古 14 地域＋世界 33 國：名稱、大地圖標籤位置 |
| `genchou.xlsx` | 以上各表（需 openpyxl） |
| `portraits/P###.png` | 專屬頭像 0–96（57 起是女性） |
| `faces/` | 每個人物（姓名＋頭像碼）與女性的頭像（`85F8_Megujin_Ult.png`、`w00_Borte.png`） |
| `heads.png` | 56 個組合臉頭（每頭：5 部位全用版本 0、全用版本 1，2 倍） |
| `genchou-md/` | `export_kaodata.py --out genchou/output/genchou-md` 的輸出（自行指定時才有） |

kaodata 資料集（`genchou-md`，遊戲代碼 GENCHOU，平台 MD）：355 人（男 313、女 20 為 1000 起、家族區子女 22 為 2000 起，比照其他 genchou 資料集），82 人用專屬頭像、273 人用組合臉；97 張專屬頭像、56 個組合臉頭。沒人用的 20 張女性頭像（美版只留 20 位女性）標 `group: 女性`，ROM 裡沒有她們的名字所以不給 `name`。人名是英文，所以沒有 `reading`；各版本都沒有中文名，也沒有 `nameZh`。色盤是 palette line 1 的 16 色（MAME 色階）。組合臉的 slot 順序是遊戲的疊圖順序（上部、下部、眼、鼻、口），眼鼻口會蓋住上部／下部的格子。

## 進度

- ✓ 解壓縮（`$33F0`，位元串流 LZ，`rom.decompress`）
- ✓ 4 劇本：區塊 A／B、家族區、地名與標籤位置的載入（`$26250`）；劇本 4 的格 69 由載入程式清空
- ✓ 人物：姓名（含羅馬數字字形）、王家、所在、體力、戦闘 政治 魅力 指揮、年齢、頭像碼；身分 3 = 國王
- ✓ 國：相鄰、金、食糧、人口、畫面上的三個數值
- ✓ 王家：名稱、第一個國、國王、后妃；女性：姓名、所在、頭像碼；家族區（8 人＋子女名字）
- ✓ 頭像：專屬 97 張（壓縮）＋組合臉 56 頭（5 部位 × 2 版本，未壓縮）；kaodata 資料集 `genchou-md`
- … 未解：見 ROM_FORMAT.md §7（子女格式、國與女性的多個欄位、大地圖、戰場、兵科等主檔表都還沒做）

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 選單選劇本 1–3（劇本 4 在載入程式入口把 D2 改成 3），在 `$26384` dump RAM，比對區塊 A／B、家族區、地名、標籤 x／y；再用同一套解碼器解 RAM | 4 劇本全部 5522/5522、637/637、624/624、495/495、33/33、33/33 bytes；人物、國、王家解碼一致 |
| `verify_faces.py` | 標題畫面存檔；把頭像碼寫進劇本 1 鐵木真的 ROM 記錄後開新遊戲，比對選單畫面 VRAM tile `$200` 起 960 bytes、CRAM palette line 1、截圖的 40×48 pixel | 357/357（專屬 97、組合臉碼 260：人物、家族、女性用到的全部）；子女的碼另跑 `--codes`：22/22（專屬 9、組合 13） |
| `verify_persons.py` | 人物 +15..+18 寫進鐵木真（`$FF0011`），讀 Info → Ruler 面板的 Polit／War／Lead／Charm／Body／Age | 346/346 種數值組合（涵蓋 4 劇本人物與家族區 348 筆） |
| `verify_countries.py` | 國的 +10..+15、+21..+23 寫進 Onon River（`$FF0A3A`），讀第一回合主畫面國資訊 | 113/113 |
| `verify_kaodata_export.py` | 參考渲染器（`tools/kaodata.py`）與 `rom.face_tiles` 逐 pixel 比對、checksums | 355/355 人（女 20、子女 22）、97/97 張、OK |

女性頭像碼加 `0x39` 才是專屬頭像編號，這是從 `$77CC` 的程式讀出來的；`verify_faces.py` 驗的是頭像表本身（男性路徑 `$7752` 用碼 0–0x60 叫出全部 97 張），沒有另外在后妃畫面驗女性路徑。
