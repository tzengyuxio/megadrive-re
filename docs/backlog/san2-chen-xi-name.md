---
status: done
created: 2026-11-10
from: kaodata-re
sources:
  - kaodata-re@a607796:notes/san2.md
  - kaodata-re@a607796:dekoei/kaodata_export.py
---
## 結論

三國志II 的「陳嬉」不是「陳紀」的錯字，是吉川英治《三國志》的人物（曹仁的部將，望蜀の巻）。把 `san2/export_kaodata.py` 裡 `"陳嬉": "陳紀"` 這一筆拿掉，重新匯出 `san2-md` 到 `~/works/kaodata/data-local/san2-md`，跑 kaodata 的 `pnpm verify`。
本版的 `NAME_HISTORICAL` 只填 `nameHistorical`，`name` 已經是陳嬉；拿掉後 id 180 不再有 `nameHistorical`。註解寫「Same names as the SFC version」，SFC 版會同步拿掉。

## 為什麼由這裡做

`san2-md` 資料集由本 repo 的匯出程式產生，kaodata-re 不改別的 repo。kaodata-re 已在 2026-11-10 改好 DOS／PC-98／PC-88／X68000 版（a607796），koei-wiki 也已改成陳嬉。

## 已定與未定

- 已定：證據是能力值。PC 版三國志II 181 陳嬉的武力 64、魅力 34，和三國志I 197 陳嬉相同；三國志I 的陳紀是 39、19（✅ cross）。PC 版 181 和本版 180 在同一位置。讀音 `ちん き` 不必改（嬉、紀都讀き）。
- 已定：照 kaodata 的 `nameHistorical` 規則，陳嬉不填 `nameHistorical`。
- 未定：本版 ROM 的能力值沒有在 kaodata-re 核對過；改之前可以先看本版陳嬉的武力、魅力是否也接近 64、34。

## 考慮過但放棄的做法

- 把陳嬉當成陳紀的缺字代用（kaodata-re 原本的做法）：三國志I 同時有陳紀與陳嬉兩人，能力值不同，陳嬉的數值對得上陳嬉，不是陳紀。

## 結果（2026-11-10）

- 本版陳嬉（id 180）戰力 64、號召 34，和 PC 版 181 相同（✅ cross），照結論拿掉 `"陳嬉": "陳紀"`。
- 重新匯出到 `<kaodata>/data-local/san2-md`：和 `data/san2-md` 相比只有 id 180 的 `nameHistorical` 拿掉（與 `source.revision`）；`san2/verify_kaodata_export.py` ALL OK（模擬器 384/384），kaodata `pnpm verify`：560 checked, 0 mismatched。
- 收進 kaodata 的 `data/` 由 kaodata 那邊做。
