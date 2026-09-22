# ARC-AGI-2 DSPy / GEPA prompt pilot

日期：2026-09-22。狀態：baseline-002 的 384 jobs 已完成並回收 result.zip；
owner 已指示連貫進行評分、反思與後續實驗。以下最新連續執行指示取代先前 startup 停止點。
本聊天為總控，實作交給後續獨立開發 task。本文件不延長 Trial 002 的執行授權。

## 最新指示：連續執行至十輪搜尋與最終評估

Owner：「完成並取得 result.zip，下一步就是進行評分與反思等步驟，我希望可以連貫的執行」。
這次指示取代「四卡模型載入後停止」、不評分／不反思／不提交下一輪，以及必須等 owner
逐批通知才能回收的限制。資源與科學比較設定不變，仍是十個 proposer attempts 的上限。

- 延續現有開發 task 與 worktree，先驗證已回收 baseline-002 的 result/outbound identities，
  再本機評分，分列 256 train 與 128 dev；4 個 invalid 仍在分母中，不重跑基線。
- 串接真實 DSPy/GEPA、Codex CLI proposer、candidate staging、private Kaggle 四卡執行、
  完成回收、驗證與評分。每輪依結果更新下一輪，不再停在模型載入或等待 owner 手動交接。
- 可為此實作缺少的 scorer、optimizer bridge、ledger、續行控制與必要依賴，
  更新 execution decision 和過時 stop boundary，直接完成已授權工作，不反覆索取授權。
- 等待遠端執行時只做低頻狀態檢查（例如 2–5 分鐘間隔，錯誤時退避），不持續拉 logs；
  terminal 後取得一次結果。無需新建桌面排程，保持同一有限工作流程持續執行。
- 每一步先保存 ledger（目前 round、parent/candidate、kernel/version、result hash、
  已用 invocation/proposal 數、下一步），任務重啟先讀 ledger，禁止重複反思或提交。
  分開記錄 GPU 執行、反思執行、傳輸與等待時間；使用方案額度，不另問美元預算。
- 十輪結束後僅以 dev 選定 G*，凍結後才做 B1/G* 的 128 題 holdout，輸出完整報告。
  不開 public evaluation sweep、不競賽提交、不延長輪數。
- 可自行修復可逆程式／封裝問題，優先利用 checkpoint 本機恢復、不重跑已有生成。
  若必要輸入缺失、認證／平台配額不可用、證據無法驗證或修復需突破既定工作量，
  保存狀態並清楚回報真正阻礙，不以反覆等待／無限重試掩蓋問題。

本地基線證據：開發 worktree `C:/Users/wurre/.codex/worktrees/e34a/IRIS-X`，
commit `ac6f422`；結果在 `.irisx/arc-agi-2/prompt-pilot/repair-002/recovered-v1/result.zip`，
SHA-256 `4764cd569f669f8736461ddf2b5d6ac3bf1c80ddf3f903d669f8d5a43aa054af`。
所有已失敗身份和本機重建 provenance 保留，不把 recovered result 說成 notebook 原生輸出的 ZIP。

## 已完成的前次交付與停止點（被上述連續執行指示取代）

Owner 原話：「正式開啟新 task 開發並啟動 notebook，確認啟動並模型成功載入後
不監看並停止開發」。此指示界定本次 task 的執行範圍，優先於下方完整十輪路線。

- 使用新的 Sol / xhigh task，從成功 Trial 002 程式增量實作新 trial；完成本機必要驗證，
  source/version pin、split、package 與 technical preflight 後，實際提交基線 notebook。
- 授權完成這次工作所需的來源／依賴取得、既有 Kaggle CLI 認證使用、小型 private
  Dataset 上傳及第一個基線 kernel 啟動，不需再詢問是否可以提交。
- 必須掛載官方 competition，實際取得四張 L4，四個 worker 都成功載入固定 Qwen3.5-4B。
  啟動確認階段可讀 server metadata、狀態與 runtime logs；採適當間隔、不高頻輪詢。
  CLI accepted／platform RUNNING／model_load 開始訊息都不能充當 model loaded 證據。
