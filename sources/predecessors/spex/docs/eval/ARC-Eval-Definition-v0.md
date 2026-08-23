# ARC Evaluation Definition v0

**版本：** v0.1  
**狀態：** Draft for implementation  
**日期：** 2026-07-31  
**適用範圍：** ARC-AGI-1 → ARC-AGI-2 → ARC-AGI-3  
**上位文件：** `Problem Definition v1.md`  
**證據依據：** `Evidence Base v1.1`、`Evidence Adjudication v1`  
**文件角色：** 定義首個 ARC evaluation program 的研究目的、評估單位、資料邊界、指標、比較規則、階段門檻與 SOTA claim 規則。

---

## 1. Executive decision

本專案的第一個 evaluation domain 定為 **ARC benchmark series**，執行順序為：

1. **ARC-AGI-1：** 建立可重建、可歸因、成本可見的靜態抽象推理基線。
2. **ARC-AGI-2：** 驗證方法能否承受更深、多步、較高複雜度的靜態推理，而非只適配 ARC-AGI-1。
3. **ARC-AGI-3：** 在互動式未知環境中，同時進行受控 scientific evaluation 與 competition SOTA engineering。

此順序不是「三個 benchmark 測量完全相同能力」的假設，而是依序增加：

- 任務複雜度；
- 測試時適應需求；
- system scaffold 的重要性；
- interaction、memory、exploration、world modeling 與 planning 的需求；
- model-level 與 system-level attribution 的難度。

本文件允許追求 ARC-AGI-3 SOTA，但所有結果必須明確區分：

- **模型能力結果**；
- **完整系統結果**；
- **競賽配置結果**；
- **一般化或 AGI 相關主張**。

---

## 2. Alignment with the project problem definition

ARC evaluation program 用來檢驗下列原問題，而不是取代原問題：

1. specialization 相對同一 backbone 是否產生 recurring target-task gain；
2. model-level gain 與 system-level gain 的來源能否拆分；
3. 增益是否只在單一 benchmark 或已見 task family 成立；
4. inference compute、search、memory、tools、retry policy 與 environment access 是否主導 ranking；
5. 在 ARC-AGI-1、2、3 的版本遷移下，優勢是否保留；
6. SOTA configuration 是否代表 bounded system superiority，而非 specialized weights alone。

ARC-only 結果**不得**單獨支持跨領域 specialization scaling law、broad professional capability 或一般 AGI 結論。ARC 系列在本專案中是第一個受控案例域。

---

## 3. Program objectives

### 3.1 Scientific objective

> 在版本固定、資源可見且比較單位對稱的條件下，測量 ARC specialization 的增益、成本、組件歸因、跨版本 transfer 與持續性。

### 3.2 Engineering objective

> 建立可逐步擴展至 ARC-AGI-3 competition 的 solver／agent platform，最終取得當期有效規則下的最高可驗證 private-evaluation score。

### 3.3 Success is dual, not singular

每個版本維護兩種成功狀態：

- **Research-qualified：** 評估與 attribution 已達到可解釋標準，允許進入下一版本研究。
- **Benchmark-complete：** 達到 benchmark 官方 solved／grand-prize threshold，且由 private 或 semi-private evaluation 支持。

公開資料上的高分只能標為 `public-benchmark result`；除非有 private／semi-private 驗證，不得標為 verified benchmark completion。

---

## 4. Unit-of-analysis taxonomy

每個 run 必須指定一種主要 evaluation unit。

| Unit ID | Unit | 定義 | 可支持的命題 |
|---|---|---|---|
| `G` | Generalist baseline | 未針對 ARC 做同等專門化的 model 或 system configuration | 當期未專門化基線 |
| `M` | Model specialist | 主要介入發生於 weights，例如 continued training、fine-tuning、LoRA、RL、test-time parameter update | same-backbone model-level gain |
| `S` | System specialist | weights 不變；主要介入為 prompt、DSL、program search、memory、world model、tool、verifier、routing、agent scaffold | fixed-backbone system gain |
| `H` | Hybrid specialist | weights 與 system stack 均專門化，且無法乾淨拆分 | configuration-level outcome |
| `N` | Narrow/formal solver | 固定 DSL、手工 primitive、exact verifier 或受限搜尋空間中的 solver | 該窄問題空間內的 solver superiority |

