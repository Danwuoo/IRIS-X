# ARC-AGI-2 DSPy / GEPA prompt pilot

日期：2026-09-22。狀態：研究設計草案；尚未啟動模型、Kaggle 或付費呼叫。
本聊天為總控，實作交給後續獨立開發 task。本文件不延長 Trial 002 的執行授權。

## 問題與已知起點

研究問題：固定 Qwen3.5-4B 與單次推論成本限制，DSPy 管理的 prompt 經過
GEPA 的失敗回饋與 Codex 反思後，能否在未參與改寫的 ARC 題目提升 exact match？

Trial 002 的 `trial-002-smoke-002` 已驗證：4 張 L4，4 次有效生成，
runner 回報 175.427 秒，generation 各 6.579–27.157 秒，峰值約 8.7–9.3 GiB，
但 selected-output exact match 為 0/4。這是執行可行性證據，不能外推全資料集準確率、
長題延遲，或將 175 秒當成整個 Kaggle 排隊／準備時間。

目標 85% 仍保留在整條研發路線；本輪交付是一次可比較的 prompt 改善試驗，
不是 SOTA 宣告、Domain Package promotion 或競賽提交。

## 已確定選擇與待定預算

- 解題模型固定 `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`。
- Owner 已指定反思使用 Codex CLI 的 `gpt-5.6-sol` / `xhigh`，
  並將資料規模擴大為 256 optimization-train + 128 selection-dev。
- 建議先做一次反思，每次 `codex exec` 最多 15 分鐘、無自動重試；
  一次或最多三次 mutation 的選擇尚待 owner 回覆。
  模型可用性須在開發時核對，不可默默更換成其他系列。
- 擴大後的單次 mutation 方案建議最多兩個各 120 分鐘 session、每個 job 最多 300 秒；
  session 全程上限包含 setup、模型載入、推論和封包輸出。整輪最多 16 個配置 GPU-hours，
  另列實測 GPU busy time，不把兩者混用。這個預算尚待 owner 回覆。
- Codex 的計費邊界尚待 owner 回覆：建議只用既有付費訂閱額度、不加購、不轉 API。
  訂閱額度不是「免費算力」；記錄使用量，無法取得金額時標示 unknown。
- 繼續採 private Kaggle、L4 x4、Internet disabled；不監控，不設回收排程，
  由 owner 通知完成後回收。失敗不自動增開 session。

## 本輪只變動 instruction

使用一個 DSPy predictor：`demonstrations + query_grid -> predicted_grid`。
輸入仍是目前的 digit-row representation，輸出仍由相同 deterministic parser 處理。
只允許 GEPA 修改 instruction 字串，不改模型、tokenizer、parser、demonstrations、
解碼參數、output schema、測試題或答案。

| 組別 | 用途 | 推論設定 |
| --- | --- | --- |
| B0 | Trial 002 原始 prompt 的新工作負載基線 | greedy、512 output tokens、thinking disabled、一次生成 |
| B1 | 封裝成 DSPy 後的相同基線 | rendered messages 和 token IDs 必須與 B0 完全相同 |
| G1 | GEPA 首次反思產生的一個 instruction | 除 instruction 外，與 B1 完全一致 |

B0/B1 先用離線 render/tokenization parity 驗證；通過即可共用同一份真實生成，
不為 framework 包裝重花 GPU。若 parity 不成立，先修 adapter，不把差異歸因 GEPA。
首輪不用 ChainOfThought 多段呼叫、self-repair、TTT、LoRA、NVARC augmentation 或 ensemble。
若 512 tokens 系統性截斷，記錄並結束此設定，另開同時調整兩組 token budget 的比較。

## 資料隔離

從固定官方 public-training source，按 task ID 分組，預先凍結 owner 指定的
256 optimization-train、128 selection-dev；另建議保留 128 locked-holdout，合計 512 題。
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

## 一次 mutation、兩個 session 的工作量（預算待定）