- runner 在模型成功載入後，記錄 worker rank、GPU identity、model revision 與 ready 事件。
  notebook 的必要 stdout 必須即時可見，不能把 subprocess 輸出全部緩衝到全批結束。
  先讓四卡領取第一組 jobs，之後繼續基線 384 jobs，使用既定佇列排程。
- 收到四個 worker 的成功載入證據後，保存啟動 receipt 並回報；立即停止後續開發與
  外部監看，不等待推論完成、不下載完整結果、不設定排程、不執行反思或啟動下一輪。
  已啟動的 notebook 留在 Kaggle 正常完成基線，不因 agent 停止而取消。
- 若啟動／載入失敗，提供實際錯誤與已用身份；不得宣稱成功，也不盲目自動重提 kernel。
  若無法取得進行中的載入證據，要明確區分「已提交」與「載入未驗證」。

## 問題與已知起點

研究問題：固定 Qwen3.5-4B 與單次推論成本限制，DSPy 管理的 prompt 經過
GEPA 的失敗回饋與 Codex 反思後，能否在未參與改寫的 ARC 題目提升 exact match？

Trial 002 的 `trial-002-smoke-002` 已驗證：4 張 L4，4 次有效生成，
runner 回報 175.427 秒，generation 各 6.579–27.157 秒，峰值約 8.7–9.3 GiB，
但 selected-output exact match 為 0/4。這是執行可行性證據，不能外推全資料集準確率、
長題延遲，或將 175 秒當成整個 Kaggle 排隊／準備時間。

目標 85% 仍保留在整條研發路線；本輪交付是一次可比較的 prompt 改善試驗，
不是 SOTA 宣告、Domain Package promotion 或競賽提交。

## Owner 已確定的設定

- 解題模型固定 `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`。
- Owner 已指定反思使用 Codex CLI 的 `gpt-5.6-sol` / `xhigh`，
  並將資料規模擴大為 256 optimization-train + 128 selection-dev。
- 2026-09-22 owner 指定先做十輪反思：最多十個 proposal attempts，
  每輪一次 `codex exec`，無效或失敗的 attempt 也計入十輪，不另開隱藏重試。
  模型可用性須在開發時核對，不可默默更換成其他系列。
- Owner 指定 GPU 時數暫時不限，移除先前兩個 session、60/120 分鐘與總 GPU-hours
  的提案上限。平台 session 限制仍以實際環境為準；以 checkpoint 分批完成，不能假設
  一個 session 可以無限執行。每個 solver job 暫保留相同 300 秒 timeout 作公平比較設定，
  不是整輪 GPU 配額；token 與 generation 次數上限仍固定。
- Codex 使用方案使用量，不另設美元預算或美元核算關卡；不再要求 owner 回答計費問題。
  必須記錄每次執行與整輪反思的 wall-clock time。CLI 已提供的 usage 可附存，
  但不是執行前置條件；不將方案使用量寫成 API 美元成本或免費推論。
  反思取消先前提案的 15 分鐘硬停止，以十次 attempts 與有限輸入控制工作量。
- 繼續採 private Kaggle、L4 x4、Internet disabled；不持續拉 logs，不設回收排程，
  回收節奏依最新連續執行指示，允許低頻完成檢查與自動接續；無隱藏重試。

## Owner 指定：從成功實作增量開發

2026-09-22 owner 要求盡量沿用上次成功運行的程式，減少除錯及上傳等待，
並明訂官方 ARC Prize ARC-AGI-2 competition 掛載與四卡排程為必要條件。
實作基準是已驗證 commit `5388197c87a08b690ba077c1bfefd335acbb2f4b`，
對應 `trial-002-smoke-002` 的成功執行及本機 result verifier 修正。

優先保留以下已跑通的路徑與實作，僅在新 trial adapter 做必要擴充：

- `src/irisx/kaggle_runner_trial002.py` 的模型載入、native chat template、
  單次 generation、parser、hardware preflight、multiprocessing 及結果輸出流程。
