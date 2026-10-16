# MD 大航海時代 解析

KOEI，1992，MD。本作只有日版：『大航海時代』，ROM 表頭是 `(C)T-76 1992.FEB`、`GM T-76053 -10`，容量 1 MB。

本作的資料和 FC 版（`~/works/famicom-re/daikoukai`）、SFC 版（`~/works/superfamicom-re/daikoukai`）相同，只是改寫成 68000 的結構：big-endian、32 位元的名字指標。文字、頭像像素和世界地圖檔都沒有改，整份 ROM 也沒有壓縮。ROM 結構和各表的格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python daikoukai/export.py [--rom ROM] [--out DIR] [--scale N] [--no-map]   # → daikoukai/output/，約 12 秒
.venv/bin/python daikoukai/export_kaodata.py --out <kaodata>/data-local/koukai-md
.venv/bin/python daikoukai/verify_kaodata_export.py --dataset <kaodata>/data-local/koukai-md
.venv/bin/python daikoukai/verify_faces.py [--rom ROM]      # 約 45 秒
.venv/bin/python daikoukai/verify_persons.py [--rom ROM]    # 約 5 秒
.venv/bin/python daikoukai/verify_maps.py [--rom ROM]       # 約 11 秒
```

- ROM 預設讀 `roms/Daikoukai Jidai (Japan).zip`。
- 需要 Pillow。驗證腳本需要 MAME（透過 `tools/mame.py`、`tools/replay.py` 呼叫），在背景執行，不會搶走 focus。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、初始資料區塊（人物、艦隊、能力、建物旗標）、女性、國名、港口、名稱表、頭像（專屬與組合）、世界地圖 |
| `export.py` | 匯出 CSV 與 PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `koukai-md` |
| `verify_kaodata_export.py` | 用參考渲染器畫出資料集，和 ROM 解碼逐 pixel 比對，並檢查 checksums |
| `verify_faces.py` | 把序幕讀頭像碼的指令 patch 成固定碼，讓遊戲自己畫出每個頭像，再比對 VRAM tile、CRAM line 0 和畫面 |
| `verify_persons.py` | 開新遊戲後，把 `$FF1000` 起的 RAM 與 ROM 的 INIT 區塊逐 byte 比對 |
| `verify_maps.py` | 出港時把艦隊移到測試用的 chunk，比對 plane A 的 name table、CRAM line 3 和畫面 |

## 輸出（`daikoukai/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 人物 41 筆：主角、航海士 20、提督 20。欄位有國、戰鬥／航海等級、能力（主角與航海士）、頭像碼、旗標、名字指標 |
| `girls.csv` | 女性 20 筆（頭像 = 編號 + 13） |
| `ports.csv` | 港口 70 筆：交易港 50、補給港 20。欄位有座標、像素位置、地圖組、經濟圈、特產品、建物旗標 |
| `nations.csv` | 國 4 個：ポルトガル、イスパニア、イスラム、かいぞく，各國的提督與航海士 |
| `fleets.csv` | 初始艦隊 21 筆的位置 |
| `names.csv` | 名稱表 50 筆：商品、砲、船首像、船種、木材、桅、帆 |
| `faces/` | 61 個人物（含女性）的頭像 |
| `portraits/F00–F52.png` | 專屬頭像 53 張 |
| `mob_parts/`、`mob_parts.png` | 組合臉部件：4 頭型 × 5 slot × 4 頁 |
| `map.png` | 世界地圖 16128 × 8064，每個地圖組都用色盤 phase 0 |
| `map_small.png` | 1/4 縮圖，紅點是交易港、黃點是補給港，旁邊標港口編號 |

CSV 一律用 UTF-8 with BOM。

## kaodata 資料集（`koukai-md`，遊戲代碼 KOUKAI，平台 MD）

- 共 61 人：id 0–40 是人物表（41 人用專屬頭像，20 位提督用組合臉），id 41–60 是女性。
- 專屬頭像 53 張，都帶 `code`。組合臉有 4 個 variant（「頭型 0–3」），每個 variant 有 5 個 slot，每個 slot 4 頁。
- 頭像 1–12 沒有人物使用，比照 `koukai-fc` 加上 `group`：
  - 国王 1–3
  - 施設 4、5、6、7、9、10、11
  - 特殊人物 8、12
- 名字只在 ROM 文字指出身分時才給（依據見 ROM_FORMAT §4.3）。頭像 4 找不到店名，只有 group，沒有名字。
- ROM 裡沒有讀音，所以不給 `reading`；也沒有加入 ROM 以外來源的人名。
- 色盤是 palette line 0 的 16 色，換算成 MAME 色階。

## 驗證結果

| 項目 | 結果 |
|------|------|
| `verify_faces.py` | faces 73/73 一致（專屬 53，組合 20），VRAM、CRAM line 0、畫面都相同。20 個組合碼涵蓋每個頭型的每一頁 |
| `verify_persons.py` | INIT 區塊 4630/4635 bytes 一致；不同的 5 bytes 都是主角重擲過的能力 |
| `verify_maps.py` | 5/5 個 chunk 一致：起始 chunk 加上 4 個地圖組各一個；name table 784/784、CRAM line 3 與 set 一致、畫面只差船的 sprite |
| `verify_kaodata_export.py` | characters 61/61、portraits 53/53 和 ROM 解碼一致，checksums OK |
| kaodata `pnpm verify data-local/koukai-md` | 114 checked，0 mismatched |

與其他版本比對：
- 人物、女性、名稱表、港口都和 SFC 版完全一致。
- 頭像色號和 SFC 版完全相同（專屬 53/53、組合 20/20）。
- FC 版是依同一份原畫重繪的（ROM_FORMAT §4.4）。

## 進度

- [x] 文字、初始資料區塊、女性、國名、港口、名稱表
- [x] 頭像：專屬與組合，模擬器驗證
- [x] 世界地圖：模擬器驗證
- [x] kaodata 資料集
- [ ] 港町圖
- [ ] 未解欄位：初始區塊 `+0x000` 的記錄、艦隊 bytes 4–17、能力 bytes 6–9、港口屬性的 byte2／byte4
- [ ] 序幕等畫面的文字（不在字串表裡）
