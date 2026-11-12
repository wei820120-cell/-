# 題材研究：供需事件：SpaceX Kessel太空機櫃與PCB midplane材料（傳聞）

> 🤖 AI 研究（2026-11-12 11:01），僅供參考，台股代號已和上市櫃清單核對。
> 狀態：**傳聞**｜時間軸：**中期（3-12個月）**

**一句話**：Threads 個人帳號稱 SpaceX 客製機櫃 Kessel 以 PCB midplane 取代線纜、84 層 midplane 全用 M10+Q、稱 100% 用台光電 898K4、單板 2 萬美元以上——未證實，搜尋找不到 midplane、M10、台光電的任何佐證。可佐證的只有：SpaceX 與輝達要把 Vera Rubin NVL72 適配軌道（首發目標 2027 Q4），以及 FundaAI（單一來源）稱太空版代號 Kessel、約 9U、2027 年 6,000 個機櫃。

## 台股供應鏈總表

| 環節 | 代號 | 名稱 | 角色 | 影響 | 股票期貨 |
|---|---|---|---|---|---|
| 高階銅箔基板（CCL，M9／M10） | 2383 | 台光電 | 高階 CCL，貼文稱供應 Kessel 的 midplane 材料（未證實）；M9 已認證出貨 | 受惠 | PJF／小型SFF |
| 高階銅箔基板（CCL，M9／M10） | 6213 | 聯茂 | 另一家被報導取得 M9 認證的 CCL 廠 | 受惠 | KBF |
| 高階銅箔基板（CCL，M9／M10） | 6274 | 台燿 | 高階 CCL 廠，AI 伺服器 M8／M9 題材相關 | 受惠 | OVF |
| 石英布與玻纖布 | 1815 | 富喬 | 電子級玻纖紗與布廠，石英布題材相關 | 受惠 | 無 |

<details><summary>觸發來源</summary>

2026-11-12 供需失衡（需求爆發，未證實）：來自待檢視清單——Threads @thatmrchien 2026-11-11 貼文稱 SpaceX 客製機櫃 Kessel 以 PCB midplane 取代 cable cartridges、機櫃維持 18 層 compute tray 對 9 層 switch tray，84L midplane 全上 M10+Q、稱 100% 用台光電 898K4、一張板子估計 2 萬美元以上。這是個人帳號說法，未證實。
https://www.threads.com/@thatmrchien/post/DfmIndqk0m4

</details>

---

# 供需事件：SpaceX Kessel 太空機櫃與 PCB midplane 材料（傳聞）

> 資料說明：事件來自 Threads 個人帳號 @thatmrchien 2026-11-11 的貼文，**未證實**。搜尋只能佐證「SpaceX 與輝達要把 Vera Rubin NVL72 適配軌道、FundaAI 稱太空版代號 Kessel」，**找不到任何來源提到 midplane PCB、M10+Q、84 層、台光電 898K4、單板 2 萬美元**；這些細節請視為傳聞。資料來自搜尋摘要。

## 1. 貼文說了什麼（未證實）
- SpaceX 客製一個全新機櫃架構「Kessel」：**用 PCB midplane 取代 cable cartridges**；機櫃維持 18 層 compute tray 對 9 層 switch tray。
- 貼文稱最大重點是 **84 層（84L）midplane 全部用 M10+Q（石英布）**，目前看 **100% 用台光電的 898K4**，一張板子估計 2 萬美元以上、也可能更多。

## 2. 搜尋能佐證與不能佐證的
- **佐證（單一來源，未證實）**：FundaAI（Substack 研究電子報）11/6 稱太空版 NVL72 代號 Kessel，保留 72 GPU 的 NVLink 域、把 48U 機櫃縮到約 9U；稱 SpaceX 向某「領先伺服器 ODM」下 2027 年 6,000 個太空機櫃（約 43.2 萬顆 GPU、1.05 GW），每顆衛星一個 NVL72 機櫃，AI1 衛星峰值 250 kW。**SpaceX 沒有確認這張訂單，FundaAI 沒有點名製造商，6,000 個機櫃是分析師估計。**
- **相對可靠**：SpaceX 與輝達表示將改造 Vera Rubin NVL72 上軌道，SpaceX 目標 2027 Q4 首次發射；SpaceX 已向 FCC 申請最多 100 萬顆衛星的軌道資料中心系統；SpaceX 的 IPO 文件說可能拿不到足夠的 AI 晶片，並計畫建 Terafab。
- **台灣供應鏈**：TrendForce 預期台廠會爭取 SpaceX 供應鏈，Starlink 零件包含 PCB；Digitimes 4 月有「台灣供應鏈瞄準軌道資料中心」的標題（只看到標題）。**沒有任何來源點名台光電或任何台廠在 Kessel 的角色。**
- **材料背景**：M9 的關鍵是以石英布（Q-glass）取代一般玻纖布並搭配 HVLP4 銅箔；里昂稱 Rubin Ultra Kyber 的中層板預計採 M9、78 層；台光電被稱為首家取得 M9 認證並出貨的廠商，另有報導稱台光電與聯茂兩家取得 M9 認證；法人認為 PTFE 難以撼動 M9／M10 的主流地位。搜尋**沒有**找到 EM-898 型號或 M10 的具體規格。

