# MD 三國志V（中國盜版）解析

`_original/md/San Guo Zhi V (China) (Unl).zip`，2MB，無授權中國製（標題畫面標記「SKOB」），表頭被程式碼覆蓋、checksum 不對，MAME 照樣能跑。繁體中文，自訂字碼。不是光榮正式作品，所以不出 kaodata 資料集。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 判斷

- 是光榮《三國志V》的移植／改作：人物 500 人與三國志V 完全對應（503 個名字中 500 人與 DOS 中文版人名一致，只差 ROM 誤字），7 個劇本、47 城、12 陣形、33 戰法、38 寶物都是三國志V 的內容。程式是重寫的 68000 程式，資料表不是光榮格式，也沒有 KOEI LZ 壓縮。
- 頭像是三國志V 的原畫縮小重繪：與 kaodata `san5pk-dos`（DOS 中文版）同名人物並排，構圖、姿勢、服飾一致；MD 版是 40×48、MD 16 色重新上色，所以不是逐 pixel 相同。灰階相關係數同名配對平均 0.54、隨機 0.26；497 人中 52% 最像的就是同名那張。

## 指令

```bash
# 人物、7 劇本的人物／城／勢力／關係、寶物、字串表、頭像、字型表、選君主地圖 → sgz5/output/
.venv/bin/python sgz5/export.py [--out DIR]

# 驗證（MAME 跑遊戲本身的程式；MAME 在背景執行不搶 focus）
.venv/bin/python sgz5/verify_scenarios.py   # 7 劇本：載入完成時的 RAM 與 rom.py 逐欄比對（約 15 秒）
.venv/bin/python sgz5/verify_text.py        # 503 人名＋47 城名：畫進 VRAM 的字形 = ROM 字型（約 6 分）
.venv/bin/python sgz5/verify_faces.py       # 536 張頭像逐 pixel ＋ 500 人能力值讀回（約 7 分）
.venv/bin/python sgz5/verify_persons.py     # 500 人 × 8 個數字，武將一覽讀回（約 2 分）
.venv/bin/python sgz5/verify_cities.py      # 7 劇本 × 47 城 × 8 個數字，城市資訊讀回（約 3 分）

# 頭像 sheet（portrait-sheet skill；先跑 export.py）
.venv/bin/python sgz5/sheet_manifest.py
.venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py sgz5/output/portrait-sheet/sgz5/sheet.json \
    sgz5/output/portrait-sheet/sgz5/out
```

依賴：Pillow、numpy（`tools/`）；驗證需 `mame`（不需 BIOS）。`persons.csv` 的 `[EXT]三國志V_DOS_id` 讀 `~/works/kaodata/data/san5pk-dos/dataset.json`（沒有就留空）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：字型與字串、人物、城、勢力、寶物、劇本、頭像、選君主地圖 |
| `data/charset.txt` | 字型 7 bank × 240 字的轉寫（753 字；人名對齊三國志V 人名＋目視，其餘 〓） |
| `export.py` | 匯出 CSV（UTF-8-BOM）／PNG |
| `verify_*.py` | 模擬器驗證（見上） |
| `sheet_manifest.py` | 頭像 sheet 的 manifest（`portrait-sheet/1`）：500 人一人一格（493 張臉，共用的標「共用N人」，其餘「專屬」）、基本能力值；沒有人用的頭像 500–503 標 unseen（504–535 與 104–135 相同，不收），人名照 ROM（誤字不改） |

## 輸出（`sgz5/output/`，不進版控）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 500 人：姓名、基本能力（武力 智力 政治 魅力，不含寶物）、+A（未解）、頭像號、[EXT] 三國志V DOS id |
| `person_scenarios.csv` | 7 劇本 × 500 人：身份、所在、能力（含寶物加成）、經驗值、威名、忠誠、將軍職碼、寶物 |
| `cities.csv` | 7 劇本 × 47 城：勢力、君主、太守、農、商、人口、民忠、治水度、士兵數、訓練、士氣、+16/+18（未解） |
| `forces.csv` | 各劇本有君主的勢力：君主、♡、金、糧、+C（未解）、城數 |
| `relations.csv` | 各劇本勢力對勢力的數值（意義未解） |
| `items.csv` | 38 寶物；前 32 件的能力加成與各劇本持有者 |
| `strings.csv` | 城名、陣形、戰法、寶物、指令、選單等字串表（訊息類字串多為 〓） |
| `faces/` | `000_丁奉.png`…`499_*.png`（人物）、`extra_500`…`extra_535`（無人物引用） |
| `font.png` | 字型表：7 bank × 15 列 × 16 字 |
| `map.png`、`map_labelled.png` | 選君主畫面的地圖（plane B）；labelled 版標出 47 城節點 |
| `portrait-sheet/sgz5/` | 頭像 sheet：`sheet.json`、`faces/`、`out/sgz5-p01.png`…（8 張，以 B 類交接單交到 simagame 的 `inbox/`） |

