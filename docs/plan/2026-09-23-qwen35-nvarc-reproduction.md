# Qwen3.5-4B 移植完整 NVARC 路線：開發計畫

日期：2026-09-23。狀態：**owner 已要求完整規畫並開啟獨立開發 task**。
開發固定 `gpt-6-sol / xhigh`；總控使用 `gpt-6-astra / high`。

## 1. 方向、範圍與交付

Owner 先提出「用 qwen 3.5 4b 重現完整的 nvarc 路線」，接著要求
「進行規畫並寫完整開發 plan 到 docs\plan，然後開啟新的 gpt 6 sol xhigh
task 進行開發」。本計畫取代同路徑討論稿，作為獨立開發 task 工作說明。

以 Qwen3.5-4B 替換 NVARC 的 Qwen3 主幹，重建資料、專用表示、SFT、題內
適應、候選生成/排序與評估。完整系統清單同時覆蓋 SDG、TRM 與最終整合。
Qwen3.5 替換的是 Qwen 分支；TRM 維持獨立模型。未另獲縮減指示前按完整
系統規畫，先完成 Qwen 主線，再完成 TRM adapter/整合；後者不阻塞主線。

原 Qwen3 checkpoint 是方法與 lineage 參照，不要求先跑原 Qwen3 GPU 基線。
換 backbone 屬方法移植，不宣稱原權重/數值的逐位復現。85+ 保留為長期
public evaluation 與競賽目標，不作本次工程驗收門檻或預先保證。

本次交付可運作的離線程式、配置、fixture E2E、來源映射、訓練/推論入口、
靜態 Kaggle 封裝、可稽核評分與具體資源提案。不能只回另一份計畫、空介面，
或把普通 generate 改名為 NVARC 完成。

## 2. 開發授權與執行邊界

連續完成本機可逆實作、CPU 合成 fixture 測試、靜態打包、必要官方文件/
小型 source 閱讀，以及現有材料的唯讀盤點。例行技術選擇自行決定，不逐項
請 owner 確認，也不為一般實作新增 decision。

本次指令是開發交付，尚未指定新真實模型工作負載的資源上限。依
[執行政策](../development/data-and-execution-policy.md)，真實 Qwen/TRM
訓練/生成、新 SDG 呼叫、Codex proposer、Kaggle Dataset/kernel mutation、
舊 output 再取回、付費資源與競賽提交均不由本次開發指令自動啟動。
開發這些路徑並交付具體 launch/resource proposal；旧 ceiling 不轉入新計畫。

保持 USD 0 新增外部付費。不要因新 worktree 缺 cache 下載/重傳大型權重或
題庫。缺材料時完成其他獨立模組，交付精確缺項/取得命令，不把全部開發停在
第一個缺檔。不得捏造 materials-ready/runtime-verified。
小型隨機初始化網路加合成資料的 CPU 測試屬工程測試，不載入真實 4B 權重、
不讀 sealed answers、不作研究準確率。

所有舊 trial/ledger/result/outbound/notebook 身份不變，不啟動舊 controller。
不改 thesis、P1 public contracts 或開展 P3/P4 平台。開發 task 提交自身
commits 並回報，不自行 merge main、push、發佈或開更多 task/sub-agent。

## 3. 接手資料與已知研究狀態

基線 `ef05c92` 已整合完成實驗，156 tests 通過。讀 `AGENTS.md`、本計畫、
[總控交接](2026-09-23-research-control-handoff.md)，再讀 budget-ablation
control review 與 Trial 002 source-use。舊 plan 只供 lineage，不恢復授權。

B1 train 18/256、dev 12/128；九個 prompt 候選未超過 B1。64 題結果分層
診斷 off/1024、off/4096 都是 18/64，thinking/4096 為 7/64，192 次後止步；
均非官方 evaluation 分數。512 題 visible source 全部一致，舊 holdout
錯誤是 selected-test/full-task 比較問題，仍未生成/評分。Trial 002 0/4
是 inference-only，沒有驗證 TTT。開發/未來反思改為 Sol 6，不改舊模型紀錄。

Ignored evidence 不隨 Git 移動，可唯讀：

- `C:/Users/wurre/.codex/worktrees/e34a/IRIS-X/.irisx/arc-agi-2/prompt-pilot/`
  （B1、search、runtime lineage）。