## 3. 供需缺口怎麼來的（若屬實）
- 太空機櫃要把大量算力、電力與散熱塞進小體積，用 PCB midplane 取代線纜可減少連接器與重量，但層數與材料等級高（84 層、石英布），**高階 CCL 與石英布本來就是 AI 伺服器供應偏緊的環節**。
- 6,000 個機櫃（若屬實）與 2027 年出貨時程，會把高階 CCL、石英布與高層板的產能需求往前拉；但目前只有分析師估計。
- 單板 2 萬美元的說法沒有來源，**不可用來推算營收**。

## 4. 誰受惠、誰受傷（若屬實）
- **受惠（推測）**：高階 CCL 與石英布供應鏈——台光電（M9／M10）、聯茂（M9 認證）、石英布與玻纖布廠；高層數 PCB 製造商（若有被選上）。
- **受傷／風險**：因高階材料被太空機櫃占用而延後出貨的其他 AI 伺服器客戶（推測）；若設計改回線纜或改規格，PCB 方案落空。
- **替代供應**：不清楚；貼文稱台光電 100%，沒有第二來源。

## 5. 風險與資料缺口
- 貼文為個人說法；FundaAI 為單一來源；搜尋沒有找到任何台廠與 Kessel 的連結。
- 太空環境的可靠度、熱循環與輻射對 PCB 材料的要求可能不同於地面。
- 發射時程（2027 Q4）可能延後；SpaceX 自己說晶片取得有風險。
- 台灣廠商是否被選用、單板價格、層數與材料都需要供應鏈與法說驗證。

## 6. 要追蹤的時間點
- SpaceX／輝達是否公布 Kessel 規格；台光電與聯茂的法說與月營收說法；FundaAI 後續更新。
- 輝達 Rubin Ultra Kyber 中層板的材料規格（M9／M10）是否確認。

## 資料來源
- [FourWeekMBA：SpaceX Said to Order 6,000 Racks for Orbital Data Centers（引 FundaAI，僅看到搜尋摘要）](https://fourweekmba.com/ai-spacex-said-to-order-6-000-racks-for-orbital-data-centers/)
- [Light Reading：With Nvidia on board, SpaceX orbital data centers to hit 'significant scale' in 2028（僅看到標題）](https://www.lightreading.com/satellite/with-nvidia-on-board-spacex-orbital-data-centers-to-hit-significant-scale-in-2028)
- [Channel Insider：SpaceXAI and Nvidia Take AI Into Orbit: First Launch Set for 2027（僅看到標題）](https://www.channelinsider.com/ai/news-spacexai-nvidia-orbital-ai-satellite-2027/)
- [TechRadar：SpaceX admits its aims of getting data centers in space may fall short due to a lack of chips（僅看到搜尋摘要）](https://www.techradar.com/pro/our-ability-to-achieve-orbital-ai-at-scale-depends-on-our-ability-to-access-a-sufficient-number-of-ai-chips-significantly-more-than-are-currently-available-to-us-spacex-admits-its-aims-of-getting-data-centers-in-space-may-fall-short-due-to-a-lack-of-chips)
- [TrendForce：Space Launch and LEO Satellite Communications: SpaceX Extends Its Lead（僅看到標題）](https://www.trendforce.com/research/download/RP251223FE)
- [Digitimes（2026/4，台灣供應鏈瞄準軌道資料中心，僅看到標題）](https://www.digitimes.com/news/a20260402PD224.html)
- [technews：AI 伺服器材料升級（M9、石英布，僅看到搜尋摘要）](https://technews.tw/2025/09/05/2025-ai-server-material-upgrade/)
- [Threads @thatmrchien（未證實）](https://www.threads.com/@thatmrchien/post/DfmIndqk0m4)

