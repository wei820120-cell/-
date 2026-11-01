# 題材研究：AI 推論 KV cache 儲存需求

> 🤖 AI 研究（2026-11-01 10:01），僅供參考，台股代號已和上市櫃清單核對。
> 狀態：**混合**｜時間軸：**長期（1年以上）**

**一句話**：SanDisk 2026 年 8 月 Investor Day 預估 2030 年企業資料中心 flash 約 1.2 ZB、持久化 KV cache 裝機約 1 ZB、KV cache 約占 AI 資料中心 flash 市場 35%（頻道說『約三分之一』吻合）；這是賣方預測、無獨立第三方驗證，也沒有拆出訂單。已證實的買單是 SanDisk FY27 Q1 資料中心營收 48 億美元（季增 61%），但那是整體資料中心 SSD，不是 KV cache 單項。台股對應以群聯（控制晶片）為主，本次未查個股數字。

## 台股供應鏈總表

| 環節 | 代號 | 名稱 | 角色 | 影響 | 股票期貨 |
|---|---|---|---|---|---|
| 推論記憶體階層（HBM → DRAM → flash） | 8299 | 群聯 | SSD 控制晶片與 GPU 記憶體擴充方案 | 潛在受惠，未量化 | NWF／小型QNF |
| 企業級 SSD 與 NAND 供給 | 3260 | 威剛 | 儲存模組 | 潛在受惠，未查證 | NDF |
| 企業級 SSD 與 NAND 供給 | 6239 | 力成 | NAND 封測 | 跟 bit 出貨走 | KCF |
| 伺服器整機 | 6669 | 緯穎 | 雲端伺服器 | 間接，未查證 | PVF／小型PWF |
| 伺服器整機 | 2382 | 廣達 | AI 伺服器 | 間接，未查證 | DKF |

<details><summary>觸發來源</summary>

頻道貼文偵測（重要性 3）：SanDisk CEO 估計到 2030 年 KV cache 將佔 AI 資料中心 flash 約三分之一，若屬實，會帶動企業級 SSD 與 NAND 需求大幅成長，可能影響多家儲存與控制晶片供應鏈。


</details>

---

# AI 推論 KV cache 儲存需求

> 觸發：2026-11-01 00:06 頻道貼文偵測（重要性 3）——SanDisk CEO 估計到 2030 年 KV cache 將占 AI 資料中心 flash 約三分之一，若屬實會帶動企業級 SSD 與 NAND 需求，影響儲存與控制晶片供應鏈。

## 先講結論
- **數字對得上，但是賣方預測**：SanDisk 2026 年 8 月 Investor Day 的說法是——2030 年企業資料中心 flash 的可服務市場約 **1.2 ZB（zettabyte）**、**持久化 KV cache 的裝機容量約 1 ZB**，KV cache 約占 AI 資料中心 flash 市場的 **35%**（報導之間分母的說法略有不同：『市場』與『NAND 工作負載』）。頻道說的『約三分之一』和 35% 大致吻合。
- 這是**供應商替自己的市場估的規模**，沒有第三方獨立驗證；KV cache 外溢到 SSD 的比例取決於推論架構（模型大小、上下文長度、agentic 多輪對話），而這些都還在變。
- 實際的買單證據目前是 **SanDisk 自己的財報**：資料中心營收 FY27 Q1 約 **48 億美元（季增 61%）**——但這是整體 AI 資料中心 SSD 需求，**沒有拆出多少來自 KV cache**。

## 為什麼 KV cache 會變成儲存需求（機制）
1. 大模型推論時，每個 token 會產生 key／value 張量（KV cache），上下文越長、並行使用者越多，KV cache 越大。
2. 放在 GPU 的 HBM 或主機 DRAM 最快，但容量貴且有限；當上下文拉到數十萬 token、agentic 工作負載反覆讀取同一份歷史時，把冷的 KV **卸載到快閃記憶體（持久化 KV cache）** 比重新計算便宜。
3. 因此 flash 變成 HBM／DRAM 之外的**第三層**。SanDisk 的 Chief Product Officer 就是這樣定位，並推 **HBF（High Bandwidth Flash）** 當專用方案。
4. 8 月法說管理層的措辭是：KV cache 機會『持續成熟』、『依使用情境而定』，並說 AI 模型變大、上下文變長、agentic 把需求再放大——**用語仍是機會，不是已量化的訂單**。

