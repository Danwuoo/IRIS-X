# IRIS X 的 ARC AGI 2 agent 架構研究與下一步條件

研究核對日：2026 年 10 月 14 日 UTC
讀取基準：`cc14bd1a79aac1fe6135017c9e09d4834300675d`
用途：供下一階段選擇可驗證機制；這是研究建議，沒有執行模型、安裝套件、登入、啟動新 run、修改既有實作或發布執行版本。

本段描述原研究交付。後續 Stage 0 與 Agent Factory 3 的實際 CPU 元件開發狀態，
請看[目前進度](README.md)及[下一階段準備](NEXT-STAGE-PLAN.zh-TW.md)；本架構清單的
提案仍未因此成為已執行的模型／Agent 實驗。

## 先看研究清單

**先完成既定的 SFT256 A → 至多四個互斥 64-slot RL 批次 B → 以 B 整段額外 model-phase wall 配對的 extra-SFT C。這一輪保持 grid-only 與 no-TTT。** 架構研究應在這個比較之外建立新實驗身分，避免同時改訓練與推論，失去歸因能力。

下一輪最值得檢驗的是下列七個機制，依賴關係比品牌排名重要：

| 優先次序 | 可檢驗機制 | 專案現況 | 建議與啟動條件 |
|---|---|---|---|
| 1 | Direct-grid 與可逆視圖 | 目前 frozen 比較採用的主路徑 | 保留為共同基線；先分清格式、形狀、候選覆蓋與真正 exact-match |
| 2 | 程式提案與 demonstrations 執行檢查 | 舊 `arc_next_agent`、learning-agent 已有實作 | 下一個獨立架構實驗先測；需要同 checkpoint 可產生合法、非空、可泛化的程式候選 |
| 3 | 執行回饋修復 | 舊原型及 learning-agent 已有 bounded repair | 和等成本獨立重提案比較；只有修復帶來新正確候選才擴大深度 |
| 4 | 有界候選沿革與多樣性搜尋 | 舊版有 typed task memory；AVO 式變異／GA 未因此成為現行能力 | 初始程式已有可修復的 partial fit，且新增分支比重採樣有效時才研究 |
| 5 | 候選選擇與直接答案保底 | 舊 learning-agent 有 verifier tier＋八視圖 NLL＋direct floor | 先量候選池 oracle 與 top-2 的差距；池內沒有答案時不加昂貴 judge |
| 6 | Proposal／repair trajectory SFT | 舊 learning-agent 有資料與驗證接點；SOAR 是研究參考 | 在當前 A/B/C 結束後另測；只用訓練來源與獨立驗證過的軌跡，不加入 TTT |
| 7 | 條件式多 agent／多角色分工 | 新的條件研究提案；現行主控制器不是 recursive swarm | 先證明不同表示或分支有互補解，再和相同總預算的單 agent／獨立採樣比較 |

**建議方向：以 full-vocabulary Qwen14B、既有安全解譯器及可重播收據做小型 proposal → execute → repair 實驗。先量增益來源，再決定是否加 search、selector 或多 agent。AVO、Duck、Prime 的主要成績不能外推成離線 Qwen14B 的 ARC-AGI-2 成績。** 下文的成本分級與研究順序是本報告的工程判斷，不是論文已量測的 IRIS-X 結果。

## 一 現有程式究竟有哪些能力

### 目前 frozen SFT 與 RL 比較

`tools/arc_qwen_rlvr004_20261013/source/rl_session/plan.py:10–31` 寫明：SFT256 anchor、32 groups、group size 8、每批八個 parent／64 slots、最多四批、最多四次 RL update；訓練 sampler 是 grid-only。A、B、C 的選擇只用 dev16，平手固定 A → B → C。held32 是已使用過的 experiment-held-out，不能說成專案從未接觸的確認集。

`docs/plan/2026-10-13-native-research-continuation.md` 第三節另明定 identity＋固定 D4 view、至多兩個答案、PUBLIC120 的完整 120-task／167-query 分母與原 scorer、首輪不加 task adaptation。A/B/C 是不同學習率等設定的「介入套件比較」，不是只改 objective 的純因果實驗。

因此，下面的舊 agent 原型雖存在於同一 repo，**不能說成目前 run008 的 program／repair／multi-agent 已被啟用或驗證**。任何 CPU fixture、文件宣告或函式存在，也不能取代 full14B GPU、完整資料路徑及新分數的證據。

