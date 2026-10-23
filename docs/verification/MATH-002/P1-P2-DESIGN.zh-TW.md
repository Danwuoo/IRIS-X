# MATH-002 P1／P2：介面設計與預定變更

日期：2026-10-23（Asia/Taipei）。狀態：`design_proposal_not_adopted`。
文件閱讀基準：交付 `73544d6156775f9525129e3fcd4fb55cbfddae25`；現行實作
`fedf3a0ac60365fc840b7ae9aefac84a9ba7ba2d`。本文件只設計未來介面與變更，
**沒有實作、採用新契約、選題、freeze、產生資格證據或授權執行**。

一個成果與檢查：交付能逐欄位、逐路徑、逐失敗情境審閱的實作設計；以靜態
對照現行程式、[准入草案](NEXT-ADMISSION.zh-TW.md)、[原計畫](../../plan/2026-10-19-math-proof-agent-round02.md)
及既有收據檢查相容邊界。本次未啟動模型、Lean／WSL、測試、安裝、下載或
Kaggle 操作。對應的未執行案例見 [P1／P2 驗收案例](P1-P2-ACCEPTANCE.zh-TW.md)，
整輪預留及排程方案見 [P0 預算方案](P0-BUDGET.zh-TW.md)。

## 1. 不變項與現有實作邊界

研究仍比較固定模型、相同資源上限下 M-REPAIR 相對 M-SAMPLE 的完整原題證明率
及答案與證明共同成功率；M-DIRECT 是一次生成參考。兩主臂最多四次生成／四次
工具，每次 completion 不超過 4096 tokens，解出即停並保留實際成本。
純證明、答案已給定、找答案三類分開；不以 proof-only pilot 取代 joint 目標。
planned 分母、失敗、unknown、物理預留及現行數值／信任門檻不變。

| 靜態可確認的現況 | 本設計要補的介面；尚未完成 |
| --- | --- |
| `panel-proposal.json` 未 freeze、`selected_problems=[]`；要求的問題欄位多為平面結構 | 可追溯來源准入、明確轉換成 controller 使用的巢狀 runtime problem |
| `LeanWorker` 固定 imports 與 declaration，模型只能送受限 proof body；尚無原來源 `open`／`open scoped` 介面 | 可信 header、原 declaration、完整依賴 closure 與 rendered source 的一致身分 |
| `closed_exists_nat_v1` 僅處理封閉單一 Nat 存在命題，尚無真實來源題准入 | 保留此窄契約；其他答案型別各自設計與審查，未支援一律 blocked |
| controller 保留上一份完整 model text，以 4000 字元上限切回饋 | 完整 messages 精確 token 容量與版本化 token 回饋政策 |
| adapter 僅實作 context 16–8192；現行 4096＋4096 修復容量不合格 | 可重播 ContextPlan；2048 completion／512 feedback 都仍是候選 |
| CPU 真權重 JAX 診斷 max-absolute `0.588851 > 0.5`；scripted controller 與 PyTorch→Lean 為另兩條證據 | 分項全通過且綁實際 production chain 的資格收據 |
| `package_run.py` 由 committed Git bytes 遞迴收錄允許副檔名，產生 `kind=smoke, scoring=false`；controller 已拒絕此 manifest | 獨立可信 scoring 封裝、排程、資源／結果封存入口 |
| analyzer 已保留 planned 分母、拒絕重複／身分漂移、重驗 raw cost 與 proof receipt | 預先登錄的題目／family 不確定區間與累積成本曲線 |

本設計不修改 `protocol.json`、`panel-proposal.json`、smoke manifest、模型 pins、
runtime、ledger、既有收據或原始失敗。未來 runtime bytes 改動須以新 code/source
身分提交並完成適用審查；不繼承 `fedf3a0` 的回歸結果或獨立 acceptance。

## 2. 共通資料規則與信任分界

以下 `irisx.math.*.v1` 都是**提議的新 format 名稱**，不是倉庫已支援格式；
`trusted-statement.v2` 則明示更換現有 statement digest 的輸入域，不能原地重解
舊 hash。實作者應先提交 schema／轉換器與案例，再提交消費端；未知 format、
未知必填語意、缺欄位及額外未許可欄位均拒絕，不能推測預設值補成合格。

