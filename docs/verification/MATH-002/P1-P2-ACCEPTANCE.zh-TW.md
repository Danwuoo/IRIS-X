# MATH-002 P1／P2 驗收案例規格

日期：2026-10-23（Asia/Taipei）。文件基準交付：
`73544d6156775f9525129e3fcd4fb55cbfddae25`；既有實作固定於
`fedf3a0ac60365fc840b7ae9aefac84a9ba7ba2d`。
狀態：`draft_not_scoring_authorized`；**本文件全部案例的執行狀態均為 `not_run`**。

本輪成果是可逐條審閱的驗收案例；檢查方式是閱讀本文件、
[P0 預算](P0-BUDGET.zh-TW.md)、[P1／P2 設計](P1-P2-DESIGN.zh-TW.md)與既有契約，
核對每個缺口是否有正反案例、證據要求及停止條件。本輪不啟動模型、Lean／WSL、
測試、Kaggle、provider、下載或監看，不產生任何新通過收據。
文件審閱、未來程式資格與正式科學結果分別記錄：文件齊備不代表程式已實作；
mock 通過不代表真實 runtime 合格；資格控制通過也不代表配對增益成立。

## 使用規則與現況

`CASE-*` 是本文件的案例定位碼，不是新增 task acceptance criterion。
每列映射到 [MATH-002 原驗收](../../plan/2026-10-19-math-proof-agent-round02.md)
及既有 `M002-R1`／`R2`／`R3`／`CI1`；不變更 task 的 acceptance 清單、研究目標、
數值／信任門檻或歷史證據。既有 bounded R1–R3 review 結果保留；本列案例不宣稱
它們失效，也不把舊通過移植成新 runtime 的資格。

未來案例證據分為四層，須各自標示實際使用的依賴：

| 層級 | 可支持的結論 | 限制 |
| --- | --- | --- |
| `static_future` | 來源、介面、依賴閉包、身分及預登記規則的靜態檢查 | 不載入模型、tokenizer、Lean 或 provider；不是執行控制通過 |
| `authored_mock` | 自編資料、假 tokenizer／adapter／worker／remote 的契約與失敗控制 | 不製造 benchmark 解答；模擬接受收據只驗證程式分支，不是 kernel proof |
| `runtime_local` | 精確 tokenizer／真實 Lean／真實模型等各自已執行的有界控制 | 每項另註依賴；執行 tokenizer 不代表模型，Lean 不代表 TPU，CPU 不代表目標硬體 |
| `target_remote` | 真實 v5e-8、相符 Lean／隔離及實際完整控制鏈的資格 | 另受遠端 reconciliation、預留、owner scope 與審查限制 |

表格中的「預期」是未來驗收要求，不是已觀察輸出。未來產生的原始候選、診斷、
私有收據及 evaluator-only 資料留在 ignored `.irisx/line-b/MATH-002/`；Git 僅保留
適當清理後的摘要、來源指紋、程序、狀態與限制。證據應包含案例定位碼、執行時間、
受測 code／protocol／panel／model／verifier 身分、程序與各子項結果；缺漏如實標
`not_run`／`blocked`，不能補造當時未記錄的綁定。

## P1：來源、命題與答案綁定

`CASE-HEADER-01` 的 header 輸入使用設計文件的有序 typed directives，須涵蓋
`open` 與 `open scoped` 跨類別交錯；分開三個陣列而丟失原始次序的投影不合格。
尚未建模的 alias／選擇性 open／namespace 巢狀語意應 blocked，不能刪命令後接受。

