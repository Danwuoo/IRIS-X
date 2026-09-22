# ARC-AGI-2 可完成 solver 基線開發計畫

日期：2026-09-22

狀態：已依 owner 問答定稿；供獨立 Sol / xhigh task 實作及執行首輪有界 smoke。

## 1. 目的與交付邊界

本聊天作為開發總控；另開 GPT-5.6 Sol / xhigh task 實作本計畫。
長期目標是 public evaluation >=85% 作為里程碑，以及競賽 private test
>=85%。本階段建立可完成、可計分、可診斷成本的基線，不承諾分數，
不宣稱 SOTA、candidate promotion 或 Domain Package 完成。

第一個問題是：在 owner 指定的 L4 x4 環境內，能否以有界時間完成
ARC 解題、保留有效預測、回傳可驗證結果，並知道運算花在哪裡？

Trial 001 已關閉；本計畫不恢復它的執行授權，不修改其凍結身分與 bytes。
參照 [Trial 001 終態](../../trials/first-real-domain/README.md) 與
[Decision 0012](../decisions/0012-close-arc-agi-2-trial-001-inconclusive.md)。

## 2. Owner 選擇與授權範圍

2026-09-22 本聊天已明確決定：

- 找較新、參數量與 NVARC Qwen3 4B 相當、具有更強能力證據的模型，直接導入
  NVARC。預設比較約 3B-5B dense 模型；不能只看 MoE active parameters 當總容量。
- 可導入開源程式、checkpoint 與可追溯的第三方／合成 ARC 訓練資料；
  大規模 SFT、重新訓練的計算預算另訂，材料取得不等於訓練授權。
- 授權使用 Kaggle CLI 建立並執行 notebook，完成後抓取結果，中途不監控。
  這項新授權取代本次工作原先規劃的手動 transport，不適用 Trial 001。
- 曾接觸 public evaluation 答案的 checkpoint 可以用於競賽研發，必須標記
  受污染的 public 分數；另保留未經 ARC public eval 答案適應的乾淨對照。
- 首輪 smoke 為 4 題，每次總 wall-clock 最多 3,600 秒，每題最多 300 秒。
  所有 test inputs、採樣、適應與重試共用該題的 300 秒，不是每個 attempt 各 300 秒。
- 允許題內 TTT／LoRA，訓練與推論共用上述上限；離線大型 SFT／重新訓練不在
  本次執行預算內。四卡全部占用 60 分鐘的 allocation 上界為 4 GPU-hours，
  不將此上界當作實測 GPU busy time。
- 外部付費預算 USD 0，禁止外部模型 API，競賽 submission 本身不在本次授權。

本次只安排已授權的首輪單次 smoke：新模型加 NVARC 適配路徑，總上限
60 分鐘。兩條路徑各跑一次、合計 120 分鐘的可選擴大方案尚未獲選，
因此乾淨原始權重對照先保留配置與資料隔離，不額外執行對照或 checkpoint run。

授權使用現有 Kaggle CLI 認證完成必要 notebook／私有 Dataset 建立、上傳、
版本綁定與結果下載；不得列印、複製進 repo 或 notebook 的 token，亦不得由
其他瀏覽器／程式擷取秘密。登入缺失、未接受競賽條款、無 L4 x4 配額等
實際阻礙需具體回報；不自行換付費資源或其他 GPU 來冒充通過。

完整競賽限制、實際 Dataset 路徑／版本、最終模型 revision 仍須實證綁定。
開發 task 可在上述模型級別內查證並選定具體模型，固定 revision 和 bytes、
通過技術 preflight 後執行已授權 smoke，無須就同一範圍重複詢問。
保留原始權重對照設定與獨立 adapter；每題結束後清除本題適應狀態。
不得對 public evaluation test 答案做本次 TTT 或將其用作停止／排序訊號。

## 3. 已發現的設計風險

### 3.1 評分單位

現有 `src/irisx/arc_agi2.py:score_predictions` 對一題的所有 test inputs
使用 `all(test_passes)`，再按題平均。新競賽基線依逐 test output 的
exact-match pass@2 平均計分：一個 test output 只要兩個預測之一正確
即為 1，否則為 0。分母包含預先指定 workload 的所有 test outputs。