- `src/irisx/arc_trial_002.py` 的 materialization、staging、封包 digest、
  invocation 記帳、quarantine、scoring 與合法 progress stage 驗證經驗。
- `trials/arc-agi-2-baseline/kaggle-notebook.ipynb` 的 offline wheel 安裝、
  competition mount、模型查找與 runner 啟動流程，以及成功 metadata 設定。

本輪必要差異限於：可參數化 instruction、更多 jobs、每 GPU 常駐 worker 的迴圈、
新 trial 身份／資料分組、DSPy/GEPA 本機 adapter 與 Codex proposer。
不趁此換推論 engine、CUDA/Transformers 基礎版本、模型量化或重建 transport framework。
共用的純函式可小幅抽取，但不得改變 Trial 002 已執行 bytes、身份與歷史驗證結果；
新行為用新 module/config/run identity，避免直接把舊四次 invocation quota 放寬。
DSPy、GEPA 與 Codex 留在本機控制端，Kaggle 接收已凍結的 prompt/jobs，
不為了 prompt optimization 把整套新依賴加入已成功的 GPU 環境。

### 官方競賽掛載及執行驗證

每個新 notebook 均沿用成功組合：

```json
{
  "competition_sources": ["arc-prize-2026-arc-agi-2"],
  "machine_shape": "NvidiaL4",
  "enable_gpu": true,
  "enable_internet": false,
  "is_private": true
}
```

官方競賽來源必須在 `competition_sources`；自己的模型 transport Dataset
放在 `dataset_sources`，兩者都需掛載，不能以後者取代前者。
沿用成功 CLI accelerator 與 staging 路徑，核對提交後 server 保存的 competition source、
machine shape、private/Internet 設定及實際 kernel ID/version，不只檢查本機 JSON。
啟動後、載入模型前，沿用 PyTorch 與 nvidia-smi 雙重檢查：恰好四張 NVIDIA L4，
每張至少 22,000 MiB；讀取明確綁定的 competition challenge 檔並驗證 digest。
不符合即保留失敗證據並結束，不降級成單卡／雙卡跑全批。

### 四張卡都排程

把成功 runner 的「四個 worker 各做一題」增量改成「四個常駐 worker 持續領取 jobs」。
每個 worker 綁定不同 GPU 0–3，各載入一次相同模型；不把 4B 模型分片成四卡合跑一題。
先讓四張卡各收到一個基線 job，之後由 parent 動態派發給空閒 worker，避免靜態分四份
造成長題拖住單卡、其他卡提早空等。只剩不到四個 jobs 的尾段可以自然閒置。
Holdout 配對 jobs 作為同 GPU 的排程單位，同一對內 B1/G* 次序預先交錯。

每筆記錄 worker rank、physical GPU UUID、job ID、start/end、terminal state；
回傳每卡 job 數、模型載入次數與 job-active seconds，並驗證足量待處理 jobs 時四個
worker 都收到工作。job-active seconds 不冒稱硬體 GPU utilization；沒有採樣就不填。
worker 失敗不得靜默減少卡數完成整輪；保存 checkpoint 與診斷，未完成分母保留。

### 縮小上傳與除錯範圍

沿用已上傳的模型／offline dependencies Dataset 與其實際版本、hash；
模型 9 GB 級檔案不因每次 prompt 改寫而重新下載、打包或上傳。
新 trial 建立獨立的小型 runtime/outbound Dataset：穩定 runner wheel 只在程式變動時更新，
後續各輪主要傳新的 prompt、jobs manifest 與 identity binding。
若平台會重傳整個 Dataset，讓小型 Dataset 的完整內容仍保持小，不假設平台支援增量上傳。

舊 transport Dataset 可能仍有舊 outbound/wheel。新 notebook 必須明確綁定
模型來源與新 runner/outbound 的路徑、檔名和 digest，不能用第一個 `rglob` 命中結果
選到舊 trial 封包；只安裝指定版本／hash 的 wheel。模型保持相同 bytes，
不需要為了拆 Dataset 先重傳模型建立一個理想化的新目錄結構。

