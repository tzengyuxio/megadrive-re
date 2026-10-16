# MD 版分析流程與踩坑

## 流程

1. **分診**：`tools/triage.py` 看表頭、checksum、KOEI LZ、SJIS。早期 SEGA 作品（列伝）用自有字碼，不是 SJIS。
2. **找字型與字表**：先找 1bpp 16×16 字型，渲染總覽圖後目視轉寫（`glyph_match.py` 只當輔助，漢字約一半準）。用已知人名反推字碼規則。
3. **找資料載入程式**：開局時對 RAM 下 read/write tap（`drive.py --reads`），找出把 ROM 表複製到 RAM 的程式，表的順序與 RAM 位址照抄。
4. **獨立驗證**：在載入程式 rts 下斷點 dump RAM 和靜態解碼比對；欄位意義靠「把第 n 人的值寫進某人的 RAM 槽，打開狀態畫面讀回數字」。
5. **頭像／圖塊**：找畫頭像的程式（VRAM write tap），解出 tile map、調色盤、疊加的 sprite（眼、嘴）；驗證時把第 n 張的表項 patch 進固定人物的槽再截圖，逐 pixel 比對。
6. **大地圖**：從 nametable 反推壓縮格式；捲動畫面多處 dump VRAM＋scroll 暫存器比對。

## MAME 踩坑

- **搶 focus**：`tools/mame.py` 已設 `SDL_VIDEODRIVER=dummy`、`SDL_AUDIODRIVER=dummy` 和 `-keyboardprovider none` 等；Lua 輸入仍有效。
- **斷點**：`on_exec` 需 `debug=True`（`-debug -debugger none`）；用 `bpset` 後在每 frame 檢查 `execution_state=="stop"` 再 `run`。
- **暫存器名**：`REG("SP")`、`REG("PC")`；`REG("A7")` 會拿到 nil。
- **read／write tap**：`install_*_tap` 回傳的 handle 要存在全域變數，否則被 GC 後 tap 就失效。
- **讓遊戲程式跑過每一筆資料**：在 Lua 裡 push 返回位址再把 PC 設到函式入口（san3 的 `verify_faces.py`、`verify_tactical.py`），比走畫面快很多。
- **dasm 位址要加 `$`**：`dasm file,$a0,$10` ——不加的話 `a0` 被當成暫存器 A0，輸出可能好幾十 MB。
- **capstone 5 錯印**：絕對短位址如 `$E500` 會印成 `$aaaa`；反組譯用 `tools/m68k.py`（MAME 的 disassembler）。
- **VDP 記憶體**：`emu.item(VDP.items["0/m_vram"])` 讀出是 host-order 的 word，要 swab。
- **read tap 會吃到取指令**：記憶體讀取追蹤要排除 PC±16 的位址。
- **savestate 重播**（`tools/replay.py`）：數百輪驗證時只跑一次開機，每輪 load state、patch、跑幾十 frame，比每輪重開快一個數量級。ROM patch 每輪自動復原。
- 遊戲開局後會自己改資料（等級 ±1、電腦勢力行動），RAM 比對要在載入程式剛結束時做。
- 文字：光榮 MD 日版多用 Shift-JIS，片假名常以 `ESC K` 切到半形、`ESC H` 切回，半形模式的 `-` 是長音「ー」；轉全形後要做 NFC 正規化，濁音字才會和 SFC 版的資料一致（元朝秘史）。
- 色彩：MD 3-bit 色值用 MAME 色階 0, 52, 87, 116, 144, 172, 206, 255 換 RGB，才能和截圖逐 pixel 一致。
- MD 的色號 0 是透明：頭像若用到色號 0，畫面上會透出背景色，截圖比對要排除這些 pixel（kaodata 照調色盤第 0 色輸出）。
- 找版面先確認是哪個 plane：除了 A／B 還有 window plane（H32 模式寬 32 格），別把空白面板當成地圖版面（ロイヤルブラッド）。
- 選單的單次方向鍵偶爾會被吃掉，必要時在 Lua 裡「按到某個 RAM 值成立為止」（`royal/verify_scenarios.py`）。
- 有些畫面 plane A／B 共用同一個 name table，B 靠 VSRAM 捲 256 列分開；A、B 位址相同時，到 name table 第 32 列以後找 B（提督の決断）。
- 驗證頭像：用 replay 把畫頭像函式的參數改成 `moveq #n` 並關掉隨機變體，就能逐張讓遊戲畫（提督の決断）；驗證地圖：在出港訊息時改寫艦隊座標，讓遊戲畫任意區塊（大航海時代）。
- 光榮 1992 年的 MD 作品，資料表多半和 SFC 逐值相同（只換成大端序、4-byte 指標），可以拿 SFC 版解出的值當樣板在 ROM 裡搜尋定位（エアーマネジメント）。
- 會眨眼／動嘴的頭像，截圖比對前要讀 plane A name table，把指向動畫 tile 的格子排除（エアーマネジメント）。
- 畫面剛出來時調色盤可能還在淡入，讀 CRAM 要等淡入結束。VSRAM 捲動 8 時截圖的 y 也差 8。
- 按鍵：有些遊戲片頭要按 A 才跳過、標題要連按 START；命令選單的按鍵常要按住約 20 幀才反應，按太久方向鍵又會自動連續移動。`replay` 的 `at` 要算進 steps 本身的長度（每次按鍵＝hold＋20 幀放開）。
- `drive.py` 的 `--window`／`--reads` 結束幀若超過腳本總長，會什麼都不印、也不報錯，要讓視窗在最後一幀之前結束。
- `replay` 的 savestate 要存得夠早：遊戲可能在畫面出來前很久就讀了指標，存太晚 ROM patch 不會生效（ヨーロッパ戦線提前約 250 幀才正常）。
- 借用別款遊戲的模組（如 `haouden/lz.py`）時用 `sys.path.append`，不要 `insert(0, …)`，否則同名的 `verify_*.py` 會被那個資料夾的版本蓋掉。
- `drive.py --reads` 的輸出只印前 60 行，雜訊多半是 memcpy；只想看某支程式時改寫 `--lua` 自己過濾 PC。

