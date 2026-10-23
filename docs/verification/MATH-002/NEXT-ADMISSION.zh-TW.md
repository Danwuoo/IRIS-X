# MATH-002 下一輪：來源、context 與 runtime 准入草案

日期：2026-10-21。狀態：`draft_not_scoring_authorized`。
基準交付：`9d986261ca71f3af3e81e88038c144cfb133ca13`；受審程式碼：
`fedf3a0ac60365fc840b7ae9aefac84a9ba7ba2d`。

2026-10-23文件細化：[P0預算方案](P0-BUDGET.zh-TW.md)、
[P1／P2介面與變更清單](P1-P2-DESIGN.zh-TW.md)、
[未執行驗收案例](P1-P2-ACCEPTANCE.zh-TW.md)。這些文件具體化下列G1–G5，
不取代其gate、修改protocol或門檻，也不授予實作／測試／模型／遠端操作權限。
唯一canonical plan仍為[原MATH-002計畫](../../plan/2026-10-19-math-proof-agent-round02.md)。

本輪唯一成果是可審閱的准入規格；檢查方式是逐條對照既有來源、程式碼與收據，
確認每個 gate 有具體證據要求、未完成狀態及執行邊界。本文件不修改正式協定、
模型門檻或研究目標，不選題、不凍結面板，也不產生新的執行授權。
原研究仍比較固定模型、相同資源上限下 M-REPAIR 與 M-SAMPLE 的完整證明率及
答案與證明共同成功率；M-DIRECT 只作一次生成參考。目前科學結果仍 `not_estimable`。

## 本輪資源限制與證據基線

使用者目前 CPU/GPU 忙碌：本輪只讀文件、程式碼、小型收據並更新文件。
不啟動模型、Lean/WSL、測試套件、環境安裝、權重下載、重型雜湊或基準測量；
不操作 Kaggle、不啟動監看。下列實測均是未來 gate，不是本輪工作或自動續跑條件。
資源可用及適用 owner scope 確認後，才可排定對應的有界執行。

既有三份交付證據：[獨立重審](independent-review-02.json)、
[archive 修復](archive-ci-restoration.json)、[本地驗證](local-qwen3-4b-lean-validation.json)。
閱讀本地驗證時一併參照[來源補充收據](local-validation-provenance-20261021.json)；
最新遠端工作狀態見[CI 讀回](delivery-ci-readback-20261021.json)，不延伸為本輪測試結果。
前兩者支持各自的工程與完整性範圍，不授予研究 acceptance；本地證據須分三條讀取：

| 證據路徑 | 可以支持 | 不能支持 |
| --- | --- | --- |
| Scripted controller → 真正 WSL Lean → evaluator/analyzer | 受測整合、收據與分母控制 | 目標模型生成或數學能力 |
| 真實 Qwen3-4B 的 JAX 與 PyTorch BF16 數值比較 | 固定短 prompt 的逐項數值觀察 | 已通過模型資格或 TPU parity |
| PyTorch 真實權重生成的 authored 候選 → WSL Lean | 該候選及窄 Nat witness 的 kernel 驗證 | JAX controller 全鏈路、正式來源或配對增益 |

各路徑都需保留實際呼叫腳本、backend、版本、prompt、候選與收據來源；不能將
三條證據拼成一個未實際執行過的完整研究流程。已有 invalid_format、隔離冷啟動
失敗、缺漏成本和未知遠端狀態繼續保留。

## G1：來源及命題忠實性

優先準備 ProofNet-Verified 的 proof-only 路徑；miniF2F-v2c 為 joint 路徑的
獨立准入問題。這是準備次序，沒有把原 joint 目標刪除或改成純證明研究。

| 路徑 | 必須具備的證據 | 現況與停止條件 |
| --- | --- | --- |
| ProofNet-Verified | 固定來源 revision、statement-only 檔案 bytes/hash、可歸屬上游人工核對、原題與形式命題對應、imports/header 及完整 runtime pins | 已檢視八份 statement-only 檔案；尚無准入題或評分面板 |
| miniF2F-v2c | 經核實的 statement-only 取得管道、原始答案 slot 型別與語意、人工核對及相容 runtime | proof-named 欄位內容未知；整份下載後刪欄位不符合現行限制 |

