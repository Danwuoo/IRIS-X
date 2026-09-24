# NVARC 完整來源整合與 Qwen3.5-4B 開發提案

日期：2026-09-24。狀態：**owner 已授權階段 1～3（本文件 M0、M1 與融合邊界）；M2～M4 的 GPU/teacher 執行仍是提案**。
依據：owner 希望完整取得 NVARC，以融合式開發及驗證加速完成。
本文件補充既有 reproduction plan；不改寫已執行身份、驗收結果或既有授權。
檢視基準：main `70385f2`，最近開發 `e9048f8`。

## 判斷與交付目標

採用「固定完整來源 → 直接整合可沿用的原碼 → 薄層移植 Qwen3.5 →
與上游差分驗證 → 一套流程分級執行」。已有 IRIS-X transport、compact
material、LoRA reset、結果驗證及 evaluator 可保留，演算法則以可執行的
上游程式為比對基準。每個新實作都必須說明：上游哪個入口可直接用、
為何不能直接用、改動後如何證明一致或明確標示差異。

完成目標是 Qwen3.5-4B 的完整 NVARC 方法移植，包括資料/SDG、compact、
ARC SFT、task-local TTT、候選搜尋與排序、TRM 及聯合候選流程。
這個目標與原 Qwen3 權重、原訓練規模、原競賽成績的完全重現分開記錄。
Qwen3.5 的混合架構需要實際相容性驗證，不能直接套用 Qwen3 的權重、
token IDs、Unsloth 或 Megatron 相容性假設。

## 本次查核發現

1. 已有 NVARC clone，固定 commit
   `846d0198efa752534594e321fc3289fc0a06c657`。來源在先前 51fa worktree
   的 `.irisx/arc-agi-2/qwen35-nvarc/source/NVARC`。
   `git submodule status` 的七筆均為 `-`：**該 clone 的 submodule 尚未初始化**。
   另有獨立 TinyRecursiveModels cache；不可因此宣稱完整來源已可執行。
2. 七個依賴是 ARC-AGI-2、BARC、ConceptARC、MINI-ARC、TinyRecursiveModels、
   h-arc、re-arc。Qwen/TRM 的 Kaggle notebook、外部 Python 依賴、資料、
   checkpoints 也不包含在一次主倉庫 clone 裡。
3. compact pilot 003 已驗證實際 4B 保存/reload、兩個短 task-local LoRA
   steps、四次生成、候選驗證與封裝；2/4 test 有完整候選只是 availability。
   **沒有 ARC-SFT checkpoint，沒有完整 TRM 或真實 SDG 執行證據。**
4. 原 SFT 腳本使用 NeMo-RL/Megatron、四節點、tensor parallel 8、12,716
   steps；TRM README 記錄八 H100 的訓練環境。四張 L4 的短 LoRA 成功，
   不能推論可直接完成原規模 full SFT。DDP 只複製模型，不合併顯存。
5. 過去 kernel 的 mount、optional dependency、JSON 序列化、下載中斷問題，
   應固定成共用流程的回歸檢查；不再為每個新驗證建立一套相似 runner。

## 融合邊界

| 部分 | 開發方式 | 必須留下的證據 |
| --- | --- | --- |
| SDG、資料清洗/augmentation | 優先呼叫上游函式或固定 CLI，沿用 prompts；IRIS-X 接 provenance/split | 上游與整合版逐階段輸入輸出比對、各來源 counts、parents、exclusions |
| SFT | 沿用原資料表示、loss mask、batch/scheduler 語意；先確認 backend 的 Qwen3.5 支援 | 真實 optimizer update、checkpoint resume/export、token/step/記憶體實測 |
| TTT、DFS、rerank | 從固定 notebook 抽取可測函式；保留來源 hash/cell 對照；模型存取集中在 adapter | 固定 logits/seed 的 traversal、prune、votes、NLL/top-two 差分測試 |
| TRM | 直接接 pinned TRM 原碼及 NVARC 訓練/TTT 設定，替換受控 I/O | 真實模型 train/reload/TTT/inference；checkpoint 和資料來源可追溯 |
| Qwen3.5 adapter | 集中處理 tokenizer rows、tied weights、LoRA target、hybrid state、model forward | tiny 真實架構測試與 4B GPU 證據；不可用 mocks 作最終驗收 |
| 執行與評估 | 保留現有 Kaggle transport、ledger、checkpoint、truth-free result、獨立 scorer | 每階段接收前一階段的真實 artifact，雜湊與計數連續一致 |

