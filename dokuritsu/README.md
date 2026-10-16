# MD Liberty or Death 解析

KOEI，1994，MD（2 MB，`GM T-76106`，只在北美發行；日文原作是 SFC／PC 的独立戦争）。程式是 SFC 版（`~/works/superfamicom-re/dokuritsu`）
以 68000 C 重寫並英譯：同樣的表、同樣的順序（250 人、53 地點、15 州、1775 年劇本），記錄加寬、big-endian、4 byte 指標、ASCII 文字。
人物數值有改過，頭像像素相同但組合臉的位元配置不同（見下方比對）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 人物、1775 年劇本、地點、州、陣營、HEX 戰場、頭像、大地圖 → dokuritsu/output/
.venv/bin/python dokuritsu/export.py [--rom ROM] [--out DIR]

# kaodata 統一格式資料集 liberty-md
.venv/bin/python dokuritsu/export_kaodata.py --out <kaodata>/data-local/liberty-md
.venv/bin/python dokuritsu/verify_kaodata_export.py --dataset <輸出目錄>

# 模擬器驗證（MAME）
.venv/bin/python dokuritsu/verify_scenarios.py     # 1775 年劇本的 RAM 複本（約 5 秒）
.venv/bin/python dokuritsu/verify_persons.py       # 250 人的能力、名声、頭像（約 2 分鐘；--quick 10 人）
.venv/bin/python dokuritsu/verify_faces.py         # 312 個頭像碼：VRAM、CRAM、截圖（約 2.5 分鐘；--quick 20 個）
.venv/bin/python dokuritsu/verify_maps.py          # 大地圖 3 區（約 11 秒）
.venv/bin/python dokuritsu/verify_battle_maps.py   # HEX 戰場兩層，用遊戲的 LZ 解碼（約 10 秒）
```

ROM 預設讀 `roms/Liberty or Death (USA).zip`。依賴：Pillow；openpyxl（可選）；驗證需 `mame`（機型 genesis）。LZ 解碼用 `tools/koei_lz.py`。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：人物、事件人物、地點、州、1775 年劇本（人物狀態、地點狀態、陣營）、頭像（專屬＋組合）、大地圖 3 區、HEX 戰場 53 張 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py`、`verify_kaodata_export.py` | kaodata 資料集 `liberty-md` 與其驗證 |
| `verify_scenarios.py` | 開新遊戲時 `$97EC` 複製劇本後 RAM `$FF000A`–`$FF16BA` 和 ROM 比對 |
| `verify_persons.py` | 選陣營後的人物介紹頁：改 ROM 換成每個人，讀畫面上的 Leadership／Tactics／Reputation／Discipline 與 VRAM 頭像 |
| `verify_faces.py` | 選陣營畫面：改 Washington 的頭像碼，比對 VRAM、CRAM、截圖 |
| `verify_maps.py` | 第一次大陸會議選地點時的大地圖，按下鍵捲到中部、南部，比對 tile、tilemap、調色盤 |
| `verify_battle_maps.py` | 借一次 `$3C50` 呼叫解 HEX 戰場兩層，和 ROM 解碼及 SFC 版比對 |

## 輸出

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 250 人：名、姓、体力／統率力／戦術力／指導力、+31／+32（未解）、頭像碼 |
| `persons_1775.csv` | 1775 年：所在（列表）、地點欄、体力、名声、忠誠、所屬（推測）、階級（推測）、未解欄位、原始 bytes |
| `locations.csv` | 53 地點：地區、州、港（推測）、相鄰 |
| `locations_1775.csv` | 1775 年：owner（未解）、支持、食糧、武器／弾薬（推測）、駐留人物 |
| `states.csv` | 15 州：略稱、全名 |
| `sides.csv` | America／Britain：資金（推測）、待機人物 |
| `battle_maps.csv`、`battle_cells.csv` | 53 張 HEX 戰場：各地形格數；8904 格的地形、旗標、byte 1、疊加 tile |
| `dokuritsu.xlsx` | 以上各表 |
| `faces/` | 每人一張（`238_George Washington.png`） |
| `portraits/` | 專屬頭像 174 張（人物用 0–124；125–173 是大陸會議、英國等事件人物） |
| `map_0_North.png` … `map_2_South.png` | 大地圖 3 區（224 × 192，擁有者上色前的白底；外海是黑的，遊戲在那裡畫動畫 tile） |

