# megadrive-re

MD／Genesis 歷史策略遊戲的 ROM 逆向工程：解析人物、頭像、地圖等遊戲內容。光榮作品的頭像匯出成 kaodata 格式（kaodata 的 `docs/data-format.md`），非光榮作品（三国志列伝等）日後依素材站規格匯出。

每款遊戲一個資料夾，指令、輸出檔、進度寫在該資料夾的 `README.md`，ROM 格式（含未解部分）寫在 `docs/`。

## 遊戲

| 資料夾 | 遊戲 | 發行 | 狀態 |
|--------|------|------|------|
| [retsuden](retsuden/) | 三国志列伝 乱世の英雄たち（＋中文版 三國志列傳 亂世群英） | SEGA 1991 | 人物、城、劇本、頭像、大地圖 |
| [bushou](bushou/) | 信長の野望・武将風雲録 | KOEI 1991 | 劇本、武將、國、茶器、頭像（專屬＋組合臉）、大地圖、戰場地形；kaodata `nobu4-md` |
| [san2](san2/) | 三國志II | KOEI 1991 | 6 劇本、人物、州、頭像（專屬＋組合臉）、大地圖、戰場 41 張；kaodata `san2-md` |
| [san3](san3/) | 三國志III | KOEI 1992 | 劇本、人物、州、勢力、寶物、頭像（一般＋合成）、大地圖、戰場資料；kaodata `san3-md` |
| [zenkoku](zenkoku/) | 信長の野望・全国版（＋美版 Nobunaga's Ambition） | KOEI 1993 | 4 劇本、大名、國、頭像、大地圖（含開局上色）、戰場地形；kaodata `nobu2-md` |
| [genchou](genchou/) | 蒼き狼と白き牝鹿・元朝秘史（＋美版 Genghis Khan II） | KOEI 1993 | 人物、國、王家、女性、子女、頭像（專屬＋組合臉）；kaodata `genchou-md`（日版） |
| [haouden](haouden/) | 信長の野望・覇王伝 | KOEI 1993 | 劇本、人物、城、大名、頭像（專屬＋組合臉）；kaodata `nobu5-md`；地圖未做 |
| [daikoukai](daikoukai/) | 大航海時代 | KOEI 1992 | 人物、港口、國家、名稱表、頭像（專屬＋組合臉）、世界地圖；kaodata `koukai-md`；港町圖未做 |
| [royal](royal/) | ロイヤルブラッド | KOEI 1992 | 4 劇本、人物、家、領地、部隊、頭像（人物＋相談役＋部隊）、戰略地圖、戰場地形；kaodata `royal-md` |
| [teitoku](teitoku/) | 提督の決断 | KOEI 1992 | 9 劇本、提督、艦船、基地、艦隊、頭像、世界地圖；kaodata `tk-md`；作戰大地圖未解 |
| [airmanage](airmanage/) | エアーマネジメント・大空に賭ける | KOEI 1992 | 2 劇本、都市、距離、機種、製造商、頭像（部下＋交涉對象＋廠商）、大地圖；kaodata `air-md` |
| [europe](europe/) | ヨーロッパ戦線 | KOEI 1993 | 6 劇本、將領、領袖、都市、兵器、頭像、戰場地形；kaodata `europe-md`；戰場畫面未解 |
| [taikou](taikou/) | 太閤立志伝 | KOEI 1993 | 人物、勢力、城、頭像（專屬＋組合臉）；kaodata `taikoh-md`；大地圖、戰場未做 |
| [airmanage2](airmanage2/) | エアーマネジメントII 航空王をめざせ | KOEI 1994 | 4 劇本、都市、機種、事件、頭像（秘書＋職員＋國家代表＋廠商）、世界與地區地圖；kaodata `air2-md` |
| [daikoukai2](daikoukai2/) | 大航海時代II | KOEI 1994 | 人物、VIP、女性、船種、港、道具、發見物、頭像（專屬＋組合臉）、世界地圖格資料；kaodata `koukai2-md`；地圖圖形未解 |
| [dokuritsu](dokuritsu/) | Liberty or Death（独立戦争，美國限定） | KOEI 1994 | 劇本、人物、事件人物、地點、州、頭像（專屬＋組合臉）、大地圖、HEX 戰場格資料；kaodata `liberty-md` |
| [sgz5](sgz5/) | San Guo Zhi V（中國盜版，三國志V 移植改作） | — | 7 劇本、人物、城、勢力、寶物、頭像、選君主地圖；非光榮正式作品，不出 kaodata |

光榮在 MD 上發行的卡帶作品 15 款已全部處理並交給 kaodata（英日版並存者以日版為代表；Liberty or Death 只有美版）。Mega-CD 版（三國志III、ウイニングポスト、元朝秘史、覇王伝）尚未處理。

各遊戲的驗證方式與結果（皆以 MAME 跑遊戲本身的程式）寫在各自的 README。

## 共用工具（`tools/`）

| 檔案 | 用途 |
|------|------|
| `triage.py` | ROM 分診：MD 表頭、checksum、KOEI LZ 區塊、SJIS 字串 |
| `koei_lz.py` | KOEI LZ 解壓（取自 superfamicom-re） |
| `mame.py` | 用 Lua 腳本跑 MAME（背景執行、不搶 focus）：按鍵、截圖、dump RAM／VRAM／CRAM、斷點 |
| `drive.py` | 按鍵序列語法（`btn[:hold][*n]`、`w<n>`、`@tag`）、dump、記憶體讀取追蹤 |
| `replay.py` | savestate 重播：開機一次存檔，之後每輪 patch ROM／RAM、截圖或讀記憶體 |
| `m68k.py` | 用 MAME debugger 反組譯 68000 |
| `glyph_match.py` | 以系統字型比對 16×16 字形，輔助轉寫字表 |
| `kaodata.py`、`parts_sheet.py` | kaodata 格式的讀寫、參考渲染器、組合臉零件總覽（取自 superfamicom-re） |

MD 版的分析流程與踩坑見 [docs/PLAYBOOK.md](docs/PLAYBOOK.md)。