任何 superiority claim 必須保持 unit 對稱。若 `H` 或 `S` 擊敗裸模型 `G`，只能稱為完整 configuration 優勢，不能歸因於 weights。

---

## 5. Required evaluation modes

### 5.1 Science Mode

用途：component attribution、same-backbone comparison、cost-quality curve、generalization。

必須固定或明確掃描：

- exact model snapshot；
- prompt／policy version；
- context window；
- attempts；
- token budget；
- model-call budget；
- search width／depth；
- wall-clock；
- hardware；
- training and inference data access；
- random seeds；
- stop condition。

### 5.2 Open Engineering Mode

用途：探索高分架構與組件，不要求立即可歸因。

允許：ensemble、adaptive compute、specialized DSL、synthetic data、test-time training、search、verifier、memory、world model、agent-generated code 與其他合法元件。

任何有效元件若要產生 scientific claim，之後必須回到 Science Mode 進行固定 backbone 與 matched-resource ablation。

### 5.3 Official／Competition Mode

用途：產生可對外宣稱的 benchmark 或 SOTA 結果。

必須完全遵循當次官方 evaluator、competition rules、private split、submission format、network、hardware、runtime、open-source 與 disclosure 要求。官方 scorer package／competition runtime 是 source of truth；本文件中的公式僅作概念說明。

---

## 6. Common data-governance protocol

### 6.1 Dataset tiers

每個 benchmark 資料分成：

1. **Training tier：** 可用於訓練、合成資料、primitive discovery 與錯誤分析。
2. **Development tier：** 可重複使用，但所有修改與查詢次數必須記錄。
3. **Sealed validation tier：** 不允許人工查看答案；只在 milestone 評估。
4. **Public evaluation tier：** 視為已暴露 benchmark；禁止逐題人工調參。
5. **Semi-private／private tier：** 用於 verified、competition 或 benchmark-complete claim。

### 6.2 Evaluation firewall

以下任一情況會使該 set 失去 sealed status：

- 人工查看 task solution；
- 逐題修改 solver；
- 反覆用 aggregate score 選擇架構；
- 將 output／error pattern 回灌至 training；
- 使用 human replay、task-specific hint 或 handcrafted solution；
- 未揭露的 benchmark-specific synthetic generator 接近重建 test distribution。

失去 sealed status 的 set 可繼續用於 development，但不得再支持 generalization claim。

### 6.3 Contamination status

每個結果標記：

- `private-clean`；
- `semi-private-low-leakage`；
- `public-exposed`；
- `unknown-model-exposure`；
- `development-contaminated`。

公開 ARC-AGI-1／2 對 frontier pretrained models 的 exposure 通常無法排除，因此公開結果只作 benchmark proxy 與方法開發證據。

---

## 7. Common metrics

### 7.1 Primary metrics for ARC-AGI-1 and ARC-AGI-2

1. **Exact Task Accuracy @1 (`Exact@1`)**  
   每個 task 的所有 test outputs 必須 pixel-perfect；只允許第一個答案。

2. **Native-attempt Exact Accuracy (`Exact@K_native`)**  
   使用該 benchmark／competition snapshot 的官方 attempt allowance。v0 預設：
   - ARC-AGI-1 repository-native：最多 3 attempts；
   - ARC-AGI-2 2026 competition-compatible：每個 test input 提交 2 outputs。

3. **Cost-normalized accuracy**  
   至少報告：每題美元成本、tokens、model calls、wall-clock、accelerator-hours。

`Exact@1` 是跨版本研究比較的主指標；`Exact@K_native` 是官方相容指標。

### 7.2 Diagnostic metrics

- pixel accuracy；
- output-shape accuracy；
- candidate-generation ceiling；
- candidate-selection accuracy；
- train-pair consistency；
- invalid-output rate；
- timeout／OOM／runtime-failure rate；
- first-attempt solve rate；
- additional-attempt salvage rate；
- per-task compute distribution；
- task-family breakdown（僅在分類規則預先凍結時）。

