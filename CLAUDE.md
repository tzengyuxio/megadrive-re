# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

MD／Genesis 遊戲的 ROM 逆向工程專案，結構比照 `~/works/famicom-re`：每款遊戲一個子資料夾，分析結果記在該資料夾的 `README.md` 與 `docs/`。

- ROM 都放 `roms/`（不進版控），程式直接讀 `roms/` 裡的 zip
- Python 一律用 `.venv/bin/python`；lint：`uvx ruff check --line-length 120`
- 遊戲列表與共用工具（`tools/`：MAME 驅動、savestate 重播、反組譯）見 `README.md`；MD 版流程與踩坑見 `docs/PLAYBOOK.md`
- 模擬器用 MAME（`brew install mame`，`megadrij`／`genesis` 不需 BIOS），一律經 `tools/mame.py` 呼叫

## 開發慣例

- 新遊戲：開新資料夾，`README.md` 寫指令／檔案／進度，`docs/` 寫 ROM 格式（含尚未解開的部分）
- 外部資料（不是 ROM 解析出來的）欄位名加 `[EXT]` 前綴
- 匯出結果放各遊戲的 `output/`（不進版控）
- 頭像等解碼要有獨立驗證（模擬器跑遊戲本身的程式、截圖）

## 上下游

依 `~/.claude/repos.md` 的跨 repo 協作規範（用 `handoff` skill）。

- **素材站**（A 類，規劃中）：非光榮作品的素材依素材站的規格匯出；交接時附 revision 與驗證結果
- **kaodata**（A 類）：若有光榮作品，頭像依 kaodata 的 `docs/data-format.md` 匯出
- **simagame**（B 類）：研究成果要做成推文或配圖時，交接單寫到 simagame 的 `inbox/`