- `C:/Users/wurre/.codex/worktrees/918a/IRIS-X/.irisx/arc-agi-2/budget-ablation/`
  （competition snapshot、精確 tokenizer、visible audit、最新 runtime）。
- `C:/Users/wurre/Desktop/IRIS-X/.irisx/budget-ablation-review/`（獨立核對）。

B1 result SHA-256：
`4764cd569f669f8736461ddf2b5d6ac3bf1c80ddf3f903d669f8d5a43aa054af`。
Ablation result SHA-256：
`65e2d694e7268815d1b7d594218dea2012c1a7694d108048c1cb543f878edeea`。
大型 JSON 解析後選欄位讀。新產物在自己 `.irisx/arc-agi-2/qwen35-nvarc/`，
不改舊 evidence，不重建 legacy roots。

## 4. Source-to-component 與完整性

優先找 retained source，必要時查官方小型 source，綁定 revision/digest。
已審查 NVARC revision：`846d0198efa752534594e321fc3289fc0a06c657`。
Qwen 起點沿用
`Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`。
新來源不可只填 mutable `main`。逐元件記錄 upstream file/symbol、使用條件、
IRIS-X 對應、維持/改寫/未實作/未執行、驗證與 reproduction gap。

| Source | 開發用途 |
| --- | --- |
| NVARC `SDG/` | 描述清理、摘要/混合、input/output 邏輯、資料驗證及增強 |
| NVARC `ARChitects/` | 專用表示、SFT 配方、權重轉換 |
| NVARC Qwen submission notebook | TTT、augmentation、候選推論/排名與實際配置 |
| NVARC `TRM/` 和 pinned TinyRecursiveModels submodule | 獨立 TRM 資料/訓練/推論 adapter |
| Qwen3.5 官方 source/config/tokenizer | text-only 路徑、混合架構、梯度與 LoRA |
| 官方 ARC-AGI-2 + competition snapshot | full-task source parity、workload 與評分 |
| IRIS-X 成功 runtime | 四卡排程、transport、checkpoint、result verifier |

核對 paper/notebook/不同 submission 版本；不可把不同版本參數混成原法。
既有審查未找到 NVARC root license，逐元件核對，不自動認定皆可 vendoring；
可獨立實作已發表機制或引用合法依賴。某檔使用條件未清不阻塞獨立實作。
SPEX/VANTA/NeMo Agent Toolkit/Prime Verifiers/IRIS/EIDOS 是工程參考，
不導入整套框架；本次不加入 GEPA、RL、路由或其他 solver 搜尋。

## 5. 資料與 SDG 管線

統一以 task 保存全部 demonstrations/test inputs、stable task/test_index、
parent/source IDs。拆分以原題及可識別近重複群組為單位；增強後同題不可跨組。
精確與已知變形 overlap 分列，不能宣稱已證明排除所有語義污染。

分開 SFT labels、SFT validation、task-local demonstrations、solver visible
inputs 與 sealed evaluator truth。Outcome-derived cohort/metadata 不進 solver。
實作 `clean-research` 與 `competition-reproduction` 兩配置：前者排除已知
evaluation/locked-holdout 答案和可識別衍生物；後者描述原配方曝光並明列
污染標籤。此次不讀/外送舊 sealed holdout truth；以 IDs/lineage/evaluator
介面及合成 fixture 開發排除機制。Unknown 不標 clean；歷史 holdout 沒跑
不代表外部資料沒見過。`arc2_evaluation6` 是調查入口，不憑名字定案。

實作 streaming import/schema validation、dedup/grouping、seeded
augmentation、配比 manifest、deterministic shards，資料與 split 先凍結
才訓練。已有發布資料的使用與重新 SDG 分列，不能說 import 等於重跑 SDG。

SDG 保存各 stage 的 input/output、prompt/source digest、seed、父題 lineage、
filter reason、call/token counters。提供 saved-response offline replay backend
跑通 fixture；真實生成 backend 綁定模型與限額後才啟動，不偷偷呼叫 API。
SDG teacher 尚未選定，不把小詞表 solver 用於自然語言程式生成。

生成的 Python 視作不可信資料，不在有憑證 host 直接 exec。實作 executor
介面要求無網路/憑證、受限掛載、CPU/memory/time/output limits；缺隔離
環境 fail closed。預先審查 fixture 可驗證 pairing/filtering。普通 subprocess
不是 sandbox，隔離未實測須明列，不用假安全檢查器繞過缺項。

## 6. 小詞表表示與 Qwen3.5 checkpoint