ProofNet 固定來源為 `160414332dc196583f6c37c310b420d2a3b07c58`、statement tree
`394620c77ebfc275c4cd4e740a2d7c0926b2d8a5`、Mathlib
`8f9d9cff6bd728b17a24e163c9402775d9e6a365`。已核對同revision的
[`lean-toolchain`](https://github.com/marcusm117/ProofNet-Verified/blob/160414332dc196583f6c37c310b420d2a3b07c58/lean-toolchain)
為 `leanprover/lean4:v4.28.0`，24 bytes、無換行，SHA256
`26df5f74b79af0cd9e298b6583993699a54938d047ba1919428da80d3ae80c6e`；不是rc1。
既有 Lean 4.19 / Ring、NormNum closure 資格不適用於此來源。

ProofNet 的 `import Mathlib`、`open`、`open scoped` 是受信任命題環境的一部分。
未來 header 介面需有明確白名單，將原始來源與實際編譯 header、declaration、
imports closure 全部綁定；模型只提供 proof body，不能改 header、假設或目標。
不可刪除 scoped 語意或暗中移植成較容易的命題以符合現有 worker。

ProofNet 純證明題不構成答案發現分母。若後續採 proof-only 機制 pilot，須先
明列其較窄結論並走適用協定變更流程；joint 仍未估計。miniF2F-v2c 的答案 slot
不預設等同 closed Nat existential；若不同，必須另設受審型別與答案綁定契約。
不得弱化原問題來套用 `closed_exists_nat_v1`，也不能把已給答案當作自行發現。

**G1 驗收證據：**每題 provenance/fidelity/exposure/answer visibility、來源與
環境 hashes、取得管道與排除理由清單；無 gold/reference/rubric 進 solver。
題目相容性依預先規則判定，不能看模型輸出後挑選成功題；公開暴露與 authored
控制另列。現有受限 tactic grammar 的 coverage/unsupported 必須明示。
這些是未來准入條件；本輪不取得新題目、不建立 selected problems。

## G2：共同 context 與成本規格

對每題 i、臂 a、步驟 r，令 `M(i,a,r)` 為實際序列化後完整 messages，
`T` 為固定 tokenizer 加 chat template 的精確編碼，`O` 為共同 completion cap，
`C` 為已資格化 context。每次生成必須滿足：

```text
P(i,a,r) = len(T(M(i,a,r)))
P(i,a,r) + O <= C
```

`M` 必須包括 system、原始命題/header、模板、角色標記、上一候選的重新編碼、
JSON escaping、實際回饋及 generation prompt。分段 token 數相加只是診斷，
不能替代完整 messages 的編碼；不能假定前輪 O tokens 重新序列化後仍只占 O。

原協定 `C=8192, O=4096` 已不合格：既有最短修復案例需要9209 tokens。
`O=2048` 只是候選；既有4000字元回饋案例用到8136 tokens，不能據此宣告有足夠餘量。
較大 context 或較小共同 O 均須另版預登記及實測，不在本輪採用。

建議待審回饋規則：先定義固定錯誤欄位與 token cap，依固定順序序列化；超出時
保留原始診斷於隔離收據，solver 只見有 truncation 標記的決定性受限摘要。
若連最小錯誤欄位、原始候選及共同 O 都放不下，保留現行原始狀態
`context_budget_exceeded` 與分母；`context_exhausted` 僅作容量耗盡的報告分類名稱。
不截短原始命題或 proof bytes、不逐臂縮減 O、不以一次失敗暗改採樣策略。
此規則與可能的512-token回饋上限都是提案，未取代目前4000字元規則。

**G2 驗收證據：**固定 template/tokenizer hash、逐題各臂容量表、合法最大歷史的
保守上界與 authored 邊界案例、overflow分類；以及實際 prefill/decode/工具/setup
與wall成本。兩主臂沿用共同最多4次生成/4次工具的比較設計；600秒仍為 provisional。
任何新 O/C/feedback/wall 值須在評分前固定，解出即停並報實際成本。

## G3：模型數值與真實執行路徑

固定數值 gate 保持：logits shape 相同且所有值有限、每個 greedy continuation token 相同、
`max_absolute_logit_error <= 0.5` 且 `relative_l2_logit_error <= 0.03`，並符合
既定 warm-repeat 與非 deadline 條件。此次 `0.588851 > 0.5`，即使
relative L2 `0.017504` 合格且四個 greedy tokens 相同，整體仍未 qualified。
峰值處 ULP 換算是事後診斷，不能覆蓋既定 absolute gate。

**G3 驗收證據：**定位數值差異的可重播紀錄；相同模型/tokenizer revision、權重
hash、dtype、backend、套件、sharding、prompt、逐步logits與實際判定。修正 adapter
需要新 code/source identity 與適用 review；不回寫舊失敗、不因已見結果放寬門檻。
正式控制鏈還需真實 adapter → controller → worker → evaluator/analyzer 的有界
非評分整合證據，並區分任何 stand-in、手動串接或 qualification-mode 呼叫。

## G4：來源相容 runtime 與 TPU 目標資格

**來源 runtime 證據：**固定 Lean/lake/Mathlib 及所有實際依賴、工具chain bytes、
完整 import closure、header/declaration/rendered-source hashes；在目標環境實測
正負控制、最終 theorem 遞移 axioms、網路/秘密隔離與資源限制。含 `sorry` 的來源
檔只可作輸入模板；不能用其能編譯作為完整證明或無漏洞資格。

**TPU 證據：**實際 v5e、8 devices、精確模型來源/版本、G3、cold compile、warm
prefill/decode、記憶體、同環境 Lean/隔離與輸出保存。CPU虛擬devices、PyTorch控制、
WSL kernel 與本地GPU規格都不能代替這項；不得以CPU fallback記成TPU通過。
不同 runtime/backend 的資格分別列出，不把本地通過合併成遠端成功。

## G5：未知提交與評分前交付

唯一既有 Kaggle attempt 保持 `submission_unknown / version=null`，預留
1/4次與1800/21600秒；實際耗用仍 unknown。餘額3次/19800秒不構成 dispatch 授權。
只有平台/權限有實際變更後，原研究 scope 才可另記唯讀 reconcile，綁定 exact
source/version/latest/status 與單一 publisher；不明仍不得 push、換slug或退款預留。
本文件與目前 owner 的文件修正授權不啟動這些操作，也不更動 ledger。

**G5 驗收證據：**完整匹配的回讀交易、歷史與目前dispatch資格分列、未知實際成本
及實體預留未被洗掉。來源/runtime/context工作可各自準備，卻不能解除遠端gate。

全部適用 gate 齊備後，才另行準備可審閱的 protocol/panel/model/verifier/code
指紋與決定性選題、family/exposure、seed、共同預算。於任何 scored output 之前
完成所需審查及freeze；不拿 smoke manifest 當 scoring manifest。
正式結果保留 planned 分母、gain/loss、未生成配對、timeout/format/context/infra
分類及不完整成本下界。當前交付維持 `review_ready`，不自簽獨立acceptance。