Diagnostic metrics 不得取代 exact task accuracy 作為 benchmark success 指標。

### 7.3 Statistical reporting

- 確定性 solver：至少執行一次完整 frozen run，並提供逐題輸出。
- 隨機 solver：預設至少 5 個獨立 seeds；高成本 run 可降至 3，但必須標記。
- Accuracy interval：以 task-level bootstrap 或 exact binomial interval 報告 95% CI。
- Paired comparison：優先使用 paired bootstrap 或 McNemar test。
- 多組件探索：區分 exploratory 與 confirmatory analysis；confirmatory test 必須預先凍結比較。
- 不以單次最好 seed 作主要 scientific result。

---

## 8. Resource ledger

每個正式 run 必須產生 machine-readable manifest，至少包含：

```yaml
run_id:
benchmark: arc-agi-1 | arc-agi-2 | arc-agi-3
benchmark_snapshot:
evaluator_version:
evaluation_date:
unit: G | M | S | H | N
model_provider:
model_id:
model_snapshot:
weights_hash:
prompt_policy_hash:
solver_commit:
training_data_manifest:
synthetic_data_manifest:
tools:
verifier:
memory_policy:
search_policy:
num_attempts:
max_input_tokens:
max_output_tokens:
max_model_calls_per_task:
max_rollouts_per_task:
wall_clock_limit:
hardware:
network_access:
random_seed:
estimated_cost:
contamination_status:
result_status: exploratory | confirmatory | official
```

缺少 model snapshot、evaluator version、資源欄位或 dataset status 的 run，不得支持 frontier、SOTA、efficiency 或 attribution claim。

---

# Part I — ARC-AGI-1

## 9. ARC-AGI-1 eval definition

### 9.1 Role

ARC-AGI-1 是 infrastructure 與 attribution 基準。此階段的目的不是證明 AGI，而是建立：

- exact-grid generation；
- abstraction representation；
- hypothesis generation and selection；
- program synthesis／execution；
- verifier interface；
- test-time adaptation；
- cost and run logging；
- component ablation discipline。

### 9.2 Canonical data snapshot

v0 以官方 ARC-AGI-1 repository snapshot 為 canonical source：

- 400 public training tasks；
- 400 public evaluation tasks；
- rectangular grids up to 30×30；
- values 0–9；
- task solved only when all test outputs exactly match。

每次正式結果必須記錄 repository commit／release tag。

### 9.3 Required baseline ladder

至少包含：

1. `G0`：direct generalist baseline；
2. `S1`：相同模型，加固定 structured prompting／representation；
3. `S2`：相同模型，加 executable transformation／program synthesis；
4. `S3`：相同模型，加 search／verification；
5. `M1`：ARC-adapted weights，無 specialized scaffold；
6. `H1`：最佳 weights + 最佳 system stack。

若未進行 weight adaptation，`M1` 可暫缺，但不得對 model-level specialization 下結論。

### 9.4 ARC-AGI-1 research questions

- fixed-backbone system specialization 是否提升 `Exact@1`？
- gain 主要來自 candidate generation、selection、execution 還是 verifier？
- 更多 attempts 與更多 search compute 的邊際收益為何？
- public evaluation score 是否對 sealed／private evaluation 保留？
- ARC-specific weights 是否在 matched inference 下優於原始 weights？

### 9.5 Stage statuses

#### `A1-Research-Qualified`

必須同時滿足：

1. 官方 task parser、scorer 與 submission writer 通過 regression tests；
2. 建立至少一個 frozen generalist baseline；
3. 至少一個 specialization intervention 在 paired evaluation 中顯示正向增益，並完整揭露成本；
4. 至少完成一個關鍵 component ablation；
5. public evaluation 未被逐題人工調參；
6. 可從 clean checkout 重建主要結果。

#### `A1-Public-Complete`

`Exact@K_native ≥ 85%`，但僅由 public exposed set 支持。

#### `A1-Verified-Complete`

`Exact@K_native ≥ 85%`，且由官方 private／semi-private evaluation 或等價 sealed external evaluation 支持。