| 案例／對應驗收／層級 | 輸入、設定與動作 | 預期接收與拒絕條件 | 必存證據 |
| --- | --- | --- | --- |
| `CASE-SRC-01`；M2-PANEL、M2-TRUST；`static_future`、`authored_mock` | 自編來源清冊分別提供固定 revision 的 statement-only 路徑、未知 proof-named 欄位、整份含解答來源、revision／檔案 hash 漂移。模擬 acquisition preflight；不實際下載。 | 僅在取得管道已證明只含准許 statement bytes、來源許可／用途相符時進入下一 gate。未知欄位或必須先取得答案再刪欄位的路徑在取得前阻擋；不把欄位名稱當內容安全證據。hash 漂移拒絕，無 source admission／selected problem。 | 取得契約、固定 revision／statement tree／檔案身分、欄位白名單、每一拒絕原因；無任何真實解答 bodies。 |
| `CASE-SRC-02`；M2-PANEL；`static_future`、`authored_mock` | 自編 formal／natural-language 對應紀錄，分別有可歸屬上游人工核對、缺 reviewer／來源綁定、僅實作者或工具自簽、核對後 declaration 改變。檢查 admission。 | 只有能連回精確來源、原問題與形式命題的適用人工核對可准入；不要求 owner 重做已合格上游核對。缺紀錄、錯 revision 或自簽替代人工均 blocked。按預先相容性規則決定，不能看模型成敗後選題。 | review attribution／reference、被核對身分、fidelity、family、exposure、answer visibility、排除清冊與原因；評分前的決定紀錄。 |
| `CASE-HEADER-01`；M2-ENGINE、M2-TRUST、M2-PANEL；`authored_mock`，其後 `runtime_local`／`target_remote` | 自編含 `imports`、`open`、`open scoped` 的受信任 header 與 declaration；單獨變更 scoped 次序／名稱、import、假設、目標、statement hash 或 rendered source。嘗試渲染與驗證。 | 合法白名單 header 在相符 runtime 保留原語意；header、declaration、closure、rendered source 身分一致才可驗證。漂移、未白名單 header、模型改 header／新增 declaration 均拒絕。不能刪 scoped 語意或把題目改易以適配 worker。 | 原始 statement／header 與渲染來源指紋、白名單及 closure 身分、各漂移的 admission 結果；真實編譯結果另列，不以 mock 宣稱等價。 |
| `CASE-HEADER-02`；M2-TRUST、M2-SMOKE；`runtime_local`／`target_remote` | 使用自編正負控制，在精確來源所需 Lean／lake／Mathlib／依賴環境檢查 proof body、最終 theorem 遞移 axioms、網路／秘密／檔案隔離與資源界線；加入 `sorry`、禁用 tactic、偽造 accepted 輸出。 | 只有真正 kernel 通過且 axiom policy、固定命題綁定、實測隔離皆合格才 `kernel_verified`；允許 axiom 集合維持 `{propext, Quot.sound, Classical.choice}`，audit 必須唯一且未截短。`sorry` 模板能編譯不能計完整證明；偽造文字或程序 exit0 不足。Lean 4.19 控制不替代 ProofNet Lean 4.28.0 或 Kaggle runtime 資格。 | toolchain／依賴 bytes 與 hashes、實際程序、最終 theorem axiom audit、隔離負控制與 timeout／資源結果；不改寫原隔離冷啟動失敗。 |
| `CASE-ANSWER-01`；M2-ENGINE、M2-PANEL、M002-R1；`authored_mock`，綁定另需 `runtime_local` | 三種 mode 的自編問題／candidate：proof_only 的 null 與非 null answer、answer_given、已審 closed Nat existential find_answer。分別重驗 selected event 與 worker receipt。 | proof_only 必須 answer=null；proof_only／answer_given 不入 joint discovery 分母。find_answer 只有原命題本就完整表達問題、canonical Nat 固定 witness、proof／statement／spec／model text 全相符才有 joint 資格；單獨答案比對或不相干證明不足。 | 各 mode 的 admission、selection、proof／answer／joint 狀態、所用原始 bytes 指紋；mock receipt 與 kernel receipt 分開。 |
| `CASE-ANSWER-02`；M2-PANEL、M2-TRUST、M002-R1；`authored_mock` | 在 generation 前提出 rational、參數化、unique-existence、find-all 或未知答案型別；另對 kernel-bound Nat 成功控制配置不一致私有 key，只於 selection 後送 evaluator。 | 未審型別在生成前 blocked，不能轉 Nat 或弱化題目。私有 key 不一致保留 `blocked_key_disagreement`，joint 結論 blocked；key 相等不能拯救未綁定證明。新型別須另設受審契約；本文件不授予該型別資格。 | unsupported／binding 原因、selected event 指紋、evaluator consistency 狀態；私有 key／解答本體不進 solver、prompt 或 Git。 |
| `CASE-ANSWER-03`；M2-ENGINE、M002-R1；`authored_mock` | 對三模式各取完整一致的自編 event；一次只改 proof UTF-8 bytes（含空白）、model text、candidate hash、statement、accepted/status/trust flag 或 find_answer spec／answer。controller 與 analyzer 各自重驗。 | 一致控制可按 mock 契約通過；任一不一致不能選成 proof success，分析亦拒絕。JSON envelope 空白可不同；proof body bytes 不正規化、不 strip、不替換為 parser 輸出。hash 只驗一致性，任意輸入的自造 receipt 不具可信來源。 | 每個 mutation 與兩端判定；原始 model text／candidate／worker receipt 指紋、受信任產生程序與 artifact 綁定。 |

