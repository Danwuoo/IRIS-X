# IRIS X Stage 4 首個本地實作任務草案

本文件是供使用者醒後審閱、手動轉交總控的任務規格。研究完成不代表此任務已派發或獲執行授權。執行前由總控依最新本地狀態確認範圍。

## 任務

使用 GPT-6.1 Sol / xhigh，在使用者指定的 IRIS-X 本地工作環境，完成 Stage 4「可比較、可診斷的最小實驗基礎」。這次只做離線程式、合成 fixture 與測試，不執行真模型、訓練、Kaggle、付費 API/GPU、上傳、提交或發布。目標仍是官方 Kaggle ARC-AGI-2 分數嚴格大於 85；這個任務本身不產生任何官方或真模型分數。

固定研究基準：
- Repo：https://github.com/Danwuoo/IRIS-X
- SHA：6e04ee3cfcb8ebc3a43e7cff5ac32baf808dd08f
- Brief：research/stage4-arc-agi-2-research.json
- Canonical ARC-AGI-2：f3283f727488ad98fe575ea6a5ac981e4a188e49
- NVARC lineage：846d0198efa752534594e321fc3289fc0a06c657
- 實測模型：sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1；不要替換成 Qwen3.5-4B。

先讀 RESEARCH_REPORT.md、EXPERIMENT_BACKLOG.json、此 prompt，以及本地 AGENTS.md、當前 Stage 4 handoff、最新工作樹與測試結果。Brief 說 Stage 4 foundation 曾在進行中；研究快照看不到那份 WIP。請先列「已實作／尚缺／衝突」，只補缺口。記錄研究 SHA 與實際 HEAD。若 HEAD 是後繼，可在保留現有變更下進行；若不是相容後繼、出現他人同檔未完成修改或工作目錄不清楚，停止並問總控。不得 reset、覆寫 WIP 或恢復已消耗的舊執行權限。

## 已知事實

現有 BASE-30 為 5/172 pass@2、32/172 有候選、pool oracle 6/172；TTT128-30 為 10/172、54/172、oracle 11/172，parent wall 約 6.119 倍。這是 NVARC public variant，非 canonical 120 tasks/167 tests 的新實驗，也不是官方分數。TTT 已完成每題 128 updates 且 reset 驗證通過；search 與 verification 各自時間目前未知。程式讓 search 截止在 test-start +20 秒、verification 可到 +30 秒，但驗證插在 generation batches 之間，共享已流逝的時間。保留池完美重排僅可能多救一個 test/profile。

官方 submission 56840442 為 Notebook Threw Exception，public/private scores 都是 null。私有 preview 成功不代表 hidden rerun 成功；根因未知。不得寫成零分、逾時確診或已修復。

## 最小差異範圍

1. Canonical source identity 與資料邊界
   - 重用現有工具，明確區分 canonical、variant、source-matched projection、private preview、official hidden。
   - 保存 challenge source commit、原始與正規化 digest、task/test counts、demo digest、test-input ordering 與來源角色。
   - Runtime 只接受 demonstrations 的 input/output 與 test 的 input。Test output、evaluator label、oracle/pass@2、按答案衍生的路由標籤不得進 solver、scheduler、checkpoint 或 outbound。
   - 不在本任務下載資料或權重。需要已存在且授權的 canonical challenges 時，僅讀現有材料；若沒有，使用合成 fixture 完成介面並將真資料 gate 標 blocked。

2. Phase telemetry 與預算契約
   - 在現有 public/runtime adapter 上加最小欄位；保持預設 solver 行為、模型、TTT schedule、DFS threshold、augmentation、score_kgmon 不變。
   - 分開 generation／verification／parse-dedup／training／reset／load-export 的 wall timing、forward reservation/completion、tokens、候選生命週期。GPU 使用非同步執行時，記計時語義與同步策略，不把未同步 host timer 冒稱 GPU kernel 時間。既有 training phase 含全梯度掃描、同步和 ledger IO，native checkpoint flags實際為True；不得按paper敘述改成False。保留所有安全／證據gate，先量其成本。
   - 候選counter分raw returned、processed（含duplicates/invalid）、parsed unique、verification started／half／fully verified、ranked；保留votes multiplicity。原64cap是processed sequences層。
   - 熱路徑避免新增每 token fsync 或隱性 CUDA synchronize；詳細 profiling 必須顯式開關。`timing_unknown` 用 null，不以 0 代替。
   - 以 fake clock 和 fake model 測 search deadline、verification deadline、父子 watchdog、未完成 forward、candidate verification 只完成一半等邊界。合作式 deadline 與 hard parent deadline 分欄。
   - 只準備後續實驗配置：先量 phase cost，再比較相同總 test budget 下候選生成與驗證分配。不要在此task改正式方法、跑real model或聲稱改善分數。短TTT計畫須固定128-step scheduler horizon與sampler prefix，不能僅把max_steps改64而讓Trainer重算LR。