## 長期財務模型（SanDisk Investor Day，二手報導）
- FY2028～FY2030 營收年增『中後段十幾 %』（原文 mid-to-high teens，與 bit 成長一致）、非 GAAP 毛利率約 **80%**、營業利益率約 **75%**。
- 這個毛利率遠高於歷史水準，隱含假設是**供給持續緊、長約維持**；若 KV cache 需求不如預期，毛利率假設會先被檢驗。

## 台股對照（這題沒有新查個股數字）
| 公司 | 位置 | 關係 | 說明 |
|---|---|---|---|
| 群聯 8299 | NAND 控制晶片＋企業級 SSD 方案 | 控制器是 SSD 價值量的核心；其 aiDAPTIV 類方案本來就是用 SSD 擴充 GPU 記憶體 | 本次未查證數字，列追蹤 |
| 威剛 3260／宜鼎 5289／創見 2451 | 儲存模組 | 吃企業與工控 SSD 需求 | 本次未查證 |
| 旺宏 2337／華邦電 2344 | 利基型快閃（NOR／SLC NAND） | **與 KV cache 關聯弱**：KV cache 用的是大容量先進製程 NAND，不是利基型；只是同樣受惠大廠產能緊 | 既有研究 |
| 力成 6239 | NAND 封測 | bit 出貨增加會帶封測需求 | 既有研究 |
| 緯穎 6669／廣達 2382 等伺服器 ODM | 伺服器整機 | 資料中心 SSD 要裝進伺服器；需求能見度取決於雲端客戶 | 本次未查證 |

## 風險與提醒
- **賣方預測**：35% 是 SanDisk 對自家市場的估計；其他 NAND 廠或研究機構未見獨立數字。
- **替代方案多**：KV cache 壓縮／量化、更長 HBM、CXL 記憶體池、DRAM 大容量化都可以減少 flash 卸載需求（我的推論，未逐一查證）。
- **時程長**：預測到 2030 年；近期（2026～2027）的 NAND 價格主要由 AI 資料中心 SSD 整體需求與供給配額決定，KV cache 只是敘事的一部分。
- **『若屬實』的條件**：要看雲端／模型廠是否真的採用持久化 KV cache 架構並大量採購，這點本次**沒有找到客戶端的獨立證據**。

## 要追蹤什麼
- SanDisk Q1 法說全文有沒有量化 KV cache 的訂單或客戶；
- Nvidia、雲端廠（AWS、Google、Microsoft）對推論儲存層的官方架構說明；
- 企業級 SSD 合約價（TrendForce 11 月）；
- 群聯、威剛等 10 月營收與法說對企業級 SSD 的說法。

## 資料來源
- [StorageNewsletter（2026/8/19）：Sandisk 公布成長策略與長期財務模型（Investor Day）](https://www.storagenewsletter.com/2026/08/19/sandisk-details-growth-strategy-and-long-term-financial-model/)
- [CryptoBriefing：SanDisk 預期 KV cache 到 2030 年占 AI 資料中心 NAND 工作負載 35%](https://cryptobriefing.com/sandisk-kv-cache-nand-ai-data-centers/)
- [GuruFocus：SanDisk Q4 2026 法說重點（KV cache 機會逐步成熟、視使用情境而定）](https://www.gurufocus.com/news/9009608/sandisk-corp-sndk-q4-2026-earnings-call-highlights-record-revenue-and-eps-driven-by-ai-data-center-surge)
- [Sandisk 官方：Fiscal First Quarter 2027 Financial Results（2026/10/29）](https://investor.sandisk.com/node/8476/pdf)
- [tech-insider（轉述 TrendForce）：企業級 SSD 2026 Q4 價格（二手）](https://tech-insider.org/enterprise-ssd-prices-q4-2026-nand-supplier-race/)