`A1-Research-Qualified` 是進入 ARC-AGI-2 的必要條件；`A1-Verified-Complete` 是 benchmark solved 狀態，但不是進入下一階段的必要條件。

---

# Part II — ARC-AGI-2

## 10. ARC-AGI-2 eval definition

### 10.1 Role

ARC-AGI-2 用來判斷 ARC-AGI-1 方法是否只是對較淺 task distribution 有效。此階段聚焦：

- deeper multi-step reasoning；
- sequential rule application；
- symbolic interpretation；
- search-space scaling；
- synthetic-data transfer；
- refinement loop 的效益與成本；
- A1 → A2 的跨版本持續性。

### 10.2 Canonical data snapshot

v0 以官方 ARC-AGI-2 repository／2026 competition evaluator 為 canonical source：

- 1,000 public training tasks；
- 120 public evaluation tasks；
- 120 semi-private evaluation tasks；
- 120 private evaluation tasks；
- official competition objective：private evaluation accuracy 85%；
- competition-compatible submission：每個 test input 提交 2 個 outputs，任一 exact match 即通過。

每次正式結果必須記錄 repository commit、competition rule snapshot 與 evaluator version。

### 10.3 Transfer-first comparison

ARC-AGI-2 的第一個正式比較不得直接只測全新最佳系統。必須先測：

1. `A1 frozen solver` 原樣移植；
2. 僅做格式／runtime compatibility 修改的 `A1-port`；
3. `A2-adapted system`；
4. 若有 weights adaptation，再加入 `A2-model specialist`；
5. 最佳 hybrid configuration。

藉此區分：

- A1 方法的 direct transfer；
- A2-specific engineering；
- 額外 compute；
- weights adaptation；
- system adaptation。

### 10.4 Required metrics

除共同指標外，必須報告：

- A1 → A2 absolute drop；
- A1 component survival rate；
- A2-specific code／prompt／primitive proportion；
- search budget scaling curve；
- synthetic-data scaling curve；
- refinement iterations per task；
- cost per additional percentage point。

### 10.5 Stage statuses

#### `A2-Research-Qualified`

必須同時滿足：

1. 完成 `A1 frozen solver`、`A1-port`、`A2-adapted` 三組比較；
2. 至少一個 A1 核心元件在 A2 上保留正向、可重建效果，或被明確反駁；
3. 至少完成一條 matched-compute curve；
4. 主要結果不依賴 public evaluation 的逐題人工調整；
5. 建立 private／semi-private submission pipeline 或等價 sealed evaluation；
6. 明確記錄 A2-specific specialization 的比例與位置。

#### `A2-Public-Complete`

`Exact@2 ≥ 85%`，但僅由 public exposed set 支持。

#### `A2-Verified-Complete`

在 2026 competition-compatible private evaluation 或當期官方等價評估上達到 `≥85%`。

進入 ARC-AGI-3 全力 SOTA 階段的必要條件為 `A2-Research-Qualified`。是否等待 `A2-Verified-Complete` 由資源與競賽時程決定，但若未完成，必須在 ARC-AGI-3 文件中保留 `A2 benchmark unsolved` 狀態，不得省略。

---

# Part III — ARC-AGI-3

## 11. ARC-AGI-3 eval definition

### 11.1 Role

ARC-AGI-3 將 evaluation unit 從靜態 solver 擴展至互動式 capability system。核心能力構念為：

- exploration；
- modeling／world-model induction；
- goal setting／goal inference；
- planning and execution；
- online correction；
- memory and context management；
- action efficiency。

ARC-AGI-3 結果預設屬於 **system-level 或 hybrid**，除非以固定 system boundary 的 same-backbone comparison 隔離 model-level effect。

### 11.2 Mandatory three-track structure

#### Track 3A — Controlled Science

目的：回答 model/system attribution。

最低 factorial design：

| Config | Weights | Structured memory | World model | Exploration policy | Search／planning |
|---|---:|---:|---:|---:|---:|
| `A3-G0` | base | no | no | minimal | fixed minimal |
| `A3-SM` | base | yes | no | minimal | matched |
| `A3-SW` | base | matched | yes | minimal | matched |
| `A3-SE` | base | matched | matched | specialized | matched |
| `A3-SS` | base | matched | matched | matched | specialized |
| `A3-M` | adapted | no | no | minimal | fixed minimal |
| `A3-H` | adapted | yes | yes | specialized | specialized |

