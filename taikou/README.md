# MD 太閤立志伝 解析

KOEI，1993，MD（1.25 MB，`GM T-76123`）。資料和 SFC 版（`~/works/superfamicom-re/taikou`）是同一份，16 位元欄位改 big-endian、補齊到偶數位址；
頭像大多相同，但組合臉改成 5 段連續 tile，部分頭像與部件重畫。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 名表、人物、勢力、城、字串表、頭像、組合臉部件總覽 → taikou/output/
.venv/bin/python taikou/export.py [--rom ROM] [--out DIR]

# kaodata 統一格式資料集 taikoh-md
.venv/bin/python taikou/export_kaodata.py --out <kaodata>/data-local/taikoh-md
.venv/bin/python taikou/verify_kaodata_export.py --dataset <輸出目錄>

# 模擬器驗證（MAME）
.venv/bin/python taikou/verify_scenarios.py   # 開始時資料：選型畫面的 RAM vs ROM（約 5 秒）
.venv/bin/python taikou/verify_faces.py       # 258 張頭像＋518 個組合碼：VRAM、CRAM、截圖（約 30 分鐘；--quick 只跑 5 個）
```

ROM 預設讀 `roms/Taikou Risshiden (Japan).zip`。依賴：Pillow；openpyxl（可選）；驗證需 `mame`。LZ 解碼共用 `haouden/lz.py`。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、名表、開始時資料（人物、勢力、城狀態）、城、字串表、頭像（專屬＋組合） |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py`、`verify_kaodata_export.py` | kaodata 資料集 `taikoh-md` 與其驗證 |
| `verify_*.py` | 模擬器驗證（見上） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `names.csv` | 名表 716 筆：姓、名、頭像碼 |
| `persons.csv` | 人物紀錄 713 筆（241 開始時＋472 後登場）：所属、身分、居城、政略／戦術 Lv、6 能力、8 技能、未解欄位 |
| `factions.csv` | 20 勢力：大名、本城、城數、未解欄位 |
| `castles.csv` | 125 城：相鄰、地圖座標、開始時的勢力／城主（推測）／城狀態 |
| `strings.csv` | 字串表 7 個（身分、技能、能力名、陣形、配置、天候、兵種） |
| `taikou.xlsx` | 以上各表 |
| `faces/` | 每筆人物紀錄的頭像（`000_木下藤吉郎.png`） |
| `portraits/` | 專屬頭像 258 張 |
| `composite_parts.png` | 組合臉 12 型 × 5 部位（組圖順序）× 4 變化；灰色是該部位不寫的 tile |

kaodata 資料集 `taikoh-md`（遊戲代碼 TAIKOH，平台 MD）：716 人（名表 index，name 是「姓 名」，同 taikoh-sfc；沒有 reading），198 人用專屬頭像、
518 人用組合臉（code 為頭像碼）；258 張專屬頭像都附 code；組合臉 12 型，5 個 slot 照遊戲組圖順序（部位5 → 部位1–4，部位3、部位4 用同一個變化）。

## 進度

- ✓ 名表、人物 713 筆、勢力、城、城狀態、字串表（欄位沿用 SFC 研究，資料逐欄相同）；開始時資料用遊戲 RAM 驗證
- ✓ 頭像：專屬 258 張、組合臉 12 型（遊戲 VRAM／CRAM／畫面驗證）；kaodata `taikoh-md`
- 大地圖：區塊表與格 byte 位置找到，未渲染；戰場地圖未找
- 未解：見 ROM_FORMAT.md「未解」

## 驗證結果

| 腳本／比對 | 結果 |
|------|------|
| `verify_scenarios.py` | 選型畫面 RAM `$FF0040–$FF4611` 複製區 17872/17874 bytes 和 ROM 相同，另 2 bytes 是城 68、72 的 +15 已設 bit 4（已知）；勢力 20/20、人物 241/241、城狀態 123/123 |
| `verify_faces.py` | 776/776（專屬頭像 258、名表的組合碼 518）：VRAM tile 0x260 的 640 bytes、CRAM line 0、畫面 32×40 逐 pixel（共 10 個透明的色 0 pixel 不比） |
| `verify_kaodata_export.py` | 716/716 人（頭像、code、name）、258/258 張、checksums OK；kaodata `pnpm verify` 974 checked、0 mismatched |
| 和 SFC 版 `rom.py` 比對 | 人物 713/713（Id、勢力、居城、身分、Lv、能力、技能）、勢力 +0–21 20/20、城狀態 +0–2 123/123、城 123/125（二俣、小谷的格不同）、大地圖區塊表 1230/1230；名表 713/716（MD 改正 SFC 3 個錯字）、頭像碼 716/716；頭像見 ROM_FORMAT.md §6 |