| 值 | 提議的規則 |
| --- | --- |
| `*_sha256` | 小寫 64 hex；raw UTF-8 bytes 與 semantic JSON hash 用不同欄位名，均由可信端重新計算 |
| `*_revision`／`code_sha` | Git 使用完整 40 hex；非 Git 依來源格式另列，不能用可移動 tag 代替固定 bytes |
| semantic hash | 固定版本 canonical JSON：現有 `common.digest` 的 sort keys、compact separators、UTF-8、`ensure_ascii=false`；先驗 schema 再計算；不含自身 hash |
| count／seconds | count 為非 bool 非負 int；seconds 為非 bool、有限非負數；不把缺值、NaN、負值或 producer 的 `complete=true` 補成零 |
| `evidence_ref` | 可歸屬且可讀回的來源／收據定位；hash 只能偵測混用，不能替任意輸入建立真實性或人工審查 |
| 診斷與私有資料 | raw provider／工具輸出、private evaluator key、完整資格 traces 均在既有 ignored task root 的隔離子目錄；Git 僅保存適當 sanitized summary |

Solver 的問題視圖以白名單重建，禁止深拷貝整份來源／statement metadata。
來源審查、私有答案、reference proof、rubric、評分回饋及其他臂的候選不進模型。
模型的候選仍只有 `answer` 與 `proof_body`；任何新 provenance 欄位由可信端產生。

**身分必須形成單向 hash DAG。**提議 `H_v(x)=common.digest(x)`，其中 x 必含本節
明列的 `format`；不同 domain 不共用 format。`source-core.v1`、
`source-admission-core.v1`、`context-policy.v1`、`analysis-policy.v1` 及
`scoring-execution-core.v1` 的完整前綴均為 `irisx.math.`。每種 core 只 hash 下文
白名單列出的欄位；self hash、signatures、後續資格／審查收據定位、最終封裝／
notebook／artifact 回連均排除，不能用「刪除自身 hash」代替明確欄位域。
排除的證據仍須由 gate 實際讀回，驗證它指向正確 core hash 與可信來源；排除不
代表免審。immutable source core 中原始 acquisition／fidelity 證據本身的內容
hash 仍包含在 core，與後續 runtime qualification refs 明確區分。

依賴順序固定為 `source_core → trusted_statement → answer_binding → admission_core
→ runtime_panel → scoring identities → context/schedule/analysis policy → qualification
→ execution_core → notebook → package binding → execution artifacts`。
qualification 不回寫 policy，statement 不回指最終 admission；任何出現逆向
hash 依賴的 schema 在採用前拒絕。對應未來案例仍見
[驗收規格](P1-P2-ACCEPTANCE.zh-TW.md)，本次未執行。

## 3. P1-A：SourceAdmissionRecord → RuntimeProblem

提議 `format=irisx.math.source-admission.v1`；每個候選來源題一筆，從
`pending` 到 `admitted`／`excluded` 的判定在任何該輪 scored output 前完成。
准入記錄本身不代表題目已被選入面板。

| 必填欄位 | 型別／含義及檢查 |
| --- | --- |
| `problem_id`, `source_id`, `source_revision`, `source_path` | 唯一穩定 ID、固定來源與檔案路徑；拒絕路徑穿越及同 ID 不同 bytes |
| `acquisition` | `{kind, statement_only, legal_basis_ref, legal_basis_sha256, projection_ref, projection_sha256, acquired_file_sha256}`；須有實際可核對 statement-only 管道；未知 proof 欄位不可先整包取得再刪掉 |
| `source_statement_sha256`, `natural_language_sha256` | 原形式命題與原題 bytes 的固定指紋；`natural_language` 只放已准許 solver 看到的題幹 |
| `human_review` | `{status, reviewer_attribution, upstream_revision, evidence_ref, evidence_sha256, scope}`；`approved` 須綁精確原始題目／版本、量詞／型別／域／假設／目標與 vacuity 核對，不回指後續 trusted statement；可用可歸屬上游人工核對，不能由實作者代簽 |
| `family`, `related_problem_ids`, `exposure` | family 的固定分類與親緣記錄；exposure 至少含公開狀態、已見解答事件及 authored／改寫來源；unknown 不能寫成 unexposed |
| `answer_mode`, `answer_visibility`, `answer_kind` | mode 僅 `proof_only`／`answer_given`／`find_answer`；可見答案不得標成 discovery；型別與原題語意均明確 |
| `trusted_statement_ref`, `trusted_statement_sha256`, `runtime_spec_sha256` | 指向第 4 節的 header／declaration／runtime；不同 Lean／Mathlib 版本不共用資格 |
| `answer_binding_ref`, `answer_binding_spec_sha256` | `find_answer` 必填；其他模式為明確 null；不能靠可選 key comparison 補足 binding |
| `publication_policy_ref`, `admission_status`, `exclusion_reasons`, `review_ref` | 發布限制、准入結果與可歸屬審閱；排除須保留理由，不刪來源問題來隱藏缺口 |

