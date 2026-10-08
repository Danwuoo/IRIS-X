# IRIS-X 下一條技術線：讓 agent 架構是否有效成為可測量的問題

## 結論與第一份 notebook

第一份 G4 訓練／架構實驗 notebook 已完成開發與獨立 CPU 驗收；已在指定新的私人 Kaggle notebook 完成唯一一次 QuickSave，ID 137630087、version 1，並核對完整執行來源。訓練目標是單張 RTX PRO 6000 的 g4-standard-48，正式提交仍是離線 L4 ×4。沒有執行 GPU、開啟付費硬體或正式提交。

本線最重要的問題是：相同模型與可比的總資源預算下，程式提案、示例驗證與失敗回饋，能否增加 ARC-AGI-2 正確候選與 top-2 命中？研究不因來源主要在 ARC-AGI-3 就排除它們，而是把可以移植的機制拆成可驗證的 ablation。

Notebook：https://www.kaggle.com/code/danielwuu/iris-arc2-g4-agent-pilot-20261008-6deaf904

## 完成的 uncapped 結果

完整可信來源重播與檔案／事件驗證通過：四張 L4、512 次 TTT updates、六個 test searches、96 generation views，全數完成；總執行約 27 分 57 秒。100,109,230-byte inference ledger 超過舊 8 MiB 上限而沒有中止。

66 次候選出現合併為 41 個不同候選，12 個猜測欄位皆填滿，六個 tests 皆完成輸出資格檢查。然而已暴露的六個 public-dev tests，top-1、top-2、完整候選池 oracle 都是 1/6。另五題的候選池沒有正解，因此僅換排序器無法補救；值得試驗更好的提案、表示法和訓練。這不構成新架構一定有效的結論，也不是官方分數。與 E12 的比較沒有配對控制重新訓練的隨機性，不能宣稱因果等效。

## 架構如何落地

- A：direct-grid 多次提案，依固定規則投票選兩個不同結果
- B：相同模型提出程式，實際執行全部 demonstrations，保留通過者
- C：B 加上結構化失敗回饋，再修復程式

B/C 使用同一個受限 Python-syntax interpreter：支援通用迴圈、條件、索引與 grid 操作；不會 Python eval/exec、import、存取檔案、網路或 shell。它比舊的固定短 DSL 更有表達力，仍有明確語言邊界，未支援語法與空池會完整列入失敗。

每個 arm 固定 checkpoint、task groups、template、generation policy 與 seed 規則，限制並記錄 calls、prompt/generated tokens、context、wall time 與 interpreter steps。額外輸出 token/time prefixes 下的 top-1、top-2、oracle，避免把更多呼叫的成本誤當免費的架構增益。Token 數是代理量，不宣稱相同 FLOPs。demonstration 全過只表示一致性，不能當成 test generalization；第一版不假裝已執行 fresh-fold LODO。

## 與指定 sources 的整合