全 factorial 若成本不可行，可用預先註冊的 fractional factorial；但不得把未測交互作用當成零。

#### Track 3B — Competition SOTA

目的：在當期 ARC Prize competition rules 下最大化 private evaluation score。

允許所有合法的 system engineering，包括：

- frontier／open-weight model；
- specialized agent harness；
- structured or executable world model；
- code generation；
- search、rollouts、verification；
- memory compression；
- ensembles；
- adaptive compute；
- synthetic environments；
- ARC-specific training，若 competition rules 允許。

此 track 的結果分類為：

> `bounded competition-level system superiority`

除非另有 controlled evidence，不支持 specialized weights、broad agent intelligence 或 AGI claim。

#### Track 3C — General-purpose／Verified comparison

目的：測量未針對 ARC-AGI-3 特別準備的 general-purpose model／API，在一致 prompt、tool boundary 與 evaluator 下的表現。

此 track 與 competition harness SOTA 不得使用同一 leaderboard claim。若官方 Verified policy 排除 task-specific harness，則 Track 3B 的結果只能進入 competition／community 類別。

### 11.3 Native scoring

ARC-AGI-3 使用 human-normalized action-efficiency scoring。概念上包含：

1. 每 level 比較 agent action count 與 first-contact human baseline；
2. efficiency 使用平方懲罰；
3. level score 有上限；
4. 後期 levels 權重較高；
5. environment score 受完成 levels 的加權比例上限限制；
6. benchmark score為所有 environments 的平均。

**Implementation rule：** 不自行重寫 production scorer。所有正式結果必須直接使用當期官方 toolkit／competition scorer，並記錄版本與 hash。

**Known v0 source discrepancy：** 2026 technical report／官方 scoring docs 與 Kaggle competition data page對 per-level cap 的文字目前存在 `1.15` 與 `1.0` 差異。正式 competition run 一律以實際 competition evaluator 為準；未核對 scorer source 前，不得用手算值宣稱 SOTA。

### 11.4 ARC-AGI-3 primary metrics

1. official total score／RHAE；
2. environments with at least one completed level；
3. fully solved environments；
4. weighted level completion；
5. actions per completed level；
6. reset／game-over rate；
7. action-budget exhaustion rate；
8. token／model-call／wall-clock／cost per environment；
9. run-to-run variance；
10. public-to-private leaderboard gap；
11. per-environment score distribution；
12. failure mode classification：perception、goal inference、dynamics modeling、planning、memory、execution。

### 11.5 Competition-mode validity

正式 competition SOTA run 必須：

- 使用 `OperationMode.COMPETITION` 或當期官方等價模式；
- 對所有可用 environments 計分；
- 每 environment 只建立一次；
- 不讀取 inflight score；
- 遵循 reset 規則；
- 評估期間無網路；
- 遵循 Kaggle runtime、hardware 與 submission rules；
- 保存完整 code、dependency lock、model/data provenance 與 run manifest；
- 若爭取獎項，滿足 open-source／writeup deadline。

### 11.6 ARC-AGI-3 SOTA claim taxonomy

| Claim label | 最低證據 | 允許表述 |
|---|---|---|
| `Public-dev best` | 公開 games，自行評估 | public development best；不可稱正式 SOTA |
| `Community result` | community leaderboard submission | community-reported score；預設未驗證 |
| `Competition public-LB` | 官方 Kaggle public leaderboard | 當期 public leaderboard score；不得稱 final SOTA |
| `Competition private-LB` | 官方 final private leaderboard | 當期 competition SOTA／placing |
| `Verified generalist` | Foundation verified policy 下評估 | general-purpose model verified score |
| `Scientific ablation` | fixed-backbone、matched-resource、可重建 | 特定 component 的因果或條件式效果 |

對外使用「SOTA」時必須同時包含：