上表的來源與最終准入欄位分成兩個不可循環的 hash domain：

- `source_core_sha256 = H_v(source_core)`；`source_core` 精確含
  `format=irisx.math.source-core.v1`, `problem_id`, `source_id`, `source_revision`,
  `source_path`, `acquisition`, `source_statement_sha256`, `natural_language_sha256`,
  `human_review`, `family`, `related_problem_ids`, `exposure`, `answer_mode`,
  `answer_visibility`, `answer_kind`, `publication_policy_ref`。它不含任何 trusted
  statement／header／runtime／binding link、准入結果、最終 envelope 或自身 hash。
- `admission_sha256 = H_v(admission_core)`；`admission_core` 精確含
  `format=irisx.math.source-admission-core.v1`, `source_core_sha256`,
  `trusted_statement_sha256`, `runtime_spec_sha256`, `answer_binding_spec_sha256`
  （非 find_answer 為 null）, `admission_policy_sha256`, `admission_status`,
  `exclusion_reasons`。`source-admission.v1` 外層另保存完整 core、被引用物件／
  refs 及 `review_ref`；後續 review 必須明確綁此 `admission_sha256`，但 refs／
  review receipts／signatures／self hash 不反向加入此 core。RuntimeProblem
  消費這個最終 `admission_sha256`，不把 envelope 原始 JSON hash 混作它。

轉換器提議 `admit_problem(record, statement, binding) -> RuntimeProblemVnext`：
輸出明確含 `id`, `natural_language`, `answer_mode`, `statement`, `statement_sha256`,
`human_review`, `family`, `exposure`, `answer_visibility`, `admission_sha256`，以及適用
的 `answer_binding`。另外保存 proposal 欄位到 runtime 欄位的版本化對照：
`problem_id→id`、`formal_statement→statement.declaration`、
`statement_fidelity_status→statement.fidelity`、`statement_fidelity_review_ref→human_review`。
最後一項必須解析成有證據的物件，不能把文字 ref 直接視為 `approved`。
轉換後重新計算 runtime panel semantic hash；不能拿 proposal 原始 JSON 檔 hash
填入 `panel_semantic_sha256`。排程與 evaluator 均消費同一份凍結 runtime panel。

ProofNet 準備序優先，但只有 proof rate 能由合格 proof-only 題估計；joint 欄位
保持 `not_applicable`。miniF2F-v2c 的安全取得、原 answer slot 與 runtime 未解決前，
joint 仍 `not_estimable`。不得把兩者或 authored 控制湊成完整目標已完成。

## 4. P1-B：TrustedStatementVnext 與 AnswerBinding

提議 `format=irisx.math.trusted-statement.v2`。可信端註冊並固定下列欄位；模型
不能傳入／變更它們，worker 從註冊表依 ID 取回並逐項比對。

| 欄位 | 內容與邊界 |
| --- | --- |
| `id`, `fidelity`, `source_core_sha256` | 只連結上游 immutable source core，不回指最終 admission envelope／hash；authored engineering controls 維持另類別，不能出現在 scored panel |
| `source_declaration_utf8_sha256`, `declaration` | 原題完整 declaration，包括參數、量詞、域、假設、目標與必要定義；不得弱化或用較易定理替代 |
| `header_directives`, `source_header_utf8_sha256` | `header_directives` 是保留原來源跨種類順序的 array，每項精確為 `{kind, names}`；kind 僅 `import`／`open`／`open_scoped`，names 為依原順序的已審白名單名稱 array，非空且不接受自由 Lean 文字；不把三類各自分組排序 |
| `header_policy_sha256`, `render_policy_sha256` | 語法白名單與可信 renderer 版本；來源需額外命令／定義時，先記 unsupported、另審擴充，不注入自由文字 |
| `runtime_spec_sha256`, `imports_closure_sha256` | Lean/lake/toolchain bytes、Mathlib 與依賴 revision／實際 runtime tree、完整 transitive import closure；僅 hash 頂層 import 名稱不夠 |
| `semantic_sha256` | `common.digest` 精確 hash `format=irisx.math.trusted-statement.v2` 及上表除本欄以外的欄位；不含 final admission、binding、證據 refs、signatures、rendered candidate source 或 self hash；與舊 `statement_digest` 分離 |

