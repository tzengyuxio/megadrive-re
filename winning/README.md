# Mega-CD ウイニングポスト 解析

KOEI，1993.JUL，Mega-CD 限定（MD 沒有卡帶版）。SFC 版（`~/works/superfamicom-re/winning`）的移植：調教師 30、騎手 70、馬主 41 的臉碼與姓名和 SFC 版相同，頭像 208 張與合成臉部位的色號也相同，調色盤是 MD 的值。光碟格式見 [docs/DISC_FORMAT.md](docs/DISC_FORMAT.md)。

## 指令

```bash
.venv/bin/python winning/export_kaodata.py --out winning/output/kaodata/winning-md [--image IMAGE]
.venv/bin/python winning/verify_kaodata_export.py --dataset winning/output/kaodata/winning-md
.venv/bin/python winning/verify_cd_faces.py                 # 約 15 秒
```

- 映像預設讀 `roms/megacd/Winning Post (Japan).7z`（`--image` 可換），驗證用 Genesis Plus GX（`tools/gpgx.py`）。
- 顏色用 MAME 的 MD 色階（`cd.LEVELS`）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `cd.py` | 光碟解碼：人物名、馬主、調教師、騎手、頭像（`ORGKAO.DAT`）、合成臉、調色盤 |
| `export_kaodata.py` | 匯出 kaodata 資料集 `winning-md`（平台寫 MD，Mega-CD 版另行附註；結構同 `winning-sfc`：頭像 208、合成臉 8 型、人物 140） |
| `verify_kaodata_export.py` | 資料集用參考渲染器畫出來，和 `cd.Disc.face_rgb` 逐 pixel 比對（頭像、8 × 256 種合成臉、人物）；checksums |
| `verify_cd_faces.py` | 模擬器：在選調教師的畫面換掉畫臉程式的臉碼，比對 VRAM 與 CRAM |

## 進度

- ✓ 人物：調教師、騎手、馬主、人物名（與 SFC 版比對）
- ✓ 頭像 208、合成臉 8 型、調色盤 6 組，模擬器驗證；kaodata 匯出（未交）
- … 未解：馬（`UMAKAO.DAT`）、賽馬與其他資料（SFC 版已解，CD 版沒有重做）

## 驗證結果（2026-10-17）

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_cd_faces.py` | 見 docs/DISC_FORMAT.md §4 | 頭像 208／208、合成臉 72／72，tile 與調色盤全同 |
| `verify_kaodata_export.py` | 參考渲染器與 `cd.Disc.face_rgb` | 頭像 208／208、合成臉 2048／2048、人物 140／140、checksums OK |