先在本機對「實際要上傳的 staging 內容」做 offline preflight：metadata、
notebook imports、offline dependencies、mount/path selection、digest、四卡 dispatch、
多 job queue、timeout/checkpoint、result round-trip，以及舊成功 result 的 verifier 回歸。
scheduler 測試使用四個 fake workers，驗證派發與中斷、不在測試裡呼叫 GPU／外部模型。
不新增獨立 GPU smoke 反覆上傳；基線批次最先派出的四個真實 jobs 同時作整合檢查，
結果直接計入基線 384 次，故不增加暖機或隱藏 generation。

## 本輪只變動 instruction

使用一個 DSPy predictor：`demonstrations + query_grid -> predicted_grid`。
輸入仍是目前的 digit-row representation，輸出仍由相同 deterministic parser 處理。
只允許 GEPA 修改 instruction 字串，不改模型、tokenizer、parser、demonstrations、
解碼參數、output schema、測試題或答案。

| 組別 | 用途 | 推論設定 |
| --- | --- | --- |
| B0 | Trial 002 原始 prompt 的新工作負載基線 | greedy、512 output tokens、thinking disabled、一次生成 |
| B1 | 封裝成 DSPy 後的相同基線 | rendered messages 和 token IDs 必須與 B0 完全相同 |
| G1–G10 | GEPA 各輪反思提出的 instruction | 除 instruction 外，與 B1 完全一致 |
| G* | 搜尋結束後僅根據 dev 選出的候選 | 封存後才進行 holdout 評估 |

B0/B1 先用離線 render/tokenization parity 驗證；通過即可共用同一份真實生成，
不為 framework 包裝重花 GPU。若 parity 不成立，先修 adapter，不把差異歸因 GEPA。
首輪不用 ChainOfThought 多段呼叫、self-repair、TTT、LoRA、NVARC augmentation 或 ensemble。
若 512 tokens 系統性截斷，記錄並結束此設定，另開同時調整兩組 token budget 的比較。

## 資料隔離

從固定官方 public-training source，按 task ID 分組，預先凍結 owner 指定的
256 optimization-train、128 selection-dev；設計另保留 128 locked-holdout，合計 512 題。
現有 source contract 的 public-training count 為 1,000；實際 materialization 後
仍須確認排除 smoke、重複題後數量足夠。不能挪用 public evaluation 補足數量。
每題只取 test index 0，故本輪是 selected-output pass@1 pilot，不冒稱完整 ARC 分數。
其他 test inputs、題目的 augmentations 和近重複題不得跨組。

選題使用固定 seed、task ID hash 排序與事先寫定的輸入尺寸／demonstration 數分層，
不能根據答案、B0 是否解對或人工判斷難易挑題。排除已看過的四個 smoke 題；
重複／近重複檢查以可見 demonstrations、test inputs 做，規則與排除項列入 manifest。

- train：可用 ground truth 產生 deterministic feedback，提供 GEPA 反思。
- dev：只用 exact-match 分數做 candidate 選擇，dev 答案／失敗細節不傳反思模型。
- holdout：只在 instruction 與 dev 選擇結果凍結後本機計分，不用於改寫或挑 candidate。
- ARC-AGI-2 public evaluation 完整保留作後續里程碑；首輪不消耗它。
- 分組乾淨僅指專案的改寫與選擇流程，不能宣稱基礎模型預訓練沒有看過公開 ARC。

Kaggle solver 的 outbound 仍只有可見 task demonstrations 和 test inputs。
所有 evaluation truth 留本機 scorer。Codex 僅收到 optimization-train 的案例／生成／回饋，
不放在可讀取整個 repo 或 holdout 的工作目錄中。這是新的訓練回饋資料流，必須在
新 trial 的執行決策中明訂；不得套用 Trial 002 的 truth-free runtime 名稱掩蓋它。

## 十輪相依搜尋與一次最終驗證

1. **本機離線準備**：凍結 split、B0/B1 parity、package identities、budgets；
   驗證真實 DSPy / GEPA imports、adapter、重放與停止路徑，測試本身不呼叫模型。