此版 directives 僅承諾頂層 import／完整 namespace open／scoped open 的有序子集。
`namespace`／`section`／`end` 巢狀作用域、`open ... in`、selective open、alias／
renaming、hiding 及其他命令均 unsupported；不能抽掉語法後假定同義。若來源需要，
先另版擴充 typed schema、作用域與 renderer，經審查及案例驗證才准入；不得在
`names` 塞入括號／alias／任意命令。原始 namespace 或作用域無法保留時 blocked，
不能僅以 directive 名稱相同宣告語意一致。

可信 renderer 保留來源 header／declaration 語意，只替換來源模板的 proof hole；
保留原始輸入 bytes hash、可信重建 header/declaration hash、最後送 Lean 的
`rendered_source_sha256`。若 theorem name 需固定成現有 `irisx_final`，記錄明確
renaming map，確認不存在 self-reference／碰撞及 namespace 變義；無法保證即 blocked。
加入既有 `maxHeartbeats` 選項／axiom audit 命令也須列入 render policy。不能刪 `open scoped`
來遷就現有 worker；來源含 `sorry` 可作模板，不能把模板編譯成功算作證明。

`verify(statement_id, proof_body, deadline)` 與 `verify_answer(...)` 的成功仍要求：
實測同環境隔離、固定 runtime、受限 grammar、完整未截短的 proof UTF-8 bytes、
固定最終 theorem、唯一且未截短的遞移 axiom audit；允許集合仍僅
`{propext, Quot.sound, Classical.choice}`。只有 compile exit0 不足。
worker receipt 新版還需綁 `header_policy_sha256`, `runtime_spec_sha256`,
`imports_closure_sha256`, `rendered_source_sha256`；controller／evaluator／analyzer
共同重新驗證，保留 R1 的原 model text／candidate／statement 一致性。

答案介面保留既有 `closed_exists_nat_v1` 原規則：封閉單一 Nat existential、
canonical 非負十進位最多 60 digits、可信 `_root_.Exists.intro` 固定該 witness、
proof body 證明剩餘目標，最終 theorem 與 candidate/spec/normalized-answer hashes
全部綁定。現有 spec 的 `kind`, `statement_sha256`, `review_ref`, `answer_mode`
不原地擴大語意；若搭配新版 statement digest，須以獨立版本橋接明列兩個身分，
不將 v2 hash 偽裝成舊 spec。

新來源若是 Int／Rat／多值／唯一性／find-all，提議另立受審的 typed-slot 版本，
明列 `kind`, `source_slot_type`, `canonical_encoding`, `trusted_constructor`,
`original_statement_sha256`, `review_ref` 與全題語意等價證據。這只列出設計缺口，
**尚未選擇或支援任何新型別**；不得接受任意 Lean expression、Python `eval`、
外參存在式、另造 predicate 或先比對答案後接受無關證明。

## 5. P1-C：ContextPlan 與受限回饋

提議 `format=irisx.math.context-plan.v1`；欄位為 `model_spec_sha256`,
`tokenizer_files_sha256`, `chat_template_sha256`, `messages_schema_sha256`,
`serialization_policy_sha256`, `context_tokens`, `completion_tokens`,
`feedback_policy_sha256`, `overflow_policy`, `capacity_evidence_ref`。
共同 `O=completion_tokens` 與合格 `C=context_tokens` 在評分前固定。
`context_plan_sha256` 專指 policy core：精確 hash
`format=irisx.math.context-policy.v1` 與上述欄位除 `capacity_evidence_ref` 之外的
全部欄位。外層 `context-plan.v1` 保存 policy、hash 與 capacity／qualification
refs；這些 refs、signatures、self hash 及最終 artifact links 不進 policy hash。
資格收據指向既定 policy hash，不反向改 hash；model spec 也不得包含此 policy
或後續 qualification 回連，context 的數值設定由兩邊一致比對。

每次生成先從實際 controller 路徑建立完整 messages，再用與 generate 完全相同的
tokenizer/template（含 generation prompt）計算 `P`，強制 `P + O <= C`。
計算包括 system、完整原命題/header、JSON escaping、role markers、上一個完整
candidate 的重新編碼與回饋；分段 token 加總與前輪 output token 數只作診斷。
每次 event 留 `messages_sha256`, `serialized_prompt_sha256`, `prompt_tokens`,
`completion_allowance`, `context_plan_sha256`；adapter 再驗一次容量。

