# agent-factory-3：實際元件套用與既有決策條件

查核日：2026-10-14 UTC。上游固定 commit：
`a1836decb836cd52cf2b27f5022f6838cee75df3`；截至查核，GitHub 最近提交仍是
該版本（2026-05-11T14:44:26Z）。本地凍結比較基準仍為
`cc14bd1a79aac1fe6135017c9e09d4834300675d`。新增工作只位於研究支線的
`tools/arc2_agent_factory3_bridge_20261014` 與本目錄。

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

1. 先完成目前stage0與原A/B/C，不以loader／replay失敗為理由換演算法。
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
[`source-manifest.json`](../../tools/arc2_agent_factory3_bridge_20261014/source-manifest.json)。
獨立審查另見[獨立review](independent-review.md)。