上游 snapshot 不原地修改；patch/adapters 與 manifest 進 Git，來源材料留在
`.irisx/` 並可由顯式 materialization 重建。新的共享入口重用
`arc_nvarc_cli`、data/training/candidates/trm/runtime/transport 模組。
舊 pilot 程式、已執行 wheel/notebook/package 作為凍結證據保留。
不另建產品框架或通用 plugin 平台。

## M0：補齊完整可重建來源包

- 按固定 commit 取得主倉庫和 recursive submodules，重用已下載內容；
  建立單一 cache 位置，避免依賴某個可刪除 worktree 的絕對路徑。
- 固定 Qwen 與 TRM Kaggle notebook 的精確版本、cell 原文和來源 hash。
  提取函式時只剝離 notebook 安裝/上傳副作用，保留演算法和設定對照。
- 列出 NeMo-RL、TRM、推論套件版本及平台要求；上游未提供的版本記 unknown，
  經相容性驗證後固定整合環境，不能聲稱還原了未知的原始環境。
- 資產 manifest 列出 Dataset/version、大小、hash、用途、checkpoint 架構、
  授權聲明及是否含 evaluation 衍生資料。原倉庫根目錄未找到 license，
  保留 notices；來源取得和內部 adapters 與將來 vendor/公開散布分開處理。
- 完整盤點官方 artifacts、synthetic、augmented、TRM training/evaluation
  與 checkpoint。大型資料按階段取得，現有 4B base/compact 不重複下載。
- 未初始化 submodule、未固定 notebook、必要 material 缺失都使 preflight
  失敗；若某依賴不在所選路徑使用，須留下明確理由。

退出條件：乾淨目錄可重建所選路徑的精確來源和依賴；manifest 清楚區分
「來源齊備」「資料齊備」「模型齊備」。不以檔案存在取代入口可執行。

## M1：先建立上游差分測試與共用入口

建立小型 golden corpus，覆蓋矩形、multi-test、重複候選、空結果、長序列、
augmentation inverse、demo shuffle 與停止原因。兩邊使用同一份資料及 seed。

- 資料表示比對 token symbols、角色、EOS、loss masks、拼接長度；數字 token ID
  因模型不同時用明確 mapping 比對，不要求不同模型 ID 相同。
- 用確定性 fake logits 執行真實上游 DFS 與移植 DFS，比對展開、pruning、
  EOS completion、duplicate votes、shared verification views 和 top two。
- 模型數值測試用 tiny 真實 Qwen3.5：full-prefix 作 correctness oracle；
  若實作 hybrid cache/batching，比對分支互不污染及 logits 容差。優化須報
  每 token/每候選耗時與峰值記憶體，不以存在 cache 就算加速完成。
- Packing 必須處理 attention/混合 recurrent state 的樣本邊界。尚未證明
  隔離正確時保留 unpacked reference，不能直接 concatenation 後宣稱等價。
- 把既有 Dataset inventory、tuple JSON、NaN/Inf、reset、torchao 相容性、
  UTF-8 logs 和中斷下載案例加入同一套 preflight/回歸入口。

退出條件：一份 stage config 可在 offline fixtures、tiny real model、4B
三種 profile 切換，流程入口和 result schema 相同；差異都有可重現測試。