提議回饋物件 `FeedbackEnvelopeV1={status, phase, reason_code, diagnostic_excerpt,
truncation}`，由可信端按固定欄位順序轉成 solver-facing 文字。
`truncation={policy_sha256, original_tokens, delivered_tokens, truncated}`，先以固定
tokenizer 計算包含欄位／標記的完整 envelope，再按已登錄順序縮減
`diagnostic_excerpt`，不得切壞 UTF-8；其餘最小欄位不可省略。完整 raw diagnostic
只放隔離收據，模型不讀檔或取回未裁切版本。非編譯資訊先按固定白名單清理，
不得透過 traceback／路徑／審查內容洩漏秘密或答案。回饋截短不是 proof 截短。

512-token feedback 與共同 2048-token completion 均僅待審候選，沒有取代現行
4000 字元／4096 token 欄位。若採用，須另版 protocol／容量案例與成本資格。
現行 adapter 上限 8192；更大 context 不能只改 JSON，須新 adapter bytes／身分與
數值、記憶體、成本資格。完整命題、proof/model text 或最小回饋仍放不下時，
保留現行 `context_budget_exceeded` 與 planned 分母；報告可分類為
`context_exhausted`，不能重試縮短單臂 O、截 proof、換題或自動變更策略。

## 6. P1-D：QualificationReceipt 與真實鏈路

提議 `format=irisx.math.qualification.v1`，含 `qualification_kind`, `status`,
`code_sha`, `source_sha256`, `harness_source_files`, `harness_sha256`,
`model_spec_sha256`, `verifier_spec_sha256`, `context_plan_sha256`,
`backend`, `runtime_packages`, `dtype`, `device_kind`, `device_count`, `topology`,
`sharding`, `weight_files_sha256`, `prompt_sha256`, `sampling_settings`,
`controls`, `raw_evidence_ref`, `limitations`。檢查實際測得值與 freeze 身分一致；
declared pins 或手動把 adapter `qualification` 字串設成 passed 不能替代證據。

`qualification_kind` 明確分開 `numeric_parity`、`runtime_isolation`、
`production_chain`、`cost_capacity`；各項缺失／失敗即整體未 qualified。
數值門檻不變：shape 同且全有限、每個 greedy continuation token 同、
max-absolute <=0.5、relative-L2 <=0.03、warm-repeat 一致且非 deadline。
既有 `0.588851` 失敗不得回寫，不能以 ULP 或相對誤差通過洗掉。

正式目標資格須真實 v5e、8 devices；CPU virtual devices、PyTorch→WSL、本地
Lean 4.19 與 ProofNet Lean 4.28 不互相替代。`production_chain` 要在新 committed
bytes 上實際走 production adapter→controller→worker→evaluator/analyzer，使用
有界非評分控制、正常的 qualification gate 與同一結果封存路徑。
scripted/stand-in、patch、手動串接、`qualification_mode` 呼叫逐項揭露，只支持
各自範圍；不能拼接為未跑過的完整資格。這些均為日後驗收，不在本次執行。

**非評分鏈路也需要明確入口。**現行 `execute_arm` 要求 frozen protocol 與
`scoring=true`，不能把 authored 控制偽裝成已准入的科學面板來取得 E2E 收據。
提議由可信 launcher 使用獨立 `purpose=qualification` 的 control manifest，
明列 `control_set_sha256`、`control_origin=authored_engineering`、`scoring=false`、
同一 model/verifier/context/source 身分與原預算 reservation。未來 controller
可拆出兩個 gate wrapper 共用同一 bounded execution engine：
`execute_control_arm` 僅接受已審自編控制及 qualification manifest；原科學
`execute_arm` 僅接受完整 frozen scoring manifest。兩者都執行實際 adapter、
回饋、worker、receipt、成本與保存邏輯，不以 stand-in 代替。control wrapper
不得讀取 benchmark panel、混入正式 planned 分母或自簽 source fidelity；其
analysis 只產生控制報告。這是待審介面提案，不放寬既有評分 gate，也不允許
把 smoke manifest 改旗標後送入任何入口。

資格收據必須標明其涵蓋的是哪些精確 source/config bytes 與 runtime 身分。
最終 freeze／封裝若使 protocol、context、renderer、執行入口或其他受測 bytes
改變，先列逐檔相等／差異與影響範圍，補足必要資格及適用審查。單純 code SHA
或文件 commit 的 ancestry 不能移植資格；分項 model 數值證據也不自行證明
新 launcher、不同 context 或新來源 runtime 已通過。此對照是新 freeze 的
輸入證據，不回寫舊收據，也不形成 qualification→policy 的反向 hash 依賴。

