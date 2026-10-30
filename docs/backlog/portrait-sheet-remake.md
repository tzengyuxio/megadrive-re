---
status: done
created: 2026-10-31
from: simagame
sources:
  - simagame:docs/portrait-sheet.md（頭像 sheet 風格規範，正本）
  - simagame:portrait-sheets/README.md（交件位置與 notes.md 格式）
  - ~/.claude/skills/portrait-sheet/（SKILL.md、FORMAT.md、render.py）
---
# 用 portrait-sheet 重做頭像 sheet

## 結論

把本 repo 以前做過的頭像 sheet（例如各遊戲 `output/faces.png`），用 `portrait-sheet` skill 依統一規範重做一遍，交到 simagame。

- 每款遊戲寫一支 adapter（`<game>/sheet_manifest.py`），用編號把頭像 PNG 和名字、能力值的資料表接起來，產生 `portrait-sheet/1` manifest
- manifest 放在 `<game>/output/portrait-sheet/<slug>/sheet.json`，再執行 `render.py` 輸出到同一資料夾的 `out/`
- 把 `out/` 的圖連同一份 `notes.md` 複製到 `~/works/simagame/portrait-sheets/<slug>/`。notes.md 的格式見 simagame 的 `portrait-sheets/README.md`
- 舊的 sheet 不刪、不覆蓋

## 為什麼由這裡做

頭像解碼和名字表都在本 repo，simagame 只負責規範和發布。

## 已定與未定

- 已定：
  - 版面、字型、主題、命名全照 simagame 的 `docs/portrait-sheet.md`
  - 遊戲名寫台灣通行的中文名，原文標題寫在 `original`
  - 人名照遊戲原字，日文字形照舊，只合併錯字
  - `platform` 只寫中文或英文
  - 只放遊戲實際會出現的臉
  - 超過 10 張時，依勢力、劇本等有意義的分組拆成好幾組
  - 使用者同意本 repo 直接寫入 simagame 的 `portrait-sheets/`，這是例外
- 未定：
  - 中文遊戲名、人名寫法沒把握的，寫在 notes.md 的「待確認」，不要自己翻
  - 要不要 commit adapter，由本 repo 的使用者決定

## 考慮過但放棄的做法

- 由 simagame 直接讀本 repo 的檔案來排版：會違反「不跨 repo 改檔」，名字清理也需要本 repo 的知識

## 結果（2026-10-31）

- 本 repo 以前的頭像總覽（`airmanage/output/faces.png`、`airmanage2/output/faces.png`、`genchou/output/heads.png`）都是光榮作品，依 skill 由 kaodata 從資料集做，本 repo 不重做
- 非光榮、有頭像的兩款做了 sheet，交到 simagame（之後交件也放這兩處）：
  - `retsuden`（三國志列傳）：6 張、256 格 → `portrait-sheets/megadrive/retsuden/`
  - `sgz5`（三國志V，MD 盜版）：8 張、493 格（500 人，相同的臉併格）→ `portrait-sheets/koei/sgz5/`（光榮作品的盜版移植，歸 koei）
- 人名照遊戲原字，ROM 誤字不改（使用者 2026-10-31 決定）
- adapter：`retsuden/sheet_manifest.py`、`sgz5/sheet_manifest.py`
- 待使用者決定：各組 `notes.md` 的「待確認」（遊戲名、日版／中文版人名、事件人物要不要放），由 simagame 轉給使用者