## M2：優先產生真正可用的 ARC-SFT artifact

關鍵路徑是「已驗證 compact → 真實 ARC 資料 full SFT → export/reload → TTT
→ DFS → rerank → evaluator」。SDG 大量再生成不阻塞此路徑；先使用經來源與
split 查核的已發布資料。已知 `arc2_evaluation6` 排除；以 parent 分組切分，
只對 train 做 augmentation。未知來源不可混入 clean 訓練並宣稱無污染。

建議首個 integration profile 固定 16 個公開 training parents：8 train、
8 development，train 最多 128 augmented episodes、8 個 optimizer steps。
確切 task IDs、token ceiling、sequence length 在 materialization 後、執行前
固定；此為工程 profile 草案，不代表足量 ARC 訓練或品質改善。

先實測一個 full-SFT step 的各卡 peak allocation、host RAM、optimizer state、
token throughput。以原 backend 可支援 Qwen3.5 為優先；若不支援，使用經測試
的分片訓練/offload backend，保持訓練語意並記錄差異。實際選型由兼容測試
決定，不再同時維護多條未證實路線。LoRA SFT 若另作資源折衷，必須單列，
不能替代 full-SFT 完成標記。

檢查中斷續訓與連續訓練的 step/cursor/RNG/optimizer 一致性，再輸出帶新
digest 的 ARC-SFT checkpoint。後續 TTT 必須載入它；不能默默退回 base。
SFT 少步數只證明方法可執行；完整 corpus/原 steps 訓練另立規模與用量估計。

## M3：補齊兩個真正的獨立分支

**SDG：** 接通上游十階段，先用保留的 teacher responses 做完整 replay，
讓上游 generated Python 在真實隔離環境運行，驗證 timeout、資源限制、
filesystem/network 隔離與 input/output pairing/filtering。現有 Docker
launcher 測試不能代替 sandbox 執行證據。再以一個預先固定的小批次驗證
真實 teacher adapter（模型、provider、calls/tokens/成本需另固定）。
無 daemon 時安排可用的受控環境，不能退回 host 直接執行生成程式。
已發布 SDG 資料可用於 SFT，但不能記成「我們重新生成」。

**TRM：** 直接安裝固定 upstream dependencies，先完成少步數真實 training、
checkpoint/reload，再用原 TTT/inference 程式處理 visible-only tasks。
明確區分訓練 labels、題內 demonstrations 與 evaluator held-out answers。
原 eval 腳本若混有訓練和真值讀取，抽取同一演算法入口並隔離 I/O。
可先用發布 checkpoint 驗證 inference 接線，但需盤點其 training exposure；
若含 development 資料，結果只能用於工程診斷。
最後將真實 TRM candidates 接到 Qwen verification，輸出各分支及 joint
結果。Qwen3.5-4B + TRM 必須標示為移植組合，不冒充原 2B + TRM 的成績。

M2、M3 共享固定資料/候選/artifact 介面，可分工；不要求每條分支完成後
才做整合。是否啟用多 agent 由 owner 的開發安排決定，本提案不自行派工。

## M4：Kaggle 一次驗證連續流程

採用 prepare → preflight → train → export/reload → adapt/solve → package
→ 本機 verify/score 的連續 stage 流程；持續保存 stage manifest 與 terminal
failure。啟動前可在 CPU 揭露的設定、套件、inventory、serializer 問題先排除。

單卡正確性通過後再驗證四 worker 分工；「看到四卡」不算四卡執行。
比較單 worker 與多 worker 的 task coverage、重複/遺失、state isolation 和
總 throughput。訓練分片模式與推論四獨立 worker 模式分開實測。
正式 TTT rank/長度逐級提高到目標配置；r2 的通過不能驗收 r256。