新增獨立 evaluator profile；不得靜默改寫 Trial 001 evaluator 或歷史結果。
以一題兩個 test inputs、一對一錯的 fixture 證明新分數為 0.5；另測
不同題目含不同 test input 數時的分母。task-all-correct 可另列診斷指標，
不得冒充競賽主分數。

### 3.2 NVARC checkpoint 的資料曝光

NVARC `ARChitects/README.md` 列出 `arc2_evaluation6` 等 SFT 資料子集。
這是必須調查的曝光訊號，不足以單憑名稱斷言所有 checkpoint 均受污染。
逐 checkpoint 查訓練配方、來源、授權、權重版本及 public eval 曝光。
`unknown` 不可標成 clean。一般預訓練污染也不能宣稱已完全排除。

### 3.3 小模型不等於低訓練成本

先區分使用既有權重、test-time adaptation 與重新訓練的成本和授權。
不得為了重現 source 而自行啟動大型訓練、下載大量題庫或切換外部 API。
如果原方法依賴不在本次範圍內的步驟，清楚標記 reproduction gap。

## 4. Source 導入方式

開發 task 先審查 NVARC 的最小可執行路徑，必須實際接入可追溯的 NVARC
解題機制，而非只有 import、文件引用或把普通 generate runner 改名。
交付 component mapping，明示複用的 grid 表示、augmentation、適應、生成、
候選排序各部分，哪些保持原法、哪些因新模型而改寫、哪些尚未實作。
本輪不一次整合 NVARC、TRM、SOAR 等多個獨立 solver。
每個真正使用的外部元件記錄 URL、精確 commit/revision、license、
檔案 digest、取用用途與本地修改；不能把 upstream branch 名稱当 immutable identity。
未驗證 upstream 數字一律標為 source-reported。

現有素材從 `archive/pre-product-transition-2026-09-17` 以唯讀方式取用：

| 既有 source | 本階段實際用途 | 後續實驗接點 |
| --- | --- | --- |
| SPEX | 參考逐題結果、比較邊界與資源帳本 | 固定 workload 的成對比較 |
| VANTA | 參考受控執行、驗證與恢復機制 | 後續程式 solver 的隔離执行 |
| NeMo Agent Toolkit | 審查最小 profiling 欄位與代價 | 成本診斷；不預設整套框架為依賴 |
| Prime Verifiers | 審查 task/rollout/metric 的介面 | 後續 reward/訓練接點 |
| DSPy / GEPA | 讓提示與程序設定可版本化，保留失敗與生成紀錄 | 第一輪 baseline 改善實驗 |
| AFlow、RouteLLM、FrugalGPT、Agent Lightning、Prime Agent | 在 source 審查表記錄適用性與延後理由 | 本次不實作流程搜尋、路由或 RL |
| IRIS、EIDOS | 參考失敗分類、來源與證據區分 | 不恢復舊架構或旧治理 |

須交付簡短 source-use 表，區分「複用程式」「改寫機制」「僅參考」「延後」。
只寫 source 名稱不算導入；也不為宣稱導入而引入不必要依賴。
舊 registry 的不少 upstream revisions 為 Unknown；不能直接宣稱可重現上游。
不重建 `sources/`、`corpus/` 等舊根目錄。

### 4.1 新模型選擇與相容性

以 `Qwen/Qwen3.5-4B` 為第一個查證候選，`Qwen/Qwen3-4B-Instruct-2507`
作為架構較接近的相容性參考；開發 task 應再查當下可取得的同級模型，
最多整理三個候選，不做無預算的模型 sweep。比較能力證據、release/revision、
license、single-L4 memory、推論/LoRA 支援與 NVARC 移植成本。
general benchmark 較高只支持候選優先順序，不證明 ARC 較強。
查不到比原模型更強且相容的選擇時，回報證據與取捨，不偷換成原模型交差。

