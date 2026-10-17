# MD 三國志III 解析

KOEI，1992.AUG，MD（1.5 MB，68000 C 編譯，大端序）。6 個劇本，46 州，532 人。資料內容就是 SFC 版（`~/works/superfamicom-re/san3/`）的表，改成大端序、加 pad、文字改 Shift-JIS；戰場資料與 SFC 逐 byte 相同。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

Mega-CD 版（多了劇本「黄巾の乱」、何進取代賈範、頭像預先合成）見 [docs/MEGACD.md](docs/MEGACD.md)；`cd.py` 讀光碟，沿用 `rom.py` 的解碼器，kaodata 匯出預設把 CD 版的追加併進 `san3-md`。

## 指令

```bash
.venv/bin/python san3/export.py [--rom ROM] [--out DIR]          # → san3/output/（CSV、XLSX、PNG）
.venv/bin/python san3/export_kaodata.py [--out DIR] [--no-cd]     # 預設 san3/output/kaodata/san3-md
.venv/bin/python san3/verify_kaodata_export.py [--dataset DIR]
.venv/bin/python tools/parts_sheet.py --dataset san3/output/kaodata/san3-md --out san3/output/kaodata
.venv/bin/python san3/verify_scenarios.py [--dump DIR | --load DIR]   # 約 27 秒
.venv/bin/python san3/verify_persons.py [--keep DIR]                  # 約 31 秒
.venv/bin/python san3/verify_text.py [--keep DIR]                     # 約 31 秒
.venv/bin/python san3/verify_faces.py [--keep DIR]                    # 約 35 秒
.venv/bin/python san3/verify_map.py [--keep DIR]                      # 約 9 秒
.venv/bin/python san3/verify_tactical.py                              # 約 5 秒
.venv/bin/python san3/verify_cd_faces.py                               # Mega-CD，約 9 秒
.venv/bin/python san3/verify_cd_scenarios.py                           # Mega-CD，約 3 秒
```

- ROM 預設讀 `roms/Sangokushi III (Japan).zip`，`--rom` 也接受 .md。
- 依賴：Pillow、openpyxl（沒有就只輸出 CSV）。地圖標字用 macOS 的ヒラギノ角ゴシック。
- 驗證腳本用 MAME（共用的 `tools/mame.py`、`tools/drive.py`），照按鍵序列玩到指令畫面；操作序列見 ROM_FORMAT.md §1。
- 顏色一律用 MAME 的 MD 色階（`rom.LEVELS`），和截圖一致。
- Mega-CD 版讀 `roms/megacd/Sangokushi III (Japan).7z`（`--image`／`--cd` 可換），驗證用 Genesis Plus GX（`tools/gpgx.py`）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字（SJIS＋外字 48 字）、字型、人物、6 劇本（人物、州、勢力、header、寶物持有者）、州名、寶物、頭像（一般＋合成）與調色盤、大地圖、戰場 |
| `cd.py` | Mega-CD 版：`Disc`（`SMAIN.PRG` 的人物表與調色盤、`ORGKAO.DAT` 頭像與合成臉碼表、`SINARIO.DAT` 7 劇本） |
| `lz.py` | MD 版 KOEI LZ 解碼（`$3374` 的 C 實作，沒有 SFC 的查表區塊） |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 資料集 `san3-md`（一般頭像 307 張＋合成臉 13 型；另含 Mega-CD 版的 19 張重畫合成臉、未使用的劉度合成臉 `D563`、何進、20 人的「Mega-CD 版」樣貌）；讀音在姓名間加空白（`data/surnames.tsv`）；沒人用的頭像標 `group`：事件人物 10 位（附名字）、新君主／新武將男女 |
| `verify_scenarios.py` | 6 劇本：劇本載入器跑完（`$1BCB4`）時 dump RAM，與 rom.py 逐欄比對 |
| `verify_persons.py` | 改寫 RAM 的州人物串列，讓劉備的武将一覧列出 531 人；用遊戲字型從截圖讀回姓名與 7 個數值 |
| `verify_text.py` | 同上，但先把 ROM 的人名換成字型的每個碼（2 輪），逐格比對畫出的 16 × 16 字形 |
| `verify_faces.py` | 遊戲自己的頭像程式組出全部頭像（`$F466` 迴圈），逐 byte 比對；再比對 3 張頭像的 VRAM、CRAM、截圖 |
| `verify_map.py` | 密偵畫面：大地圖 tile、調色盤、plane B name table、州標記、截圖 |
| `verify_tactical.py` | 呼叫遊戲的戰場載入程式 `$47F20` 68 次，逐 byte 比對 |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 `Rom.face_rgb`（CD 版的臉和 `cd.Disc`）逐 pixel 比對；checksums |
| `verify_cd_faces.py` | Mega-CD：頭像碼寫進君主選擇畫面的 8 個君主，比對 VRAM（全部 618 格） |
| `verify_cd_scenarios.py` | Mega-CD：7 劇本載入後的工作 RAM 與 `SINARIO.DAT` 比對（人物、州） |