## 7. P2-A：可信評分封裝與排程

提議新入口 `package_scoring.py`／`scoring_run.py`（檔名尚未存在，待審），
保留原 `package_run.py`／smoke snapshots 原義；禁止只把 `scoring=false` 改 true。
封裝只讀已提交 Git bytes，檢查 clean 的全部 runtime／config 範圍、commit、
資格／審查 refs、frozen protocol／panel、來源准入及 P0 預留可行性。

沿用 `irisx.math.scoring-identity.v1` 的語意欄位：`code_sha`, `source_sha256`,
`protocol_semantic_sha256`, `panel_semantic_sha256`, `model_spec_sha256`,
`verifier_spec_sha256`。提議 execution manifest 新版另含 `format`, `kind=scoring`,
`scoring=true`, `run_id`, `source_files`, `source_sha256`, `identities`,
`context_plan_sha256`, `analysis_plan_sha256`, `schedule_sha256`,
`qualification_refs`, `review_refs`, `budget_plan_sha256`, `reservation_ref`,
`timeout_seconds`, `unique_writer`。上述 refs 由可信封裝與 scheduler 讀入，
不能由 solver／結果 producer 自填建立資格。`execution_core_sha256` 精確 hash
`format=irisx.math.scoring-execution-core.v1` 及本段所列 manifest 欄位，唯
manifest 外層 format 改用該 core format；不含 self hash、notebook identity、
signatures、後續 package／execution／artifact 回連。notebook 嵌入此 core 後
再計算 notebook source identity；外層 package binding 才綁兩個既定 hash。
後續 execution/artifact 收據指回 core／package binding，不回寫它們。
此新計算域不重解既有 smoke manifest 或既有 `notebook_identity` 的原意。

`source_files` 為完整相對路徑→committed byte hash 對照，包含所有執行入口、
common、controller、adapter、worker、evaluator、analyzer、schema／renderer、
及任何實際引用的 `lean/...` 巢狀 helpers。現行 packager 已用 recursive Git tree
收錄允許副檔名，不應把這誤述為尚無巢狀封裝；本缺口是可信 scoring 的明確
closure／dependency admission 與 consumption，而非只有列出六個最小檔名。
拒絕 untracked／dirty byte、symlink、路徑穿越、缺依賴與 undeclared import；
runtime installation 也綁定 pins、實際 tree 與資格證據。solver payload／容器內
不得含 private evaluator key、reference proof、rubric、raw provider receipts。

提議 `SchedulePlanV1={format, panel_semantic_sha256, protocol_semantic_sha256,
seeds, rows, arm_order_policy, seed_derivation_policy, setup_policy,
budget_plan_sha256}`。`rows` 在執行前列出每個 `(problem_id, seed, arm)` 及共同
上限；三個 arm 均列 planned，M-DIRECT 的成本獨立預留，不假定能重用主臂候選。
seed0 先行，seed1/2 只有事前列入方案與預留才執行，不依成功率選擇追加。
臂順序採事前決定且平衡的固定規則，例如以 `digest([schedule_seed,problem_id])`
最低 bit 決定 SAMPLE／REPAIR 次序；實際規則須在 freeze 前選定並 hash。
候選 RNG 維持或明確另版現行 `digest([seed,problem_id,index])` 對映，第一輪相同
seed 的共同隨機數關係明列；不得因觀察輸出更換 RNG／候選。

每臂新 state、無前臂候選／feedback／KV cache；SAMPLE 的四個候選也不讀前候選。
允許預先 qualified 的不可變權重／編譯 cache，但須固定 warm-up／使用規則，
分列一次性 setup 與每臂實際 cache allocation／prefill／decode／tool 成本；
不能把 REPAIR 多出的 prompt 或編譯歸零，不能重複扣除／漏扣 shared setup。
凍結 schedule 消費同一份 runtime panel，controller 保留 fresh output directory
及禁止 automatic partial resume 的規則。

scheduler 只透過既有單一 task ledger／lock 預留整套 v5e-8 timeout；不得另造
ledger、清未知 reservation、分割裝置秒冒充 wall 秒或換 writer 繞 gate。
4 次／21600 秒、單次 <=10800、首 smoke <=1800、未知 1 次／1800 秒不變。
`submission_unknown` 未經適用 scope 的 exact source/version/latest/status
唯讀 reconciliation 前，不能 dispatch。結果原子保存 planned checklist、
candidate／tool／checkpoint／execution／artifact manifest；terminal 取回新目錄
並核對 manifest/hash 後才分析。crash、timeout、not_reached 均保留，無自動續跑。

