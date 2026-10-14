# IRIS-X：RL 方法、數學差異與下一個可識別消融

研究日期：2026-10-14 UTC。核對基準：`cc14bd1a79aac1fe6135017c9e09d4834300675d`。

後續狀態：本文分析的是固定基準。新研究線另完成了真正 upstream
`TrainingSample`／`DDISLoss`／`MeanMetricState` 的離線 CPU bridge，見
[實際整合](../arc2-agent-factory3-20261014/integration.zh-TW.md)與[進度入口](README.md)。
下文「本地獨立表達」仍描述未修改的 frozen runtime，不再代表整條研究線沒有執行上游元件。

本文只做公開第一手文獻與既有來源碼研究。未改動 runtime、凍結檔案、門檻或實驗配置；未訓練模型、安裝套件、呼叫模型 API、登入供應商或發布執行版本。文中「已實作」只表示來源碼存在，不表示完整 Qwen14B GPU 更新、ARC-AGI-2 效益或四張 L4 推論已驗證。所有後續實驗均是新提案，不能直接寫回目前凍結 A/B/C。

## 1. 結論先行

1. 先完成目前 A/B/C 的可稽核實驗，不宜以換成 GRPO、PPO 或另一個框架來回應 loader／replay 失敗。當前 B 是 **group-centered、逐序列等權、原始 token 重播的 DDIS 硬遮罩 policy gradient**，沒有 advantage 標準差正規化、critic、reference KL 或 entropy bonus。
2. **目前可提交更新裡，DDIS 硬遮罩理應完全不啟動。** 這是依本地來源碼與門檻推導的條件式數學結論：同一批 rollout 到最後 commit 之前權重不變，非強制 token 必須通過 `|logπ−logμ| ≤ 0.20`、p95 ≤ 0.05、unclipped fraction = 1。其 ratio 落在約 `[0.819, 1.221]`，嚴格位於 `(0.8, 1.28)` 內。若 PPO 也採相同非對稱界線 `(0.8,1.28)`（或另已確認其 clipping 未啟動），且 advantage、normalizer、ratio 定義和其他項完全相同，DDIS 與 PPO 未截斷項的**梯度相同，scalar loss 不同**。標準對稱 ε=0.2 的 PPO 在 ratio>1.2、A>0 時仍可能截斷，不能直接宣稱等價。這不是外部論文的 ARC 成績，也不適用於任意 stale／多次更新版本。
3. 完整 G=8 組中，RLOO advantage 恰是目前 advantage 的 `8/7` 倍。只改 group mean 為 leave-one-out mean，通常只是梯度全域縮放，不能當作獨立的新推理機制；Adam、epsilon、gradient clipping 會使參數步長並非嚴格等比例。
4. 真正可改變目前更新方向的低整合成本因素是 **response-length weighting、跨題 reward weighting、正負樣本的利用方式**。但全零或全一組沒有相對信號，先換 objective 並不能憑空創造成功樣本。
5. 已找到直接 ARC-AGI-2 的 RL 文獻 Enigmata，故不能寫成「RL 完全沒有 ARC-2 證據」；但其模型、資料與算量無法外推到本地最多四次 LoRA 更新。GRPO／DAPO／Dr. GRPO／RLOO 的原始方法實驗本身，也不提供本地配置的直接 ARC-2 驗證。詳細數字與限制見第6節。[Enigmata](https://arxiv.org/html/2505.19914v2)

## 2. 目前凍結版本到底做了甚麼

### 2.1 已實作的實驗配置

- A：同一 session 的 Qwen3-14B、BF16 frozen base／FP32 rank-8 LoRA，SFT256，真實儲存、重載並核對。
- B：從 A 開始；32 個固定 training parents，每個採 identity transform、最後一個原始 demonstration 留一法查詢，8 次隨機樣本。按原順序分成最多四個**互不重疊的 64-slot batch**，每批 8 parents；完整批次最多 commit 一次，總計最多四次。批次內政策不變，後續批次使用上一個已確認政策。不是每批重新跑全部 32 parents，也不是最多四遍 256-sample sweep。
- B 採 temperature=1、top-p=1、原生 grid DFA 下完整合法 support；RL LR=1e-6。
- C：另從 A 開始，fresh AdamW、LR=2e-4、constant schedule，延續 SFT。對齊 B **整段額外 model-phase 的同步 wall time**，包含 setup、rollout、reward、replay、hash、Python、失敗／rollback、save／reload／verify；不可 idle padding。容許差為 `min(120, max(5, 0.05×W_B))` 秒。
- 主比較沒有 TTT。順序為 A/B/C dev16 → 凍結所選 arm → 該 arm 的 PUBLIC 預測 → A/B/C reused held32 預測 → 關閉模型 → held 與原始 PUBLIC scorer。PUBLIC 保留 120 tasks／167 queries 的完整分母。
- 這是 **intervention-package comparison**，不是只隔離 objective 的因果比較：B/C 的資料流程、LR、更新數與計算構成都不同。保留這個實用成本對照是合理的，但論述須相符。

本地依據：[plan.py](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/plan.py)、[MEASURED-POLICY.json](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/design/MEASURED-POLICY.json)、[目前研究審查](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/native-continuation-20261013/independent-research-review.md)。舊 SFT64／full256 protocol review 是歷史版本，不能取代上述配置。

### 2.2 精確 objective

以下公式由本地 `reviewed/rl_math.py:68–160` 與 `rl_session/runtime.py:396–496` 核對，不是把 GRPO 論文公式套在專案名稱上。

令 g 為 parent group，i 為該組 rollout，t 為生成的 assistant token；Tᵢ 是該回覆的原始生成 token 長度，Gg 是 eligible group size。完整 production batch 中 Gg=8。M 是本批 mixed groups 數。

- `Rᵢ ∈ {0,1}`：EOS 結束、可解碼、整個 grid 與該 training LOO target 完全相等才是 1。
- `Aᵢ = stopgrad(Rᵢ − mean_g R)`，不除 group std。
- `ρᵢₜ = exp(clamp(log πθ(aᵢₜ|sᵢₜ) − log μ(aᵢₜ|sᵢₜ), −20, 20))`。
- `mᵢₜ = 1[eligible ∧ assistant_generated ∧ 0.8 < ρᵢₜ < 1.28]`。
- `L = −Σg Σi Σt [mᵢₜ × stopgrad(ρᵢₜ) × Aᵢ × log πθ(aᵢₜ|sᵢₜ)] / [max(1,M) × Gg × Tᵢ]`。

這裡的 π 和 μ 都是 **相同 DFA support 上重新正規化的機率**，不是 full-vocabulary likelihood。模型仍保留原詞表與 head，但 policy loss 在合法 grid token 分布內計算。不能拿 full-vocab NLL 當 behavior denominator，也不能把它描述成訓練自然語言 CoT、工具呼叫或 program synthesis。

`runtime.py` 逐軌跡做等價 micro-contribution，以避免保留整個 batch 的計算圖；混合組才 backward，但只要批次有 mixed group，所有 admitted trajectories 都做 unchanged-policy replay admission。全部通過後才 commit。任何 slot missing／infrastructure-excluded 都不能提交該部分 batch；之前完整 batch 的更新與實體成本仍保留。

AdamW 實際是 betas=(0.9,0.999)、eps=1e-8、weight_decay=0、foreach=False；commit 要求每個 adapter tensor 有 finite gradient、至少一個非零 gradient，並做 max-norm=1 clipping。四次 update 的上限是 LoRA optimizer commit，不是四個 backward call。

本地依據：[數學模組](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/reviewed/rl_math.py)、[runtime.py](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/runtime.py)、[actor.py](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/actor.py)、[training reward/data](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/data.py)。

### 2.3 DDIS 名稱與 upstream 邊界

DDIS 的正式展開是 **Direct Double-sided Importance Sampling**。GLM-5 §4.1.2 描述以 rollout log-probability 作 denominator、對 ratio 雙側硬遮罩；agent-factory-3 固定 commit 的 loss 使用 `ratio.detach() × advantage × logp`，兩端界線也採嚴格不等式。其作者文章示意式寫成含端點區間，實作的 strict boundary 才是這次程式比較依據。[GLM-5 原始報告](https://arxiv.org/html/2602.15763v1)、[agent-factory-3 固定版 loss](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/src/agent_factory_3/trainer/losses/ddis_loss.py)

本地只借用這個 loss 機制並獨立表達；不是 agent-factory-3 的完整移植。上游可有 asynchronous pipeline、staleness filtering、OPSM、entropy token mask、MoE routing replay、GPT-OSS MXFP4 與 SGLang。這些都不能算成本地已實作。上游 examples 是 Wordle／Minesweeper；其結果不構成 ARC-AGI-2 證據。[上游固定版 README](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/README.md)

注意 GLM-5 報告的「ARC benchmarks」在該文意指 Agentic、Reasoning、Coding，不能僅憑這個縮寫誤稱 ARC-AGI-2 成績。

## 3. 與主要 RL 方法逐項比較

### 3.1 REINFORCE：最接近的基本估計器

經典 sequence-return 形式是 `E[(R−b) Σt ∇logπ(aₜ|sₜ)]`；action-independent baseline 可降變異而不改變該期望梯度。它本身不要求 critic、ratio clipping、reference KL 或 entropy bonus。這是估計器族，不能把某一 RLHF 實作的 KL 全都歸成 REINFORCE 的必要條件。[Williams 原始論文](https://link.springer.com/article/10.1007/BF00992696)、[LLM REINFORCE/RLOO 原文 §§2–3](https://arxiv.org/html/2402.14740v1)

本地在理想 μ=π 時，其更新是 group-baselined、長度加權的 REINFORCE-style surrogate。**不能直接稱為無偏的完整 sequence-return REINFORCE**：組平均包含自身樣本、每條有 action-dependent 的 1/Tᵢ、且只以隨機出現的 M 個 mixed groups 正規化。這是本地公式的分析，不代表程式錯誤；只是必須精確描述欲最佳化的 weighting。

### 3.2 RLOO：不是新的免費信號

RLOO 用同 prompt 其餘 G−1 個獨立樣本的平均 reward 作 baseline：

`Aᵢᴸᴼᴼ = Rᵢ − (Σj≠i Rⱼ)/(G−1) = [G/(G−1)] × (Rᵢ−mean_g R)`。

因此目前完整 G=8 時，若保留其他一切，其 loss gradient 只是 8/7 倍。包含自身的 group-mean estimator，在理想 iid、on-policy、sequence-sum 與固定分母條件下有 `(G−1)/G` 的縮小因子；RLOO 修正這一點。前述條件不會自動消除本地 1/Tᵢ 與 mixed-group selection 的其他 weighting。

RLOO 原始 LLM 研究針對 TL;DR、Helpful/Harmless 等 preference alignment，含其 RLHF reward/KL 設計，沒有直接 ARC-2 驗證。若要在本地提案實作，仍須說明採哪個 reward、是否 KL、sequence-sum 或 token-average，而非只有 `algorithm=RLOO`。[原始 RLOO 論文](https://arxiv.org/html/2402.14740v1)

### 3.3 GRPO／DeepSeekMath

DeepSeekMath 的 outcome GRPO 使用 `(Rᵢ−mean_g R)/std_g(R)`，以 PPO-style clipped ratio surrogate、每條回覆 token 平均後再 group 平均，另加 reference-policy KL；不需 learned critic。原文另有 process-supervision 版本，並非所有 token 只接同一 outcome reward。其直接實驗是數學推理，不能作為 ARC-2 或本地離線 14B 的實證。[DeepSeekMath §4.1](https://arxiv.org/html/2402.03300v3)

本地已實作的是 group mean，不是 std normalization；也沒有 reference forward。以 binary reward 計，std normalization 會按題目成功比例重新加權，不能當作單純數值穩定化。以 population std 示意：G=8、只有 1 成功時，std≈0.331，該組 advantage 被放大約 3.02 倍；4 成功時放大 2 倍。sample std／epsilon 的選擇還會改變實際縮放，須另外凍結。

這項小改動確實能改變多組合併後的方向；但將稀少成功組拉高權重是否幫助 ARC transfer，仍是新假設。全零／全一時 centered advantage 仍為零，除以 epsilon 不能產生正確例子。

### 3.4 PPO clip 與 DDIS hard mask 的差異

PPO 的 maximize surrogate 是 `min(ρA, clip(ρ,1−εlow,1+εhigh)A)`；典型 actor-critic PPO 另估 value/GAE，但 PPO clipped actor surrogate 可以搭配別種 advantage，不能說只要用 clip 就必須另載完整 critic。[PPO 原始論文](https://arxiv.org/abs/1707.06347)、[DeepSeekMath](https://arxiv.org/html/2402.03300v3)

在界線之外，二者差異可直接算出：

| ratio／advantage | PPO 對 logπ 的 maximize 梯度 | 本地 DDIS maximize 梯度 |
|---|---:|---:|
| ρ<0.8、A>0 | ρA，保留回拉方向 | 0 |
| ρ<0.8、A<0 | 0 | 0 |
| 0.8<ρ<1.28 | ρA | ρA |
| ρ>1.28、A>0 | 0 | 0 |
| ρ>1.28、A<0 | ρA，保留回拉方向 | 0 |

這個比較假設 PPO 也用同一組 asymmetric bounds；原始 PPO 常用對稱 ε。若 ε=0.2，其上界1.2低於本地admission容許的1.221，因此 ratio在(1.2,1.221]且A>0時，標準PPO會截斷，本地DDIS仍保留梯度。邊界點導數／subgradient需另訂實作測試。

**本地特有的推導：** production gate 的 `exp(−0.2)=0.818730753`、`exp(0.2)=1.221402758` 已保證上述中間一列，且 `minimum_unclipped_fraction=1` 再次檢查。forced tokens 的 masked probability=1、logp=0、梯度=0。故通過 gate、沿用同 advantage／normalizer，且PPO採相同非對稱界線或另已確認未截斷的一次更新，從 DDIS 換成未截斷 PPO 不應改變梯度方向或大小；不值得先花 GPU 當品質 ablation。DDIS 的 detach 是重要的：若錯誤保留 `ρ×logπ` 的 ratio 梯度，會額外產生 `logπ+1` 因子，並非 PPO 梯度。

本地核對位置：`actor.py:291–349`、`runtime.py:427–486`、`plan.py:173–176`。這僅是通過目前精確 gates 的條件式推論，不能解讀成已觀測「所有 GPU ratio 都相等」；完整模型數值證據仍待真實執行。

### 3.5 Dr. GRPO：已經做一半，另一半才有新差異

Dr. GRPO 研究指出 GRPO 的 per-response 1/Tᵢ 和 per-group std 會引入長度／難度 weighting；其主要修改移除 std，將回覆長度分母改為固定常數，例如 maximum generation length。原論文的最小 reasoning 設定不加 reference KL。實證是 MATH／AIME 等，不是 ARC-2。[Dr. GRPO §§3.1–3.2](https://arxiv.org/html/2503.20783v1)、[官方程式庫](https://github.com/sail-sg/understand-r1-zero)

本地早已沒有 std，但仍有 1/Tᵢ，因此不是完整 Dr. GRPO。在 direct-grid 任務，長度通常反映 grid 大小／格式而非長 CoT；固定分母可能加重較大 grid 的 token 貢獻，未必符合按 query 計分的公平 weighting。可研究「只改長度分母」，但應報大小分層、正負回覆長度、梯度 norm 與 adapter step norm，不能把長 CoT 論文的偏差解讀直接照搬為本地改善保證。

### 3.6 DAPO：不等於本地 0.28 上界

DAPO 保留 standardized group advantage 與 PPO min-clip，分開上下 ε；加入 dynamic sampling、跨樣本 token-level reduction，以及 overlong filtering／reward shaping，並去除 reference KL。原文基本正誤 reward 是 +1/−1，本地是 1/0；在無額外 shaping 的 std-normalized advantage 下，這個正向仿射轉換會抵消，但在本地未除 std 的 objective 會改變尺度。原報告用 Qwen2.5-32B，AIME2024 avg@32 達 50；不是 ARC-2。[DAPO 原文 §§2–4](https://arxiv.org/html/2503.14476v2)、[官方 repo](https://github.com/BytedTsinghua-SIA/DAPO)

本地 `(0.8,1.28)` 是雙側 hard-mask，不會因此變成 DAPO。現有零變異組不更新、以 mixed groups 當分母，也不等於「持續多採樣補足 mixed batch」：目前明確禁止 reward-dependent replacement／resampling。DAPO 的跨 token 分母與 Dr. GRPO 固定常數分母也不相同，前者仍隨該批總長度變動。

若未來研究 dynamic sampling，必須新訂**總嘗試上限與總 physical wall 上限**，保留被丟棄的全零／全一組；不能只用 accepted samples 計算效率。否則在稀疏成功率下會消耗更多 rollout，卻把它誤記成「每個 update 更有效率」。

### 3.7 其他 critic-free 方法：可研究，但優先度較低

- **ReMax**：每個 prompt 另產 greedy completion，以其 reward 作 baseline，再對 stochastic completion 做 REINFORCE。少了 critic，但增加至少一條 greedy rollout；在 binary exact reward、greedy/stochastic 同為零時仍無信號。原文的速度／記憶體優勢來自其 RLHF 測試，不是本機時間保證。[ReMax](https://arxiv.org/html/2310.10505v3)
- **REINFORCE++／baseline variant**：將 advantage 的尺度處理放到 global batch，搭配 PPO clip；baseline variant 使用 group centering，KL 設計亦有別於原始 GRPO。不要把 group std、global std 與無 std 混寫。同批全域縮放主要改步長，跨題 weighting 則視 centering／return 定義而變；64 slots、少數 mixed groups 下須注意 batch 統計不穩。[REINFORCE++ v2](https://arxiv.org/html/2501.03262v2)
- **BOTS 等 curriculum／task selection**：這是選題機制，不是 loss 的替代品。其原文雖使用 ARC-AGI-2 public training data，evaluation 段列的是 ARC-AGI；不能把其 ARCAGI 表格直接當 ARC-2 result。實驗使用 8×A100、GRPO、16 rollouts／prompt，與當前固定 disjoint32 parents 不同；若另做研究，先設 training-only selection 與未使用 family confirmation。[BOTS §§D.1–D.3、G.10](https://arxiv.org/html/2510.26374v3)

## 4. KL、entropy、importance mismatch：不能互相代替

- **reference KL**：約束目前政策相對固定 A/reference。需要有明確 reference-policy 機率、方向、估計器與係數。可用同 base 切換 adapter 計算，不一定需常駐第二個完整模型，但 reference forward／切換與數值 admission 的成本必須算入。現有 code 沒有這項。
- **behavior mismatch**：`logπ−logμ` 比較 learner replay 與真正採樣政策。這不是 reference KL。單條樣本的 mean log-ratio 也不能當成已精確量到 KL divergence。ratio correction 不能修補錯 prefix、不同 mask、retokenization 或偷偷換 tokenizer。
- **完整 off-policy 無偏性**：單 token ratio 並不一般地等價於整條 trajectory 的 importance product，也沒有自動修正改變後的 prefix/state distribution。加上 hard mask 後是帶偏差的 surrogate。GLM-5 也把非同步做法描述為接受受控 off-policy bias。本地目前採同步、單版本、單次 commit，不能拿上游 asynchronous 成功來解除這些 guards。[GLM-5 §4.1.2](https://arxiv.org/html/2602.15763v1)
- **entropy**：現有 actor 沒有儲存完整 support entropy，也沒有 entropy bonus。可由選中 token 的 `−logμ` 求 sampled surprisal 統計，但那不是每個 state 的完整 categorical entropy。新增診斷需新 schema／版本；新增 entropy bonus 會改 objective。grid grammar 下 forced tokens entropy=0，平均時須另報 nonforced。
- **entropy mask ≠ entropy bonus**：上游可只學高 entropy tokens；這是梯度選擇，與鼓勵政策保持多樣性的 bonus 不同。本地兩者都未實作。多次 rollout 相同、grid oracle coverage 下跌時才值得另提探索實驗；不能為使曲線漂亮而直接調 sampling temperature 或加入新 reward。

## 5. 非 RL 對照：比再加入一套 critic 更容易回答問題

### 5.1 目前 C：已實作，應保留

C 回答「同樣額外 wall time 拿去繼續 SFT，是否更值得」。它不是 matched-data／matched-LR 的單一 objective 對照，所以 B>C 也不能單獨證明 DDIS 數學比 CE 優越。

### 5.2 新提案：rejection sampling／verified self-training

RAFT 是 reward-ranked filtering 後做 supervised fine-tuning 的原始代表；本地可以研究更簡單的「僅保留 exact reward=1 的已驗證生成，再做 CE」，不必採 learned reward model，也不必安裝 RAFT framework。[RAFT 原始論文](https://arxiv.org/html/2304.06767v3)

這個對照能測正樣本模仿是否已足夠、負樣本抑制是否有額外價值。但有三個限制：

1. 若 G=8 全零，沒有可訓練 positive corpus；不能將失敗回覆中的看似合理片段當正解。
2. 在本地**直接 grid exact-match**設定，每個成功樣本的語意答案就是既有 training target；自訓練主要改變成功題目的加權與模型產生的 tokenization，而非憑空增加新規則或新標籤。若要學 program／reasoning traces，須另立輸出、驗證與資料隔離契約。
3. 採樣／驗證／失敗／去重／存檔的成本仍算到 self-training arm。不可只比較 CE backward 耗時，宣稱它省掉 rollout。全部 accepted duplicates、對 parent 的 weight 與 token-length reduction 須預先固定。

### 5.3 建議分清兩種新對照

- **機制診斷（最小）**：從同一 A、同一完整 train-only batch 出發，分別算現有 signed centered loss 與 positive-only loss，先比較可稽核梯度方向／尺度。若未授權模型 backward，只可先對保留 logp／reward 做 scalar weighting 分析，不能把它稱為 model-gradient proof。
- **品質實驗（之後另批准）**：相同 A、fresh optimizer、事先固定 LR／norm 設定，各做一次 update，再用同一已凍結 train-derived dev set 比較；不得用 PUBLIC 結果選法。共用第一批資料是因為兩 arm 都從 A 開始；一旦各自更新，之後 rollout 要各自重採，不能把 stale pool 當 on-policy。
- 若重點是「知道哪些題還做不好」而不是自生成的 tokenization，可加 **同 reward32 prompts 的已知 target CE**。這比 generic C 更能隔離資料選擇，但它是新增控制，不是重新命名既有 C。

## 6. 直接 ARC-AGI-2 證據的範圍

**Enigmata 是這次查到可明確歸為直接 ARC-2 的 RL 結果。** Qwen2.5-32B-Instruct → RFT → VC-PPO；表3的 ARC-2 是 0.0、0.0、0.6，ARC-1 是 6.0、8.4、32.8。除 AIME 外以四次評估平均報分；不是 IRIS-X 的固定167-query micro pass@2。訓練包含 ARC-1/2 public training 與其他 puzzles/math，cold start RFT 使用 DeepSeek-R1 候選。其 VC-PPO 有 value pretraining、actor/critic 不同 GAE λ、無 KL。正文稱370 steps，附錄稱425，不能自行消解成一個「確定步數」。這支持有可驗證 RL 研究，並不支持重型 PPO 在單卡14B比目前方案更好。[原文 §§4–5、附錄B–C](https://arxiv.org/html/2505.19914v2)

這次檢索沒有找到能乾淨識別「相同離線 Qwen14B、相同資料與成本下，GRPO/RLOO/PPO/DDIS 誰在 ARC-2 勝出」的公開原始實驗。這是檢索範圍內的未找到，並非聲稱此類研究絕不存在。不得把以下混成直接證據：數學 benchmark、RLHF win-rate、Wordle／Minesweeper、ARC-1、使用 ARC-2 training data 但不報 ARC-2 eval，或 GLM 論文的 Agentic/Reasoning/Coding 縮寫。

## 7. 必須保留的 admission／驗證清單

### A. Training reward 與隔離

- 凍結 train32/dev16/held32 分割、PUBLIC parent／ancestor／alias exclusions、原始 task hash、transform、固定 LOO fold 與 record hash。
- reward target 只在 RewardPanel 的 evaluator 端；actor 只收 permitted demonstrations 和 query input。任何 public test output、答案衍生排序／難度／選題訊號不可流入更新。
- 記錄同 session SFT 是否看過該 exact reward record；另做 ancestor／augmentation 語意 lineage，不把「actor 當前 prompt 看不到最後 output」誤稱「模型從未看過」。
- 正常模型 invalid／non-EOS 長度截斷是 eligible reward=0；infrastructure timeout、OOM、provenance failure、未抵達 slot 是 reward=None／未知，不是假負樣本。
- parent-level reward、有效樣本數、全零／全一／mixed、training pass@8 均保留完整分母。不能用 missing rows 組出較漂亮的 group mean。

### B. 原始 token 與數值 replay

- 保留原始 prompt_ids／generated_ids，禁止 text round-trip 重分詞；每個位置對齊 causal prefix、DFA state、support、sampling temperature、top-p、EOS 與 behavior logμ。
- 同一 batch 僅一 actor version，same base／adapter／tokenizer／prompt template／source identity；禁止混合 stale trajectory。
- sample 可有 KV cache；replay 必須正確 position_ids／cache_position、no KV cache、autograd on、train mode以啟用 checkpointing，同時 dropout=0。這些不是「train/eval 名稱相同」就能推定一致。
- unchanged-weight 計算非強制 token max／p95 abs logprob gap、ratio coverage，維持精確 source-bound gates；不可看見結果後放寬容差。出現差異先定位 backend/cache/precision/prefix，而非直接用大 clipping interval 掩蓋。
- 當 batch 完全零信號，現有 runtime 可不 replay。故「zero-signal batch 完成」不能聲稱「該 batch 的 model replay parity 已證明」。

### C. 真實 gradient／更新

- prompt、padding、tool observation 不進 policy loss；model-generated assistant tokens 使用原位置。當前 grid-only 路徑沒有 tool transcript，不因註解提到 tool mask 就宣稱支援 agentic training。
- `log_mu` 與 reward／advantage 必須 detached；π 保留 autograd。測兩端 boundary、正負 advantage、zero reward、singleton support、空／非法 mask、NaN/Inf、超出 precision range。
- 現有 `effective_tokens` 包含 zero-advantage；`contributing_tokens` 只檢查 advantage 非零，仍可包含 forced tokens。**兩者都不等於真正有資訊的 policy-gradient token 數**；至少另交叉統計 mixed ∩ nonforced ∩ unclipped，並檢查梯度本身。
- 現有 commit 只要求所有 adapter gradients finite 且任一非零；不能據此宣稱每個 LoRA target family 都有非零信號。建議報每層／target family 的 gradient norm、clip 前後 norm、adapter delta、Adam finite state、save/reload identity。
- 批次各軌跡 backward 可先累積，但 ALL replay gates 過後才更新；任何未完成／數值失敗須清梯度並保留正確 rollback 邊界。rollback 不重設實體採樣／計算成本。

### D. 真實 physical cost 與部署

- 分開 planned／dispatched／eligible／not-reached／excluded／replayed／backward／committed，並保存每次失敗、取消與 rollback 的成本。
- 報 whole B/C wall、rollout latency／tokens、replay+backward、persistence、peak allocated／reserved、host memory與磁碟；不能把 nested ledger event 全部直接相加造成重算。
- 一張 RTX PRO 6000 訓練成功，不代表四張 L4 推論成功；4×24GB 不自動成為單卡96GB。依固定原 checkpoint，另驗證分片／量化／offload 的 accuracy、kernel、memory 與速度，不能把研究時換 precision 的結果算成原模型重現。
- critic-free 少一個 learned value component，但 rollout 可能仍占主要時間。reference KL 加 forward、ReMax 加 greedy、dynamic sampling 加 rejected rollout、PPO 加 value work及通常多輪更新，都要算完整成本。
- 目前最多四批且 B phase有7200s上限；「256 planned」不是「256必定完成」。保護 PUBLIC／closure reserves，不能為了補足信號擠掉後段評估。

## 8. 失敗類別 → 最小下一步（全部為新提案）

| 觀測 | 可下的結論 | 不改目前凍結比較的下一步 |
|---|---|---|
| loader／source／process admission 失敗 | 尚未測到 RL 科學假說 | 修好執行門檻、重現精確 provenance；不換 objective |
| incomplete audit／missing logμ／prefix不符 | 未知或不可用訓練證據 | 停止該 batch；保留前面已提交 B；修完整性，不能補成 reward=0 |
| 全零且完整 | 此政策／題目／預算沒有成功訊號 | 該批不更新；只有整個B從未commit時B才等於A，否則保留先前B。後續先作train-only coverage／資料/表示檢查，必要時另訂verified SFT或curriculum |
| 全一且完整 | 該 training reward 已飽和 | 原 batch no-update；另次預先選更有挑戰的 train-only folds／families，不在目前跑到一半換題 |
| 有 mixed，但非強制 token 幾乎沒有／全零 grad | 相對 reward未轉成有用梯度 | 檢查 grammar、mask、detach、梯度連通；不是放寬 admission |
| replay gate失敗 | learner概率與行為概率不可信或成本不可行 | cache／position／precision／backend診斷；保持no-update |
| mixed、replay、梯度均通過，B無轉移 | 此低劑量介入沒有測到改善 | 完成 C；先判斷步長、長度／題型 weighting、coverage，而非宣稱所有RL無效 |
| B>A但C≥B | 暫無超過額外SFT的實用優勢 | 保留較簡單控制；若仍研究，做 matched-data positive-only vs signed 的單步比較 |
| B>A且B>C | 小型package-level正訊號 | 新凍結unused parents/families replication；不拿reused held32當全新確認 |
| token/adapter變化顯著但coverage下降 | 可能集中機率而削弱多樣性 | 同預算pass@1/2與candidate coverage分開報；先做診斷，再提entropy/KL或採樣新版本 |

## 9. 整合成本與排序

下列為工程相對判斷，不是測得工時或成功率；任何實作都需新 source identity、CPU正反例及獨立review。

| 候選 | 相對整合成本 | 最早合理觸發條件 | 優先度 |
|---|---|---|---|
| 保留目前DDIS＋補齊有效信號解讀 | 最低；先分析現有receipts | 第一個完整批次可取得 | 現在 |
| RLOO group baseline | 低，但G8主要是8/7縮放 | 研究baseline無偏性／尺度而非品質名稱競賽 | 低 |
| DDIS→PPO min-clip | loss低；多輪/stale protocol高 | 另行允許真正多次更新且確實有ratio出界 | 相同bounds且未clip的一次更新無新增差異；標準ε=.2需另檢查 |
| 僅修改固定長度分母（Dr.-inspired） | 低至中；改更新weighting與admission測試 | mixed足夠，且梯度明顯受Tᵢ/大小分層支配 | 第一梯隊備選 |
| 僅加入group std | 低；需固定std定義、epsilon與zero處理 | mixed組成功率差異大，想隔離題目weighting | 第二梯隊 |
| 同pool positive-only/self-training | 中；新分支／CE mask／成本與資料freeze | 有足夠verified positives，且需要拆解正負樣本效益 | 第一梯隊備選 |
| ReMax | 中；額外greedy、baseline receipts | 採樣昂貴且已有證據greedy baseline能提供不同信號 | 後置 |
| reference KL／entropy bonus | 中；新增機率或entropy統計、係數與成本 | 真有政策崩塌／coverage流失，且有足夠steps研究 | 後置 |
| DAPO dynamic sampling／BOTS | 高；改選題與完整成本帳 | 大量零信號已確認，且另有足夠training pool與研究預算 | 新protocol |
| full actor-critic PPO／VC-PPO | 高；value資料/模型/狀態/GAE/多輪更新 | 有理由相信token credit assignment是瓶頸，先證實資源可行 | 最後 |

**最小下一個品質消融的建議：** 先完成原 A/B/C；若已有完整 mixed/replay/gradient 證據而 B 的優勢不清，優先預先凍結一次「同 A、同第一批原始 trajectories、同 optimizer recipe與LR、signed centered vs verified positive-only」比較，完整保留成本及train-derived dev分母。若主要觀測是 length-weighting 明顯主導，改採只換 1/Tᵢ 為固定常數的比較。兩者擇一，不在同一輪同時改std、KL、entropy、採樣、模型與資料。

在這之前，最有價值的是區分「沒有成功樣本」、「有成功但未通過數值／完整性」、「真有更新但沒有轉移」；這三種結果對下一步的含義完全不同。

## 10. 第一手資料與查核限制

本次 live web 閱讀日期均為2026-10-14 UTC。正文連結均為原始論文、出版頁或作者官方repo；沒有用第三方摘要當作數學或成績證據。

- DeepSeekMath／GRPO：arXiv 2402.03300v3，§4.1與appendix。
- REINFORCE：Williams 1992出版頁；LLM具體估計器另核對RLOO原文§2。
- RLOO：arXiv 2402.14740v1，§§2–3。
- PPO：arXiv 1707.06347；相關actor公式也交叉核對DeepSeekMath與RLOO原文。
- DAPO：arXiv 2503.14476v2，§§2–4；官方repo BytedTsinghua-SIA/DAPO。
- Dr. GRPO：arXiv 2503.20783v1，§3；官方repo sail-sg/understand-r1-zero。
- DDIS：GLM-5 arXiv 2602.15763v1，§4.1.2；agent-factory-3固定commit `a1836decb836cd52cf2b27f5022f6838cee75df3`，`ddis_loss.py` blob `28afd41a146e1bc2c178f50c0b68eb5d2fa7fdfb`。
- ReMax：arXiv 2310.10505v3；REINFORCE++：arXiv 2501.03262v2。
- RAFT：arXiv 2304.06767v3；Enigmata：arXiv 2505.19914v2；BOTS：arXiv 2510.26374v3。

上游程式只作固定版本的來源核對，未安裝或執行；BOTS的引用以作者arXiv v3為準。本文沒有讀取PUBLIC evaluator答案本體，也未產生新accuracy。