2. **Kaggle A**：B1 在 256 train + 128 dev 生成，共 384 次 Qwen 呼叫。
   四個 persistent workers 共用任務佇列，每 GPU 一個模型，不為每題 reload。
3. **第 r 輪本機反思，r = 1…10**：回收並驗證上一批結果，scorer 產出 train feedback。
   DSPy GEPA 依凍結 seed 與 per-example frontier 選 parent，再選最多三個 train traces，
   透過 Codex CLI proposer 產生 Gr；保存 parent、instruction diff、failure hypothesis、
   預期改善與 prompt hash。不是事先平行產生十個互不相依的 prompt。
4. **第 r 輪 Kaggle 評估**：合法、未見過的 Gr 在同一 256 train + 128 dev 生成，
   每輪至多 384 次。回收後使用 cache 完成 GEPA 的 minibatch 比較、接受／拒絕與
   frontier 更新，再進下一輪。退步的 child 不覆蓋目前最佳 candidate。
   無效 instruction 記錄拒絕；相同 instruction 復用既有結果，不啟動重複的 GPU 工作。
5. **凍結選擇**：搜尋結束後，僅根據 dev 從 B1 和 GEPA 合法接受的候選選 G*。
   同分先保留 B1；若只有新候選並列，再用預先固定的短 instruction、較早出現順序裁決。
   保存 candidate hash 與選擇紀錄後，禁止再反思改寫。
6. **獨立 holdout 批次**：B1 與 G* 各跑 128 題，共最多 256 次。
   兩組同 GPU／設定、預先固定且交錯的配對排程；回收後本機計分。
   若 G* 就是 B1，只需 128 次共同基線生成，回報未選出改善候選，不製造兩組獨立結果。

完整上限為 `384 + 10 × 384 + 2 × 128 = 4,480` 次 Qwen solver generation，
十次 Codex proposer attempts。若每批各用一個 kernel，為十二個邏輯批次：
一個基線、十個候選、一個 holdout。平台限制可能要求把同一批切成多個 session；
每個 transport 身分獨立，分批不增加 logical jobs、反思輪數或 generation 配額。

GPU 不設總時數上限不等於沒有工作範圍。每次啟動、失敗、timeout、截斷皆入 ledger，
中斷且已開始的 invocation 不自動重跑；checkpoint resume 只排尚未開始的 job。
若需重跑已消耗的 job，另列修復需求，不能藏在上述成功數量中。
先用完整基線的 input tokens、generation 長尾、timeout 與 worker 使用率估算後續耗時，
不以四題 smoke 平均值保證吞吐，也不臨時挑短題完成後宣稱全量比較。

十輪是搜尋上限，不是十個必須全都進 Kaggle 的新 prompt。資料／執行錯誤需先修復；
若僅一兩輪 dev 無改善仍繼續既定搜尋，避免稀疏 exact-match 提早終止。
到第十輪即結束，不自動延長為更多輪；所有案例已解對或無可用反思資料時可提前完成。

Kaggle 斷網、Codex 在本機反思，故每輪有「回收 → 本機反思 → 下一批提交」的交接。
依最新連續執行指示低頻檢查完成並回收，不新增桌面排程。
報告要把 GPU 執行、反思執行、上下載與排隊時間分開；
不能把人工交接等待歸為模型慢，也不能只報 generation 秒數掩蓋整輪周轉時間。

## 控制反思模型的壓力

256 題 train 是可供分析與抽樣的資料池，不是每次反思的上下文。先以 deterministic
本機程式產出 parse、形狀、顏色／位置、截斷、timeout 等錯誤統計，再由預先固定的
train-only sampler 選最多三個有代表性的失敗案例，避免三題都是同一類錯誤。
抽樣規則、seed、被排除與選中的 case IDs 均記錄；若使用自訂 sampler，明列為 GEPA 適配。
跨輪優先覆蓋尚未用過的失敗類型與案例，只有 parent 預測／回饋實際改變才優先重訪。
十輪最多三十個案例呈現槽位不代表看過全部 256 題；報告唯一案例覆蓋率。

