# MD 三国志列伝 乱世の英雄たち 解析

SEGA，1991，MD（ROM 表頭 `(C)SEGA 1991.APR`，`GM G-5510`，1MB）。非光榮作品，所以不出 kaodata 資料集，素材依素材站規格（規劃中）再補。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 人物、城（3 劇本）、頭像 PNG、字型表、大地圖 → retsuden/output/（中文版 → retsuden/output/cn/）
.venv/bin/python retsuden/export.py [--rom ROM] [--out DIR] [--scale N]

# 驗證（MAME 跑遊戲本身的程式；每支幾分鐘，MAME 在背景執行不搶 focus）
.venv/bin/python retsuden/verify_faces.py       # 256 張頭像逐 pixel 比對狀態畫面
.venv/bin/python retsuden/verify_scenarios.py   # 3 劇本 × 33 表，載入完成時的 RAM 比對
.venv/bin/python retsuden/verify_persons.py     # 256 人 × 15 個數字，狀態畫面讀回
.venv/bin/python retsuden/verify_maps.py        # 大地圖捲動，畫面上的 plane B 比對

# 頭像 sheet（portrait-sheet skill；先跑 export.py）
.venv/bin/python retsuden/sheet_manifest.py
.venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py retsuden/output/portrait-sheet/retsuden/sheet.json \
    retsuden/output/portrait-sheet/retsuden/out
```

ROM 預設直接讀 `_original/md/Sangokushi Retsuden - Ransei no Eiyuutachi (Japan).zip`；所有腳本加 `--rom "$HOME/game-library/_original/md/San Guo Zhi Lie Zhuan - Luan Shi Qun Ying (China).zip"` 改跑中文版（依 ROM 內容自動判斷版本）。依賴：Pillow、numpy；openpyxl（可選，.xlsx）；驗證需 `mame`（`brew install mame`，不需 BIOS）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、人物、城、劇本 33 表、武器、頭像、大地圖；`LAYOUTS` 為日版／中文版兩組位址 |
| `data/charset.txt` | 16×16 字型 968 字的轉寫（目視，ROM 原有的誤字照錄） |
| `data/charset_cn.txt` | 中文版字型 1034 字的轉寫（同 bitmap 沿用日版，其餘 383 字目視） |
| `export.py` | 匯出 CSV（UTF-8-BOM）／XLSX／PNG |
| `verify_*.py` | 模擬器驗證（見上） |
| `sheet_manifest.py` | 頭像 sheet 的 manifest（`portrait-sheet/1`）：256 人一人一格、片假名讀音、標籤（君主／其餘淡色「武將」），人名照 ROM（誤字不改） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 3 劇本共 647 筆登場人物：姓名、讀音（中文版無）、所在城、所屬君主、身分（君主／太守）、體力、武力、知力、統率力、文官値、武官値、徳、忠誠度、機動力、士氣、等級、官位碼、兵力、武器、攻撃力×2、未解欄位原值 |
| `cities.csv` | 3 × 40 城：座標、勢力、君主、太守、金、米、民（千）、産業値、6 個未解欄位原值 |
| `retsuden.xlsx` | 以上兩表 |
| `portraits/P###_姓名.png` | 256 張頭像（48×64，眼開口閉；人物號＝頭像號） |
| `font.png` | 16×16 字型總覽 |
| `map.png`、`map_labeled.png` | 大地圖（1280×1152）、加城號與城名標註 |
| `portrait-sheet/retsuden/` | 頭像 sheet：`sheet.json`、`faces/`、`out/retsuden-p01.png`…（6 張，以 B 類交接單交到 simagame 的 `inbox/`） |

## 進度

| 項目 | 狀態 | 證據 | 說明 |
|------|------|------|------|
| 字型 968 字、字碼、小字型讀音；人物名、城名、武器名 | 🟡 | code | 字型為目視轉寫，沒有和模擬器畫出的字形比對；ROM_FORMAT §1、§2 |
| 劇本 3 個（189／200／215 年）× 33 表 | ✅ | emu | `verify_scenarios.py` 在載入完成 `$3FF8` 比對 RAM，33/33 表一致；ROM_FORMAT §3 |
| 人物欄位意義（狀態畫面 15 個數字、兩種攻撃力、武器加成） | ✅ | emu+modified | `verify_persons.py` 把每人的值寫進関羽的槽，從狀態畫面讀回；ROM_FORMAT §3 |
| 頭像 256 張（底圖＋眨眼 sprite＋嘴型） | ✅ | emu+modified | `verify_faces.py` 把每張頭像換進劉備的槽，與畫面逐 pixel 比對；ROM_FORMAT §4 |
| 大地圖（字典 RLE 圖塊＋分塊 nametable） | ✅ | emu | `verify_maps.py` 32 個停點的 plane B 全部一致；ROM_FORMAT §5、§6 |
| 城座標 | 🟡 | code | 由 `$674DC` 讀表得知，沒有單獨驗證；ROM_FORMAT §2 |
| 中文版（三國志列傳 亂世群英）資料表 | ✅ | emu+cross | 資料表與日版逐 byte 相同，4 支驗證腳本在中文版全部通過；ROM_FORMAT §9 |
| 中文版字型 1034 字 | 🟡 | cross | 651 字與日版 bitmap 相同，其餘 383 字目視轉寫；ROM_FORMAT §9 |
| 城、人物、勢力的未解欄位；官位碼對照 | ❌ | | 見「未解」 |
| 戰場地圖、事件、劇情文字 | ❌ | | 見「未解」 |

## 未解

- 城欄位 `E280`–`E5A0`（6 個 long 表）：載入的 RAM 位址與大小已知，意義未解（ROM_FORMAT §3、§8）
- 人物 `BA00`、`BC00`、`F000`（`F000` 載入時轉成 byte 值−0xB8），勢力 `E710`（ROM_FORMAT §3、§8）
- 官位碼完整對照：只確認 4＝君主、bit 4 顯示額外稱號；田疇的官位碼異常（rank 4），原因不明（ROM_FORMAT §3、§8）
- 大地圖調色盤第 1 組 entry 9、12 執行時會變，原因未查（ROM_FORMAT §6）
- 戰場地圖、事件、劇情文字：未找（ROM_FORMAT §8）
- 中文版雜項字串：`0xB352` 的 `lea $8A3C2` 指向數字、官職名、指令名等字串，未逐一整理（ROM_FORMAT §8）

## 驗證結果

| 腳本 | 日版 | 中文版 |
|------|------|--------|
| `verify_faces.py` | 256/256 頭像一致 | 256/256 頭像一致 |
| `verify_scenarios.py` | 189／200／215 年各 33/33 表一致 | 189／200／215 年各 33/33 表一致 |
| `verify_persons.py` | 256/256 人 15 個數字＋等級全吻合 | 256/256 人全吻合 |
| `verify_maps.py` | 32 個停點全部一致，覆蓋 17768 格（可捲動範圍 144×144 的 86%） | 32 個停點全部一致，覆蓋 19160 格 |
