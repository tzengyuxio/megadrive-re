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
```

ROM 預設直接讀 `roms/Sangokushi Retsuden - Ransei no Eiyuutachi (Japan).zip`；所有腳本加 `--rom "roms/San Guo Zhi Lie Zhuan - Luan Shi Qun Ying (China).zip"` 改跑中文版（依 ROM 內容自動判斷版本）。依賴：Pillow、numpy；openpyxl（可選，.xlsx）；驗證需 `mame`（`brew install mame`，不需 BIOS）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、人物、城、劇本 33 表、武器、頭像、大地圖；`LAYOUTS` 為日版／中文版兩組位址 |
| `data/charset.txt` | 16×16 字型 968 字的轉寫（目視，ROM 原有的誤字照錄） |
| `data/charset_cn.txt` | 中文版字型 1034 字的轉寫（同 bitmap 沿用日版，其餘 383 字目視） |
| `export.py` | 匯出 CSV（UTF-8-BOM）／XLSX／PNG |
| `verify_*.py` | 模擬器驗證（見上） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 3 劇本共 647 筆登場人物：姓名、讀音（中文版無）、所在城、所屬君主、身分（君主／太守）、體力、武力、知力、統率力、文官値、武官値、徳、忠誠度、機動力、士氣、等級、官位碼、兵力、武器、攻撃力×2、未解欄位原值 |
| `cities.csv` | 3 × 40 城：座標、勢力、君主、太守、金、米、民（千）、産業値、6 個未解欄位原值 |
| `retsuden.xlsx` | 以上兩表 |
| `portraits/P###_姓名.png` | 256 張頭像（48×64，眼開口閉；人物號＝頭像號） |
| `font.png` | 16×16 字型總覽 |
| `map.png`、`map_labeled.png` | 大地圖（1280×1152）、加城號與城名標註 |

## 進度

- ✓ 字型與字碼（16-bit，字號＝高 byte×64＋低 byte）、小字型片假名（讀音）
- ✓ 人物 256 名＋讀音、城名 40、武器名與加成、城座標
- ✓ 劇本 3 個（189／200／215 年）× 33 表：載入程式 `$3E28`，RAM 完全一致
- ✓ 人物欄位意義：狀態畫面 15 個數字全部對上（含兩種攻撃力公式）
- ✓ 頭像 256 張（底圖＋眨眼 sprite＋嘴型），與畫面逐 pixel 一致
- ✓ 大地圖（字典 RLE 圖塊＋分塊 nametable），捲動驗證全部一致
- 未解：見 ROM_FORMAT.md §8
- ✓ 中文版 `San Guo Zhi Lie Zhuan - Luan Shi Qun Ying (China)`（三國志列傳 亂世群英）：同一套程式與資料搬移位置、換成 1034 字的繁體字型；資料表與日版逐 byte 相同，沒有讀音。位址對照見 ROM_FORMAT.md §9

## 驗證結果

| 腳本 | 日版 | 中文版 |
|------|------|--------|
| `verify_faces.py` | 256/256 頭像一致 | 256/256 頭像一致 |
| `verify_scenarios.py` | 189／200／215 年各 33/33 表一致 | 189／200／215 年各 33/33 表一致 |
| `verify_persons.py` | 256/256 人 15 個數字＋等級全吻合 | 256/256 人全吻合 |
| `verify_maps.py` | 32 個停點全部一致，覆蓋 17768 格（可捲動範圍 144×144 的 86%） | 32 個停點全部一致，覆蓋 19160 格 |