### 舊推論原型

`tools/arc_next_agent.py:543–696` 有 `grid`、`program`、`repair` 三種 arm。

- grid 直接輸出 ordered test-grid vector；program 從相同可見 demonstrations 提案。
- 程式由受限 AST interpreter 處理，沒有模型來源的 host `eval`／`exec`／`compile`。
- repair 收到的是實際 demonstration 執行錯誤與差異；成功後回到獨立提案。
- 用整個 task 的 output vector 去重投票，再為各 query 留最多兩個不同 grid。`lodo_status=not_run`；不能把 demo-fit 稱為 LODO。
- 上層需要真正的 process deadline；原型 callback 本身只在返回後辨識超時。

來源：`research/arc-next-line/architecture-memo.zh-TW.md`（2026-10-08）、`research/arc-next-line/README.md`、`tests/test_arc_next_agent.py`。

### 舊 learning-agent 整合版

`tools/arc_learning_agent_20261011/INTERFACES.md` 與 `controller.py` 顯示的是 host-deterministic 控制器，並非改寫 Transformer 架構：

- `program_reason()`（419–433 行）：direct-grid 無候選、可逆視圖不一致或支持少於兩個不同視圖時，`auto` 才升級程式分支；也有明確 always／never。
- `propose_program()`／`execute_program()`（461–510 行）：只有所有 demos exact-fit 的程式才能跑 query。partial cell fit 只能用來找 repair parent，不能當正確 query 證據。
- `programs_phase()`（512–535 行）：有界新提案與修復；有一個全 demo-fit 程式便停止修復。這是可檢驗的 heuristic，不是泛化保證。
- `select()`（537–562 行）：full_agent 優先 program tier，其後才是完整八視圖 NLL、support、穩定 tie-break；若選出的兩格全來自 program，會放回一個 direct candidate。Program tier 可能選錯，也可能擠掉較好的 direct 候選，應單獨量測。
- Typed hypothesis／verifier receipts／parent links 限於單題，題間清除。多個 logical policy view 共享 physical calls，不能把它們當獨立重跑或等算力 ablation。
- 整合版歷史上包含 global LoRA、訓練來源的 verified trajectories、demo-only task adaptation；目前 frozen no-TTT 實驗不繼承其中所有開關。

`src/irisx/arc_candidates_neutral.py` 保留 symbolic provenance 與 native likelihood 的不同證據類型；hash 只證身分，demo-fit 不能冒充 native eight-view verification。

### 歷史負結果帶來的順序

`research/arc-next-line/uncapped-result/README.md` 的已暴露小面板有 41 個不同候選，但 top-1、top-2、pool-oracle 都只有 1/6。`research/stage4-e20/README.md` 的固定 macro grammar development screen 沒有產生候選向量。這些觀察支持「先改善提案／表示，再處理選擇」；不支持「所有搜尋永遠無效」。它們的模型、資料及曝光情形不同，不能拿來當 Qwen14B 新基線。

## 二 證據可比性必須先分清

### ARC AGI 1 與 ARC AGI 2