目標移植原 compact grid/small-vocabulary 機制，從明確 grammar 推導 digit、
換行、分隔、結束符及 mapping；不使用 evaluator 答案決定詞表。
核對原 16 embeddings 在新模型是否仍適用；需額外 token 時明列差異，
不為湊數刪掉必要符號。原生 tokenizer 僅作相容性診斷，不能冒充目標完成。

轉換器接受 immutable base + vocabulary manifest，輸出新目錄/digest。
正確處理 tied/untied embedding-output head、config IDs、tokenizer、weight
index 及 reload，不沿用 Qwen3 的 tensor 名/token IDs，不覆寫原權重。
以 tiny tensors 驗證 row selection、sharing、save/load、grid round-trip。

Text-only 路徑明示保留/移除的視覺模組、chat template 與 special tokens。
小詞表 grid solver 若無自然語言通道，不照搬 B1 thinking 開關或 prompt GEPA。
普通 chat Qwen 配置保留為獨立對照，與轉換後 checkpoint 明確區分。

## 7. 真正的 SFT 訓練入口

實作 dataset/model identities、loss mask、packing、optimizer/schedule、seed、
gradient accumulation、trainable parameters、precision、step/token limits、
checkpoint/resume/export。核對原 loss/mask 配方，所有修改列清楚。

使用支援 Qwen3.5 的模型類別，驗證 DeltaNet/attention 的梯度路徑與 LoRA
target mapping；不能照貼 Qwen3 module list 或以 no-grad forward 假裝訓練。
Full SFT 是方法比較基準，LoRA/QLoRA 若作資源縮小方案，以命名配置記錄
差異，不靜默取代完整 SFT。

Tiny CPU model + synthetic data 驗證有限 loss/gradient、預期參數更新、凍結
參數不變、padding/packing mask、checkpoint restore 的 optimizer/scheduler/
RNG/data cursor。Optional hybrid-model 測試缺依賴時單列 skip/gap；toy
測試不稱作真實 Qwen3.5-4B 相容性驗證。

先依參數/config 推算 memory 區間，提出實際單步 throughput/peak memory
測量設計。未量測的 throughput 寫未知，不以 inference tok/s 推算 SFT。
上游多節點訓練不等於 L4×4 可行；分列 full SFT 與 memory-saving 方案的
方法差異，不自動改用付費 GPU。Training checkpoint（optimizer 等）與
inference result.zip 分開 artifact kind；export 不夾帶訓練資料或 evaluator truth。

## 8. Task-local LoRA/TTT 與推論

基底 ARC-SFT checkpoint 在 worker 常駐；每題重置 adapter、optimizer、RNG、
cache，只以該題公開 demonstrations 與增強形成訓練樣本。Leave-one-out 等
配方按核對後 source 實作，不用 test truth、不跨題保留適應狀態。

實作 rotation/transpose/color permutation/demonstration shuffle，保留 source
映射與 inverse transform；驗證非方形 grid、color 0、多 test 與可逆性。
同題所有 test inputs 共用該題適應，task 級 deadline 累計 TTT 和全部候選，
不在每個 test/attempt 重置。

候選數、seed、decoding、batching、max tokens、EOS/full-grid、排序規則
全部進配置。每次呼叫及 returned sequence 分別計帳；fallback/複製不是
新增有效模型候選。核對 source 的 likelihood/verification/aggregation，
只用 solver-visible 資料；先 inverse transform 再 canonical 去重，保留
來源、score/votes、deterministic tie-break。不能用 evaluator truth 選 top two。
Cap/缺 EOS/不完整 grid 不因可解析就算完成；候選不足列明 missing/fallback。

## 9. TRM 分支與最終整合

完成獨立 dataset conversion、checkpoint manifest、train/eval launch adapter、
candidate interface，使用 pinned upstream/submodule，保留 architecture/state/
augmentation 與曝光設定，不把 Qwen weights 載入 TRM。

缺實際 weights/dependencies 時完成資料、配置、adapter 和 fixture integration，
列明真實 backend 及缺項，不以 mock 宣稱實測。兩個 solver 的 score 不可
未校準直接相加；先核對原集成規則，固定 selection/tie-break/分支成本。
提供 Qwen-only、TRM-only、combined 配置，未實測標 not_evaluated。

完整清單含 SDG/Qwen/TRM/integration，各原 submission 組合分開記錄。
不可把 2B/TRM 與 4B-only 的參數/分數拼成同一復現版本。