HEX 戰場的畫面（MD 的戰場 tile）還沒找，所以戰場只匯出格子資料、沒有圖。

kaodata 資料集 `liberty-md`（遊戲代碼 LIBERTY，平台 MD，結構同 liberty-sfc）：250 人（name 照 ROM 英文 "George Washington"，沒有 reading、
nameZh）、專屬頭像 174 張（頭像碼 0000–00AD）＋組合臉 4 型 × 5 部位 × 4 變體（80 張零件，人物 125 人用組合臉，頭像碼照 ROM 填）。
沒人用的 125–173 依 liberty-pc98／-dos 的同順序加 group：大陸會議 22、英國 22、傳令 2、海軍 2、傭兵 1；name 只在 ROM 的事件人物表有名字時給
（40 人；補給官與 169–173 沒有）。

## 進度

- ✓ 人物 250 人（畫面驗證能力與名声）、地點 53、州 15、1775 年劇本（RAM 完全一致）
- ✓ 頭像：專屬 174＋組合臉（遊戲 VRAM／畫面驗證 312 碼）；kaodata `liberty-md`
- ✓ 大地圖 3 區（tile、tilemap、調色盤；外海動畫格與擁有者上色另列）
- ✓ HEX 戰場 53 張的格子資料（遊戲的 LZ 解碼器驗證，和 SFC 版逐格相同）
- 戰場畫面、外海動畫 tile 與位置表、擁有者上色遮罩未做
- 未解：見 ROM_FORMAT.md「未解」

## 驗證結果

| 腳本／比對 | 結果 |
|------|------|
| `verify_scenarios.py` | `$9810` 時 RAM `$FF000A`–`$FF16BA` 5809/5809 bytes 和 ROM `0x5A946` 相同 |
| `verify_persons.py` | 250/250 人：Leadership、Tactics、Discipline、Reputation（人物狀態 +6）畫面數字相同，VRAM 頭像 960 bytes 相同（体力與名字不在這頁，沒比） |
| `verify_faces.py` | 312/312（專屬 174、組合 138）：VRAM、CRAM line 2、畫面 40×48 逐 pixel（598722 個非透明 pixel） |
| `verify_maps.py` | 北／中／南三區：VRAM tile 除擁有者上色（色 15 → 3／8／12，6699／5333／4089 px）外 0 差異；tilemap 572／593／501 格相同，其餘 100／79／171 格是外海動畫 tile、0 其他；調色盤（不含水色 9–11）13/13 |
| `verify_battle_maps.py` | 遊戲的 `$3C50` 解出層 A 17824/17824、層 B 17808/17808 bytes 和 ROM 解碼相同；和 SFC 版 8904/8904 格相同 |
| `verify_kaodata_export.py` | 250/250 人（頭像、頭像碼、名字）、174/174 張（像素、頭像碼、group、name）、4096/4096 組合碼、checksums OK；kaodata `pnpm verify` 424 checked、0 mismatched |
| 和 SFC 版比對 | 人物順序 250/250 同（id 82 Gage、238 Washington）；頭像碼、+31／+32、種別 0 差異；能力有改：体力 82 人、統率 61 人、戦術 200 人、指導 229 人不同（例：Washington 戦術 SFC 88 → MD 58，畫面確認）。地點 53/53 全欄相同；劇本：人物狀態只有 person 31 的地點欄不同（MD 15、SFC 16），地點狀態、陣營、各串列全同；HEX 戰場 8904/8904 格同 |
| 和 SFC 版頭像比對 | 專屬頭像 174/174 張像素相同（色號 8／14／15 對調：SFC 8→MD 15、14→8、15→14）；組合臉 80 張零件像素相同，但型 1 與型 2 對調、部位讀的位元也不同，所以同一個頭像碼組出的臉多半不同：125 個組合臉人物只有 3 人和 SFC 版相同 |
| 和 DOS／PC-98 版比對 | DOS／PC-98 每人一張 64×80 專屬頭像（299 張 = 250 人＋49 事件人物），和 MD 解析度、畫法不同，無法逐像素比；事件人物 125–173 和 DOS 250–298 目視是同一批人、同順序（Hancock、傳令、海軍、傭兵隊長） |