每次完整 proposer 輸入（指令、parent prompt、統計、案例與 feedback）最多 32 KiB UTF-8，
摘要最多 2 KiB。案例超出剩餘容量時以固定順序減少案例數或選下一個可容納案例，
不能截斷 grid 冒充完整案例；排除的大題列入 coverage limitation。
Codex 輸出結構化的短診斷與 instruction；instruction 最多 4,096 字元，且
以固定 Qwen tokenizer 驗證最多 512 tokens，超限就拒絕，不再次要求模型修稿。
這些是資料大小與產品 prompt 限制，不冒稱 Codex 內部 reasoning token 硬上限。

只傳 train 的聚合統計與選中案例，不傳 128 題 dev 的 trace 或答案。
每次反思使用獨立最小上下文；parent instruction 加摘要即足夠，不累積整條聊天、
全部 raw logs 或前代完整反思紀錄。相同模型、輸入與設定以 hash cache 復用回應，
重放不消耗新的反思額度。每次報告輸入 bytes、耗時與接受／拒絕結果，usage 有值才附存。

## 真正使用 DSPy / GEPA

實作採固定版本的 `dspy.GEPA` 與可注入的 instruction proposer，不能只有名稱或自寫
「叫模型改 prompt」而宣稱 GEPA reproduction。使用真實 parent selection、
per-example frontier、reflective mutation、minibatch acceptance 與 dev selection，
報告上游預設和本次分批適配的差異；十輪整體收益不能直接證明每個機制各自的效果。

本機 optimizer 使用 identity-bound Qwen request/result cache。缺少真實 prediction
就輸出 pending batch，停止並保存 state；不合成 response、不連線呼叫 Qwen API。
每批回來後以固定 seed、固定 proposal cache 重放／續行同一 trial。
若上游沒有合用的 checkpoint API，用薄 adapter 做可測的重放，不宣稱上游原生支援。
使用 fake backend 測試「重放不再呼叫 Codex、不重複 GPU 請求、正確 parent/selection」。

GEPA 設定採明確的 metric budget，不用不可見的 auto 搜尋額度；
reflection minibatch 上限 3、`use_merge=False`、`track_stats=True`。
開發時依被 pin 版本的計數語意與離線 mock trace 推導並凍結 `max_metric_calls`，
不可沿用舊 40 題提案的 96 次額度，也不拿重複的 feedback callback 當新 generation。
另有獨立全域上限：最多 4,480 solver calls、十個 proposal attempts、十二個邏輯批次。
總 GPU 時數不設 owner 上限，平台 deadline 由 checkpoint 處理；
metric calls 不能當成 GPU calls 或 CLI turns。
本輪先不加入消融實驗，沒有數據支持時不能聲稱反思或 Pareto 機制各自造成收益。

Metric 的主分數是整張 grid exact match 0/1。Train feedback 另提供 parse error、
尺寸差異、顏色／位置錯誤摘要及截斷狀態。cell accuracy 只作診斷，不能把大量背景格
正確算成解題成功；不使用 Codex 主觀打分取代 deterministic scorer。
輸出 instruction 禁止題號 lookup、整張答案硬編碼及新增工具／程式碼執行。

## Codex CLI proposer

本機已只讀確認 `codex-cli 0.147.0` 支援 `exec`、`--model`、`--json`、
`--output-schema`、`--output-last-message`；未測試任何付費模型呼叫。
Proposer 用專用最小資料目錄與 read-only sandbox、結構化 JSON response，
不繼承會附帶無關資料的 task 歷史／MCP／hooks；開發時驗證實際生效設定與可見檔案邊界。
只授予 prompt 改寫所需資料，禁止 repo 操作、web 搜題、Kaggle 操作和工具輔助解題。
每次記錄開始／結束時間與 elapsed seconds；失敗與中斷也消耗一次 proposer attempt。
CLI 一次 exec 可能包含多個內部 model turns，報告名稱使用「一次反思執行」。
記錄 model、reasoning、CLI version、輸入輸出 hash、wall time、exit status，
usage 欄位有值就保存、沒有則 unknown。不估算美元費用、不增加費用批准關卡。
無效 JSON／方案額度不足不自動重試或換模型；保留狀態，後續仍受十輪總數限制。