## 輸出（`san3/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 532 人：姓名、讀音、生年、頭像（`P###` 一般／`C####` 合成碼）、陸指 水指 武力 智力 政治 魅力、野心 運 冷静 勇猛、相性、義理、血縁、未解欄位 |
| `person_scenarios.csv` | 6 × 531：登場、年齢、身分、勢力、所在、忠誠、兵士、訓練、士気、寶物 |
| `provinces.csv` | 46 州：名稱、讀音、地圖格、未解欄位 |
| `province_scenarios.csv` | 6 × 46：勢力、人口 金 米 開発 治水 商業 税率 民忠 訓練 士気、未解欄位 |
| `factions.csv` | 各劇本的勢力：君主、首都、州、旗色、未解欄位 |
| `items.csv` | 13 寶物：種類、加算、6 劇本的持有者 |
| `scenarios.csv` | 6 劇本：標題、年、勢力數、君主、header、extra |
| `san3.xlsx` | 以上各表 |
| `faces/`、`portraits/` | 532 人的頭像（合成臉已組好）；一般頭像 P001–P307 |
| `composite_parts.png` | 合成臉 13 型 × 5 部位的所有變體（灰 = 不畫） |
| `font.png` | 2151 格字型（含結尾標記），依碼排序 |
| `map.png`、`map_provinces.png` | 大地圖 240 × 224（州格是黑格）；放大 4 倍標州號與州名 |
| `tactical/` | 68 筆戰場：三層 CSV＋B 層示意圖（不是遊戲畫面） |
| `kaodata/san3-md/`、`kaodata/mob_parts*` | kaodata 資料集；`tools/parts_sheet.py` 的零件總覽 |

## 進度

- ✓ 文字：Shift-JIS＋外字 48 字；字型 2150 字、半形字
- ✓ 人物 532 人；6 劇本的人物、州、勢力、header、extra、寶物持有者
- ✓ 州名、寶物、州的地圖座標（45／46）
- ✓ 頭像：一般 307 張（2 組調色盤）、合成臉 13 型；kaodata `san3-md`
- ✓ 大地圖：name table、tile、調色盤、州格
- ✓ 戰場 68 筆（資料；與 SFC 相同）
- ✓ Mega-CD 版：7 劇本（人物、州）、頭像 618 格與合成臉碼表，模擬器驗證，kaodata 匯出（未交）
- … 未解：戰場畫面組裝、南海的地圖座標、各表的未解欄位（見 ROM_FORMAT.md §10）

## 驗證結果（2026-10-16）

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 6 劇本在 `$1BCB4` dump RAM，header、州（20 欄）、勢力、人物（11–13 欄）、extra、寶物持有者逐欄比對 | 每劇本 header 1/1、州 46/46、勢力 21/21、人物 531/531、extra 22/22、寶物 13/13，OK |
| `verify_persons.py` | 武将一覧 67 頁 × 3 欄組截圖，字型比對讀回 姓名 齢 知 政 武 魅 陸 水 | 531/531 人全同，OK（人物 531 貂蝉不在劇本裡，未涵蓋） |
| `verify_text.py` | 人名換成字型的每個碼，截圖逐格比對字形 | 2149/2149 碼相同（1 個空白字形不比），OK |
| `verify_faces.py` | 遊戲的 `$F42C` 依序組出每個頭像，比 `$FFB004` 的 960 bytes 與調色盤號；省份畫面換成 3 張頭像比 VRAM tile `0x208`、CRAM 第 3 列 16 色、截圖 40 × 48 | 一般 307/307、合成 311/311；劉備 0xA1、77（調色盤 1、用到色 15）、0x8DA4（合成）：VRAM OK、CRAM 16/16、截圖 1920/1920 pixel，OK |
| `verify_map.py` | 密偵畫面 | tile 0x2A1 OK、調色盤 OK、name table 794/794、州標記 45/45、截圖 48208/48208 pixel，OK |
| `verify_tactical.py` | `$FF9014` = 0–67 逐一呼叫 `$47F20`，比 `$FFCC04` | 68/68，OK |
| `verify_kaodata_export.py` | 參考渲染器與 `Rom.face_rgb` | 人物 532/532（合成 311）、頭像 307/307、checksums OK；含 CD：人物 533/533、頭像 327/327、樣貌 20 |
| `verify_cd_faces.py`／`verify_cd_scenarios.py` | Mega-CD 版（2026-10-17），見 docs/MEGACD.md §5 | 頭像 619/619；7 劇本人物 531/531、州 46/46 |

人物的 RAM 欄位另外對照畫面：劇本 1 平原 人 370000、金 2300、米 50000、兵 9500；徴兵清單 劉備 68、関羽 103（98 + 寶物 5）、張飛 99；募兵清單魅力 99、96、36。
