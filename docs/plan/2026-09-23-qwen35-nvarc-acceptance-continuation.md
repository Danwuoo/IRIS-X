# Qwen3.5-4B NVARC 驗收後續開發計畫

日期：2026-09-23。驗收基準：main
`e7d74a68d4975e728a4a20cdf46d35dadaf1cda0`。
結論：**尚未通過完整開發驗收，回原 task 繼續實作**。

本計畫補充[原完整計畫](2026-09-23-qwen35-nvarc-reproduction.md)，不取代
既有產品、資料、執行邊界。[驗收報告](../../trials/arc-agi-2-qwen35-nvarc/control-review.md)
保留重現方式、驗收基準與本機證據。先前完成的程式與通過測試保留，
不得以重寫整個平台取代缺口修復。

## 1. 續作位置與交付方式

- 原 task：`01a0cca1-174b-7e61-9fcb-90324664709d`，
  **在 main 繼續 Qwen3.5 NVARC 開發**。
- 模型與 effort：`gpt-6-sol / xhigh`。
- 工作目錄：`C:/Users/wurre/Desktop/IRIS-X`，直接在 `main` 做小型 commits；
  不新增 task、worktree 或開發分支，不自行 push。
- 先讀本報告與原計畫，再核對最新 HEAD 和工作樹；不要覆蓋其他人的未提交變更。
- 連續完成以下可獨立完成的本機工程工作。遇到單一依賴阻塞時記錄確切原因，
  接著完成其他項目；不要只更新 gap 文件就宣告本輪完成。

## 2. R1：先修驗證邊界與材料身份

### Outbound schema

為 inference workload 建立結構化驗證：train demo 可有 input/output，test
僅有准許的輸入欄位。拒絕 test output、額外 truth/answer-derived metadata，
也驗證 task/test 身份、唯一性、grid、config 與 binding 的一致性。
不能只在正常 builder 刪欄位，必須在獨立 verifier 也拒絕重算合法 hash 的
惡意或誤建封包。訓練標籤留在獨立的 training artifact。

### Result/checkpoint semantics

要求 result 的 checkpoint 已完成，且所有指定 task 都有一致的 terminal
record；失敗 task 可以是 terminal，但不能把 pending 當完成。核對身份、
完整 task/test 分母、狀態與候選規則、nonnegative typed counters、reservation
和實際呼叫紀錄。不允許將缺 task、重複 task、錯誤分母或倒退計帳合法化。
Resume checkpoint 與可交付 result 的規則要分清楚。

### Model material

拒絕空清單、重複/不安全 path、缺必要 config/tokenizer/weight members、
index 與 shards 不一致，以及可被 loader 讀取卻未列入 manifest 的檔案。
依實際支援的格式定义必要集合，不把某一種 checkpoint 排列硬套所有格式。
處理 symlink/path escape；converter 先驗證原始基底材料和 tokenizer，
再產出 derived identity，不接受無法驗證的 caller-provided digest 作為證據。

驗收：三個已重現 P1 反例都必須拒絕；合法 fixture、完整失敗紀錄、
合法 checkpoint resume、支援的 tied/untied 和 shard 格式仍通過。
新測試驗證真實輸入/輸出邊界，不寫鏡像常數測試。

## 3. R2：建立可重做的 CPU ML 驗證環境

本機 Python 3.12.10 已有 torch：
`C:/Users/wurre/AppData/Local/Programs/Python/Python312/python.exe`。
驗收者已用它通過原先被 skip 的 SFT/resume test。預設 Python 3.14 缺 torch
不能再被當成整台機器的阻塞原因。

建立獨立、可重做的 optional ML dependency profile，記錄 interpreter、版本、
安裝/離線 cache 使用方法與測試命令。先檢查既有環境/cache；不要為了測試
下载真實權重或改動共享全域依賴。必要的外部依賴取得若受政策限制，記錄
缺失 package/version 和可執行解法，繼續其他工作，不把未跑測試算 PASS。

在具備支援依賴時，使用 tiny random Qwen3.5 config 和 tensors，測試小詞表
conversion/reload、loss masking、實際可訓練參數和 finite gradients、SFT
resume，以及 PEFT attachment/TTT reset 成功和例外兩條路徑。不得把
transition model 或 mock 改名為真實 Qwen3.5。對 claimed components 的
ML 驗證 profile 採缺依賴明確失敗；一般輕量 offline suite 可保留 optional skip。

驗收：已具備 torch 的合成訓練測試必須實跑；新增 architecture/PEFT 測試
逐項列 pass 或具體 dependency blocker，不能以整份 suite 綠燈遮蔽 skip。

## 4. R3：完成可用的 bounded DFS

用明確堆疊等不受 Python recursion limit 影響的方式保留來源 traversal、
EOS、累積 NLL pruning 和 deterministic ordering。測試超過 1000 token 的
deterministic path，含允許完成、budget 截斷、deadline、無合法候選各情況。

將 sequence limit、expansion limit、completed candidates 和 stop reason
分開記錄；說明 grid serialization 長度與 cap 的關係。預設 256 expansions
不能被呈現為支援 1024-token 可達完成長度。不要單靠加大 limit 隱藏成本。

針對原 NVARC batch/cache 設計做 source-backed 對照，實作可支援的 prefix
cache/batching adapter，與無 cache 參考版用 tiny logits/model 做候選、排序、
計帳 parity。Qwen3.5 hybrid state 不支援的部分明確拒絕或用有名稱的 fallback，
不能靜默降級後宣稱完全重現。選擇 fallback 時量測 tiny workload 成本並保留
GPU 效能未知。避免相同 canonical candidate 的重複 verification，若改動
共享 view/評分重用，需保持來源 scoring semantics 與 deterministic ties。