## 10. 四 L4 runtime、封裝與帳本

優先沿用 `arc_budget_ablation.py` full-visible audit、
`kaggle_runner_budget_ablation.py` GPU gate/persistent workers/dynamic queue；
參考 `arc_trial_002.py` 的 multi-test scorer/supervisor，以及
`arc_prompt_pilot.py`/`arc_prompt_kaggle.py` 可獨立重用的 transport。
不呼叫已關閉的 search controller，不另造通用 scheduler。

Inference 保留官方 `arc-prize-2026-arc-agi-2` 掛載、private、Internet disabled、
`NvidiaL4`、四個不同 GPU UUID、各卡 model-ready/dispatch。每 worker 載入
一次基底後按 task 動態派工。Distributed training 用獨立 mode，不能把
推論 independent-worker 假設套到 collective training。

Mount 只解析明確 owner-qualified/legacy paths，不遍歷 `/kaggle/input` 猜檔。
已有 base Dataset `danielwuu/irisx-arc-agi-2-trial-002-smoke-001` version 2
保留複用；本次不做 status/mutation。新 SFT weights 規畫獨立 identity 與
必要上傳，不覆寫 base，也不因重用目標而省略新 trained artifact。

New manifest/checkpoint 綁定 model/tokenizer/data/workload/runtime/config。
Atomic ledger 分計 SGD steps、tokens、generation calls/sequences、SDG calls、
各分支/階段 elapsed。Pending 呼叫保守計帳，resume 不歸零；不支援任意
TTT step 恢復時明訂 task-boundary checkpoint，中斷不得隱藏重跑成本。
Worker timeout/OOM/crash 都產生 terminal record/partial result，supervisor
實際控制 deadline，不只在 generate 回傳後標超時。

Inference outbound/result 不含 evaluator truth、答案 digest 或 outcome metadata。
SFT labels 屬獨立 training-data artifact，日後依批准 manifest allowlist
傳輸，不混入 inference package。記錄 stop reason、完整性、token coverage、
load/TTT/generate/rank elapsed、peak memory、各卡 jobs、wall time；unknown
用 null，wall time 不冒充 GPU busy time。

## 11. 評估設計

本次只做離線工程測試；未來同 workload 的真實對照配置如下：

| 配置 | 回答的問題 |
| --- | --- |
| Q0 原始 Qwen3.5 | 新 workload 的未專用化對照，不冒充歷史 B1 |
| Q1 ARC SFT/小詞表、無 TTT | 專用化後能力與可完成性 |
| Q2 同 Q1 + TTT | 固定推論條件下的適應增益 |
| Q3 完整 Qwen 候選生成/排序 | 完整方法額外品質/成本 |
| T / Q3+T | TRM 互補性與可部署整合結果 |

Q0/Q1 同時改 SFT/表示，不只歸因 SFT。需要因果分離另提小詞表未 SFT
對照，不臨時追加執行。Ablation 的關閉項與候選預算差異明列。

主要 evaluator 按每個 test output exact-match pass@2 平均，分母涵蓋所有
指定 test outputs；另列 pass@1、task-all-correct、完整/invalid/timeout/OOM/
not-executed。兩次相同預測不是獨立樣本。Fixture 至少含一題兩 test 一對
一錯、不同 task test 數、缺失候選。Full-task source 和 selected-test
execution view 分開驗證，杜絕舊 holdout bug。

Train/selection-dev/locked-eval 的曝光與使用次數分列，不能用 train 擬合、
事後 oracle union 或歷史 64 題診斷分數宣稱泛化。新 split/public evaluation/
舊 holdout 真實執行留待授權。此計畫不另訂 promotion 數字門檻。

## 12. 布局與開發順序

建立 `trials/arc-agi-2-qwen35-nvarc/` 為唯一狀態頁，初始
`development-authorized-no-execution`；保留 source-use、configs、runbook、
reproduction matrix、resource proposal。不假造新 execution decision。

程式在 `src/irisx/` trial-specific 模組，按 data/representation/training/
adaptation/candidates/runtime/evaluation 拆責任，命名由開發決定；避免
service/registry 平台化。Heavy ML lazy import，optional dependency lock
與基本離線輕量 runtime 分離。新增 subpackage 時確認 wheel builder 包含它。