## 如何使用既有 sources 與日後更新

| Source | 本輪具體責任 | 驗證產物 |
| --- | --- | --- |
| DSPy | Signature / predictor / instruction 與 GEPA bridge | render parity、serialized program、adapter tests |
| GEPA | trace feedback、mutation、minibatch 比較、candidate selection | parent/child lineage、scores、proposal cache、accept/reject |
| SPEX | 配對比較與資源／證據記帳 | 每題 win/loss/tie、accuracy vs cost report |
| VANTA | 中斷、重放、不重複扣額／提交 | kill/replay、budget exhaustion tests |
| EIDOS | 區分觀測、推論、未知與 exposure | claim/evidence 對照、污染標記 |
| NVARC | 保留已驗證的 grid rendering / worker 經驗 | 本輪不加入 TTT 或資料增強，避免混淆變因 |

Archive `archive/pre-product-transition-2026-09-17` 只讀，原始 registry
`corpus/sources.yaml` 的 DSPy tree `824de62cb23e2bf8b52adcb05a8804ef2c148e5d`、
GEPA tree `eb66cc8bf0cdf9e7d3d25cf9f26ab0fd951bb833` 是本地 lineage，
其 upstream revision 仍 Unknown。開發 task 必須比較 archive 實際相關檔案與選定上游版本，
在新 trial source-use 記錄 exact file paths、mechanism、採用／不採用原因與測試，
不能只列 source 名稱。實際執行依賴另 pin release/commit、wheel digest 與 license。
不還原 legacy roots、不從 archive import runtime。

日後新方法先寫 source delta 與一個可反駁的假說，再用固定小 dev workload 和同額
generation budget 比較；本輪 pin 不隨 main branch 浮動。已打開的 holdout 成為已用證據，
下一輪不能反覆調整後仍宣稱它未見。公榜里程碑使用另外凍結的較大 evaluation。

## 結果與停止條件

交付每輪 parent/child、train/dev 曲線、B1/G* holdout 配對表、exact-match
numerator/denominator、wins/losses/ties、valid/timeout/OOM/truncation、tokens、
median/p95 latency、peak VRAM、Qwen 與 Codex 各自執行時間，
以及 prompt、split、source、runtime、result identities。

僅當 dev 選中新候選 G*，且 holdout 的 net wins > 0、沒有新的 invalid／timeout、
兩組採相同每題 generation 設定，才標記「值得擴大重驗」。128 題的一題是 0.78125 個百分點；
不能因分母擴大就宣稱統計穩健或泛化成功。報告配對不確定性與具體失敗，禁止只報勝例。
這是後續研究建議，不變更既有產品 acceptance / promotion 門檻。

十輪結束後若兩組均零分、無改善、退步或僅 train 改善，停止擴大同一 prompt search，
保留負結果；不以單輪失敗判定整體方法無效，也不把十輪成功歸因到未做消融的機制。
下一個假說再考慮 reasoning token budget、program synthesis 或 NVARC TTT，
每次獨立比較。執行未完成則回報 partial/inconclusive，不能只用完成子集算總準確率。

新開發 task 的第一個 handoff 是離線可執行實作、sources audit、split manifest、
執行時間估算與 preflight。將 owner 本輪已給的模型、資料流、十輪、GPU 不設總時數
與方案使用量指示記錄在新的 execution decision 及 trial/run IDs，不重問已定的資源選擇。
正式執行必須使用新 trial 並通過技術 preflight；Trial 001/002 的身份與結果保持不變。

## 參考（2026-09-22 查閱）

- [DSPy GEPA 實作](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/gepa/gepa.py)
- [DSPy GEPA proposer](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/GEPA/GEPA_Advanced.md)
- [GEPA 官方程式](https://github.com/gepa-ai/gepa)
- [Codex 非互動模式](https://learn.chatgpt.com/docs/non-interactive-mode?translationFallback=zh-Hant)

以上動態文件是設計參考，執行前仍需 pin 實際依賴；不是已完成的實驗證據。