## 壓縮

光榮 1992–93 年的 MD 作品（全国版、三國志III、覇王伝）用和 SFC 相同的 KOEI LZ 格式（武将風雲録、三國志II 沒有壓縮），但 MD 的解碼器把查表寫成程式碼，ROM 裡找不到 `tools/koei_lz.py` 用來定位的表。可以把 `koei_lz.BLOCK` 接在 ROM 後面當表用（全国版的做法），或用 san3／haouden 的 `lz.py`（不需要表的寫法）。元朝秘史（日美兩版）用的是另一種 MD 自己的 LZ（`genchou/rom.py`）。劇本差分也不一定壓縮：提督の決断的 SFC 版是 LZ，MD 版直接存差分記錄，找指標表即可。

## kaodata 匯出

光榮作品的頭像依 kaodata 的 `docs/data-format.md` 匯出（`<game>/export_kaodata.py --out <dir>`，共用 `tools/kaodata.py`），交接時輸出到 kaodata 的 `data-local/<id>/`，再在 kaodata 跑 `pnpm verify data-local/<id>`。

- **色盤換算**：所有資料集（`nobu2-md`、`nobu4-md`、`nobu5-md`、`san2-md`、`san3-md`、`genchou-md`、`koukai-md`、`royal-md`、`tk-md`、`air-md`、`europe-md`）一律用 MAME 色階，CRAM word `----BBB-GGG-RRR-` 的每個 3-bit 值 0–7 → 0, 52, 87, 116, 144, 172, 206, 255（各遊戲 `rom.py` 的 `md_rgb`）。這是 MAME 截圖的實際輸出，驗證時能逐 pixel 一致。
- `name` 照 ROM 原文（錯字照錄），史書寫法放 `nameHistorical`；`reading` 只在 ROM 有讀音時給，全形平假名、姓名之間空一格。外部來源的人名不放進資料集。
- 沒有人物使用但有意義的頭像加 `group`（如「姫」「事件人物」），名字要有 ROM 依據才給 `name`。