1. **本機離線準備**：凍結 split、B0/B1 parity、package identities、budgets；
   驗證真實 DSPy / GEPA imports、adapter、重放與停止路徑，測試本身不呼叫模型。
2. **Kaggle A**：B1 在 256 train + 128 dev 生成，共 384 次 Qwen 呼叫。
   四個 persistent workers 共用任務佇列，每 GPU 一個模型，不為每題 reload。
3. **本機反思**：下載驗證一次，scorer 產出 train feedback。
   DSPy GEPA 以凍結 seed 選擇最多 3 個 train traces，透過 Codex CLI proposer
   產生 G1；保存 parent、instruction diff、failure hypothesis、預期改善與 prompt hash。
   若沒有失敗案例則不花反思額度；若全零仍允許一次有具體 feedback 的反思。
4. **Kaggle B**：G1 在同一 256 train + 128 dev 生成 384 次，另對 locked holdout
   執行 B1 與 G1 各 128 次，共 640 次。兩組配對排程、同 GPU／設定比較，
   任務順序預先凍結並交錯，降低 worker 或執行順序偏差。
5. **本機判讀**：先只用 train/dev 完成 GEPA minibatch 接受／拒絕與 candidate selection，
   保存選擇結果；再開 holdout scorer。若 G1 在 dev 落敗，正式選擇維持 B1，
   G1 的 holdout 對照仍作預註冊診斷，不能據此翻轉選擇。

合計最多 1,024 次 Qwen solver generation、一次 Codex 反思。B 的 holdout predictions
可以先計算，但答案、分數與 predictions 不得回流 optimizer；它們在選擇凍結前隔離保存。
預算是上限，不是要求用滿；若 G1 無效／等同 B1，停止而不花第二個 session。
每次啟動、失敗、timeout、截斷皆計入 ledger；不隱藏重試，不因 cache miss 自動呼叫雲端。

上述工作量是完整資料覆蓋的上限，不承諾能在建議時間內跑完。先用 A 的實際 input
tokens、generation 長尾、timeout 與 worker 使用率估算 B，不以四題 smoke 的平均值保證吞吐。
若不足以在已選預算內完成，就回報並保留完整分母，不能臨時挑短題完成後宣稱全量比較。

若 owner 選三次反思，需改成基線批次、最多三個相依 mutation 批次，再對 dev 選定的
唯一候選做一次獨立 holdout 比較。最寬上限為 1,792 次 Qwen 呼叫、三次 Codex exec、
五個 Kaggle sessions；不能沿用兩個 sessions 的授權。每輪只根據先前 train/dev 更新，
連續兩輪無 dev 改善即停止。本文的一次 mutation 工作量目前是預設提案，並非已選執行額度。

## 控制反思模型的壓力

256 題 train 是可供分析與抽樣的資料池，不是每次反思的上下文。先以 deterministic
本機程式產出 parse、形狀、顏色／位置、截斷、timeout 等錯誤統計，再由預先固定的
train-only sampler 選最多三個有代表性的失敗案例，避免三題都是同一類錯誤。
抽樣規則、seed、被排除與選中的 case IDs 均記錄；若使用自訂 sampler，明列為 GEPA 適配。

每次完整 proposer 輸入（指令、parent prompt、統計、案例與 feedback）最多 32 KiB UTF-8，
摘要最多 2 KiB。案例超出剩餘容量時以固定順序減少案例數或選下一個可容納案例，
不能截斷 grid 冒充完整案例；排除的大題列入 coverage limitation。
Codex 輸出結構化的短診斷與 instruction；instruction 最多 4,096 字元，且
以固定 Qwen tokenizer 驗證最多 512 tokens，超限就拒絕，不再次要求模型修稿。
這些是資料大小與產品 prompt 限制，不冒稱 Codex 內部 reasoning token 硬上限。

只傳 train 的聚合統計與選中案例，不傳 128 題 dev 的 trace 或答案。
每次反思使用獨立最小上下文；parent instruction 加摘要即足夠，不累積整條聊天、
全部 raw logs 或前代完整反思紀錄。相同模型、輸入與設定以 hash cache 復用回應，
重放不消耗新的反思額度。每次報告輸入 bytes、實際回傳 token usage、耗時與接受／拒絕結果。

