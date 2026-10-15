# agent-factory-3：實際元件套用與既有決策條件

查核日：2026-10-14 UTC。上游固定 commit：
`a1836decb836cd52cf2b27f5022f6838cee75df3`；截至查核，GitHub 最近提交仍是
該版本（2026-05-11T14:44:26Z）。本地凍結比較基準仍為
`cc14bd1a79aac1fe6135017c9e09d4834300675d`。此處保存該次上游查核及後續 Stage 1 整合契約。
研究問題與固定 A/B/C 見[研究主頁](../README.md)，目前執行進度見[當前狀態](../DEVELOPMENT-PROGRESS.zh-TW.md)。

## 1. 現在確實套用了甚麼

這次新增**直接執行上游程式的離線整合層**，不是再引用一次 DDIS 名稱：

| 元件 | 原始固定來源 | 實際本地接點／證據 |
|---|---|---|
| `TrainingSample` | [types.py:10–58](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/src/agent_factory_3/trainer/types.py#L10-L58) | `bridge.prepare_batch` 建立64個真正上游物件，執行其Pydantic長度validator；保持原始token、completion mask、behavior logp與group統計 |
| `DDISLoss` | [ddis_loss.py:63–164](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/src/agent_factory_3/trainer/losses/ddis_loss.py#L63-L164) | `bridge.compute_loss` 真正呼叫 `compute_unpacked`；`proof.run_proof` 已執行forward與autograd，對照凍結本地math |
| `MeanMetricState` | [metric_state.py](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/src/agent_factory_3/trainer/losses/metric_state.py) | 上游loss回傳16種mergeable metric states；測試不等大小分片的sum/count合併，不做mean-of-means |

上游3個Python檔與LICENSE逐byte保留，Git blob ID與SHA256均核對。
新增adapter、fixtures、source manifest、tests與NOTICE有清楚界線。這是
**已離線整合且實際執行上游元件**；目前凍結訓練runtime仍使用原本本地公式，
尚未接成生產runtime，也未做GPU訓練或ARC品質實驗。

先前本地 `reviewed/rl_math.py` 及 `rl_session/runtime.py` 只獨立表達相同
DDIS機制，註解明確說未執行上游source。因此新增的確切差異是實際元件相依、
嚴格receipt→upstream sample映射、可重跑的差分oracle及可合併診斷，不是宣稱
換了一個新RL演算法。

## 2. 不能整套直接換入的原因

上游[架構與安裝入口](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/README.md)
針對GPT-OSS agentic RL。`RLFlow`的orchestrator與trainer分process，經queue交付
samples、staleness filter、train step與weight sync。`SampleProcessor`區分
infra/model error，建立group-centered advantages；`ModelTrainer`整合FSDP2、
PEFT與packed loss。[RLFlow](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/src/agent_factory_3/trainer/rl_flow.py)、
[SampleProcessor](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/src/agent_factory_3/trainer/sample_processor.py)、
[ModelTrainer](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/src/agent_factory_3/trainer/model_trainer.py)。

完整[pyproject](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/pyproject.toml)
要求Python≥3.12、torch≥2.9且<2.10、Transformers≥5.2、Accelerate、PEFT、TRL、
SGL kernels、Harmony、FastMCP、Liger/Triton等；部分依賴是作者git forks。
它們沒有在本次安裝或執行。採用這些依賴會改變既有離線wheelhouse、模型／精度、
kernel與記憶體需求，不能只以「較新框架」跳過既有admission。

[Wordle例子](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/examples/wordle/README.md)
使用4×H100 80GB：2卡SGLang TP2 rollout、2卡FSDP2訓練。
[Minesweeper例子](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/examples/minesweeper/README.md)
是3個單卡rollout server加1卡FSDP/CPU offload訓練。根README另稱可在2×H100做
GPT-OSS120B LoRA；這是上游說明，沒有在本地測量，也不是Qwen14B單卡或四張L4
部署證據，更不是ARC-AGI-2成績。

Qwen dense路徑沒有GPT-OSS MoE router可重播；R3/routing replay、MXFP4 backward、
DFlash、async、staleness、OPSM與entropy masking均不會自動成為本地已套用元件。
尤其async會改變當前同batch單actor／原始replay契約，故本次不接入。

## 3. 如何保持原決策，不暗換objective

- B仍每批8個parents、每個8個samples，共64 slots；固定32個parents分成最多4批。
- reward仍是training LOO的binary exact-match。infrastructure缺失是未知，不能補0。
- advantage仍為 `R − group_mean`；不除std、不加critic、reference KL或entropy。
- 原始generated token logp直接映射；prompt位置補0並mask。沒有decode→encode。
- 上游loss固定 `eps_low=.2`、`eps_high=.28`、`use_opsm=False`、`entropy_top_pct=None`。
- 上游`divisors`明確指定為 `max(1,M)×8×T_i`，M為mixed groups。這對齊原本本地數學，
  沒有為了測試通過而改公式。完整64個samples包含全0／全1組；這些組advantage為0，
  只保留診斷分母。整批M=0時不呼叫loss/replay，延續原本no-update行為。
- 上游預設`loss_aggregation_mode="seq-mean-token-sum"`不等於本地逐序列token-mean；
  若直接載入TrainingConfig預設，會改變length weighting，因此沒有採用。
  [上游divisor分派](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/src/agent_factory_3/trainer/rl_flow.py#L65-L91)。
- AF3的integer weight version只用batch-local symbol0映射原本policy UUID；原始
  generation_epoch另存。batch序號與epoch都不冒稱實際committed weight version。
- `MeanMetricState`保留sample/token weighting。`algo/ratio_max`是各sample最大值的平均，
  不是全batch最大值；`algo/kl_gen_train`是抽到token的log差統計，不是完整分布KL證明。

A=SFT256、C=對齊B整段額外wall time的SFT、LR／資料／update限制、noTTT、dev選擇及
PUBLIC120/167完整分母保持原樣。本研究沒有改動run008、main或工程管理支線。

## 4. 已完成的離線驗證

正式測試命令與有效套件版本見[validation.md](validation.md)。目前實際結果：

- 真正上游TrainingSample：64個；generated tokens：224；mixed groups：6。
- 真正上游loss與凍結本地loss均為 `0.0014256983995437622`；absolute gap為0。
- underlying synthetic-logit gradient最大絕對差為0；逐trajectory reduction的gradient差亦為0。
- gradient norm為 `0.017627257853746414`，finite且非零。singleton support的原始logits
  gradient為0。這是合成小tensor的autograd證據，不是Qwen／LoRA梯度或model replay。
- 測試包含正／負advantage、zero-signal、strict邊界、detached behavior/ratio、prompt mask、
  不同長度、非等大metrics合併、原始token順序、重複／缺slot、混合／stale identity、
  fatal／stop、NaN/Inf/huge integer、dtype／autograd狀態及normal/-O。

這些結果只能支持「選定上游元件與原凍結公式在受測離線契約下相容」。沒有model、
optimizer、reward target、PUBLIC答案、Kaggle API、auth、training launch或provider mutation。
經審查的Git來源／測試／研究記錄保存由研究lead另行處理，不是provider execution。

## 5. source到admission的界線

Bridge讀取／hash的是5個固定公開本地source檔，並檢查相同宣告與完整64-slot結構。
容量採用凍結factory的vocab151936、context4096、prompt3072、generated1024；support≤27
來自actor；numeric gap取原plan。原始prefix hash可重算，但DFA support、state與實際
模型概率沒有在這層重新執行驗證。完整raw receipt digest把所有宣告綁在一起。

`BatchContext`中的training32、exclusions、record／panel／source／actor身份都是呼叫端
宣告；hash一致不等於真實來源。沒有讀到PUBLIC target不等於自動證明所有輸入來源無洩漏。
因此所有summary都明確標 `provenance_authenticated=False`、
`model_replay_verified=False`、`production_update_authorized=False`。

未來若在**獨立的新runtime successor**真正接線，最小驗收為：

1. 原 A/B/C 仍沿原 admission 執行並產生 audit；CPU companion 或尚未產生的 audit
   不構成其新增事前 gate。未來 AF3 模型 hook 才需要本節的獨立 successor 驗收。
2. 保留原RewardPanel／owned actor的真實train-only lineage、公開parent／ancestor／alias
   排除、exact record、sampling support、原始IDs、來源／adapter／tokenizer／prompt身份。
3. 在相同A與相同完整train-only原始batch上，把本地與上游loss作影子對照；全部replay gates
   過後才允許既有owner commit。影子診斷耗時完整計入新版本成本，不能隱藏在控制組外。
4. 驗證unchanged-model replay、nonforced gap、真正LoRA各target梯度／adapter delta、
   rollback與save/reload；維持批次更新與原成本限制。該步需local側正式來源封裝與審查，
   不是把本bridge的成功當作放行token。
5. 全A/B/C及full PUBLIC scorer仍依原順序與完整分母。B≤C時不能用上游名稱宣稱增益；
   B>A且B>C也只按既有條件進下一個unused-parent／family replication。

任何async／staleness／entropy／OPSM／模型或資料更動都必須另立假設及對照，不能在同一
DDIS標籤下偷偷帶入。這次實際套用的目的是可稽核component接點與可重跑差分驗證。

## 6. 授權與再散布

上游[LICENSE](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/LICENSE)
為Apache-2.0，保留著作權／license／attribution，修改時須標示。本次三個source檔未修改；
新增glue／tests另列，附完整license與IRIS-X自加NOTICE。上游該commit沒有root NOTICE。
不得把IRIS-X整體license誤當成取代這些元件條款；也沒有宣稱上游作者背書。

本次完整來源與blob/SHA256可見
[`source-manifest.json`](../../../tools/arc2_agent_factory3_bridge_20261014/source-manifest.json)。
獨立審查另見[獨立review](independent-review.md)。

## 7. Stage 1：完整 batch與逐軌跡續接

目標是讓已實際採用的 Agent Factory 3 元件具備可接續原 runtime 的**完整 batch
契約＋逐軌跡 shadow loss**接口，而不是直接把64條真實模型 graph 堆到記憶體。
新碼應使用獨立 successor 路徑與身分；原 run008、actor、math、plan、producer、
collector 與 scorer 保留原 bytes。不能 monkey-patch 原 frozen 模組或用新 identity 冒充舊版本。

AF3-0 的原 bridge 先驗證64個 declarations，再一次呼叫 upstream
`compute_unpacked`；它只接受 CPU replay tensors。本輪 O2 已完成完整 batch 驗證後
的逐軌跡 CPU reduction；尚待本地處理的是與真實模型 owner／device 的接點，
並非再證明同一個小 tensor 公式。

來源接點：
- [原 runtime 更新流程](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/runtime.py#L396-L496)：完整 batch、逐軌跡 replay／backward、全部 admission 後才 commit。
- [原 actor identity 與 support](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/actor.py)：原始 token、DFA、權重／cache／來源一致性。
- [目前 bridge](../../../tools/arc2_agent_factory3_bridge_20261014/bridge.py)、[實際上游來源 manifest](../../../tools/arc2_agent_factory3_bridge_20261014/source-manifest.json)、[CPU proof](../../../tools/arc2_agent_factory3_bridge_20261014/proof.py)。

### 離線實作與驗收契約

以下保留已交付離線工具的契約；完成範圍見[Stage 1 獨立審查](../stage1-independent-review.md)，
當前實驗狀態只見[進度頁](../DEVELOPMENT-PROGRESS.zh-TW.md)。

#### S1-O1：完整 batch 的非機密接線契約

第一個真實來源接點是**已存在的 training-only audit 檔**，不是 stage0 compact report。
`TERMINAL-VALIDATION.json` 沒有原始 trajectories，不能由它反推或補造。原
[`experiment_flow/flow.py`](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/experiment_flow/flow.py#L220-L246)
將 `{batch, summary, update, ...}` 保存為 `experiment/audit/sweep-N.json`，其中
`update.replays[]` 保留 `log_pi`／`log_mu`／`detached_DDIS_loss`；原
[`audit_checks.py`](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer/audit_checks.py#L201-L275)
已有逐軌跡對照責任。先做明確指定檔案＋獨立來源hash的離線 audit adapter，保存原拒絕／
缺失狀態；沒有真實檔案時只交 synthetic schema 測試。

stage0 單檔上限16MiB不能直接放寬；原證據規畫的單batch audit上界約88MiB，不代表
實際檔案都如此大。先核對實際size，超限明確拒絕；若確實需要較大輸入，另審有界reader
的大小／深度／JSON／no-follow／中斷cleanup設計，不能偷偷改既有安全上限。
只使用保存的 logp 可以重算loss及 `∂loss/∂logp`，無法重建模型graph、LoRA梯度或真實replay。
這個 audit-loss companion 使用獨立 opt-in 入口；既有 stage0 prepare／analyze 保持標準
函式庫與原介面，不暗中載入 PyTorch。目前輸出僅保留不含原始tokens／grids的緊湊
batch conformance與unknown／rejection分類，對照原 recorded `detached_DDIS_loss`。
只有宣告性資料時，仍明列 provenance 未驗證；不能改名成新的 collector 成功收據。

先列出 producer 欄位→bridge 欄位→owner 核對責任的逐項映射：固定32 parents／records、
batch0–3、每批8×8完整 slots、policy identity、generation epoch、actor／cache mode、
原始 prompt/generated IDs、位置、DFA support／states、behavior logp、reward provenance。
只能以 training-owned receipt 作將來真實來源；不能從 evaluator 答案或 PUBLIC outcome
補欄位。metadata 自洽不是 provenance authentication，沒有的證據保持 missing。

交付應是獨立 adapter 契約與 fabricated 非ARC fixtures。測試覆蓋錯版本、缺／重／亂序slot、
混合 cache／prompt、fatal／stop、retokenization、source drift、未知／非法reward與 zero-signal。
不新增登入、provider 操作、檔案搜尋或秘密資料讀取功能。

#### S1-O2：使用真正 upstream loss 的逐軌跡 reduction

完整 batch 必須先通過現有結構檢查，固定 advantage 與分母 `M×8×T_i`，然後逐軌跡
計算 upstream contribution；不得對單條 trajectory 重算 group baseline／M 或當成一個新batch。
本次 upstream bytes 與 license 保留，streaming 邏輯寫在新 glue。零advantage仍保留原 replay
診斷要求，整批 M=0 則不做 replay／loss／更新。

CPU 驗收：同一64-slot synthetic batch 比較 frozen local、目前 full upstream與新streaming
scalar／原始 logits gradients／metric weighting；不同長度、mixed counts、嚴格ratio邊界、
zero groups 均需通過。normal／`-O`、失敗／timeout／cleanup、graph釋放與禁止提前commit
測試分開列出。不得以 mock 成功聲稱真實 owner rollback 或模型梯度驗證。

#### S1-O5：本地模型接線的 shadow 規格與交接

產出 source-bound、預設不執行的接線規格；在本地另行審查的 successor 上，從**同一A、
同一完整原始 training batch、相同 unchanged-policy replay**比較本地與上游的 loss／
LoRA各target梯度。不能用額外抽樣、不同tokenization或不同模型副本掩蓋差異。

shadow 計算不是免費：新增 forward／backward、hash、Python、同步、記憶體、保存及失敗
成本全部記錄。若接進正式 B，其整段額外 wall 必須由 C 匹配，且仍受原整場12h與各
operation／batch期限限制。若作另立診斷，不可把它的成本或結果移植成既有 A/B/C 的證據。

此階段目前只準備接口、非模型 CPU 測試與本地交接，不在本環境載入Qwen、執行LoRA、
建立新GPU工作、提交Kaggle或呼叫本地executor。真正模型驗收仍需接收端的來源與材料。

### 本地模型證據的驗收契約

| 項目 | 已有 | 本地真實接線仍須提供 |
| --- | --- | --- |
| 來源與數學 | 固定 upstream／frozen local hashes、合成loss／logit-gradient parity | successor封裝與實際執行source一致，不能沿用舊admission |
| reward／資料 | 完整slot與排除宣告檢查 | authenticated train-only lineage、原records與排除、實際reward；無PUBLIC答案流入 |
| actor與replay | 原IDs／prefix／DFA宣告／version一致性 | 同原模型與adapter、真實DFA support、teacher-forcing causal alignment與cache實證 |
| 數值 | synthetic零差、strict bounds | 原nonforced max≤.20／p95≤.05／unclipped=1，以及每個LoRA tensor finite gradient、至少一個非零；不能只看scalar loss |
| 狀態與失敗 | CPU負例與結構拒絕 | 零更新前權重不變、完整batch才commit、真實rollback、save/reload、owner終止與完整receipt |
| 資源與結果 | 小CPU fixture | 單訓練GPU的peak memory／全B wall；最終4×L4另驗；原完整A/B/C與PUBLIC120／167評分 |

以上重申既有契約，不另加與研究問題無關的管理門檻。缺一項不能改寫為0分、已驗證或放行。