## 驗證結果（2026-10-16，MAME 實跑）

- `verify_scenarios.py`：7 劇本全部 ALL OK——人物 500/500、城 47/47、勢力 20/20、城的勢力 47/47、君主 20/20、寶物持有 32/32、關係表 400/400、年月 1/1。
- `verify_text.py`：人名 503/503、城名 47/47，VRAM 上的字形與 ROM 字型逐 bit 相同（以 ROM patch 讓選君主畫面畫出指定的名字）。
- `verify_faces.py`：頭像 536/536（VRAM tile、CRAM 色盤、畫面 40×48 逐 pixel）；能力值 500/500 人 × 4 個數字從君主資訊欄讀回。
- `verify_persons.py`：502/502（500 人＋2 組自訂值）× 8 個數字（武力 智力 政治 魅力 經驗值 威名 氣力 忠誠）從武將一覽讀回；忠誠 101 的 266 人畫面不顯示數字。
- `verify_cities.py`：331/331（7 劇本 × 47 城＋2 組自訂值）× 8 個數字從城市資訊欄讀回。

## 進度

| 項目 | 狀態 | 證據 | 說明 |
|------|------|------|------|
| 分診：三國志V 移植、無壓縮、自訂字碼 | ✅ | cross | 500 人名與三國志V DOS 中文版一致；見「判斷」、ROM_FORMAT 總覽 |
| 字型與人名 503、城名 47 | ✅ | emu+modified | `verify_text.py` patch 名字查表，VRAM 字形與 ROM 字型逐 bit 相同；ROM_FORMAT「文字與字型」 |
| 陣形、戰法、寶物、指令、選單字串 | 🟡 | code | 字串表結構已解，字為目視轉寫，沒有模擬器比對；ROM_FORMAT「字串表」 |
| 7 劇本的人物、城、勢力、寶物持有、關係表 | ✅ | emu | `verify_scenarios.py` 載入完成時的 RAM 與 `rom.py` 逐欄比對全部一致；ROM_FORMAT「劇本」 |
| 人物欄位意義（8 個數字） | ✅ | emu+modified | `verify_persons.py` 改寫武將一覽首頁的記錄（含 2 組自訂值）後讀回；ROM_FORMAT「人物」 |
| 城欄位意義（8 個數字） | ✅ | emu+modified | `verify_cities.py` 把各城的值寫進洛陽（含 2 組自訂值）後讀回；ROM_FORMAT「城」 |
| 頭像 536 張 | ✅ | emu+modified | `verify_faces.py` 換君主比對 VRAM、CRAM、畫面，500–535 patch 頭像程式；ROM_FORMAT「頭像」 |
| 頭像來源（三國志V 原畫縮小重繪） | 🟡 | cross | 和 kaodata `san5pk-dos` 同名人物並排比對，灰階相關係數同名 0.54、隨機 0.26；見「判斷」 |
| 選君主地圖與城節點 | 🟡 | code | 由程式與表解出，沒有驗證腳本；ROM_FORMAT「選君主地圖」 |
| 字型其餘 927 字（訊息） | ❌ | | 見「未解」 |
| 人物 +A、將軍職名、戰法持有；城 +16/+18；勢力 ♡／+C；關係表意義 | ❌ | | 見「未解」 |
| 戰略大地圖、戰鬥地圖 | ❌ | | 見「未解」 |

## 未解

- 字型 927 字未轉寫：只出現在訊息與寶物效果說明裡，目前記為 〓（ROM_FORMAT「文字與字型」「未解」）
- 人物 +A（各劇本共用的 word，疑似 12 個陣形的位元旗標）、將軍職名稱表（職碼 +4 已知）、戰法／特技的持有資料（ROM_FORMAT「人物」「未解」）
- 城 +16/+18（值 300–900，疑似農／商上限）、勢力 +C 與 ♡ 的意義、20×20 勢力關係表的意義（ROM_FORMAT「城」「勢力」「未解」）
- 劇本名：選單上是圖，沒有文字（ROM_FORMAT「劇本」）
- 戰略畫面的大地圖（有旗子那張）未解，只解了選君主畫面的地圖（ROM_FORMAT「未解」）
- 頭像 500–503 的用途，以及 504–535 為什麼和 104–135 相同（ROM_FORMAT「頭像」）
- 戰鬥、事件、AI 等程式未看（ROM_FORMAT「未解」）
