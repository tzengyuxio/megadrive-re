# MD 大航海時代II 解析

KOEI，1994，MD。本作只有日版：『大航海時代Ⅱ』，ROM 表頭是 `(C)T-76 1994.APR`、`GM T-76163 -00`，容量 2 MB，有 SRAM。

資料和 SFC 版（`~/works/superfamicom-re/daikoukai2`）相同，改寫成 68000 的結構：big-endian、16 位元欄位對齊偶數位址、名字從記錄裡移出來，改成 32 位元的 ROM 指標。文字是半形假名（`ESC K`／`ESC H` 切換片假名）混 Shift-JIS 漢字，不再用 SFC 的自訂字型碼。頭像是同一份原畫，配合 MD 的一組 16 色色盤重新編過色號，用 KOEI LZ 壓縮（`tools/koei_lz.py`）。ROM 結構和各表的格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
.venv/bin/python daikoukai2/export.py [--rom ROM] [--out DIR]   # → daikoukai2/output/，約 1 秒
.venv/bin/python daikoukai2/export_kaodata.py --out <kaodata>/data-local/koukai2-md
.venv/bin/python daikoukai2/verify_kaodata_export.py --dataset <kaodata>/data-local/koukai2-md
.venv/bin/python daikoukai2/verify_faces.py [--rom ROM] [--keep DIR]   # 約 10 秒
.venv/bin/python daikoukai2/verify_scenarios.py [--rom ROM]            # 約 4 秒
.venv/bin/python daikoukai2/verify_maps.py [--rom ROM] [--keep DIR]    # 約 7 秒
```

- ROM 預設讀 `roms/Daikoukai Jidai II (Japan).zip`。
- 需要 Pillow。驗證腳本需要 MAME（透過 `tools/mame.py`、`tools/replay.py` 呼叫），在背景執行，不會搶走 focus。
- 進主角選擇畫面的按鍵：`w1500 start w300 start w300 start w300`（第 2484 幀）。選完主角後，「名前を変えますか?」按 `b`（或 `right` `c`）選「いいえ」就進入遊戲（リスボン）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、初始資料區塊（人物、VIP、女性、船種、港、港的狀態、道具）、船種規格、字串表、頭像（專屬與組合）、世界地圖的區塊 |
| `export.py` | 匯出 CSV 與 PNG |
| `export_kaodata.py` | 匯出 kaodata 統一格式資料集 `koukai2-md` |
| `verify_kaodata_export.py` | 用參考渲染器畫出資料集，和 ROM 解碼逐 pixel 比對，並檢查 checksums |
| `verify_faces.py` | 在主角選擇畫面讓遊戲自己的 LZ 解碼與組合臉程式做出每一張臉，逐 byte 比對；再用 patch 換臉，比對 VRAM、CRAM line 3 和畫面 |
| `verify_scenarios.py` | 主角選擇畫面時，把 `$FF0000` 起的 RAM 與 ROM 的 INIT 區塊逐 byte 比對 |
| `verify_maps.py` | 讓遊戲的區塊展開程式 `$3C470` 展開全部 4050 個地圖區塊，和 `Rom.block_cells` 逐 byte 比對 |

## 輸出（`daikoukai2/output/`）

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 人物 120 筆：主角 6、仲間 63、劇情人物 10、提督 41。能力 7 項、年齡、航海／戰鬥 Lv 與經驗、國籍、頭像碼、母港（推測）與未解欄位 |
| `vips.csv` | VIP 20 筆（執事マルコ、各國國王、總督…）：頭像、港 |
| `women.csv` | 女性 30 筆：頭像（97 + 編號）、年齡、港（推測） |
| `ship_types.csv` | 船種 25 筆與 12 bytes 規格 |
| `ports.csv` | 港 130 筆：交易港 100、補給港 30。座標、國籍；交易港另有經濟、工業、各國占有率、商品分類價格、地域、道具 |
| `items.csv` | 道具 100 筆：分類、價格、效果值、說明 |
| `discoveries.csv` | 發見物 100 筆：名稱、說明 |
| `strings.csv` | 字串表 15 張共 627 筆（國名、商品、階級、技能、木材、船首像、酒、人名池…） |
| `faces/` | 170 張：人物 120、VIP 20、女性 30 |
| `portraits/000–133.png` | 專屬頭像 134 張（128–133 用主角選擇畫面的灰色色盤） |
| `packs/pack0–6.png` | 組合臉 7 包，每包第 n 列是四個部件都取 n 的臉 |
| `world_map.png` | 世界地圖 2160 × 1080，一個 cell 一個 pixel：藍＝海、綠＝陸、黃＝其他地形 tile（海岸、河、山等）。地圖本身的 tile 圖形與色盤還沒找到，所以只是示意圖 |
| `world_map_ports.png` | 放大 2 倍，紅框是交易港、黃框是補給港，標上編號與港名 |

CSV 一律用 UTF-8 with BOM。

## kaodata 資料集（`koukai2-md`，遊戲代碼 KOUKAI2，平台 MD）

- 共 170 人，編號比照 `koukai2-pc98`：0–119 是人物表（66 人用專屬頭像，54 人用組合臉），120–139 是 VIP（頭像取 VIP 記錄 +7），140–169 是女性（頭像 97 + 編號，依據是 `$41510` 用記錄位址算出頭像號）。
- `reading` 只給人物 0–119，比照 `koukai2-sfc`（名字相同，讀音就是名字的平假名）。VIP 與女性不給讀音。
- 主角 0–5 各有一個 `expressions`：主角選擇畫面中沒被選到的灰色臉（頭像 128–133）。
- 專屬頭像 134 張，都帶 `code`。沒有人物使用、但劇情程式用固定編號畫出的頭像（18、19、22、25、94），加上 group「事件人物」。名字只在劇情文字自報姓名時才給：18「レオン・フェレロ」（「私がレオン・フェレロです」）、25「エゼキエル」（「私の名はエゼキエル」）。21、23、59、92、93、95、96 找不到 ROM 依據，不加 group。
- 組合臉 7 個 variant（第 0–6 包），slot 依遊戲的複製順序排：下半臉、上半臉、部件B、部件A（A1 與 A2 兩段由同一組 bits 決定，合成一個 item）。
- 色盤是 CRAM line 3 的 16 色（專屬頭像與組合臉共用），後面接主角選擇畫面的灰色 16 色，都換算成 MAME 色階。
- `tools/kaodata.py` 的 checksums 還沒涵蓋 `expressions`，所以 `export_kaodata.py` 自己補上 `ch:<id>/1`。

## 驗證結果

| 項目 | 結果 |
|------|------|
| `verify_faces.py` | 遊戲自己解出的臉：專屬頭像 134/134、組合臉 109/109（人物用的 54 個＋每包每個部件 n = 0–7 各一次）和 rom.py 逐 byte 相同。畫面 4/4（頭像 0、77，組合臉 0x8070、0xE5BE）：VRAM tile 0x5A0、CRAM line 3 16/16、截圖 1920 pixel 全同 |
| `verify_scenarios.py` | INIT 區塊 28236/28236 bytes 和 RAM 相同 |
| `verify_maps.py` | 地圖區塊 4050/4050：`$3C470` 寫出的 24 × 24 cell 與 rom.py 相同 |
| `verify_kaodata_export.py` | characters 170/170（含 6 個 expressions）、portraits 134/134 和 ROM 解碼一致，checksums OK |
| kaodata `pnpm verify data-local/koukai2-md` | 310 checked，0 mismatched |

與 SFC 版比對：
- 人物 120、VIP 20、女性 30、船種 25（含規格）、港 130 與交易港狀態 100、字串表、地圖區塊 4050 與 metatile 表都完全一致。
- 道具說明 12 筆、發見物 35 筆文字不同：MD 版把部分漢字改成假名（「華奢」→「きゃしゃ」等）。SFC 版有幾處是 SFC 解碼用的字型對照表錯字，例如 SFC 解成「ティシサット**鷹**」，MD 的 Shift-JIS 是「ティシサット**滝**」。
- 頭像是同一份原畫重新上色：專屬頭像 0–127 有 102 張完全符合一個色號對應（SFC → MD：12→10、13→12、15→14，其餘不變），全部 245760 pixel 有 98.6% 符合；女性頭像改得最多。組合臉的 SFC 色盤不同，54 張只有 89% pixel 符合同一個對應。

## 進度

- [x] 文字、初始資料區塊、船種規格、字串表
- [x] 頭像：專屬與組合，模擬器驗證
- [x] 世界地圖：區塊與 metatile，模擬器驗證
- [x] kaodata 資料集
- [ ] 世界地圖的 tile 圖形與色盤（`$1256A` 依緯度帶選 palette line，`$122FA` 從 `0x8FA5A` 載入色盤）
- [ ] 艦隊（INIT `+0x1774` 起，結構和 SFC 不同）
- [ ] 未解欄位：人物 +17／+25／+26／+28／+29、船種與規格的意義、港的狀態的一部分
- [ ] 劇情、訊息文字（`0x97000` 起的指標表）