模型、資料、runtime wheels 分層固定；每次修程式只更新小型 runtime 資產。
先回收 logs、stage summary、checkpoint/result manifest；大型權重以固定
shards 回收，逐檔驗證並可續傳同一 immutable version。已保有且 digest
相同的 artifact 不反覆下載。checkpoint 恢復仍計入同一累積用量。

建議新的開發執行授權以「固定科學配置＋整個 session 用量上限＋可修程式
錯誤」為單位，涵蓋 staging、必要私有 Dataset 更新、push、監測、回收與
本機 scoring，省去每個 JSON/mount 修復都重開一次決策的往返。
**具體初始提案**：Kaggle private/Internet-off/USD 0，最多四個 accepted
kernel versions，每次最多 30 分鐘、最多四 L4，總分配 GPU 時數最多八小時；
失敗與純 staging 也計入上限。所有版本使用獨立身份，固定上述小型資料，
不碰既有 holdout、不做 competition submission、不增加 paid teacher。
此上限只用於第一輪整合診斷，不保證足以完成 full SFT/TRM/SDG 全部驗收。
提交前須依硬體配額及實測可行性固定每 stage tokens/steps/forwards/deadline；
若不足，交付實測預算與缺口，不能悄悄縮小方法後宣稱全完成。
真實 SDG teacher 小批次及完整規模訓練使用另列的精確執行提案。

以上全部是建議的新邊界；Decision 0027 已結束，不能沿用其額度。

## 完成判準與交付

| 層級 | 必須交付 | 不可混稱 |
| --- | --- | --- |
| 完整來源整合 | 可重建來源/依賴/資產 manifest、source map、差分測試 | clone 成功不代表方法完成 |
| 完整方法開發驗收 | 真實 SDG 小批次及 sandbox、真實資料 SFT checkpoint、完整目標 TTT/DFS/rerank、真實 TRM train/TTT、聯合流程與獨立結果驗證 | mocks、短 LoRA、發布權重 inference 均不能代替缺失階段 |
| 有效性與規模驗證 | 凍結 dev 上 base、SFT、SFT+TTT、TRM、joint 的 pass@1/@2、coverage、時數/顯存，完整配置與資料 lineage | 可執行不代表分數提升；小資料不代表原規模重現 |

評分在本機 evaluator，正確答案及 outcome-derived metadata 不進執行包。
工程選型只用固定 development split；既有 holdout 維持封存。比較報告須
揭露 shared training exposure、缺候選及多 test task 的計分單位。

交付一份最新 reproduction matrix：每列有 upstream reference、reuse/patch
說明、真實 artifact、驗證命令、實測及剩餘差異。只有所有方法列通過才可
宣稱完整方法開發驗收完成；環境阻礙須標 partial，不以 tests 數量替代。
開發沿用 owner 偏好的 main、gpt-6-sol/xhigh，每個 milestone 小提交。
handoff 執行 `python tools/repository_check.py --all`，ML 改動另跑 strict
`tools/nvarc_ml_profile.py`；涉及真實來源的差分測試不得 silent skip。

## 來源

- [NVARC](https://github.com/1ytic/NVARC)：三部分方法及 Kaggle 資料/notebook 索引。
- [固定 submodules](https://github.com/1ytic/NVARC/blob/846d0198efa752534594e321fc3289fc0a06c657/.gitmodules)。
- [SFT 執行腳本](https://github.com/1ytic/NVARC/blob/846d0198efa752534594e321fc3289fc0a06c657/ARChitects/run_sft_4b.sh)。
- [TRM 訓練與材料](https://github.com/1ytic/NVARC/blob/846d0198efa752534594e321fc3289fc0a06c657/TRM/README.md)。
- [本機獨立驗收](../../trials/arc-agi-2-qwen35-nvarc/control-review-e9048f8.md)。
- [既有來源對照](../../trials/arc-agi-2-qwen35-nvarc/source-use.md)與
  [reproduction matrix](../../trials/arc-agi-2-qwen35-nvarc/reproduction-matrix.md)。