Qwen3.5-4B 的 hybrid attention 與 NVARC 原 Qwen3 路徑不同；原版 adapter
不能直接載入。NVARC 還要求專用 tokenizer/16 embeddings 與 SFT，不能對
未訓練的新模型直接刪減詞表後聲稱等價。保留原 tokenizer 的移植、適應哪些
權重、kernel/LoRA support 與任何必要訓練都要明示。
若完整重現必須先做未授權 SFT，應交付具體阻礙與最小訓練提案，同時完成
不依賴該訓練的實作；不得捏造已完成 NVARC reproduction。

對照配置保留原始、未做本專案 ARC 答案訓練的權重；題內適應若獲准，
只使用該 task 公開 demonstrations，不能讀 test truth，task 間重置適應狀態。
外部訓練資料需記錄來源、版本、授權、原題/生成 lineage 與 public eval
精確及已知變形重疊；無法確認的曝光仍為 unknown。

## 5. 實作範圍

### 5.1 新身分與最小契約

- 預留新工作區 `trials/arc-agi-2-baseline/`，logical trial ID `arc-agi-2-trial-002`。
- run IDs 使用 `trial-002-smoke-001` 等獨立身分；bytes 改變即換版本或身分。
- `.irisx/arc-agi-2/trial-002/` 放 source、weights、wheelhouse、outbound、
  checkpoint、quarantine、verified result 與本機 scoring。
- 只讀複用原 workspace 已有且驗證通過的公共材料，可避免在新 worktree
  重複下載；新產物不能覆寫原 `.irisx/` Trial 001 路徑。不得列印 secrets。
- 先複用 canonical JSON、digest、grid validation、隔離 view 等通用能力。
  凍結 runner、notebook 與 Trial 001 特有 helper 保持相容與身分不變。
- P1 EngineeringTrial 強制至少一個 candidate；若本輪只執行一個基線配置，
  不捏造 candidate、不複製 baseline 冒充比較。使用 trial-specific supporting
  artifacts 明示 readiness/measurement，不修改 P1 public schema。
  乾淨對照與 NVARC 適應確實構成兩個配置時可按原契約建模，但未執行的對照
  結果維持 not_evaluated，不觸發 selection。
- 若後續确实需要 core contract 變更，提出最小具体差異，由總控處理。

### 5.2 資料與 workload

- 使用已採用的官方 ARC-AGI-2 commit
  `f3283f727488ad98fe575ea6a5ac981e4a188e49`；取得與驗證分離。
- smoke 從 public training split 以預先指定 seed、task ID 排序與
  可用輸入形狀條件決定 4 題，選題不得看 solver 成敗或 test 答案。
- smoke 包含所選題目的全部 test inputs，保留穩定 task/test_index 對應。
- training smoke 成功只證明執行可行；可能已被 checkpoint 見過，不能推估
  generalization 或 public eval 分數。
- 完整 public evaluation 可準備、計分及封裝，但不默認納入首輪執行。
- outbound 僅含 demonstrations 與 test inputs；test truth、答案 digest、
  分數、以答案導出的特徵及 evaluator metadata 不外送。

### 5.3 Solver 與 L4 調度

- 首選每張 GPU 一個持續存活的 worker，共四個；模型只載入一次並分派 task。
  任務少於 worker 時允許閒置，不能捏造四卡利用率。
- GPU 型號/數量、實際可用顯存與每張卡的裝置綁定要可觀察。
- 可選單 worker 開發診斷，但不能將其稱為 L4 x4 驗證。
- 每個 test input 最終兩個 grid 預測。內部採樣／候選數、seed、token cap、
  decoding 與排序策略顯式設定並納入身分；本輪不擴張成 ensemble 搜尋。
- 合法但錯誤的 grid、解析失敗、timeout、OOM、worker crash、未執行必須區別。
  為 submission 完整性補的 fallback grid 明確標記，不計入模型有效生成率。
- TTT 的執行與 budget 按第 2 節定稿選擇；不得擴大為離線 SFT。

### 5.4 有界執行與可觀察性

- 除 model generation 的軟限制，還要有獨立 supervisor 控制 worker deadline；
  不再只依賴 `generate(max_time=...)`。