验收：長序列不崩潰，所有停止路徑可辨識，限額不超支；來源/reference
parity 有測試。效能最佳化不能混入未經驗證的候選選擇變更。

## 5. R4：SFT collective backend 與受控續訓

補上實際可執行的 distributed SFT entry/backend，不能只產生 torchrun argv。
依選用 backend 明確支持 DDP 或 sharding；DDP 不代表模型/optimizer 已分片。
Data sharding、gradient accumulation、global steps/tokens、rank seed、
checkpoint ownership、barrier/failure 和 resume cursor 必須一致。

用 tiny CPU 模型和兩個 Gloo processes 測試 collective 更新、資料不重複分配、
checkpoint/resume 和 worker failure。實作 task/session wall-time supervisor、
終止與 checkpoint 完整性規則，不只在訓練返回後標超時。記錄中斷造成的
已消耗成本；不能透過 resume 重置 budget。

採 source-backed external framework adapter 即可，不自行重寫 Megatron。
GPU-only sharding 的程式可完成靜態/CPU 可測部分，但未實測能力要列明。
驗收報告須將「single-process」、「CPU collective 已測」與「GPU sharding
未測」分別列出；禁止只因 GPU 未授權而省略 distributed implementation。

## 6. R5：SDG 與 TRM 可執行 adapter

SDG：保留 saved-response replay，補足階段 orchestrator、provider adapter
介面、可恢復階段身份與失敗/重複 call 計帳。開發測試使用 saved/fake teacher。
Generated-program executor 必須接到真實可執行的隔離 backend，驗證網路、
credentials、mount、CPU/memory/wall limits 和輸出格式；caller 傳入
`attested: true` 不能證明隔離已成立。沒有受支援的隔離環境時 fail closed，
可以用受控 fixture 驗證 launcher/拒絕路徑，不能在 host 直接執行生成程式。
區分 backend enforcement、launch fixture 與真實 sandbox integration 證據。

TRM：核對本機 pinned upstream source 的 preprocess、train/eval flags、
epochs/steps 語義、checkpoint 格式和 output schema。補上實際 invocation
wrapper、supervision、identity binding、結果讀取與候選 normalization，
使 training/preprocess/eval spec 不再是唯一交付。使用極小合成資料驗證
可測的 upstream preprocessing/輸出解析；不啟動真實 TRM 訓練/推論。
Qwen-only、TRM-only、combined 路徑皆保持可辨識 backend/source 與完整 failure
records；fixture prediction 不能冒充 TRM model output。

可用來源快照：
`C:/Users/wurre/.codex/worktrees/51fa/IRIS-X/.irisx/arc-agi-2/qwen35-nvarc/source/`。
先核實 pinned identity，再依既有 source-use 規則複用；缺失不猜 API，
也不為此重抓舊 GPU output。不得將本機絕對來源路徑寫成 portable runtime 預設。

## 7. R6：整合驗收與完成定義

| 項目 | 本輪要求 | 可保留的外部/硬體關卡 |
| --- | --- | --- |
| Truth/result/material verification | R1 已知反例拒絕，合法資料 regression 通過 | 真實大型模型材料尚未取得 |
| CPU SFT/resume | 已安裝 torch 實跑，環境與命令可重做 | 4B gradients、VRAM/throughput |
| Tiny actual Qwen3.5/PEFT | 實作測試與依賴 profile；可用依賴下實跑 | 精確列出的依賴阻塞及真實 4B 相容性 |
| DFS | 安全長序列、cap/stop reason、來源語義和 reference parity | 真實 hybrid cache/GPU performance |
| Distributed SFT | 可執行 backend、tiny CPU collective 與 supervisor 測試 | GPU-specific sharding 和大型訓練 |
| SDG | 階段 adapter、計帳、隔離 backend 和 fail-closed 驗證 | 真實 sandbox runtime 缺失、teacher calls/完整資料 |
| TRM | source-backed invocation/output adapter、合成 preprocess/解析測試 | 真實依賴/weights、train/eval |
| Integration | fixture E2E、crash/timeout/resume、完整狀態文件 | 真實 Q0–Q3/T 評估及 ARC 成績 |

按 R1 → R2/R3 → R4/R5 → R6 推進；依賴阻塞不阻止獨立工作。
每項交付說明 code path、test command/result 和 residual gap。更新
`reproduction-matrix.md`、runbook、trial README 與資源提案，移除過度廣泛的
「implementation-verified」敘述，清楚區別 implemented、fixture-verified、
real-backend-verified、missing。保留本次 control-review 作為被檢查版本的歷史
快照，另加 resolution 表指向修復 commits，不改寫當時發現。

最後在 repository root 執行 `python tools/repository_check.py --all`、
ML CPU profile、fixture E2E 與 `git diff --check`。回報 commit、每項修復和
未完成項。只有具體 missing implementation 都處理完，才可報本輪工程完成；
依賴或硬體阻塞就報 partial，不自行改成已驗收。

## 8. 不變的執行邊界

本輪是 owner 已授權的本機開發續作，不另造 execution decision。不做新真實
Qwen/TRM/SDG teacher generations 或訓練、Codex proposer calls、Kaggle
Dataset/kernel/status/retrieval、競賽 submission、付費工作、真實大型資料/權重
下載或舊 holdout scoring。不改任何歷史 frozen identity、產品 public contract
或 promotion threshold。所有 probe/log/generated output 放 `.irisx/`。
真實執行所需資源另保留具體 draft proposal；不可將本計畫當成 launch approval。
