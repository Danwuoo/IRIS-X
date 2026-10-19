# MATH-002：固定模型的採樣與工具回饋修復

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