- leaderboard 類型；
- benchmark／competition year；
- evaluation date；
- private 或 public；
- system unit；
- scorer version；
- cost／compute boundary；
- verified status。

### 11.7 Stage statuses

#### `A3-Research-Qualified`

- 完成至少一組 fixed-backbone component ablation；
- 主要 ARC-AGI-3 score 使用官方 scorer；
- 公開與 sealed／private status 分開；
- 建立 replay／trajectory logging；
- 能將失敗定位到至少一個預定義機制類別；
- 資源與 action budgets 完整可見。

#### `A3-Competition-Ready`

- submission notebook／container 在官方 runtime 完整通過；
- competition mode restrictions 通過自動測試；
- no-internet dependency 完整打包；
- 所有 public environments 可無人工介入執行；
- private run 不依賴 score feedback；
- release／open-source checklist 完成。

#### `A3-SOTA`

當期 official private competition leaderboard 第一名，或官方定義的等價最高有效 score。

#### `A3-Solved`

當期官方 private evaluation 達到 100%，並滿足相應 grand-prize eligibility／verification requirements。

---

## 12. Cross-stage transfer evaluation

ARC-AGI-1 → 2 → 3 的價值不只在分數遞增，而在於識別哪些機制能遷移。

每個 A1／A2 核心元件在進入下一階段時標記：

- `directly reusable`；
- `reusable with interface adaptation`；
- `reusable with retraining`；
- `benchmark-specific`；
- `harmful／negative transfer`；
- `not evaluated`。

### 12.1 Required transfer matrix

| Component | A1 effect | A2 effect | A3 effect | Resource matched? | Transfer status |
|---|---:|---:|---:|---|---|
| object／scene representation |  |  |  |  |  |
| hypothesis generation |  |  |  |  |  |
| executable program／world model |  |  |  |  |  |
| verifier |  |  |  |  |  |
| search／planning |  |  |  |  |  |
| test-time adaptation |  |  |  |  |  |
| memory／context policy | N/A | N/A／limited |  |  |  |
| exploration policy | N/A | N/A |  |  |  |

跨版本 score correlation 本身不構成 mechanism transfer；必須有 component-level intervention 或 frozen-port comparison。

---

## 13. Efficiency and scaling protocol

每一個主要 system 至少執行三個 inference budget points：

- `Low`；
- `Matched`；
- `High`。

具體 token／call／rollout 上限由 baseline calibration 決定並凍結在 experiment preregistration 中。

必須報告：

- score vs tokens；
- score vs wall-clock；
- score vs dollars／accelerator-hours；
- score vs attempts／rollouts；
- marginal score gain per 2× compute；
- saturation or failure point。

不同系統若未在相同 budget point 比較，只能支持 configuration-level performance，不得支持 algorithmic efficiency claim。

---

## 14. Minimum ablation set

每個正式版本至少完成：

1. no specialized prompt／policy；
2. no verifier；
3. no search／single candidate；
4. no synthetic data or task-specific training；
5. fixed compute vs adaptive compute；
6. base weights vs adapted weights（若適用）；
7. full system vs best minimal system。

ARC-AGI-3 另需：

8. no persistent memory；
9. no explicit world model；
10. random／minimal exploration vs specialized exploration；
11. no replanning；
12. no executable code tool（若 full system 使用）。

Ablation 關閉某元件時，其他資源不得自動補償；若無法完全匹配，必須揭露 residual asymmetry。

---

## 15. Reproducibility package

每個 milestone release 至少包含：

- source commit；
- dependency lock；
- model and weights identifiers；
- data manifest and hashes；
- training recipe；
- prompts／policies；
- evaluator version；
- run manifests；
- per-task／per-environment outputs；
- aggregate metrics；
- cost ledger；
- failed runs；
- known deviations；
- contamination disclosure；
- claim classification。

無法公開 proprietary model internals 時，仍必須公開 API model ID、snapshot、request parameters、date、prompt、tool boundary、token limits 與完整 outputs／replays。

---

## 16. Invalid or downgraded evidence

以下結果不得作為主要 scientific evidence：