- 計時從 session 起點包含模型載入／編譯／初始化；任務工作另記錄時間。
  3,600 秒總 budget 內至少預留最後 180 秒收尾，supervisor 應在該保留區前
  停止新工作及終止未完成 worker。CLI outer timeout 同樣不超過 3,600 秒。
  每題 300 秒累計包含題內適應、全部 test inputs 的生成與重試。
- supervisor 定期输出 stage、已完成數、當前 task、elapsed、剩餘預算；
  未產生第一個 token 時也要有可見 heartbeat。記錄 heartbeat 的耗時開銷。
- 記錄 model load、tokenization/prefill（可測時）、TTFT（可測時）、
  generation time、輸入/輸出 token 數、tokens/s、GPU peak memory、停止原因。
  無法取得的欄位寫 unknown，不寫 0；GPU busy time 不以 wall time 假冒。
- 任務 timeout 可終止並重建 worker；所有重試與重載都計入同一 session budget。
- 原子 checkpoint 綁定 solver/model/source/workload/configuration/runtime 身分。
  並行完成採 job key 集合追蹤，reject duplicates、未知 key、錯誤身分與損毀。
  不照抄 Trial 001 單工 contiguous-prefix 假設到四卡調度。
- 恢復可重做未完成 job，但不能重置累計預算；無法確認的中斷時間需有明確
  保守計帳策略。新運算預算必須另建 run，不能冒充 resume。
- 中斷或 timeout 後仍有 truth-free partial result/diagnostics；partial 和 complete
  狀態不可混淆。模型重載後的總成本必須保留。

### 5.5 Notebook、CLI 執行與結果回收

- 提供獨立新 notebook 與 metadata，使用 Kaggle CLI 及既有認證。
  授權建立新的 private kernel 與必要 private Dataset 版本；不得覆寫既有
  Trial 001 kernel/Dataset。不得發布為 public 或送交競賽 leaderboard。
- `kernels push` 會啟動執行：只在最終 bound artifacts 與 preflight 通過後呼叫，
  不用 push 當作純上傳測試。記錄 kernel ID、version、job identity 與時間。
- 本機已觀察 CLI 2.2.4；其 `push --help` 有 `--timeout` 與 `--accelerator`，
  沒有新版文件的 `--no-run`。以安裝版本及真實 API 為準，勿假定 flag 可用。
- accelerator 名稱必須查實；NvidiaL4 與 NvidiaL4X1 不能靠字面推定卡數。
  notebook 在開始模型工作前確認真實 L4 x4，失配即結束並回報。
- measured execution 關閉 Internet；依賴需預先取得並綁定版本，不能執行時下載。
- 先做靜態 preflight，再由 notebook 在尚未推論前確認 GPU、顯存、掛載與版本。
  本機 fake runner 不能冒充已通過 L4 runtime preflight。
- 明示 public acquisition 與離線 tests/build/preflight 的界線。
- 回傳 prediction、progress、checkpoint、runtime observations、identity manifest。
  raw output 若保留，須有大小界線且不能含 evaluator truth。
- owner 要求中途不監控：保留 notebook 內部記錄與 deadline，但不輪詢 Kaggle
  status、不串流/反覆下載 logs、不反覆回報未變狀態。優先用可用的 completion
  notification；否則在預定上限後加收尾餘裕做一次完成檢查與 output 下載。
  若仍排隊或尚未結束，回報等待狀態，不能偷偷啟動 polling loop 或第二次 run。
  需要 task 醒來取回時使用 app 原生的單次延後取回安排，不部署背景常駐監控。
- `kernels output` 下載必須綁定已提交的 kernel version（若版本介面不支援，
  以結果 manifest 的精確 run identity 驗證），不能拿同 kernel 舊輸出當本輪結果。
- 本機 quarantine 驗證路徑、檔案集、digest、身分、workload coverage 後才計分。
- 結果分開報告 score、有效生成率、完成率、timeout/OOM、wall-clock、GPU 資源。
  正確率分母不可丟掉 timeout 或未完成的指定 test outputs。
- 不觸發 Trial 001 的 selection、五百分點門檻或 Domain Package builder。