## P1：完整 context 與模型資格

| 案例／對應驗收／層級 | 輸入、設定與動作 | 預期接收與拒絕條件 | 必存證據 |
| --- | --- | --- | --- |
| `CASE-CTX-01`；M2-ENGINE、M2-SMOKE、M2-PANEL；`authored_mock`，精確數量需 `runtime_local` | 自編所有角色／模板／原題／header／generation prompt 及最大合法歷史，含引號、反斜線、Unicode 與 JSON re-encoding。針對完整序列化 messages 建立 `P+O=C` 與 `P+O=C+1` 邊界。 | 使用固定 tokenizer＋chat template 的完整 messages 編碼；等於上限可進生成，超一即在呼叫前 `context_budget_exceeded`。片段 token 數相加、假定上一候選 re-encode 仍只有 O tokens，皆不能作容量證明。 | tokenizer/template hashes、完整序列化規格、逐題逐臂逐步 P／O／C 容量表、最大歷史上界與邊界結果；mock 數量不替代精確 tokenizer。 |
| `CASE-CTX-02`；M2-ENGINE、M2-PANEL；`authored_mock`，精確 token cap 需 `runtime_local` | 固定格式錯誤欄位及待審 feedback cap；測 cap 內、超 cap、連最小欄位也放不下、原始候選已占滿 context。比對前後 immutable bytes。 | 採用新政策前須版本化及審查；目前 4000 chars 不被本文件替換。未來若採 token cap，固定順序決定性摘要並標 truncation，完整原診斷隔離保存。最小內容仍超限即保留原始 overflow 狀態及分母；不截 statement／proof、不 auto-cap、不逐臂縮 O、不更換策略。 | 政策版本、raw／solver-visible feedback 各自指紋與截斷標記、overflow 分類、immutable bytes 比對；2048 O／512 feedback 仍是候選值。 |
| `CASE-PARITY-01`；M2-SMOKE；`authored_mock`，真資格需 `runtime_local`／`target_remote` | 自編 logits／continuation 組合分別卡住 shape、NaN／Inf、greedy、max_abs、relative_l2、warm repeat、deadline；另設剛好等於固定門檻控制。真資格再以相同模型／權重／tokenizer／prompt／dtype／backend 重作。 | 所有條件同時成立：shape 相同、全有限、每個 greedy continuation token 相同、`max_abs <= 0.5`、`relative_l2 <= 0.03`、既定 warm-repeat 與非 deadline。任何一項失敗皆 unqualified；現有 `0.588851 > 0.5` 仍失敗，ULP／四 token 相同不能改判。 | 每子 gate 真值、逐步數值與 greedy、精確環境／權重／prompt 身分、cold/warm／deadline 原始觀察；保留失敗，不事後改閾值。 |
| `CASE-PARITY-02`；M2-SMOKE、M2-REMOTE；`static_future`、`target_remote` | 比較未修改 production backend gate 的實際 v5e-8 與 CPU virtual devices、patched loader、PyTorch stand-in／手動串接路徑。核對資格標籤與執行來源。 | 只有真 v5e、8 devices、精確執行源及所有適用控制合格才可稱目標 TPU qualification。patched CPU、PyTorch、WSL、mock 路徑各自限縮標籤；不得靠 patch／fallback 將它們標成 TPU 或 production JAX 通過。 | 實際 accelerator／device inventory、code／harness 身分、backend、patch／fallback 與限制；與歷史三條路徑分列。 |