## 8. P2-B：AnalysisPlan 與成本曲線

提議 `format=irisx.math.analysis-plan.v1`，含 `identities`, `schedule_sha256`,
`unit=problem`, `seed_aggregation`, `family_definition_sha256`, `denominators`,
`missingness_policy`, `proof_rule`, `joint_rule`, `paired_rules`,
`uncertainty_method`, `cost_axes`, `cost_cutpoints`, `cost_allocation_policy`,
`reporting_scope`。評分前固定方法／數值參數；分析器不從已見效果選區間、
cost cutoff、排除規則或題目 family。private key 僅 evaluator 在候選選定後使用，
key 衝突阻擋 joint 結論；不能回流選答或生成。
`analysis_plan_sha256` 精確 hash `format=irisx.math.analysis-policy.v1` 與上述
全部 policy 欄位；其 `identities` 僅允許既有 scoring-identity.v1 的 format、
code_sha、source_sha256、protocol_semantic_sha256、panel_semantic_sha256、
model_spec_sha256、verifier_spec_sha256，**不含** analysis／context／schedule
policy hash、execution manifest、qualification 或最終 artifact 回連。
外層 `analysis-plan.v1` 的證據／審查 refs、signatures、self hash 及 artifact links
排除在 policy hash 外。schedule policy 同樣不得反向包含 analysis plan 或其
資格／execution 收據；因此 manifest 可以同時引用這些先算好的 policy hashes。

所有 planned `(problem,seed,arm)` 都保留。完整 proof success 仍須 matching
trusted receipt＋fidelity；joint 分母只含事前合格 `find_answer`，`proof_only`／
`answer_given` 為 not_applicable。任何未合格 find-answer 誤入面板使該 joint
結果 blocked，不能事後移除以改善率。缺任一臂列 `incomplete_pair`、任一臂
未生成列 `no_generation_pair`；兩者不能歸 tie/gain/loss。零生成保持 null rate／
`not_estimable`。報 known successes／planned 的 end-to-end completion，另表
完成配對的 gain/loss；機制效果不把 infra 阻塞偽裝成模型推理失敗。

統計具體候選：同題所有預先登錄 seeds 先取平均，題目為單位；分 family
列每臂 proof／joint rate 與 paired difference。提議固定 95% percentile
cluster-bootstrap、10000 replicates、RNG seed1729；以 family 為 cluster 抽樣
並攜帶其題目與 seeds，另以 family 分層的 problem bootstrap 作敏感度描述。
這些參數**尚未採用**，適用審查可在看到 scored output 前決定；若採其他方法
需寫完整演算法與參數。family 太少（原提案只有三類）或單一有效 cluster 時，
明列區間不穩定／不估計；不由此主張廣泛泛化或顯著增益。科學單位不能改成
`題數×seed數`；gain/loss、ties、incomplete 和 no-generation 都同表保留。

成本從 raw receipt 重驗既有 R2 schema，不能信 producer completeness flag。
每次候選保留 prompt/output tokens、actual generation phases、tool calls/wall、
verifier setup、arm wall；shared cold setup 在 run 層單列並採預登記 allocation。
wall 軸以單調時計的實際不重疊 timeline 計算，禁止把重疊 phase 相加成 arm wall。
累積 token／wall 曲線：按候選順序及預先定義截點，僅在合格證明已完成核驗時
將成功由0變1；全部 planned 題仍在每個截點分母。固定截點超過共同上限拒絕。

只要 cost 缺失／非法／timeout partial，保存原始數值與 issues，合法部分標
`observed_lower_bound`；不得補零，亦不得把下界當精確橫軸而宣稱較省。
涉及不完整成本的點另層顯示或標不可識別區間，完整成本子集另表但不替換
planned 主分母；沒有足夠成本證據就不給精確 cost-efficiency 排名。

## 9. 預定逐路徑變更清單

以下全是未來變更提案；**本次只新增本文件**。新檔名不代表已存在或已納管，
原路徑下適用 AGENTS／CI admission 在真正編輯前另行確認。無需新共用產品契約；
若牽涉共用 runner/inventory/gate，依既有 workstream 範圍走獨立小型審查。