- 只報 best seed；
- 只報 aggregate score，沒有逐題／逐環境輸出；
- 使用 evaluation score 反覆調參但未標記 development contamination；
- model snapshot 不明；
- attempts、tokens、search、rollouts 或 tools 不明；
- public game/task 被人工看過後仍稱 zero-shot generalization；
- public leaderboard 暫時第一名直接稱 final SOTA；
- community leaderboard score稱 verified；
- system specialist 擊敗裸 generalist 後歸因於 weights；
- ARC-AGI-3 public game高分外推為 private generalization；
- ARC-AGI-1／2 公開資料高分直接稱 benchmark solved；
- 不同 scorer／rule snapshot 的分數直接比較。

上述結果仍可保留為 engineering observation，但 evidence status 必須降級。

---

## 17. Decision log fields

每次 major experiment 應新增 decision record：

| Field | 說明 |
|---|---|
| Decision_ID | 唯一識別碼 |
| Benchmark | A1／A2／A3 |
| Question | 被裁決的問題 |
| Configs | 比較的 run IDs |
| Unit | G／M／S／H／N |
| Resource parity | Strong／Partial／Weak |
| Result | Supported／Conditionally supported／Indeterminate／Refuted |
| Effect size | absolute pp、relative gain、cost delta |
| Generalization status | public／sealed／private／cross-version |
| Claim allowed | 最窄可支持表述 |
| Claim prohibited | 不可外推表述 |
| Reversible if | 哪種新證據會改變判定 |

---

## 18. v0 unresolved decisions

下列項目在 implementation 前必須補齊，但不阻止 v0 成為工作規格：

1. ARC-AGI-1 sealed validation 的具體切分與保管人；
2. A1／A2 Low／Matched／High compute 的數值；
3. stochastic run 的最終 seed 數與成本上限；
4. private／semi-private evaluation access path；
5. ARC-AGI-3 competition scorer 的 cap discrepancy；
6. ARC-AGI-3 Kaggle runtime、hardware、submission quota 的 pinned rule snapshot；
7. ARC-AGI-3 failure taxonomy 的 annotation protocol；
8. model-level adaptation 是否納入第一輪，或先以 system-level specialization 起步；
9. synthetic task／environment generator 的 leakage audit；
10. 對外 SOTA publication 的 independent reproduction 要求。

所有未決項目狀態為 `TBD`，不得以推測填入。

---

## 19. Acceptance criteria for Eval Definition v0

本文件在以下條件成立時可升級為 v1：

1. A1 canonical repository、evaluator 與 data manifests 已凍結；
2. A1 baseline ladder 已執行至少一次；
3. run manifest schema 已由實際 pipeline 驗證；
4. public／sealed／private 的資料治理已落地；
5. compute tiers 已以 baseline calibration 數據定義；
6. A2 porting test 已可執行；
7. A3 official scorer discrepancy 已由實際 scorer source 核對；
8. competition rules snapshot 已保存；
9. claim taxonomy 已在至少一份正式實驗報告中使用；
10. 所有重大偏差已進入 decision log。

---

## 20. Short operational statement

> 本專案先在 ARC-AGI-1 建立可重建、可歸因且成本可見的 specialization baseline，再以 ARC-AGI-2 測試跨版本複雜度與 transfer，最後在 ARC-AGI-3 同時運行 fixed-backbone scientific ablation 與 competition SOTA engineering。所有高分均依 model／system unit、資料暴露、資源配置、evaluator snapshot、private verification 與時間索引分級解讀。

---

## 21. Source basis

### Internal authoritative documents

- `Problem Definition v1.md`
- `Evidence-Base-v1.1.xlsx`
- `Evidence-Adjudication-v1.xlsx`
- `Evidence-Adjudication-v1.md`

### External primary sources, accessed 2026-07-31

- ARC-AGI-1 official repository and task specification.
- ARC Prize ARC-AGI-1 & ARC-AGI-2 technical guide.
- ARC-AGI-2 official repository and 2026 competition specification.
- ARC-AGI-3 technical report.
- ARC-AGI-3 official scoring documentation and toolkit documentation.
- ARC Prize Verified Testing Policy.
- ARC Prize 2026 ARC-AGI-3 competition page and Kaggle competition data specification.