## P2：可信 scoring 入口與配對排程

`CASE-SCORING-03` 使用設計文件提議的可信 `purpose=qualification` 控制入口；
不得把目前僅接 frozen scoring 的 `execute_arm` 以改旗標、偽造人工題目核對或
虛構已freeze面板繞過。控制入口與正式入口須共用真實 bounded engine，控制
候選只在非評分報告中出現。資格後 final freeze bytes若改變，另核對差異與
適用補驗／審查；不以相同ancestor commit宣稱新bytes繼承全部資格。

| 案例／對應驗收／層級 | 輸入、設定與動作 | 預期接收與拒絕條件 | 必存證據 |
| --- | --- | --- | --- |
| `CASE-SCORING-01`；M2-ENGINE、M2-PANEL、M2-DELIVERY；`static_future`、`authored_mock` | 自編 smoke manifest、僅改 `scoring:true` 的 smoke、缺 semantic hashes、非 frozen protocol、異動 provenance 的 panel、重複／缺漏題、未規劃 seed、model/verifier 身分不符。逐項嘗試 scoring preflight。 | smoke 與 flag-flip 均拒絕。只有可信 committed execution manifest，完整 code/source／protocol semantic／exact panel semantic／model／verifier 身分、適用 freeze 與預算齊備才可進入排程。panel 含 provenance，題目須恰一次；輸出出現前已固定。 | manifest 與 canonicalization 規格、各負控制拒絕原因、freeze／review references、身分比對；現有 smoke raw-file hashes 保留原義。 |
| `CASE-SCORING-02`；M2-ENGINE、M2-SMOKE、M2-DELIVERY；`static_future`、`authored_mock` | 自編已 committed runtime payload，加入 nested helper 或 bootstrap／runner 實際 import；分別漏封裝、改 bytes、同名未追蹤鄰檔、路徑跳脫、symlink、manifest 與執行 code 不符。 | 完整可信執行閉包均被封裝及綁定；漏 nested helper、漂移與不安全路徑拒絕，不能僅檢查既有頂層 `RUNTIME_SOURCES` 即稱完整。dry packaging／身份控制不發送 provider。 | 相對路徑→committed blob／SHA256 清單、依賴閉包理由、bootstrap／runner 身分、payload 與實際執行 bytes 比對、各拒絕紀錄。 |
| `CASE-SCORING-03`；M2-ENGINE、M2-SMOKE、M2-TRUST；`target_remote` | 未來有界非評分控制：真實 production model adapter→controller→來源相容 worker→evaluator→analyze.py；完整保存候選、cost、工具及最終分析。對照 scripted adapter、手動 PyTorch→Lean 的來源標籤。 | 真實鏈路每一段都由同次執行身分串起，才能支持 production E2E 資格；scripted proof／cost 只支持控制流程，不計真模型能力。非評分控制不能混入正式 panel 或成果分母，通過仍不等於模型增益。 | 實際呼叫入口與父子程序、model response、候選／receipt／analysis 綁定、全程環境與成本、non-scoring 標記；缺任一環節為 blocked。 |
| `CASE-SCORING-04`；M2-ENGINE、M2-PANEL、M2-DELIVERY；`static_future`、`authored_mock` | 自編 source core→trusted statement→binding→admission→panel 的 hash graph；另含 context／analysis policy core 與後續 qualification evidence。加入自身hash、下游回指、排除欄位中偷放實際語意變更、不同 canonicalization 或錯誤計算域。 | 明定版本及計算域後可由根至葉單向重算，不需固定點或循環。source core 不含 downstream statement／binding；policy core 不含其後產生且回綁該policy的evidence。簽章／定位排除不能使原題、header、binding、預算或統計方法漂移而身份不變；最終封存仍綁排除欄位及實際證據。循環、錯域、未綁證據或實質變更漏hash皆拒絕。 | 每個node的schema／包含與排除欄位、canonical bytes/hash、拓樸順序、重新計算結果與各mutation拒絕原因；不將自編圖當成現有介面已實作。 |
| `CASE-PAIR-01`；M2-ENGINE、M2-PANEL；`authored_mock`，warm/cache 實測需 `target_remote` | 自編固定 panel／seed／arm schedule；中途缺一臂、重複 job、已有 output root、未規劃 seed、整輪 stop、個別 arm 解出即停。檢查生成 seed 派生與排程 manifest。 | M-SAMPLE／M-REPAIR 相同最多四次生成／工具與共同 wall／O；M-DIRECT 一次。arm 順序／區塊、seed 派生與 early stop 在評分前固定；fresh result root，無自動 partial resume。未執行配對保留 planned，不事後挑 seeds／重排或跨臂加資源。 | planned schedule、seed 派生規則、實際順序、early-stop／未完成原因、每臂 ceilings；整輪資源對應 [BUD-03／06](P0-BUDGET.zh-TW.md)。 |
| `CASE-PAIR-02`；M2-ENGINE、M2-TRUST、M2-PANEL；`authored_mock`，runtime 控制另列 | 在 metadata／nested statement 放自編 sentinel gold、reference、rubric、review 訊息；令前一臂輸出、repair feedback、KV state／cache 跨臂可見。檢查所有 solver-visible prompt 與狀態邊界。 | solver 只見白名單 statement／問題／mode；evaluator-only sentinel 不進 prompt／selection。M-SAMPLE 每次獨立，不見前候選或 feedback；M-REPAIR 只見同題同 seed 同臂合法前一步。禁止跨臂／跨題候選及 KV 污染。 | 每步 solver-view／prompt 指紋、sentinel 掃描、狀態重置規則、candidate parent chain、拒絕／洩漏觀察；使用自編 sentinel，不取得答案。 |
| `CASE-PAIR-03`；M2-SMOKE、M2-PANEL；`static_future`、`target_remote` | 預登記 cold／warm policy、compile cache 使用、每臂 context／KV 重置與 setup 成本分攤；以有限非評分控制觀察首臂與後臂實際成本。 | warmup 不用正式題／答案，兩主臂同一政策；編譯快取可共用時記錄實際命中及準備成本，不能把一臂 cold charge 隱去或另一臂沿用候選 KV。政策或耗用不符即停止 freeze／重新評估預算，不能事後更換計費法。 | cache/warmup provenance、cold compile／warm prefill／decode、setup ownership、實際單調時鐘範圍、政策 deviations；對應 [BUD-07](P0-BUDGET.zh-TW.md)。 |