| 現行或提議路徑（相對 repository root） | 未來具體變更與依賴 |
| --- | --- |
| `research/math-proof-agent/round002/source-policy.json`, `source-feasibility-notes.json` | 保留既有證據；未來新 source admission 記錄引用原證據，不回寫歷史取得／exposure |
| `research/math-proof-agent/round002/source_admission.py`（新提案） | 嚴格 SourceAdmissionRecord 驗證與 proposal→RuntimeProblem 轉換；依 P1-A、runtime／binding 合格紀錄 |
| `research/math-proof-agent/round002/statement_schema.py`（新提案） | TrustedStatement v2 白名單、版本 digest、renderer、header／closure binding；不得兼容重解舊 hash |
| `research/math-proof-agent/round002/lean_worker.py` | 新版固定 header renderer、runtime／closure與receipt欄位；保留受限 proof grammar、原 Nat、隔離／axiom gate；先處理 v1/v2 明確分派 |
| `research/math-proof-agent/round002/evaluator.py` | 與 worker 同版的 proof/header/answer receipt validator；typed slots 尚未採用，unsupported 仍 fail closed；private key 仍隔離 |
| `research/math-proof-agent/round002/context_plan.py`（新提案）、`context_controls.py` | 完整 messages tokenization、FeedbackEnvelope／truncation metadata、容量表；真實 tokenizer 測量屬未來 scope |
| `research/math-proof-agent/round002/model_adapter.py`, `remote_smoke.py` | 定位 parity 修正、資格 receipt consume/binding、實際 topology／cost；任何新 context 實作另版，新 qualified production 呼叫不能繞 gate |
| `research/math-proof-agent/round002/controller.py` | 使用准入 runtime problem、ContextPlan、受限回饋、新 receipt validator；受信任 qualification／scoring wrappers 共用同一 bounded engine並保持不同gate；保留 first-accepted、所有 raw cost、fresh state/no resume |
| `research/math-proof-agent/round002/common.py` | 新 schema helpers、canonical域與scoring manifest驗證；既有 cost schema不改門檻，不容 producer 自簽 qualified |
| `research/math-proof-agent/round002/package_scoring.py`, `scoring_run.py`（新提案） | 新可信 scoring 封裝／固定 schedule／planned checklist／artifact原子保存，完整 nested source closure；smoke入口保持原義 |
| `research/math-proof-agent/round002/kaggle_run.py`, `sdk_readback.py` | 若 scoring metadata整合需要，僅在新實作範圍內接既有ledger/lock/exact-readback gate；本次不改ledger/monitor/remote狀態 |
| `research/math-proof-agent/round002/analyze.py` | 消費凍結 AnalysisPlan、grouped區間／cost curves／partial下界；保留原身份、proof與raw cost二次驗證 |
| `research/math-proof-agent/round002/protocol.json`, `panel-proposal.json` | 直到來源／context／runtime／預算／審查齊備才另版freeze；本次不改值或selected problems |
| `research/math-proof-agent/round002/test_*.py`, `lean/*_controls.py` | 後續按[P1／P2案例](P1-P2-ACCEPTANCE.zh-TW.md)增補真正邊界／反例；stdlib/mock、tokenizer、native／模型／TPU資格分層，均未執行 |
| `docs/verification/MATH-002/` 及原 plan/task/catalog/handoff | 未來記新 code/source checkpoint、案例結果、獨立review與限制；本次文件無法升格資格或acceptance |

## 10. 依賴順序與待審決定

```text
P0 整輪預算／不變門檻
 ├─ P1-A 來源／人工核對 ─ P1-B header/runtime／答案綁定
 ├─ P1-C context／feedback設計 ─ 實際容量與成本資格
 └─ P1-D 數值修正設計 ─ 真實目標 parity／isolation／production chain
                ↓（離線介面可並行準備；資格實測另需執行scope）
P2 schema統一 → scoring packager/schedule → AnalysisPlan／收據驗證
                ↓
所有資格＋未知提交reconciliation＋適用獨立審查＋可行預留
                ↓
另版protocol/panel/model/verifier/code/seed/budget freeze → 正式配對
```

可審查的決定點依序為：P0 可行題數／seed／共同 wall（仍受成本資格約束）、
安全來源取得與 joint typed-slot 是否必要、header allowlist及runtime資格範圍、
共同 O／feedback cap及overflow政策、數值修正、排程／setup計費規則、區間演算法
及成本截點。沒有任何項目可在結果出現後為了成功率改動；來源不滿足原配額時，
保留原提案並先版本化理由與結論範圍，不能把 proof-only 的就緒當 joint 已完成。

本文件與同批 P0／案例／計畫／交接更新只使下一輪開發可審閱，維持
`review_ready`／研究 `not_estimable`，不自簽獨立 acceptance，也不啟動下一步。