| 階段 | 交付 | 驗收 |
| --- | --- | --- |
| D0 | source inventory/版本對照/材料缺項 | 每元件可追溯，不重跑舊實驗 |
| D1 | data isolation/SDG replay/augmentation/tokenizer converter | deterministic fixture、round-trip、曝光拒絕 |
| D2 | SFT/export/resume、TTT/reset | CPU 梯度/狀態隔離；實際架構未測項分列 |
| D3 | candidates/inverse/ranking/scorer | 多 test、去重、cap/missing/failure E2E |
| D4 | 四卡 runner 靜態封裝/supervisor/ledger/result | fake-worker crash/timeout/resume 和 truth 邊界 |
| D5 | TRM adapter/integration、SDG executor 介面 | 真/fixture backend 不混淆、候選來源可稽核 |
| D6 | 本機 fixture E2E/runbook/resource proposal | clean checkout 可重做，repo checks 通過 |

連續完成所有能獨立完成的工作，不逐階段等 owner。缺依賴交付 concrete gap，
不以 TODO/stub 冒充完成，也不因此省略其他可完成模組。可使用 source-backed
external adapter，不要求重寫 ML framework。各階段完成做小 commits。

## 13. 測試與完成定義

聚焦 augmentation invertibility、詞表/權重一致性、mask/gradient、TTT 跨題
污染、source view、多 test 分母、ranking 不讀 truth、ledger 重入/重複、
worker 強制停止、checkpoint identity、package path/digest。用 tiny tensors/
合成 CPU fixtures；不為文件/常數寫鏡像測試。Optional 真實架構測試明列
pass/skip/missing，不用 mocks 宣稱 Qwen3.5-4B 支援已驗證。

交付 documented offline E2E command：合成資料經 tiny training/adaptation
或明確標記 fixture backend，到 candidates/result verifier/multi-test scorer。
可重做，無網路、真實權重/holdout truth 存取。從 repo root 執行：

```powershell
python tools/repository_check.py --all
```

狀態分開 `implementation-verified`、`materials-ready`、`runtime-verified`、
`sft-trained`、`full-method-measured`。本次工程交付不越級宣稱後四者。
缺實際 artifact/dependency 的部件標 partial/gap。

## 14. 真實執行提案與回報

開發末交付 `execution-proposal.md` 和 machine-readable draft manifests：
分開最小 Qwen3.5 gradient/tokenizer/TTT feasibility、小型 SFT pilot、完整
SFT、Q0–Q3 評估與 TRM/SDG 額外需求。每階段列 materials/workload IDs、
steps/tokens、calls/sequences、task/session wall limits、checkpoint policy、
收尾預留、軟硬體、paid cap、可複用 Dataset、停止條件及 retrieval/scoring。

未來第一步提案是最小相容性實測，不把所有階段串成無上限 run。估算與
量測分列，throughput/VRAM 未知就明寫。建議限額可以具體，但標 proposed
而非 owner-approved。真實 launch 要有可驗證的新授權與完整非空限額，
預設 dry-run；不能只因 `--execute` 就把草案當批准。Fixture E2E 不受此阻塞。

最終回報 commits、變更/測試、元件完成狀態、實際 source、未實測/缺項、
資源提案與可審閱命令/manifests。新 GPU/generation/reflection/Kaggle
mutation 應為零。需要 owner 決策時先完成其他獨立工作再交付具體選項，
不讓 owner 重述交接。

## 15. 官方 source 索引

2026-09-23 查閱；branch URLs 僅為索引，實作仍需 immutable binding。

- [NVARC](https://github.com/1ytic/NVARC)
- [SDG](https://github.com/1ytic/NVARC/blob/main/SDG/README.md)
- [ARChitects](https://github.com/1ytic/NVARC/blob/main/ARChitects/README.md)
- [Tokenizer](https://github.com/1ytic/NVARC/blob/main/ARChitects/cut_tokenizer.ipynb)
- [SFT](https://github.com/1ytic/NVARC/blob/main/ARChitects/run_sft_4b.sh)
- [Qwen notebook](https://www.kaggle.com/code/sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue)
- [TRM](https://github.com/1ytic/NVARC/blob/main/TRM/README.md)
- [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)

本次 web 未能解析 NVARC PDF，Kaggle writeup 未回傳可讀正文，不宣稱已
核對全部超參數/最終集成規則。D0 優先找本機 snapshot 補足，缺項明列，
不得依 search snippet 捏造方法細節。
