# MD 信長の野望・武将風雲録 解析

KOEI，1991.OCT，MD（1 MB，無壓縮，68000 C 編譯，大端序）。2 個劇本（1555 戦国の動乱、1571 信長包囲網），48 國。資料內容與 SFC 版（`~/works/superfamicom-re/bushou/`）幾乎相同，結構改成 16／32 bit 的 C struct。文字碼 = SFC 碼 + 1（`0x8141–0x84A4` = 字型第 0–867 字）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python bushou/export.py [--rom ROM] [--out DIR] [--scale N]   # → bushou/output/（CSV、XLSX、PNG）
.venv/bin/python bushou/export_kaodata.py --out <kaodata>/data-local/nobu4-md
.venv/bin/python bushou/verify_kaodata_export.py --dataset <kaodata>/data-local/nobu4-md
.venv/bin/python bushou/verify_scenarios.py              # 約 10 秒
.venv/bin/python bushou/verify_generals.py               # 約 15 秒
.venv/bin/python bushou/verify_text.py [--quick]         # 約 40 秒
.venv/bin/python bushou/verify_faces.py [--quick]        # 約 2.5 分鐘
.venv/bin/python bushou/verify_maps.py                   # 約 6 秒
```

- ROM 預設讀 `roms/Nobunaga no Yabou - Bushou Fuuunroku (Japan).zip`，`--rom` 也接受 .md。
- 依賴：Pillow、openpyxl。字型總覽與戰場示意圖的標字用 macOS 的ヒラギノ角ゴシック。
- 驗證腳本用 MAME（共用的 `tools/mame.py`、`tools/replay.py`）：照按鍵序列玩到某一幀存檔，之後每一輪改 RAM、重播、讀 VRAM／CRAM／RAM 與截圖。操作序列見 ROM_FORMAT.md §8。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字與字型、外字、劇本（國、茶器、大名、武將）、登場武將、頭像（專屬＋組合）、調色盤、大地圖、戰場地形與戰場名 |
| `data/charset.txt` | 字型 868 字對應的字元（沿用 SFC；`〓` = 外字，見 `rom.GAIJI`） |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | 匯出 kaodata 資料集 `nobu4-md`（專屬頭像 204 張＋組合臉 8 頭；沒有武將用的 180–203 標上 `group` 事件人物／姫，有標籤的附 `name`） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 ROM 解碼逐 pixel 比對；checksums |
| `verify_scenarios.py` | 2 劇本在選大名畫面的 RAM `$FF1000` 與 ROM 劇本區塊逐 byte 比對 |
| `verify_generals.py` | 尾張的武將清單畫面：姓名與政治 戦闘 教養 魅力，含隨機改寫 RAM 的輪次 |
| `verify_text.py` | 868 個文字碼逐一換進信長的姓名（RAM），比對遊戲畫進 VRAM 的字 |
| `verify_faces.py` | 204 張專屬頭像＋282 種組合臉碼逐一換進信長的頭像碼，比對 VRAM、CRAM、截圖 |
| `verify_maps.py` | 大地圖 plane B tilemap、tile、調色盤、截圖；戰場地形與 SFC 比對 |

## 輸出（`bushou/output/`）

| 檔案 | 內容 |
|------|------|
| `scenarios.csv` | 2 劇本：年月、開局武將 250／255、登場武將 120／91、大名 41／32 |
| `generals.csv` | 716 筆（劇本 × 開局／登場）：姓名、生年、年齢、登場年、政治 戦闘 教養 魅力 野望、忠誠、所在國、大名、頭像碼、未解欄位 |
| `provinces.csv` | 2 劇本 × 48 國：大名、金 米 石高 治水 町 文化 技術 民忠 城 兵 鉄砲 訓練 兵忠、武將、未解欄位 |
| `province_list.csv` | 48 國的名稱與相鄰國 |
| `daimyo.csv` | 2 劇本的大名：同盟、關係表（未解）、未解欄位 |
| `tea.csv` | 2 劇本 × 48 茶器：名稱、持有者、值（未解） |
| `battle_maps.csv` | 野戰 48＋城 49：戰場名、地形（hex），城的第二層 |
| `bushou.xlsx` | 以上各表 |
| `faces/`、`portraits/` | 466 位不同的（姓名, 頭像碼）各一張（組合臉已組好）；專屬頭像 F000–F203 |
| `mob_parts/`、`mob_parts.png` | 組合臉 8 頭 × 5 區 × 4 頁的零件 |
| `map.png` | 大地圖 plane B（240 × 224，不含 plane A 的文字與家紋） |
| `battle_maps/field/`、`battle_maps/castle/` | 地形值示意圖（不是遊戲畫面，MD 戰場畫面未解） |
| `font.png` | 868 字的字型，旁邊是 `data/charset.txt` 的字 |
| `kaodata/nobu4-md/` | 手動跑 `export_kaodata.py --out bushou/output/kaodata/nobu4-md` 時的資料集 |

## 進度

- ✓ 文字碼（含跳脫碼 `85F0–85F2`）、字型 868 字、外字
- ✓ 劇本 2 個：國 48 × 72、茶器 48 × 20、大名 48 × 34、武將 272 × 40、登場武將 30 bytes
- ✓ 頭像：專屬 204 張、組合臉 8 頭（區域表 `0x5DB1E`），單一調色盤；kaodata 資料集 `nobu4-md`
- ✓ 大地圖：plane B tilemap、CHR、調色盤
- ✓ 戰場地形 48＋49 張、第二層、戰場名（與 SFC 逐 byte 相同）
- … 推定：登場武將表（未在遊戲中等到登場）
- … 未解：MD 戰場畫面組裝、國 +2/+42/+44/+68、大名關係表與 +31/+32、武將 +24/+30/+31/+32、茶器的值、文字控制碼（見 ROM_FORMAT.md §9）

## 驗證結果

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_scenarios.py` | 劇本 1、2 選到選大名地圖，RAM `$FF1000–$FF5253` 與 ROM 區塊逐 byte 比對；再從 RAM 讀回武將記錄與國的 13 個數值 | 劇本 1：16882/16980 bytes 相同，劇本 2：16856/16980；不同處只有 國 +42（48）、+45（36）、+69（10）、武將暫存格 255–256、劇本 2 大名 +33（26，重新編號）。武將 250/250、255/255，國 48/48，OK |
| `verify_generals.py` | 尾張的武將清單（開発 → C），從 plane A 讀姓名（字型點陣比對）與四項能力（數字 tile）；另 4 輪把 7 人的姓名與能力隨機改寫 | 5 輪各 7/7 列相同，且依政治遞減排序，OK |
| `verify_text.py` | 選大名畫面按 C 出「織田信長でよろしいですね」，把信長的姓名（RAM 武將 119 +4／+11）換成字碼，比對 VRAM tile `0x200` 起畫出的點陣 | 未改時 織田信長 OK；868/868 字碼、跳脫碼 OK（37 秒） |
| `verify_faces.py` | 尾張國畫面的信長頭像；把 RAM 武將 119 +28 換成每個碼，比對 VRAM tile `0x300` 的 960 bytes、CRAM 調色盤 3、截圖 (16,112) 的 40×48 | 未改時 = 頭像 25 OK；專屬 204/204、組合 282/282：VRAM／CRAM 與截圖皆一致（色 0 透明，顯示背景色 (87,0,0)），OK（149 秒） |
| `verify_maps.py` | 選大名畫面：plane B tilemap、VRAM tile、CRAM 0、截圖中未被 plane A／游標 sprite 蓋住的格；戰場地形與 SFC ROM 比對 | tilemap 840/840、tile 429/429、調色盤 OK、截圖 750/750 格；野戰／城／城第二層 與 SFC 相同，OK（6 秒） |
| `verify_kaodata_export.py` | 參考渲染器與 `Rom.face_rgb` 逐 pixel 比對、checksums | 466/466、204/204、OK |

國的欄位另外對照尾張國畫面截圖（金 230、米 210、城 335、兵 80、石高 405 等）。