## P2：成本、分母及統計

| 案例／對應驗收／層級 | 輸入、設定與動作 | 預期接收與拒絕條件 | 必存證據 |
| --- | --- | --- | --- |
| `CASE-COST-01`；M2-ENGINE、M002-R2；`authored_mock` | 自編 raw cost 含合法零值、負數、bool、NaN／Inf、錯型別、缺必填、未知欄位、consumed>prompt、累加溢位；producer cached complete 與 raw 刻意矛盾。controller ingestion 與 analyzer 各重驗。 | count 為非 bool 非負 int，時間為有限非 bool 非負數；非法／缺值不補零、不 coercion。raw 及獨立重驗支配 complete；cached flag 不能拯救。合法部分只入 observed lower bound，非法欄位明列 issues。 | 原 raw receipt、兩端 validation、逐欄 issues、合法 lower bound 與 aggregation errors；不修改既有失敗。 |
| `CASE-COST-02`；M2-ENGINE、M002-R2；`authored_mock` | partial=true、generation deadline、tool timeout、格式錯誤後已耗 tokens、無生成、setup failure、parent timeout 的自編事件；於原子 checkpoint 不同階段模擬中斷。 | deadline／timeout 強制 partial，不能因 parse failure 隱去物理成本；已消耗值保留。缺 final receipt 不當零消耗，unknown／lower bound 清楚；保留 checkpoint，無自動重跑或憑 final flag 計完整。 | checkpoint／事件時序、各 phase 成本與 partial 理由、parent／child timeout、剩餘 planned 項；預留不因失敗退還。 |
| `CASE-ANALYSIS-01`；M2-ENGINE、M2-PANEL、M2-DELIVERY、M002-R1／R2；`authored_mock` | 自編固定問題×seed×arm 全網格，分別移除 row、兩主臂皆無生成、只一臂無生成、重複 observation、未規劃 row、錯 statement／mode／identity、假 success receipt。 | planned 分母固定；缺 row=not_completed，未生成 pair 與 incomplete pair 分列，不能當一般 tie 或刪除。無任何生成則 rate=null／not_estimable。重複／未規劃／錯綁定拒絕。proof／given／find_answer 模式分層；不把 proof-only 算 joint。 | planned／observed reconciliation、各狀態 counts、gain/loss/tie 與未完成／無生成數、proof／joint 分母、所有拒絕原因；自編數字不標模型成果。 |
| `CASE-ANALYSIS-02`；M2-PANEL、M2-DELIVERY；`static_future`、`authored_mock` | 自編同題多 seed、不同 family、單一 family／極少題、缺重複觀察及 gain/loss 控制；依評分前固定 estimand 與 uncertainty 方法產生預期報表。 | 以題為單位，seed 是同題 repeated measures，不膨脹獨立 n；family 聚類依預登記。proof／joint 各列 paired gain/loss 與未完成狀態，family 數不足則明列不可估／限制；不以極小 pilot 宣稱一般化能力或顯著增益。 | 每題彙整規格、seed／family membership、estimand、區間方法與適用條件、可手算自編控制；正式跑後不得因結果改方法。 |
| `CASE-ANALYSIS-03`；M2-ENGINE、M2-DELIVERY、M002-R2；`static_future`、`authored_mock` | 自編事件時間線包含 cold compile、cache allocation、prefill、decode、tool、setup、arm wall、whole-run wall 及 partial receipt；按固定 cost axis 建 proof／joint 成功曲線。 | 各層時鐘與包含關係明列；compile/prefill/decode 等分項不可再加到已含它們的 wall。run wall、arm wall、模型分項分開報；shared setup 僅按預定規則歸屬一次。partial 曲線標 lower bound／unknown，不畫成完整等成本優勢。 | clock/phase 定義、原時間線、成本歸屬表、curve 資料與圖例規則、觀察下界與缺值數；paired arms 不重複計費，參照 [BUD-04／07](P0-BUDGET.zh-TW.md)。 |