## 真正使用 DSPy / GEPA

實作採固定版本的 `dspy.GEPA` 與可注入的 instruction proposer，不能只有名稱或自寫
「叫模型改 prompt」而宣稱 GEPA reproduction。若採一次 mutation 方案，只能稱
GEPA integration / one-mutation pilot；尚未驗證多代進化或 Pareto search 的優勢。

本機 optimizer 使用 identity-bound Qwen request/result cache。缺少真實 prediction
就輸出 pending batch，停止並保存 state；不合成 response、不連線呼叫 Qwen API。
第二批回來後以固定 seed、固定 proposal cache 重放／續行同一 trial。
若上游沒有合用的 checkpoint API，用薄 adapter 做可測的重放，不宣稱上游原生支援。
使用 fake backend 測試「重放不再呼叫 Codex、不重複 GPU 請求、正確 parent/selection」。

GEPA 設定採明確的 metric budget，不用不可見的 auto 搜尋額度；
reflection minibatch 上限 3、`use_merge=False`、`track_stats=True`。
開發時依被 pin 版本的計數語意與離線 mock trace 推導並凍結 `max_metric_calls`，
不可沿用舊 40 題提案的 96 次額度，也不拿重複的 feedback callback 當新 generation。
另有獨立全域上限：一次 mutation 方案最多 1,024 solver calls、
1 proposal、2 kernels、session deadline；metric calls 不能當成 GPU calls 或 CLI turns。
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
外層 supervisor 執行 15 分鐘 deadline 與 process-tree 終止，失敗也計費／計次。

CLI 一次 exec 可能包含多個內部 model turns，不能稱為「一次 API request」或假設
15 分鐘等於金額硬上限。記錄 model、reasoning、CLI version、輸入輸出 hash、
JSONL usage、wall time、exit status；若有額外美元預算，需先確認可執行的計費限制，
不能用事後 token 記錄冒充 hard spend cap。無效 JSON／額度不足不自動重試或換模型。

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

交付 B1/G1 配對表、exact-match numerator/denominator、wins/losses/ties、
valid/timeout/OOM/truncation、tokens、median/p95 latency、peak VRAM、兩種模型成本，
以及 prompt、split、source、runtime、result identities。

僅當 dev 選中 G1，且 holdout 的 net wins > 0、沒有新的 invalid／timeout、
兩組都在相同硬預算內，才標記「值得擴大重驗」。128 題的一題是 0.78125 個百分點；
不能因分母擴大就宣稱統計穩健或泛化成功。報告配對不確定性與具體失敗，禁止只報勝例。
這是後續研究建議，不變更既有產品 acceptance / promotion 門檻。

兩組均零分、無改善、退步或僅 train 改善時，停止擴大同一 prompt search，
保留負結果；一次 mutation 的失敗不代表 GEPA 方法整體無效。
下一個假說再考慮 reasoning token budget、program synthesis 或 NVARC TTT，
每次獨立比較。執行未完成則回報 partial/inconclusive，不能只用完成子集算總準確率。

新開發 task 的第一個 handoff 是離線可執行實作、sources audit、split manifest、
成本估算與 preflight。Owner 確認本輪資源／資料流後，記錄新的 execution decision
及 trial/run IDs，再執行上面批次；Trial 001/002 的身份與結果保持不變。

## 參考（2026-09-22 查閱）

- [DSPy GEPA 實作](https://github.com/stanfordnlp/dspy/blob/main/dspy/teleprompt/gepa/gepa.py)
- [DSPy GEPA proposer](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/GEPA/GEPA_Advanced.md)
- [GEPA 官方程式](https://github.com/gepa-ai/gepa)
- [Codex 非互動模式](https://learn.chatgpt.com/docs/non-interactive-mode?translationFallback=zh-Hant)

以上動態文件是設計參考，執行前仍需 pin 實際依賴；不是已完成的實驗證據。