## 6. 驗證與完成定義

開發完成與真實基線完成是不同狀態：

1. **implementation-ready**：離線測試通過；新 notebook、source audit、命令與
   handoff 文件齊全；真實模型身分、依賴、資料缺項明列。
2. **package-ready**：實際材料齊全且靜態 preflight 通過，owner 能按文件執行；
   缺真實 checkpoint、依賴或可用 Dataset 時不得宣稱此狀態。
3. **runtime-verified**：授權的 CLI smoke 完成、下載並本機驗證；所有指定 jobs 有
   terminal records，且至少一個非 fallback 的模型預測為有效 grid。
   同時完整報告所有失败；零有效生成時結論是執行診斷失敗，不能稱可用基線。
4. **baseline-measured**：另行確定 workload 與執行範圍後，取得完整可比較的
   本機評估。smoke 不能替代此階段，更不能宣稱 85% 或 promotion。

必要測試集中在實際風險：

- test-output 評分單位、兩個預測語義、錯誤／缺失結果與完整分母。
- solver 輸入不含 truth、答案 digest 或 feedback。
- fake workers 模擬卡死、OOM、out-of-order completion、重載及總预算耗盡。
- checkpoint 原子性、恢復計帳、重複 job、身分不符、錯誤 GPU assignment。
- result path traversal、錯誤 digest、partial 冒充 complete、submission task 對齊。
- import/test/preflight 不觸發模型載入、網路下載或 GPU 執行。
- Trial 001 retained behavior 與 frozen artifact audits 保持通過。

handoff 前從 repo root 執行：

```powershell
python tools\repository_check.py --all
```

不要求為簡單文件或映射寫形式化測試，不以 mocks 推論模型品質或性能。

## 7. 開發 task 工作順序與回報

1. 讀本計畫、root AGENTS 與 Trial 001 closure，確認工作樹與凍結界線。
2. 完成新模型選擇、NVARC 相容性、checkpoint 曝光與可取得性審查。
3. 依定稿範圍更新必要的現行文件；如需持續治理新模型／硬體／評分邊界，
   只用一份簡短的新 decision 記錄已獲 owner 同意的範圍，不改寫舊 decisions。
4. 實作最小 solver adapter、新評分 profile、觀測與 bounded worker 路徑。
5. 做 offline fake-worker recovery/failure tests，再完成 notebook 與包驗證。
6. 綁定精確材料，執行授權的 Kaggle smoke，完成後下載、quarantine 驗證與評分。
7. 更新新 trial README 作為單一目前狀態，完整執行 repo validation。
8. 回報變更、測試、source 真正使用情況、kernel/version、真實結果或具體缺項。

開發 task 可以先用 supporting artifacts 完成最小流程；不要為一次 smoke
重建通用 scheduler、capability registry、完整 observability 平台或 P3 runtime。
本次 source 適配及單一配置 smoke 不能證明「新模型勝過舊模型」，對照未跑時
必須保留此限制。

外部 task 不自行擴張成第二 solver、prompt optimization、workflow search、RL、
完整 public sweep 或比賽提交；這些由總控根據本輪結果另開工作。
本輪未授權 run 失敗後無上限重提；已提交的失敗作業也消耗 run 與時間預算。
保留獨立 worktree，完成後提供 commit 與驗證摘要，不自行 merge/push。

## 8. 查閱來源

- [NVARC](https://github.com/1ytic/NVARC)
- [NVARC ARChitects 訓練說明](https://github.com/1ytic/NVARC/blob/main/ARChitects/README.md)
- [NVARC submission notebook](https://www.kaggle.com/code/sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue)
- [ARC Prize 2026 ARC-AGI-2](https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2)
- [L4 規格](https://www.nvidia.com/en-in/data-center/l4/)
- [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
- [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [Kaggle CLI kernels 文件](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md)
- [既有 source 冷封存說明](../../archive/README.md)
- [目前 P1 契約](../product/contracts.md)
- [目前 operating model](../development/operating-model.md)

網頁查閱日期為 2026-09-22；精確上游版本與規則快照由實作 task 審查綁定。