3. 完整輸出與故障證據
   - output-valid、notebook-exit、evidence-qualified、promotion四個結果分開測。合法檔仍可能伴隨unhandled exception，不能據此保證Kaggle能評分。
   - 驗證所有 actual task IDs、每題多 test 順序、每個 output 恰有 attempt_1/attempt_2、1..30 矩形整數 0..9。
   - 核對既有checkpoint的原子寫入，補working-root submission copy與exporter的交易邊界；generic write_new是exclusive-create+fsync，不能把它或copyfile當原子替換。加入 late task、首個 test timeout 後後續 test、worker crash、OOM-like exception、缺 dependency、export 中斷、disk-full-like write failure 的合成負例。
   - 保留上一份完整且合法的輸出；model／duplicate-first／constant fallback 獨立 audit，不把 filler 說成模型候選或成功。
   - 如研究建議的「提早寫 fallback submission」需要改動既定 promotion／strict evidence 契約，本 task 只寫未啟用的測試與差異說明，不擅自放寬 gate。
   - 對 official failure 建立 evidence checklist，只記需取得哪個 phase/traceback/hardware/input-digest/exit-code，不查 Kaggle，也不虛構 hidden 根因。

4. 可讀實驗計畫
   - 輸出一份機器可讀 canonical 受控小實驗計畫，包含一個 changed factor、固定 controls、task-level dev/confirmation partition（探索共用24dev，選定final configuration後才一次解鎖96confirmation，不能多實驗重複使用）、有限預算、artifact hashes、accept/kill/stop criteria。
   - 這是 plan，不是 dispatch；所有真模型與外部執行標 requires_owner_authorization。
   - 公開 checkpoint 已有 public-eval descriptions／validation exposure，歷史專案也已評分同120tasks，故96task lock僅限制Stage4之後的選模，不可命名為專案／模型未曝露freshholdout。Bootstrap按task重抽後重新計sum(correct)/sum(tests)，不要改成task-macro。

建議先檢視的既有模組：tools/nvarc_public_eval.py、tools/nvarc_public_eval_runtime.py、tools/nvarc_public_eval_parent.py、tools/nvarc_native_multitask.py、tools/nvarc_native_solve_runtime.py、tools/score_nvarc_public_eval.py、tools/nvarc_official_adapter.py、tools/nvarc_official_parent.py、tools/nvarc_native_export.py、tools/arc_kaggle_submission.py，以及對應 tests。若 WIP 已提供功能，沿用，不另造平行 framework。新增 solver interface 應延後至需要不同 solver 時。

## 本地驗收

- 針對上述 source／denominator／truth isolation／timing／failure lifecycle 的合成測試通過。
- 至少含 unequal multi-test counts、test-order 改變、extra/missing ID、duplicate JSON key、bool-as-int、NaN、invalid shape/color、truth-field injection、partial verifier、deadline before/after reserved forward、unlaunched task 等負例。
- 預設行為若變化，需逐項列出原因與測試，不能宣稱「純 telemetry」卻改 solver。
- 先檢查suite是否觸發真模型權重、GPU forward或訓練；若超出本task synthetic/fake範圍，列blocked並問總控，不在test名義下越界，也不冒稱全suite通過。依repo指令執行適用focused checks及python tools/repository_check.py --all；記錄 passed/failed/skipped/never-run。舊快照有 523 tests、2 failures、1 skip，只能當歷史，不能沿用為今日結果；不得刪 owner ZIP 或改歷史 acceptance 讓檢查變綠。
- 測試預算建議：使用已授權本地CPU、不新增外部服務費、單次完整檢查最多 20 分鐘，整體 CPU 測試最多 60 分鐘；如現有完整 suite 合理需要更久，先報實際原因給總控，不取消必需驗證。無 GPU memory 或權重需求；用 synthetic/fake backend。

## 交付

- 簡短 implementation summary：HEAD、改動檔案、與現有 Stage 4 WIP 的接合差異。
- 驗證記錄及新 experiment plan JSON，列明未執行項與未知數。
- 給總控的下一個有限 GPU／官方 run 提案：item/provider/hardware、次數、最長時間、quota 與 USD ceiling、資料與 artifact bindings、禁止自動 retry 的停止條件。不要自動執行。此提案暫以2026-10-05取得的官方條文（12h、L4×4 aggregate96GB、no Internet）規劃；Kaggle文字索引有約2週延遲，action-time須另核，load/export/cleanup都算總時間。
- 不 commit、push 或 publish，除非總控轉交的明確使用者授權另有涵蓋。

## 停止與詢問條件

當離線交付與驗證完成，即停止並回總控。任何 real model/訓練/Kaggle save-run-submission/retrieval、paid compute/API、資料或權重取得、上傳／分享、未解 checkpoint／code／dependency／synthetic-data／最終release各層license的複製發布、改驗收門檻、重用 frozen identity、碰觸未授權工作樹，都先停止並請求該具體權限。預算時間經過不是批准，公開分數提高也不是官方 >85。