ARC-AGI-1 起源於 2019 年；ARC-AGI-2 於 2025-03-24 發布。ARC2 官方 repo 列出 1,000 public-training tasks、120 public-evaluation tasks，另有 semi-private 與 fully-private test sets；官方描述兩個 private sets 與 public eval 按人類難度校準接近。Public 研究結果不是 hidden competition 成績。官方資料格式以 exact grid 為準，不能用 cell accuracy 代替。（[ARC2 發布公告](https://arcprize.org/blog/announcing-arc-agi-2-and-arc-prize-2025)、[官方資料與 split 說明](https://github.com/arcprize/ARC-AGI-2)）

本案 167 是 pinned project input 的 query 數，不是 120 個 task。主要指標是 project micro pass@2；論文常用先在題內正規化的 task-macro pass@2，兩者不能直接排列比較。所有實驗至少另列 task-macro、all-test task success、完整分母與 missingness。目標 151/167 只是本案目標，不是對 official private >90% 的預測。

### ARC AGI 3 的 preview public 與 private

2025-07-18 至 08-19 的 preview competition 是 3 個 public environments 加 3 個 hidden environments。2026 正式版於 3 月發布，分成 25 public-demo、55 semi-private、55 fully-private。官方特別說 private 比 public 更難，並刻意相對 public 做 out-of-distribution；這和 ARC2 的 split 難度設計不同。（[ARC3 官方技術報告，第 3.6、6.1 節](https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf)、[正式發布](https://arcprize.org/blog/arc-agi-3-launch)）

ARC3 的 RHAE 結合關卡完成及相對人類的動作效率，內部推理／工具呼叫並不都算環境動作。它不是 ARC2 exact-grid pass@2，也不是 GPU wall 效率；public RHAE 100 不能翻譯成已解決全套 private ARC3，更不能翻譯成 ARC2 100。（[官方 scoring methodology](https://docs.arcprize.org/methodology)）

## 三 主要原始研究的查核結果

下面都是此次實際讀取的原始報告、論文或作者 repo。數字按原文保留其測試範圍，不把不同 model、split、budget、metric 合成排行榜。

| 方法及來源日期 | 機制與原文觀察 | 對本案可借鏡之處與限制 |
|---|---|---|
| **AVO**；原始 kernel 論文 2026-03-25；ARC3 報告 2026-08-21 | Agentic Variation Operators 讓 coding agent 依 lineage、執行證據與 supervisor 改變搜尋方向。ARC3 報告使用 Opus 5，25 public-demo／183 levels，100.00 RHAE | 借用有界 parent links、失敗紀錄、停滯後換假設。原文明說與 VISTA／約 30% model baseline 不是 controlled ablation；沒有小模型 ARC2 證明。[論文](https://arxiv.org/abs/2603.24517)、[NVIDIA 報告](https://developer.nvidia.com/blog/nvidia-avo-reaches-100-on-arc-agi-3-demonstrating-a-frontier-level-general-purpose-architecture-for-long-horizon-autonomous-agents/) |
| **Duck Harness**；2026-07-01 | Tufa Labs 的 minimal coding REPL，grid 狀態外置、image＋text 觀測、淘汰舊訊息。Qwen3.6-27B FP8，25 public games 各 20 次，mean score 1.6002 ± 0.4475 | 借用短而有型別的 feedback／狀態。不是 Qwen14B，也不是 ARC2；Milestone 1 冠軍不等於高 public 分數或 private 全解。別和 2025 preview 的 StochasticGoose 混為一談。[原始報告](https://tufalabs.ai/research/duck-harness/)、[官方 repo](https://github.com/Tufalabs/duck-harness) |
| **Prime Agent**；2026-08-24 | Persistent IPython／RLM、recursive sessions、recovery 與跨 descendant 的資源帳。論文報 ARC3 public RHAE Best@1 95.5%；比較參考線來自外部官方結果 | 可借用任務局部 history／完整計帳。作者 native-harness rerun 未重現外部基準，不能隔離 harness 因果增益；Factorio case 還保存了 reward exploit，提醒持久記憶會放大錯誤。[論文](https://arxiv.org/html/2608.23552v1)、[官方 repo](https://github.com/PrimeIntellect-ai/prime-agent) |
| **Arcgentica**；2026-02-10 | Stateful REPL、程式互動與條件 recursive delegation。Opus 4.6 在 ARC2 public120 得 85.28%，報價 $6.94/task；所列 baseline 79.03%、$3.81/task；最多九個額外子 agent、每題兩次 attempt | 是真正 ARC2 的系統證據，但 frontier hosted API、成本較高，且未單獨隔離 delegation。官方 task-normalized 分數不可當本案 167-query micro。其 GPT5.2 59.81% baseline 只含107題，全文另列全120題53.33%，不得混用。[報告](https://www.symbolica.ai/blog/arcgentica)、[repo](https://github.com/symbolica-ai/arcgentica) |
| **LLM seeded genetic search**；2026-09-23 | Quantized Qwen3.5-4B 提 41-operation DSL seeds，再做 GA。ARC2 public eval 按 ID 前60題由 seed pool 2/60 到6/60；九個 demo-perfect 程式只有六個 test 正確 | 最接近小模型＋可執行搜尋的證據之一。但前20題用於開發、random control 中途改設定、不是完整公開集或等算力比較。支持測試，不能宣稱乾淨確認或可直接放大到90%。[論文](https://arxiv.org/html/2609.27242v1) |
| **CoreThink compositional reasoner**；論文 2026-04-02，稱原工作於2025-11發布 | Object abstraction／structured hints／多樣候選；ARC2 public pass@2 自報24.4%，和 ARC Lang Solver 的 meta-selector ensemble30.8%；較強單 solver26.6% | 支持「先有互補池，再研究 selector」。使用 Grok4、o4-mini、Claude，不能視為同一離線模型的架構 ablation；包含 cell-level majority，移植時不能默默產生新合成 grid。[論文](https://arxiv.org/html/2604.02434v1) |
| **SOAR**；v1 2025-07-10，v2 2026-03-16 | Search/refine 後 hindsight relabel、分別訓練 sampling/refinement。v1 Qwen2.5-Coder7B 從 Sample&Refine 14.25% 到36.25%；完整配置含 test-time training，搜尋量達6000次 | 官方 repo 明確是 ARC1。可借 train-only trajectory 學習與失敗重標記；不能把36.25%當 ARC2、純SFT或 no-TTT 效果。本輪不搬入TTT、外部資料或完整成本。[v1 論文](https://arxiv.org/html/2507.14172v1)、[版本日期](https://arxiv.org/abs/2507.14172)、[repo](https://github.com/flowersteam/SOAR) |

另外兩份參考值得保留，但不提升其證據強度：

- **ARCANA**（2026-07-10）自述 perception、latent-program proposal、symbolic executor、reflective refinement 與 learned meta-controller，並自報 48M、ARC2 semi-private 32.5%。本次論文頁未提供可核對的作者實作／權重連結，也沒有找到官方成績 receipt；其表格把 NVARC 寫作 660M／LongT5 等描述，和本專案既有 NVARC 來源脈絡不一致。因此先列為構想，不作資源決策的主依據。沒有認定它造假，也沒有把未核實當零分。（[原始論文](https://arxiv.org/html/2607.09059v1)）
- **GEPA optimize_anything**（2026-02-18）官方案例的 32.5→89.5% 是 **ARC-AGI v1 public test**、Gemini3 Flash；演化出 code verification、repair、direct-output fallback，並增加每題推論成本。這不是 ARC2 的接近90%證據。可借 design-time trace-informed search；若未另凍結訓練／開發／最終測試邊界，反覆優化 harness 會污染評估。（[原始案例與完整例子](https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/)、[官方 repo](https://github.com/gepa-ai/gepa)）

## 四 七個機制的最小隔離測試

以下都是**將來另立身分的實驗設計**，沒有修改目前 frozen A/B/C。為避免和訓練臂混淆，推論臂改稱 G、P、R，而不用 A、B、C。

### 1 Direct grid 與可逆視圖

**問題：** 模型沒有學到規則，還是候選格式／形狀／view handling 有問題？

最小比較保留同 checkpoint、tokenizer、chat template、native grammar、identity＋固定 D4 view、至多兩答案。把 valid-grid、shape-correct、exact、missing 分開；任何非可逆的輸出還原都應 fail closed。額外 stochastic samples 必須成為獨立預算臂，不能在 RL 結果不佳後偷偷增加。

整合成本低，因已有路徑。風險是把 D4 agreement 當正確性、把短答案的低 NLL 當推理可靠度。當 canonical／transformed prompt 的合法率或輸出長度差異主導失敗時，先查表示與 context；不直接上多 agent。

### 2 程式提案加 demonstration verifier

**問題：** 同一模型把規則編成可執行程式，能否產生 G 沒有的正確答案？

P 對每題做獨立程式提案，僅透過既有 bounded VM 執行；所有 demos exact-fit 後才跑 query。用同 frozen weights 與相同總 model-phase wall，比較 G 和 P；完整詞彙／程式 tokenizer 能力必須保留。另列 parse、unsupported syntax、runtime、demo mismatch、gas exhausted、all-demo-fit、可執行 query 分母，禁止把中途 reject 的題刪除。

整合成本低至中，主要是目前 Qwen14B 輸出契約、計量及測試接線。資料風險是背示範／輸入查表；語言風險是 safe DSL 無法表達規則。只有 P 有非零 held-out success 或與 G 互補，才值得加強程式訓練；全空池時先檢查 grammar、prompt、能力保留與資料，而不是先換 selector。

### 3 執行回饋修復

**問題：** 真實 mismatch feedback 是否比把剩餘算力花在另一個獨立 proposal 更好？

R 和 P 使用相同程式格式、初始提案分布及 executor；R 至多一個修復回合起步。對照保留相同總呼叫／token ceiling 並真正量整段 wall，不能只比較「各四次 call」。共享的第一個 proposal 可做成本分析，但共享部分不可當獨立重跑。

Feedback 只帶舊程式 digest、已看到 demos 的 shape／mismatch／runtime receipts；不帶 public query truth。量修復前後合法率、demo-fit、held-out exact、消耗、最後 top-2。若 R 的新正確候選／秒低於獨立重提案，應減少深度。修正某個 demo 的 cell 不代表修好規則。整合成本中。

### 4 有界 lineage 與多樣性搜尋

**問題：** 在固定資源內保留幾個不同假設，比一條長 repair chain 更有效嗎？

先不用完整 AVO 或 GPU genetic engine。以兩條有界 parent lineage、不同 seed／表示，記錄實際程序及整個 task output vector。對照「同成本獨立重提案」；若要加入 mutation，只允許既有 DSL 的可重播變更，所有執行照常收費。停滯判定、parent 選擇與每條 chain 深度在看評估結果前固定。

舊 typed memory 可重用，但 AVO 式主動變異、GA、persistent REPL 都是新工作。整合成本中至高；主要風險是搜尋擬合 demos、受限語言、反覆探索同一假設，以及跨題記憶洩漏。觸發點是已有可執行且部分接近的候選，後續變異真的解到新增 held-out cases；不是只看到較高 cell fitness。

### 5 Selector 與證據校準

**問題：** 答案已在 pool 內，為何兩個輸出槽仍選不到？

先在完全相同、已封存的 pool 上重播：固定順序／整體向量投票、現有 program-tier＋NLL、取消 program tier 的共同 NLL 等明確政策。不得用 test truth 排序；oracle 只能由封存後 evaluator 算。用訓練來源或已揭露 dev 校準政策，之後在另一批凍結題確認。

至少列 pool-oracle、top-2、oracle-minus-top2、各 origin 的 unique solves、program tier 擠掉正確 direct 的次數，以及每個 selector 的額外 scoring forwards。沒有 oracle gap 時不要買 judge 成本。有 gap 且可重播 heuristic 改善後，才研究 learned selector。真正 LODO 要在生成、選擇、memory、feedback 全部移除該 demo output，重新做 procedure；跑回已看過的 demos 不算。

先做 deterministic replay 的成本低；新 learned selector 成本中至高，還需離線可部署資料與校準。單一 prompt 自報 confidence 不算 verifier。

### 6 Proposal 與 repair trajectory SFT

**問題：** Grid-only SFT 是否削弱 code proposal？針對實際失敗軌跡訓練能否改善推論效率？

這是當前 SFT/RL 套件比較之後的獨立訓練題目。先保存 frozen-base 與 SFT256 的 G/P/R 表現，再比較相同訓練時間的 grid continuation 和混合 proposal／repair continuation，保留 grid retention。不能只測訓練後 R 一條路徑便宣稱是 agent 架構加成。

每筆軌跡固定 parent／family／split、原程式、真實 executor feedback、修正 target、source digest、completion-only loss mask。Target 要重播驗證，tool text 不進 assistant loss；合成題按 generator family 分組。SOAR 式 hindsight relabel 產生的是新的 synthetic task，不是原題被成功解出；必須另記 provenance。Dev／PUBLIC trace 不能回流成下一輪訓練而仍稱 holdout。

整合成本中至高，資料品質通常比接 trainer 更重要。需要先有足夠非重複、可驗證且非平凡的訓練軌跡，才考慮小型 train-only 續訓；本報告不授權外部 teacher、下載 corpus 或 TTT。

### 7 條件式多 agent

**問題：** 多角色帶來的是獨立假設，還是同一模型的重複思考和更多 prefill？

最小候選是同一 frozen Qwen14B 的兩個短分支，例如 pixel/grid 與 object/relations 表示，各自提出可驗證候選。先讓兩分支獨立，最後用 deterministic executor 合併；不加無界互談、recursive spawn、跨題技能記憶或第二 backbone。與兩次同表示獨立採樣及單 agent 同總 wall／tokens 比較，才能區分角色分工和單純多花算力。

先離線量候選互補性，再決定是否做 conditional gate。可見訊號可用合法候選缺失、視圖分歧、demo 執行錯誤與剩餘 budget；不能使用 evaluator 的錯誤類別或 query truth 來決定是否開分支。兩視圖一致仍可能共同錯誤，所以 gate 的 false-negative 要在開發集量測。

整合成本高於 G/P/R，主要增加 context、scheduler、共享預算及證據歸屬。只有互補解的收益在相同總預算仍存在，且排程減少無效呼叫，才升級成 multi-agent 研究；Arcgentica 及 ARCANA 的整體結果不能替這項 ablation 作答。

## 五 共同實驗與部署契約

1. **凍結比較單位。** 新架構實驗固定 base／adapter／tokenizer／precision／source／seed policy、task groups、executor、sampling、所有 budgets。先以很小的 training-derived engineering panel 排除格式／資源錯誤，再預先固定較大的 task-disjoint development panel；小面板不能 promotion。不得用 PUBLIC120 挑 harness／提示／修復深度。
2. **分開 caps 與實際成本。** 記 input/output tokens、prefill、decode、scoring forwards、CPU gas、wall、peak allocated／reserved memory、失敗與未知成本。相同 ceiling 不是相同 FLOPs；沒有用掉的資源、早停、卡住及重試都要保留。
3. **同時報覆蓋與選擇。** Primary exact-grid、全分母、每 task gain/loss、pool-oracle、選擇差距、有效與無效候選、不同 lineage 的解題互補。重複題及同族變形不是獨立樣本；不只報成功子集。任務群組 paired uncertainty 和 seed variation 用來描述不確定性，不能把小樣本最佳點當保證。
4. **不降低安全與科學邊界。** 模型程式只在既有 VM；不要為了搬入 Duck／Prime 的任意 Python REPL 而開 host exec。Solver 看 demos＋query input，evaluator 在 owner 關閉與封存後才讀 query answers。Task-local memory 題間重置。保留既有數值 replay、checkpoint reload、closure、scorer bytes 與完整 physical charges。
5. **4 L4 不等於一張96GB卡。** NVIDIA L4 每卡24GB；RTX PRO6000 G4 每卡96GB。若以14B參數估算，BF16純權重約28GB（十進位），還未計KV／activations，因此舊8–9B「每張一 replica」建議不能直接搬到Qwen14B。須另比較經驗證的量化 replica 或跨卡切分；不能因為四卡總和96GB便宣告可行。Blackwell訓練可用也不證明Ada L4的kernels／數值／throughput可用。（[NVIDIA L4 規格](https://www.nvidia.com/en-eu/data-center/l4/)、[Google G4 規格](https://docs.cloud.google.com/compute/docs/gpus/)）
6. **推論並行和多 agent 是兩件事。** 四卡可排不同 task，不代表四個 agent 互談更快。先測一個實際可部署單元，保留最長 prompt 和失敗 cleanup 的餘裕，再評估四卡排程。沒有硬體實測之前，整合成本只報質性風險，不編造秒數或VRAM峰值。

## 六 第一輪結果如何決定研究下一步

| 看到的證據 | 下一個問題 | 暫緩什麼 |
|---|---|---|
| Frozen A/B/C 還沒完成或數值／closure失敗 | 先完成真正可解讀的同-session比較 | 所有新agent效果宣稱 |
| 大量 malformed／context-excluded，oracle幾乎空 | 格式、context、表示、full-vocabulary能力與訓練覆蓋 | Learned selector、recursive swarm |
| G有候選，P只有合法程式卻不fit demos | Program prompt、語言可表達性與train-only trajectory | 擴大程式搜尋深度 |
| P有真實互補解，R不如獨立重提案 | Proposal diversity／restart | 更深repair chain |
| R在同成本產生更多held-out正解 | 整理可重播repair資料與小幅lineage探索 | 立即套完整外部harness |
| Pool-oracle提高但top2不動 | 固定pool selector replay、program-tier偏差 | 更多proposal成本 |
| 分工分支有unique solves，但總wall後無收益 | Gate、排程、重複prefill和跨卡部署 | 宣稱multi-agent優勢 |
| B沒有有效reward variance | 依既定audit區分乾淨零訊號與未完成；整個B都沒有有效更新才B=A，後續零訊號batch保留先前完整已commit的B | Reward-conditioned重抽樣、改門檻或把demo-fit當test truth |

本表提供研究觸發條件，沒有改寫現行 admission／promotion thresholds，也沒有加入新的模型執行授權。

## 附錄 名稱對照與延後理由

主線仍是上述七個機制。下列名稱只用來釐清 repo 研究歷史與可借用介面，並非要求把每個框架裝入提交包。

| Repo 提到的名稱 | 精確角色與此次查核來源 | 對本案處置 |
|---|---|---|
| NeMo RL | 訓練後端／SFT、RL工具；[官方 repo](https://github.com/NVIDIA-NeMo/RL) | 不能把backend支援當Qwen14B此環境已相容；不替換frozen optimizer／sampling semantics |
| NeMo Agent Toolkit | 工作流profiling與observability；[官方profiler文件](https://docs.nvidia.com/nemo/agent-toolkit/latest/improve-workflows/profiler.html) | 可借call／token／latency欄位；不是ARC演算法，也不是NeMo RL |
| Prime Verifiers | 訓練／評估環境、rollout、reward介面；[官方 repo](https://github.com/PrimeIntellect-ai/verifiers) | 與Prime Agent不同。先對照契約，不因採用名稱宣稱reward有效 |
| DSPy／GEPA | LM程序與trace-informed文字／程式配置搜尋；[GEPA repo](https://github.com/gepa-ai/gepa)、[原始論文](https://arxiv.org/abs/2507.19457) | 歷史prompt搜尋不等於新agent已採用；有可測的workflow缺陷才另做design-time search |
| AFlow | Code-represented workflow space的MCTS；[官方 repo](https://github.com/FoundationAgents/AFlow)列HumanEval、MBPP、GSM8K、MATH、HotpotQA、DROP | 沒有在該來源建立本案ARC2增益。先用固定G/P/R，避免同時搜尋workflow與權重 |
| RouteLLM／FrugalGPT | 強弱模型路由與budget-constrained cascade；[RouteLLM](https://github.com/lm-sys/RouteLLM)、[FrugalGPT](https://github.com/stanford-futuredata/FrugalGPT) | 目前只有一個主offline Qwen14B與兩個答案槽；先證明可部署候選有差異，再研究router |
| Agent Lightning | 將agent執行與資料驅動最佳化相接；[Microsoft原始專案](https://www.microsoft.com/en-us/research/project/agent-lightning/) | 訓練介面參考，不是本案RL或multi-agent收益證據；增加依賴前要先有具體瓶頸 |
| Jev／REFLEX | TypeSafe的Choice、Score、Noul型別決策；REFLEX以低confidence升級強LLM；[官方文件](https://docs.typesafe.ai/introduction)、[REFLEX論文，2026-09-22](https://arxiv.org/html/2609.26532v1) | 一般工具控制證據，不是ARC2規則歸納；未核實可離線部署權重。Demo exact-match直接算，不用learned judge猜 |
| SPEX／VANTA／IRIS／EIDOS | 本repo冷封存的predecessor材料，upstream均Unknown；來源為archive tag下的`corpus/sources.yaml`與`sources/README.md` | 分別借measurement、受控執行、state/failure attribution、provenance概念。不能錯認成網路同名產品，也不恢復舊架構或授權 |

### 讀取範圍與尚未建立的事實

- 實際讀取：2026-10-08 architecture memo／next-line README，2026-10-13 continuation plan，2026-10-11 learning-agent README／INTERFACES／controller／learning_cycle，現行 `rl_session/plan.py`、measured-policy相關引用，E20／uncapped歷史摘要、neutral candidate證據契約，以及冷封存registry／foundational synthesis。
- 主要web來源均於2026-10-14打開或搜尋後核對原文；引用使用原作者／官方頁。動態README的日期是此次查閱日，不能冒充paper發表日或固定upstream commit。
- 舊archive的local tree fingerprints不證明上游exact revision。這次沒有安裝、clone、抓weights或執行外部repo，沒有建立runtime相容性、license完整審查或獨立benchmark reproduction。
- 沒有讀取或匯入官方private task答案，沒有產生新模型分數。ARCANA的官方receipt及可重現實作仍未核實；各harness的本地Qwen14B收益、4L4吞吐、真正最適修復深度都仍未知。

**可立即採取的結論是研究順序，而非分數承諾：完成frozen學習比較，建立同checkpoint的G/P/R證據，再由候選覆蓋、互補性、selection gap與整段成本決定是否加搜尋或條件多agent。**
