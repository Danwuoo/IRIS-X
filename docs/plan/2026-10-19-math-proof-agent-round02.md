# MATH-002：固定模型的採樣與工具回饋修復

目前文件交付入口：[2026-10-23 P0／P1／P2 審閱包](#2026-10-23p0p1p2-文件交付)。
下列原始執行範圍及歷史修正保留其日期與脈絡；最新文件工作不啟動其中的操作。

日期：2026-10-19。本 task 的 owner scope 來自本次原始 ChatGPT 指示。
在既有數學 branch `feat/math-proof-agent-20261018` 延續，起點
`0deff2254d2e3b63b88c2eefc4c4f73856663047`；實際桌面 checkout 為
`C:\Users\wurre\Desktop\IRIS-X-Math`，task venv 在
`.irisx/line-b/MATH-002/venv/`。完整非 shallow clone，僅 clone 子程序
`GIT_LFS_SKIP_SMUDGE=1`；乾淨數學分支 fetch/pull --ff-only 後起點不變。

唯一研究問題：相同資源上限下，M-REPAIR 是否比 M-SAMPLE 更有效提高完整
證明率及找答案且證明共同成功率？M-DIRECT 是一次生成的低成本參考。
不保證正增益，零／負結果、基礎設施阻塞與未完成分母一律保存。

## 本次新增授權

允許專用 checkout 實作、必要公開依賴與授權相容模型／資料、既有本地
Kaggle 認證、新建 task private TPU notebook、推論／Lean 驗證、監看與
取回結果，以及普通 commit/push 到既有數學 branch／Draft PR #10。
此範圍只擴大 MATH-001 的離線限制，不重寫歷史交接、不擴大 ARC 或全庫權限。
不做 SFT/RL/TTT/LoRA/蒸餾/synthetic SGD，不用付費服務，不取得公開
benchmark 解答或被安全阻擋的移轉封包，不聯絡研究者，不改 main/develop/ARC refs。

同時最多一個本 task TPU run；最多四次提交，失敗／smoke／未知均占次數。
提交前預留整套 v5e-8 timeout，總和 <=21600 秒，每次 <=10800 秒，第一個
smoke <=1800 秒。平台更低限制優先。未知提交只讀回查、不重送；連續兩次
同根因失敗停止同類遠端重試。模型每次輸出 <=4096 tokens，兩個主比較臂
相同四次生成／工具／wall 上限，解出即停並報實際成本。

## 一個實作與驗收順序

- **M2-BASELINE**：先重跑 R5 有效 seed、來源 binding、runner／gate／no-training
  定向安全回歸與 R001。自測不能升格 WSF-R5/MATH-001 獨立 acceptance。
- **M2-ENGINE**：單模型 adapter、固定命題 Lean worker、有界 controller、原子
  候選／工具事件與保留 planned 分母的 analyzer。Gold/reference/rubric 不進 solver view。
- **M2-TRUST**：固定 Lean/lake/mathlib，限制 proof body，無秘密／外網、唯讀
  輸入與資源限制先實測；最終 theorem 相依 axiom policy 合格才算 kernel_verified。
  沒有實測 isolation 不稱 sandbox，安全不足停止模型程式執行。
- **M2-SMOKE**：先 commit 待驗程式再封裝自足 notebook；硬體 gate 必須實際
  v5e、8 devices。量 cold/warm inference、CPU reference parity、Lean 正負控制、
  輸出保存。故障保留 preflight_failed，不以 CPU fallback 充數。
- **M2-PANEL**：24題仍為提案。需合法來源與人工形式忠實性核對，技術成本
  通過後在目標評分前凍結實際面板、來源/family/exposure/answer visibility、
  seed0、模型完整 revision 和預算；seed1/2 僅預算允許再做。缺少人工核對
  紀錄即 blocked，不由實作者代簽；可採精確上游版本的可歸屬人工核對，不必
  要求 owner 重做。純證明與答案已給定題不可計 joint discovery，找答案須額外
  證明回傳答案與固定命題之 kernel 綁定，不能只並列答案比對與任意證明。
- **M2-REMOTE**：單一 `.irisx/line-b/MATH-002/` state/lock；預設只讀監看，
  60秒輪詢、錯誤最多300秒退避且有界。CLI 2.2.4 status/logs/output 實作忽略
  version，故 exact-version 與 latest source readback 一致且唯一 task writer
  才採信 latest；terminal 新目錄取回、manifest/hash 核對後才分析。
- **M2-DELIVERY**：code checkpoint 與 delivery 分離，研究結果／sanitized
  tests/run summary／handoff／task/catalog／原 renderer BOARD 完備。
  最終停 review_ready，原 ChatGPT 獨立驗證；科學未完成不標成 Goal 達成。

## 已知前置限制

既有 R001 是 authored CPU certificate audit，並非 model/Lean/TPU 成績。
目前 repository 未凍結 formal panel；來源補查已找到上游人工核對候選，詳見
round002/source-feasibility-notes.json，尚待安全取得欄位與相符runtime。
8192 context 無法容納4096-token舊候選、提示與另4096輸出；正式freeze前必須
由實測選定可行的共同context/輸出上限。固定tokenizer測量確認4096+4096超限；
2048僅為待預登記的共同上限候選，仍需逐題精確容量檢查與TPU成本實測。
closed_exists_nat_v1已以自製控制實測：固定wrapper把回傳Nat綁為原始存在命題的
witness，核心與遞移axiom檢查通過才接收。但沒有真實來源題目獲准使用此路徑；
miniF2F-v2c的安全statement-only取得、原始答案slot語意與runtime仍有缺口。
Kaggle CLI 2.2.4 和既有帳號讀權已核對，TPU 可用性與 Lean 信任條件待實測。
所有不可公開 proofs／原始收據只放 ignored task root。

## 獨立 review 後的受限工程修正（2026-10-19）

本次 owner 指示只修 M002-R1/R2/R3 與 M002-CI1，不開始新科學實驗。
專用桌面現場起點為 delivery `fb5cc667a2971f53a3fe3a6c387b02a0ff08f3fa`，
對應受審 code `d6e4309607936b66d34573350b9697e5fddc7b0f`；origin、分支、
worktree、乾淨狀態與 ancestry 已核對，只對數學分支 fetch/ff-only，沒有增量。
依據 [PR10 獨立 review](https://github.com/Danwuoo/IRIS-X/pull/10#pullrequestreview-5567278465)
修正以下契約；原 review 的失敗與舊 developer receipts 保留。

- M002-R1：所有模式綁定原始 proof UTF-8 bytes、固定 statement、model text 與
  一致的 trusted worker receipt；controller 與 analyzer 各自拒絕不相符紀錄。
  原 find_answer answer/spec/witness 綁定保留。
- M002-R2：共用成本 schema，count 是非 bool 非負 int，時間有限且非負；
  analyzer 從原 receipt 重驗，缺值、非法值與 partial 不可被 producer 旗標掩蓋。
  原始失敗保留，合法部分只能報 observed lower bound。
- M002-R3：歷史 terminal/retrieval 與當前派送資格分開；來源、版本、status
  回查失敗撤回資格，只有完整匹配的唯讀回查解除。所有新測試用 mock/temp state。
- M002-CI1：只允許 round001/round002 目錄內 Python source，保留其他 active
  executable/AST/archive 檢查；runner/inventory/commit gate 納管 math stdlib/mock
  tests，native 模組仍在 import 前阻擋。既有 public matrix 不放寬；不執行原
  audit/aggregate，也不要求歷史 failure 全綠。R001 source/results 不改寫。

此工程修正明確允許 task scope 所列三個 shared tools、三個對應 test、
tests/inventory.json 與 tests/README.md 的窄整合，不擴大其他 core/ARC 權限。
plan 與 task 的 scope/acceptance controls 隨 code checkpoint 固定；後續 delivery
只更新 implementation SHA、證據、review/catalog/BOARD/handoff metadata。
normal/-O 定向正負控制分列；已有 Lean 僅重跑既有受限常數控制，kernel 證據
與 mock 證據分開。本輪零 Kaggle 操作；不讀寫原 task ledger、不另造 ledger、
不 push/cancel/reconcile、不取得模型或 benchmark 答案，不修改其他 refs。

既有唯一 attempt 維持 submission_unknown/version null，預留 1/4 次與
1800/21600 秒。日後平台或權限改變，唯讀 reconcile 必須由原研究 task 的範圍
另行記錄；不明仍不得派送。工程交付只到 review_ready，研究保持 not_estimable；
MATH-001/R001/WSF-R5 歷史獨立驗證狀態不變。

## 2026-10-23：P0／P1／P2 文件交付

本輪 outcome：交付可審閱的資源方案、介面與變更設計，以及尚未執行的驗收案例，
讓正式 M-SAMPLE／M-REPAIR 對照的開發依賴與停止條件可逐項審查。
本輪 check：文件／catalog／task／生成 BOARD 一致性、相對連結、預算算術及 Git
差異範圍；這些是文件檢查，不是測試套件、runtime 資格或獨立 acceptance。

| 審閱文件 | 內容與交付界線 |
| --- | --- |
| [P0-BUDGET](../verification/MATH-002/P0-BUDGET.zh-TW.md) | 原有物理預留、24 題方案的上限算術、含 M-DIRECT 的條件式可行排程、實測待補項及 BUD-01–08。不是 ledger 或新預算授權。 |
| [P1-P2-DESIGN](../verification/MATH-002/P1-P2-DESIGN.zh-TW.md) | 來源、可信 header、答案綁定、完整 context、資格收據、評分入口與分析介面；逐路徑變更清單與依賴。全部是未實作提案。 |
| [P1-P2-ACCEPTANCE](../verification/MATH-002/P1-P2-ACCEPTANCE.zh-TW.md) | 輸入、預期結果、拒絕條件及所需證據；區分靜態／mock、真 Lean／模型與目標環境資格。案例均未執行。 |

### 不變的研究與驗收基線

主問題維持相同資源上限下，M-REPAIR 相對 M-SAMPLE 的完整原題證明率及找答案與
證明共同成功率；M-DIRECT 保留一次生成參考。proof-only 與 answer-given 不進
joint discovery 分母；ProofNet 的較窄 proof-only pilot 不能完成 joint 目標。
固定來源／命題忠實性、最終 theorem axiom policy、答案／證明／收據綁定及 evaluator
隔離要求不變。既有數值 gate 仍同時要求所有 logits 有限、shape 一致、greedy tokens
一致、max absolute error <=0.5、relative L2 <=0.03、warm repeat 一致及非 deadline。

原四次提交／21600 秒、單次至多10800秒、單一 publisher、未知仍占一次／1800秒
的規則不變；失敗與後續 qualification 也占預留。兩主臂最多四次生成／四次工具不變。
既有600秒 wall 為 provisional；8192 context／4096 completion 已知未合格。
本輪不採用2048 completion、512-token回饋、更大 context、縮小面板、刪除seed、
新模型或任何門檻變更。P0 的數字方案供審閱，未選題、未排定正式 run、未 freeze。

### 開發依賴與未來驗收順序

1. P0先建立整輪可行性與未定項。P1來源／可信header與runtime設計、共同context及
   adapter數值問題可並行；不以未知遠端狀態禁止這些離線準備。
2. P2先完成可信 scoring packager／runner、schema轉換、確定排程及分析報告契約。
   原smoke manifest的raw-file hashes與scoring=false不能改旗標後充當評分身份。
3. 實作須有新的code/source身份、影響範圍回歸與適用審查；本輪沒有授權執行這些
   驗收案例。資格階段須實際走真模型adapter→controller→Lean worker→evaluator/analyze，
   scripted及獨立PyTorch控制保持各自來源。
4. 平台／權限確有變更後，才在原研究適用範圍記錄唯讀reconcile；unknown未解除
   仍不得派送。目標TPU、同環境Lean／隔離／成本／輸出取回資格皆需其實際證據。
5. 所有適用gate齊備及所需審查完成後，才固定protocol/panel/model/verifier/code、
   seed及共同預算，再進正式評分。結果保留planned分母、未生成／缺失配對與不完整
   成本；seed按題重複測量，不充作獨立樣本。零／負增益亦可構成完整可信交付。

### 本輪操作界線與交接狀態

本次owner明確要求文件工作；不啟動模型、Lean／WSL、測試或Kaggle，不安裝環境、
下載權重／題目、取得benchmark解答、修改ledger或啟動監看。只允許必要文件編輯、
metadata生成與靜態文件檢查。protocol、panel、model候選、runtime source與原始
收據／review不變，實作checkpoint仍為`fedf3a0ac60365fc840b7ae9aefac84a9ba7ba2d`。
工程仍`review_ready`，科學結果仍`not_estimable`；本輪文件的後續commit身份不能
追認為新程式資格或獨立驗收。具體改動與檢查記錄見[HANDOFF](../verification/MATH-002/HANDOFF.md)。

後續owner已明確允許將這九個文件／metadata變更普通commit、push至目前數學分支，
並更新Draft PR #10；方案仍未採用、案例仍未執行，實作仍固定於上述checkpoint。
此Git交付不啟動模型、Lean／WSL、測試或Kaggle，不要求CI重跑，也不合併PR。