## 遠端及整合邊界

| 案例／對應驗收／層級 | 輸入、設定與動作 | 預期接收與拒絕條件 | 必存證據 |
| --- | --- | --- | --- |
| `CASE-REMOTE-01`；M2-REMOTE、M002-R3；`authored_mock`，實際交易另屬 `target_remote` | 自編歷史 terminal／retrieval 已有、目前 exact source／version／latest／status 有一項失敗或矛盾的狀態；再提供完整一致交易。只用 mock state，不碰真 ledger。 | 任一不確定即撤銷當前 dispatch eligibility，歷史結果保留。只有完整匹配交易才可解除該 guard；source-only 不足。未知 version=null 仍占1次／1800秒，不退款／換 slug／重送。完整交易也不代替其他 gate 或 owner scope。 | 歷史／目前 eligibility 分列、readback transaction 身分、mock 變化、guard 原因；[BUD-01／05](P0-BUDGET.zh-TW.md) 的原物理預留不變。本輪無實際 reconcile。 |
| `CASE-CI-01`；M2-BASELINE、M2-DELIVERY、M002-CI1；`static_future`，未來定向執行屬 `authored_mock` | 按已審 source／inventory／runner／gate 邊界檢視新 helper 與測試規劃；自編允許 round001/round002 Python 路徑及越界 executable、native import 前阻擋案例。 | 未來實作仍受 exact path、AST／archive 與 no-training 邊界管制；新測試只能走已適用類別及審查。不得借改 branch 名或本設計重開 `repository_check.py --all`／`arc-unit-audit`。focused 成功不能稱全 CI 或獨立 acceptance。 | 精確 code/inventory/runner 身分、依賴類別、被擋路徑、未跑／scope-stopped 清單與定向結果；本文件不指示重跑歷史 R5／R001。 |

