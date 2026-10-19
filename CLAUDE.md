# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

MD／Genesis 遊戲的 ROM 逆向工程專案，結構比照 `~/works/famicom-re`：每款遊戲一個子資料夾，分析結果記在該資料夾的 `README.md` 與 `docs/`。

- Python 一律用 `.venv/bin/python`；lint：`uvx ruff check --line-length 120`
- 遊戲列表與共用工具（`tools/`：MAME 驅動、savestate 重播、反組譯）見 `README.md`；MD 版流程與踩坑見 `docs/PLAYBOOK.md`
- 模擬器用 MAME（`brew install mame`，`megadrij`／`genesis` 不需 BIOS），一律經 `tools/mame.py` 呼叫

## 開發慣例

- 新遊戲：開新資料夾，`README.md` 寫指令／檔案／進度（交接段落見共通語言 §9），`docs/` 寫 ROM 格式（含尚未解開的部分）
- 外部資料（不是 ROM 解析出來的）欄位名加 `[EXT]` 前綴
- 頭像等解碼一定要有模擬器證據（§6 的 `emu`／`capture`：跑遊戲本身的程式、比對 VRAM 或截圖），只有 ROM 解析不算

## RE 共通語言

@~/.claude/re-common.md

本 repo 路徑 ↔ 共通層名（既有的 `output/` 照共通語言 §1 先不搬）：

| 層 | 本 repo |
|---|---|
| original | `roms/*.zip`（卡帶，No-Intro；程式直接讀 zip）、`roms/megacd/*.7z`（Mega-CD，Redump）、`roms/megacd/bios/`；`roms/megacd/.cache/` 是映像解出的 .iso／bin，可重建 |
| references | 沒有固定位置（來源網址寫在各遊戲的 `docs/`） |
| captures | 沒有固定位置（MAME 的截圖與 savestate 放暫存目錄，跑完即刪；GPGX 的 savestate 只在記憶體） |
| extracted | `<遊戲>/output/`：CSV、xlsx、頭像與地圖 PNG 等解碼結果 |
| generated | `<遊戲>/output/`：零件總覽（`tools/parts_sheet.py`）等 |
| runtime | `.emu/`（`tools/gpgx.py --build` 編出的 Genesis Plus GX 與 `system/`）；MAME 用 brew 安裝，經 `tools/mame.py` 呼叫 |
| export | `<遊戲>/output/kaodata*/`：kaodata 資料集（交給 kaodata，依它的 `docs/data-format.md`） |
| docs | 本檔、`README.md`、`BACKLOG.md`、`docs/PLAYBOOK.md`、各遊戲的 `README.md` 與 `docs/` |
| tools | `tools/`（共用：MAME／GPGX 驅動、反組譯、kaodata 讀寫等）；各遊戲資料夾裡的 `*.py`（解碼、匯出、驗證） |

## 上下游

依 `~/.claude/repos.md` 的跨 repo 協作規範（用 `handoff` skill）。

- **素材站**（A 類，規劃中）：非光榮作品的素材依素材站的規格匯出；交接時附 revision 與驗證結果
- **kaodata**（A 類）：若有光榮作品，頭像依 kaodata 的 `docs/data-format.md` 匯出
- **simagame**（B 類）：研究成果要做成推文或配圖時，交接單寫到 simagame 的 `inbox/`
