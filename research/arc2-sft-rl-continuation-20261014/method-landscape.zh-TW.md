# ARC-AGI-2 下一階段：方法、Agent 機制與 RL 選項

查核日期：2026-10-14 UTC。研究來源固定為
[`cc14bd1a79aac1fe6135017c9e09d4834300675d`](https://github.com/Danwuoo/IRIS-X/tree/cc14bd1a79aac1fe6135017c9e09d4834300675d)。
本文件是研究與實驗次序建議，不代表已採用、已訓練或已取得新分數。
研究線從 run008 延伸；main、run008 原分支及工程重整線保持獨立。

**進度入口：** 本文主體保存研究完成時的來源與提案；當前實作、任務、證據與下一步
統一見[開發進度管理](DEVELOPMENT-PROGRESS.zh-TW.md)。第 7 節保存實驗順序與
觸發理由，不另維護執行狀態；元件設計見[整合說明](agent-factory3/integration.zh-TW.md)。

## 一、先講結論

1. **先完成目前的小型、可解釋比較，而非先換大型 Agent 框架。** 共同基準 A=SFT256，B=有限的可驗證 reward 更新，C=等整段額外時間的 SFT。三者差異、reward 訊號與實際成本還沒有本輪有效結果。
2. **最值得排進後續的三項是訓練資料／verified-trajectory SFT、demo-only TTT、程式提案與執行回饋修復。** 它們各自解決不同瓶頸，應分開測；不應同時更換模型、訓練目標、搜尋及選答。
3. **RL 優先比較真正不同的目標與資料使用方式。** 本地 DDIS 不是完整 GRPO/PPO。先驗證非零有效梯度，再考慮 advantage normalization、長度權重及 rejection-SFT 對照。只把 group mean 換成 RLOO 名稱，通常不是有識別力的新實驗。
4. **多 Agent／遞迴委派應放在後面。** 先證明獨立提案有互補解、修復優於同成本多抽樣、選答確有損失；多個角色可以由同一模型輪流擔任，不必先增加模型副本或框架。
5. **成功案例必須分資料集與成本。** ARC1 的 TTT／SOAR、ARC3 的 AVO／Duck／Prime，不能直接作 ARC2 公開120題或離線14B的成功證據。PUBLIC90 是目標，不是預測。

## 二、四個概念其實是不同的維度

| 維度／方法 | 它決定什麼 | 本案定位 |
|---|---|---|
| SFT | 用哪些有目標答案的樣本做監督式參數更新 | 已實作的共同 SFT256 錨點；額外 SFT 是成本對照 |
| RL／RLVR | 如何用 reward 改變產生答案或行動的機率 | 已實作的首輪研究變因；效果尚待真實結果 |
| TTT | 是否在收到新題時，暫時更新模型參數 | 本輪明確關閉；後續獨立消融 |
| Agent 架構 | 如何表示問題、提出候選、呼叫工具、獲得回饋、修復與選答 | 舊線有原型；目前 run008 仍是 grid-only 比較 |

TTT 描述更新發生的時間與資料邊界，SFT／RL 描述訓練目標。因此「先 SFT，再做 demo-supervised TTT」、「先 RL，再做同樣 TTT」及「搜尋產生可驗證軌跡，再 SFT」都成立；有效性需要各自對照。Agent 也可以完全不更新權重，僅執行提案／工具／選答流程。

**「原始 TTT 論文」需分兩個來源：** Sun 等人的 2019 預印本／ICML2020 工作，是對未標記測試輸入建立自監督任務，研究影像分布偏移；並不是 ARC 程式搜尋實驗。ARC 專用的 Akyürek 等人 2024 工作（2025 v2 改題名為 *Few-Shot Learning*）則用本題可見 demonstrations 做 leave-one-out、增強與 LoRA，並研究與程式合成集成。兩者都不能讀未知 query 的答案。[TTT原始論文](https://proceedings.mlr.press/v119/sun20b.html)、[ARC專用TTT](https://arxiv.org/html/2411.07279v2)、[官方程式碼](https://github.com/ekinakyurek/marc)

## 三、Repo 現況：已實作不等於已證明有效

### 3.1 目前凍結的首輪實驗

- **A：** 同一 session 真正訓練256次、保存並重載的 SFT 錨點；不是把歷史 A64 改名。
- **B：** 32個訓練 parent，固定拆成最多4個不重疊 batch；每批8 parent×8 sample=64 slots，最多256 attempts、4次更新。訓練用 demonstration-LOO 的 exact 0/1 reward；不因失敗或全零而補抽樣。
- **C：** 從同一 A 出發，fresh optimizer 做額外 SFT；匹配 B 的**整段同步模型階段 wall time**，包括 setup、抽樣、reward、replay、失敗／rollback、save／reload／verification；不靠 idle padding 湊時間。
- **評估：** dev16 選一次 A/B/C，平手固定 A→B→C；先凍結選擇再做 selected PUBLIC、held32 預測、模型關閉與評分。本輪不加 TTT。
- **分母：** PUBLIC120=120 tasks／167 queries，兩個固定視圖共334 planned views；micro pass@2 分母永遠167。缺少評分是未知，不是0分；已有評分中的缺失／非法答案才按原 scorer 算錯。
- **限制：** held32 已被專案重複使用，不是全新確認集；B lr=1e-6、A/C lr=2e-4，故比較的是干預組合，不是只改 objective 的因果實驗。完整 session 上限43200秒包含 queue 到 closure。

來源：[現行policy](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/design/MEASURED-POLICY.json)、[實際plan](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/plan.py)、[現代batched consumer](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer/validate_owned_outputs.py)。注意 `source/validation/` 還有舊 A64 schema，不能誤當現行 consumer。

### 3.2 已有歷史證據

- 完整 native TTT 曾在**修改過的公開輸入**把 top2 從5/172升至10/172，但時間約6.119倍；不能換算成目前 PUBLIC120 的效果。
- 後續 uncapped native 搜尋在四個已曝光開發 tasks／六個 queries 留下41個不同候選，top1、top2、pool oracle 都只有1/6。對那些既有候選，換 selector 無法補出不存在的答案；這只定位該次局部瓶頸，不證明搜尋永遠無效。
- v25 留存 SFT256／generation 成本觀察，不等於本輪 RL 已通過或新 accuracy。v39 是環境／cuDNN byte mismatch 的 ERROR，沒有新 PUBLIC 分數。

來源：[歷史研究彙整與逐項artifact索引](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/native-continuation-20261013/historical-experiments.md)、[原uncapped結果](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/arc-next-line/uncapped-result/README.md)、[目前handoff](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/native-continuation-20261013/RUN008-LOCAL-HANDOFF.md)。以上是保存的歷史觀察，本次沒有重新查詢 provider 或執行模型。

## 四、Agent 架構：先比較機制，再決定框架

| 候選機制 | Repo 身分 | 值得測什麼 | 最小對照／導入成本 |
|---|---|---|---|
| **Direct-grid transduction** | run008 現行路徑 | 基礎表示與格子生成；不把語法合法率當正確率 | 保留 A/B/C 相同 decoder、固定視圖；最低額外成本 |
| **Independent program proposals** | 舊 `arc_next_agent`／learning-agent 已實作，未在本輪啟用 | 程式是否補到 grid 分支解不到的規則 | 同 checkpoint、同整段預算下對照 direct-grid；記非法／超時／demo不合；中等成本 |
| **Execution-feedback repair** | 舊原型及controller有實作 | 示範執行結果能否引導修正，不只是增加嘗試次數 | 用相同起始候選，比較修復與更多獨立提案；中等成本 |
| **Bounded search／evolution** | NVARC DFS 有歷史線；SOAR式演化是研究參考 | 單純抽樣以外的探索是否增加候選覆蓋 | 同模型、同總wall／generation預算；不得把oracle選答放進solver；中高成本 |
| **Hybrid grid＋program selector** | 舊learning-agent有router／selector接線 | 兩種表示是否互補、兩槽選擇是否丟掉正解 | 先測候選oracle再測top2；有oracle增益才研究selector；中等成本 |
| **Proposal／repair trajectory learning** | 文件有資料契約；SOAR為外部參考 | 把真實執行回饋與可重播修正教給模型 | train-only verified trace SFT vs同量grid／rejection-SFT；資料與lineage成本中高 |
| **Persistent REPL／recursive delegation** | Arcgentica、AVO／Duck／Prime為外部機制參考 | 外部狀態、分解與獨立子假設是否有額外價值 | 先同模型單控制器 vs有限角色，匹配總tokens與wall；高成本，不先接整套框架 |

舊 Agent 的受限 AST interpreter 是將候選程式視為資料解譯，並限制物件、迴圈、遞迴、資源與 host API；**單做 AST filtering 並不等於 sandbox**。後續執行回饋須由實際候選程式與可見 demonstrations 產生；不得把未知 query 的正確答案回傳給 proposer、repairer 或記憶庫。

來源：[原架構memo](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/arc-next-line/architecture-memo.zh-TW.md)、[CPU原型](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_next_agent.py)、[learning-agent總覽](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_learning_agent_20261011/README.md)。更細的名稱與實際接線見 [Agent證據附錄](agent-architectures.zh-TW.md)。

### 4.1 名稱應如何使用

- **BARC：** induction（合成規則程式）與 transduction（直接產生輸出）互補的原始證據；不是「兩個agent聊天」的證據。研究用ARC1與合成程式資料，不能直接承諾ARC2效果。[論文](https://arxiv.org/abs/2411.02272)、[官方repo](https://github.com/xu3kev/BARC)
- **SOAR：** 抽樣／演化修復→hindsight產生可驗證問題—程式對→微調，再做test-time adaptation。v2是2026-03-16；14B結果42.75%，五模型集成52%，用ARC1的400train／400test；每模型每題6000 attempts，集成30000。該14B結果也先用各模型、各輪 pooled training data，再做兩輪test-time training，並非只靠14B自產資料。可借「學會提案與修復」，不能說14B在ARC2已52%或把整條線當低成本。[論文Table6](https://arxiv.org/html/2507.14172v2)、[官方repo](https://github.com/flowersteam/SOAR)
- **NVARC：** synthetic data＋SFT＋TTT＋增強搜尋／選答，是ARC2競賽相關的組合案例。NVIDIA報告的27.64%是Kaggle公開榜；主辦方2025最終 private evaluation 列24.0%，兩者不要混用。其大規模離線資料／訓練不能視作目前一張卡四次RL更新的等價預算。NeMo RL 作為工具名稱，也不證明使用的是RL目標。[作者repo](https://github.com/1ytic/NVARC)、[NVIDIA說明](https://developer.nvidia.com/blog/nvidia-kaggle-grandmasters-win-artificial-general-intelligence-competition/)、[主辦方最終結果](https://arcprize.org/competitions/2025)
- **Arcgentica：** ARC2的執行工具／遞迴委派參考，但frontier API模型、成本增加與多種harness變更同時存在，不能單獨歸因於multi-agent。[作者報告](https://www.symbolica.ai/blog/arcgentica)
- **AVO／Duck／Prime：** Repo確實研究過；其主要已報告成果在ARC3互動環境，與ARC2靜態grid任務不同。借鑑的是外部狀態、假設檢驗、工具回饋、探索與學習接線，不是直接搬分數或安裝框架。詳細benchmark分層與官方連結見附錄。
- **TRM：** 屬於替代神經表示／遞迴答案精煉，不是遞迴多Agent。原文7M參數的ARC1與ARC2結果也有明顯差距。要試須另立模型、資料、訓練和推論基線，不能混進本輪LoRA消融。[原論文](https://arxiv.org/abs/2510.04871)

## 五、RL 方法清單：差別在目標與採樣，不在縮寫

### 5.1 現有 DDIS 的精確定位

Repo 從固定 upstream independently expressed 的 DDIS 全名為 **Direct Double-sided Importance Sampling**。本地使用 exact binary reward、group mean baseline、原始 token 的 DFA-conditioned behavior log-probabilities、detached importance ratio、嚴格雙側區間遮罩，並依序列長度／有效組別正規化；沒有默認加入 reward std normalization、critic、reference KL、entropy bonus、OPSM 或新的staleness機制。

它可視為一種 group-baseline policy-gradient／REINFORCE 類更新，加入importance weighting與雙側遮罩；**不是標準GRPO整套流程，也不是PPO的min-clipped objective**。來源：[本地數學](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/reviewed/rl_math.py)、[GLM-5原始報告§4.1.2](https://arxiv.org/html/2602.15763v1)、[作者DDIS說明](https://huggingface.co/blog/ycchen/agent-factory-3-en#ddis-and-staleness-filter)。GLM報告中的ARC指Agentic/Reasoning/Coding，並非ARC-AGI-2的評測結果。

### 5.2 有意義的候選與對照

| 方法／家族 | 現在的身分 | 與本地差異／考慮理由 | 排序與代價 |
|---|---|---|---|
| **Group-baseline REINFORCE／現有DDIS** | 本地已實作，待真實效果驗證 | 最直接測exact reward能否產生正確梯度；保留當前基線 | 第一優先；先測訊號與replay，不擴訓練 |
| **RLOO** | 外部演算法對照 | baseline排除自己；完整8樣本時 advantage恰為目前中心化的8/7倍 | 適合數學單元對照，不優先宣稱新方法收益；低成本 |
| **GRPO** | Repo研究候選，未完整實作於run008 | 原版group reward標準化、PPO類ratio clipping、reference KL等設計需逐項分清 | 真正有訊號後，一次只改一項；中等成本 |
| **Dr. GRPO式 normalization 消融** | 新後續候選 | 區分group std造成的題目權重與長度normalization效果 | 比單純改名更有識別力；先train-only數學／小型受控測試 |
| **DAPO式改良** | 新後續候選 | clip-higher、token-level loss、dynamic sampling、overlong處理是不同改變 | dynamic sampling不能偷渡到現有不補抽樣契約；另立實驗，中高成本 |
| **PPO／value-critic PPO** | 外部完整RL基線 | value模型／advantage估計、rollout與更新批次增加記憶體、狀態與調參量 | 暫後置；需證明比簡單critic-free更值得 |
| **Rejection-SFT／verified self-training** | 非RL，但必要對照 | 只用實際驗證過的成功候選做SFT，測正樣本模仿／加權是否已足夠；本地exact-grid正例的語意答案仍是已知training target | 優先於大型框架；匹配rollout與訓練總成本，失敗與丟棄資料仍計費 |
| **TTRL／test-time RL** | 外部研究，非本輪安排 | 用推論時代理reward，例如majority agreement，未必是真正correctness verifier | 低優先；錯誤共識可能自我強化；不得取代exact訓練reward或取得query答案 |

原始來源：[GRPO／DeepSeekMath](https://arxiv.org/abs/2402.03300)、[RLOO研究](https://arxiv.org/abs/2402.14740)、[PPO](https://arxiv.org/abs/1707.06347)、[Dr. GRPO](https://arxiv.org/abs/2503.20783)、[DAPO](https://arxiv.org/abs/2503.14476)、[TTRL](https://arxiv.org/abs/2504.16084)。詳細公式差異、RL直接ARC2證據及來源限制見 [RL證據附錄](rl-methods.zh-TW.md)。

**本地條件式推導，不是新實驗結果：** 現行接受門檻是最大 replay log-prob gap≤0.20 且 strict-DDIS coverage=100%，並非本輪已通過的GPU測量；在相同模型權重的batch內先rollout/replay，最後才commit，因此可接受token的ratio落在約[exp(-0.2), exp(0.2)]，嚴格位於(0.8,1.28)。在相同advantage與normalizer下，若PPO使用相同不對稱bounds，或另行確認PPO的clip未啟動，其未截斷ratio項與detached-ratio×logπ具有相同梯度。標準對稱ε=0.2的PPO仍可能截斷ratio介於1.2至1.221的正advantage token，不能由DDIS門檻推定它也完全不clip。故優先把DDIS改名PPO，通常無法回答品質改善來自何處；放鬆數值門檻也不是合法的消融方式。

**RL有直接ARC2研究，但效果不能誇大。** Enigmata的Qwen2.5-32B＋RFT／VC-PPO在論文列ARC1=32.8%、ARC2=0.6%。它不是本地14B／最多四次LoRA更新的對等實驗，不能用ARC1大幅改善推算ARC2。[原論文](https://arxiv.org/html/2505.19914v2)

## 六、每次必須看到哪些訊號

1. **資料：** train／dev／held parent隔離、augmentation ancestry、SFT實際暴露記錄與reward樣本暴露。只用允許的train targets；public／held答案不進模型、提示、記憶或資料篩選器。
2. **Reward：** planned256、actual dispatched、eligible、infrastructure excluded、context excluded、not reached分開；記完整all-zero、all-one、mixed groups和pass@8 coverage。未完成audit不能推論零訊號，非法模型輸出0與基礎設施失敗null不可混用。
3. **梯度／replay：** 原token、原prefix、原legal-token mask、behavior logμ與target logπ一致；nonforced tokens另外檢查，不能靠forced tokens稀釋誤差。保持p95≤0.05、max≤0.20、strict-DDIS coverage100%既有界限；記adapter梯度與實際committed更新、save/reload驗證。
4. **成本：** B與C整段wall、失敗與rollback成本不退回；token數、knownforward work與wall分列。不能將kernel time、GPU-billing與整段耗時混稱。未知device state要停，不能繼續湊分數。
5. **評估：** 相同case IDs下報A/B/C gain／loss、dev一次性選擇provenance、held重用限制；選好方法後固定PUBLIC120／167。oracle只能在隔離的evaluator做診斷，不能回饋到該輪選答或訓練。
6. **判讀：** provider完成、runtime安全完成、comparison完整、成本匹配、scorer完成、方法收益是不同欄位；缺任何一項，就保留該項未知／失敗。

來源：[SFT256／batched protocol研究審查](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/native-continuation-20261013/independent-research-review.md)、[metering檢查](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer/ledger_checks.py)、[PUBLIC檢查](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer/public_checks.py)。

## 七、建議的實驗順序與觸發條件

| 順序 | 問題與最低對照 | 何時推進 | 何時先停／換問題 |
|---|---|---|---|
| **0：離線證據與續接** | 保持凍結source、確認目前consumer與資料契約、修正可重現工程問題 | source與CPU/failure review清楚，再交本地executor | 工程錯誤不是0分；不把半成品或舊receipt當新authority |
| **1：既有A/B/C** | 同session A；B固定batch；C整段wall matched；固定dev/held/PUBLIC | 得到完整reward/replay/checkpoint/closure/scoring證據 | zero-signal與incomplete分開；不因零訊號當場換parent／加抽樣 |
| **2a：若訊號太稀疏** | train-only curriculum／verified trajectories／rejection-SFT，保留原A與同總成本對照 | 先提升合法率、非零可驗證成功與候選多樣性 | 不盲目增加RLsteps或把partial score改成主要成功指標 |
| **2b：若RL確有更新** | 新獨立panel上重複A/B/C；再分離std／length weighting、KL等一個變因 | gain/loss與成本顯示值得再測 | 無淨增益不promotion；小樣本不稱全面能力提升 |
| **3：TTT獨立消融** | 同一已凍結checkpoint，無TTT vs固定demo-only TTT；必要時做訓練方法×TTT的2×2 | 有可重載穩定baseline且整段預算可容納 | 不從未知query學label；不把更多推論算力當免費增益 |
| **4：Agent機制** | 同checkpoint、同總預算比較grid／independentprogram／feedbackrepair | repair勝過額外獨立提案、或program與grid明確互補 | 候選池沒正解先改提案／資料；不是先改selector |
| **5：Selector／多角色** | 固定候選池測兩槽選擇；之後單控制器vs有限委派 | oracle有增益但top2流失，或子假設真正互補 | 多角色只增加成本、共享錯誤或污染選擇時停止 |

以上保存研究完成時的條件式次序；目前採取的工作與狀態見[開發進度管理](DEVELOPMENT-PROGRESS.zh-TW.md)，本節不構成提交或訓練授權。

## 八、硬體現實與尚缺證據

- 本案一張訓練卡與最終四張L4是兩個問題。官方規格RTX PRO6000 G4每GPU96GB，L4每GPU24GB；14B×2bytes約28GB只是BF16權重下限，尚未含activation、KV、LoRA與optimizer，因此單L4不能照搬完整BF16訓練配置。四張卡不會自動成為一塊可任意分配的96GB顯存。[Google規格](https://docs.cloud.google.com/compute/docs/gpus/)、[NVIDIA L4規格](https://www.nvidia.com/en-eu/data-center/l4/)
- 後續需實測兩卡sharding＋兩replica、四卡sharding或量化replica等方案；分別驗證最長context、數值、reload、throughput和12h涵蓋度，不先承諾哪個可行。這是部署候選，不是本輪方法變更。
- 尚缺本輪有效A/B/C與PUBLIC完整結果、獨立未重用確認panel、current14B RL peak memory／replaybackward時間、四L4部署實證。外部論文的高分、CPU fixture通過或provider COMPLETE都補不了這些證據。
- 大規模SOAR搜尋、NVARC合成資料、critic-based PPO及多frontier-agent成本都不等價於本案budget；目前不估算未取得tariff的美元成本，不引入付費資源。

## 九、本輪交付與限制

本研究只檢查公開repo來源、已保存的歷史文件與live primary research。沒有讀取evaluator答案、重新跑scorer、取得Kaggle登入、查詢provider或啟動訓練。
研究完成當時，離線開發半成品保存在 `0451441727e8aea602873902ebccbf6b38576e03`，當時的輸出路徑race與最終integration review尚未完成。這段是歷史狀態；後續實作與驗證統一見[開發進度管理](DEVELOPMENT-PROGRESS.zh-TW.md)。工具測試仍不證明方法有效。