- NVIDIA AVO：借用「執行、取得可驗證回饋、修復與保留提案沿革」，不套用其 ARC-AGI-3 headline 分數。[NVIDIA 原始報告](https://developer.nvidia.com/blog/nvidia-avo-reaches-100-on-arc-agi-3-demonstrating-a-frontier-level-general-purpose-architecture-for-long-horizon-autonomous-agents/)
- Duck harness：借用清楚的工具介面及狀態／上下文管理，實驗程式回饋是否有用。[Tufa 原始報告](https://tufalabs.ai/research/duck-harness/)
- Prime Agent：借用可追蹤的工具使用與記憶邊界；不讓跨題答案或 evaluator 標籤進入 solver。[論文](https://arxiv.org/html/2608.23552v1)
- Jev：已確認是 TypeSafe 的 typed decision 模型；目前沒有核實可直接離線部署的官方權重。採用 typed 控制界面，第一版由 deterministic executor 判斷示例 exact match。[官方介紹](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- NeMo：把 NeMo RL 的 SFT／後訓練介面、Agent Toolkit 的 profiling 分開處理。第一版使用較輕的 HF＋PEFT，保留模型／資料／artifact 契約；不因安裝完整 framework 就預設 ARC 能力提高。[NeMo RL](https://github.com/NVIDIA-NeMo/RL)、[Profiler](https://docs.nvidia.com/nemo/agent-toolkit/latest/improve-workflows/profiler.html)

專案既有 NVARC、E20、truth-free submission exporter 與 source identity 不是丟棄重做：保留前者作實測 incumbent，採納 E20 零候選的負面證據，沿用固定 ARC source pin、完整分母、真值隔離與可重播證據。舊的 16-symbol compact vocabulary 不適合通用程式輸出，本線保留三個原始 tokenizer 的完整 vocabulary。

## 模型與訓練

順序維持：IBM Granite 4.2-8B、Qwen3.5-9B、Seed-Coder-8B-Reasoning。三個官方 repository、revision、config、tokenizer 與 weight-shard LFS hashes 均已鎖定，但沒有下載 weights 或宣稱訓練完成。

- Granite：dense Granite，約 8.792B，vocab 100352，Apache-2.0
- Qwen：完整 conditional/hybrid checkpoint 約 9.653B，vocab 248320，Apache-2.0；明確 text-only calls，保留 vision memory，沒有默默替換模型
- Seed：Llama 架構，約 8.250B，vocab 155136，MIT；指定 repository 儲存 FP32，載入時明確轉 BF16，沒有改用另一個 -bf16 repository

第一版採 BF16＋LoRA＋SDPA。公開 training 的 task identity 先做固定分組，再展開 demonstrations／augmentation；32 個 training groups 與四個 development groups 分離。訓練目標是從其餘 demonstrations 預測 withheld training demonstration，完整保留 grid，超長 row 不截斷。smoke2 先確認兩步真實梯度與 adapter 匯出重載；pilot16／128 另需手動開啟。量測訓練 loss、固定 dev rows 的訓練前後 token-weighted NLL、實際 updates、tokens、時間與資源，再分開測 base／adapter 的 A/B/C。

四個 development groups 只是第一個工程 screen，不能用來宣稱泛化勝出。後續應擴大固定 held-out task groups、配對種子與等預算曲線，再決定模型與是否投入 trajectory SFT 或 RL。

## G4 到四 L4

Google 官方 g4-standard-48：48 vCPU、180 GiB RAM、一張 96 GB 等級 RTX PRO 6000 Blackwell。實際 CUDA free memory、driver 和 compiled kernels 由 runtime gate 驗證。[Google 規格](https://docs.cloud.google.com/compute/docs/accelerator-optimized-machines#g4-vms)

保留 pinned base、LoRA safetensors、完整 tokenizer／template、license／source card、code、wheel lock、資料與模型 manifest。先驗證單張 L4 的峰值與重載，再用四個獨立 replica 分派任務；不能把 4×24 GB 當成任意單模型可直接使用的 96 GB。不要搬 Blackwell compiled cache 或假定 Blackwell-only quantization 在 Ada 可用。官方 notebook 仍需離線、12 小時內產生完整 submission.json。[官方條件](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview/description)

## 驗收邊界

新線 85 個 focused tests、兩個 notebook inert tests、五個 genuine SDK wire tests 通過；另外有 19 個獨立負面控制。三個真實 tokenizer JSON 用 Tokenizers 0.22.2 與官方 HF Jinja 設定完成 CPU 邊界／label-mask 檢查。完整歷史 aggregate 仍是 1,432 tests、35 errors、一個 failure、59 skips，主要缺 retained historical fixtures／models，沒有把缺件補造來取得全綠。

這些是 CPU、資料契約、來源與封裝驗證。GPU compatibility、訓練品質、agent 架構增益、L4 fit／速度和官方提交 readiness，仍必須由實際手動執行的結果建立。