## 預算案例的對應

預算案例由 [P0-BUDGET](P0-BUDGET.zh-TW.md) 定義，本文件不重設其金額、秒數、
題數或採用狀態。全部保持 `not_run`：

| P0 案例 | 與本文件的連結 | 原驗收 |
| --- | --- | --- |
| BUD-01、BUD-02、BUD-03 | 原總額／未知預留、24題不可行、條件方案的算式與每次 ceiling | M2-PANEL、M2-REMOTE |
| BUD-04 | `CASE-CTX-01/02`、`CASE-PAIR-01`、`CASE-ANALYSIS-03` 的共同資源／context 政策 | M2-ENGINE、M2-PANEL |
| BUD-05 | `CASE-REMOTE-01` 的未知不退款、不 retry／換 slug | M2-REMOTE、M002-R3 |
| BUD-06 | `CASE-PAIR-01`、`CASE-ANALYSIS-01/02` 的 planned、seed 與不可事後擴樣 | M2-PANEL、M2-DELIVERY |
| BUD-07 | `CASE-PAIR-03`、`CASE-COST-01/02`、`CASE-ANALYSIS-03` 的真實完整 setup／clock | M2-SMOKE、M002-R2 |
| BUD-08 | 文件不構成 freeze、執行授權、實作或科學通過 | M2-DELIVERY |

## 本輪僅以閱讀完成的審閱清單

下列是文件 reviewer 的檢閱項，不是測試執行，也不填入案例的 pass 欄：

- 研究問題仍為固定模型、共同資源上限下 M-REPAIR 對 M-SAMPLE 的完整證明及 joint 成功率；M-DIRECT 保留參考角色，正／零／負結果均可報告。
- P0 的條件方案和 P1 的 context／feedback 候選仍待適用審查及資格，不改寫現有 protocol／panel／ledger，也未凍結新題目。
- 每個來源、header、答案型別、token 序列化、parity、manifest、排程、成本、分母及遠端阻塞，都能連到至少一個正反案例及必存證據。
- `static_future`／`authored_mock`／`runtime_local`／`target_remote` 的依賴與結論分開；真實模型 E2E 與 scripted controller／PyTorch 手動路徑分開。
- 新實作需要新的 code/source identity 與適用 review；文件沒有重用舊資格、製造 fresh passes、刪除歷史失敗或放寬閾值。
- task 保持 `review_ready`，科學結果維持 `not_estimable`；本輪沒有模型、Lean／WSL、測試、Kaggle、下載、provider 或監看操作。

未定設計項由 [P1／P2 設計](P1-P2-DESIGN.zh-TW.md)維護：header 白名單／渲染與
closure schema、新型別答案契約、共同 O／C／feedback cap、scoring runner 執行閉包、
arm 排程與 cache/setup 歸屬、family 不確定區間及 curve 規格。案例要求先把它們
版本化、審閱及適用資格補齊，再進正式 freeze；目前不以待定值冒充已採用契約。
