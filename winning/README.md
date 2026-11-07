# Mega-CD ウイニングポスト 解析

KOEI，1993.JUL，Mega-CD 限定（MD 沒有卡帶版）。SFC 版（`~/works/superfamicom-re/winning`）的移植：調教師 30、騎手 70、馬主 41 的臉碼與姓名和 SFC 版相同，頭像 208 張與合成臉部位的色號也相同，調色盤是 MD 的值。光碟格式見 [docs/DISC_FORMAT.md](docs/DISC_FORMAT.md)。

## 指令

```bash
.venv/bin/python winning/export_kaodata.py --out winning/output/kaodata/winning-md [--image IMAGE]
.venv/bin/python winning/verify_kaodata_export.py --dataset winning/output/kaodata/winning-md
.venv/bin/python winning/verify_cd_faces.py                 # 約 15 秒
```

- 映像預設讀 `_original/megacd/Winning Post (Japan).7z`（`--image` 可換），驗證用 Genesis Plus GX（`tools/gpgx.py`）。
- 顏色用 MAME 的 MD 色階（`cd.LEVELS`）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `cd.py` | 光碟解碼：人物名、馬主、調教師、騎手、頭像（`ORGKAO.DAT`）、合成臉、調色盤 |
| `export_kaodata.py` | 匯出 kaodata 資料集 `winning-md`（平台寫 MD，Mega-CD 版另行附註；結構同 `winning-sfc`：頭像 208、合成臉 8 型、人物 140） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 `cd.Disc.face_rgb` 逐 pixel 比對（頭像、8 × 256 種合成臉、人物）；checksums |
| `verify_cd_faces.py` | 模擬器：在選調教師的畫面換掉畫臉程式的臉碼，比對 VRAM 與 CRAM |

## 進度

| 項目 | 狀態 | 證據 | 說明 |
|------|------|------|------|
| 人物名表（姓、名） | ✅ | cross | 與 SFC 版比對只有 110 的名字不同；DISC_FORMAT §2 |
| 馬主 41、調教師 30、騎手 70 的臉碼與姓名 | ✅ | cross | 與 SFC 版全同；DISC_FORMAT §2 |
| 騎手記錄的其他欄位 | ❌ | | 見「未解」 |
| 頭像 208 張（含秘書） | ✅ | emu+modified | `verify_cd_faces.py` 在 `$18C6A` 改臉碼參數，比對 VRAM 與 CRAM，208/208；DISC_FORMAT §3 |
| 合成臉 8 型 | ✅ | emu+modified | `verify_cd_faces.py` 72/72；DISC_FORMAT §3 |
| 調色盤 6 組 | ✅ | emu+modified | `verify_cd_faces.py` 比對 CRAM 第 3 列與秘書的第 0 列；DISC_FORMAT §3 |
| kaodata 資料集 `winning-md` | ✅ | checksum | `verify_kaodata_export.py` |
| 馬（`UMAKAO.DAT`） | ❌ | | 見「未解」 |
| 賽馬資料、`EVENT.DAT` 等 | ❌ | | 見「未解」 |

## 未解

- `UMAKAO.DAT`：馬的頭部圖，格式未解（DISC_FORMAT §1、§5）
- `EVENT.DAT`、賽馬資料等：SFC 版已解，CD 版沒有重做（DISC_FORMAT §5）
- 騎手記錄除臉碼與人物編號以外的欄位：格式同 SFC 版的 22 bytes 加 2 個 pad，欄位沒有對照（DISC_FORMAT §2、§5）

## 驗證結果（2026-10-17）

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_cd_faces.py` | 見 docs/DISC_FORMAT.md §4 | 頭像 208／208、合成臉 72／72，tile 與調色盤全同 |
| `verify_kaodata_export.py` | 參考渲染器與 `cd.Disc.face_rgb` | 頭像 208／208、合成臉 2048／2048、人物 140／140、checksums OK |
