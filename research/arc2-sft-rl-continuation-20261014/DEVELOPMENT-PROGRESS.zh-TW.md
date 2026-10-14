# ARC-AGI-2 開發進度管理

更新：2026-10-14 17:09 UTC；本頁為持續更新的唯一進度管理文件。
工作分支：`feat/arc2-sft-rl-continuation-20261014`。
研究基準：[`cc14bd1a79aac1fe6135017c9e09d4834300675d`](https://github.com/Danwuoo/IRIS-X/tree/cc14bd1a79aac1fe6135017c9e09d4834300675d)。

**Stage 1 離線支援已交付；重要 RL 來源 AF3 的研究整併與本地循環交接已通過離線驗收。真實 A/B/C 實驗證據仍未完成。**
已發布來源與 CPU 元件驗證不能替代 Qwen／LoRA replay、GPU、完整比較或 ARC 分數。
本環境只進行離線開發；真實訓練、執行與提交仍由本地端依其來源、材料與權限處理。

## 一、文件責任與更新規則

- **本頁：** 唯一維護當前狀態、計畫、任務依賴、驗收條件、證據索引與下一步。
  每次有實作、測試、審查或發布結果，先更新對應任務列，再補證據與日期；未取得的結果保持未知。
- [資料夾 README](README.md)只提供導覽；根目錄、research 與 docs 索引只連到本頁。
  [NEXT-STAGE-PLAN](NEXT-STAGE-PLAN.zh-TW.md)保留舊路徑與標題連結，不另維護一份計畫。
- [本地交接](OFFLINE-LOCAL-HANDOFF.md)維護使用方式與安全限制；方法總覽、論文附錄、
  固定來源及歷史審查保存技術理由與當時證據，不回寫成新的執行結果。
- 狀態用語：`待開始`、`進行中`、`待驗收`、`完成`、`受阻`。只有滿足該列完成條件並有
  精確證據才標為完成。對真實實驗另註明 `未執行／未驗證`，不以支援工具進度代替。
- 證據應記錄精確 source SHA、適用範圍、命令／測試結果、審查或 CI 連結及限制。
  發布須記錄 commit／tree／branch readback；本地測試、Git 保存、CI、模型與方法效果分開。
  新結果追加或明確替代舊狀態；舊失敗、實體成本、來源與時鐘不刪除。

## 二、目前基線與證據索引

| 證據 ID | 已核對結果 | 邊界與來源 |
| --- | --- | --- |
| E0 | Stage 0 已發布 `0d4d19c71d2c84720d4956b36d8e99108e8c0a2b`；normal 148／`-O` 148 通過 | [commit](https://github.com/Danwuoo/IRIS-X/commit/0d4d19c71d2c84720d4956b36d8e99108e8c0a2b)、[獨立審查](offline-continuation-review.md)；來源綁定 inert plan、collector 結構聚合與安全 I/O，不證明真實收集或模型成功 |
| E1 | 實際呼叫上游 `TrainingSample`、`DDISLoss`、`MeanMetricState` 三個元件；normal 25／`-O` 25 通過，合成 raw-logit loss／gradient 差為 0 | [整合說明](agent-factory3/integration.zh-TW.md)、[驗證](agent-factory3/validation.md)、[獨立審查](agent-factory3/independent-review.md)；僅 synthetic CPU，沒有真實 Qwen／LoRA graph |
| E2 | 2026-10-14 16:10 UTC 最終發布核對：`66e54c90febd4d7f1a1e08f1f8b0e8d6c7c671ca`；tree `d74130a4f20ba45998fbf0d73858608536ffc824`；33 個變動檔案 readback | [commit](https://github.com/Danwuoo/IRIS-X/commit/66e54c90febd4d7f1a1e08f1f8b0e8d6c7c671ca)；包含 E1 與原導覽／計畫。run008 維持 `cc14bd1a`；本頁後續工作尚需自己的新版本核對 |
| E3 | E2 的精確 [CI run38595816563](https://github.com/Danwuoo/IRIS-X/actions/runs/38595816563) 已結束：failure；1 個 job 失敗、3 個 cancelled | repository invariants 的 6 項既有 README 缺詞；unit／packaging 步驟 skipped，不能稱 CI 通過 |
| E4 | 歷史本地完整 suite：1,583 tests、2 failures、35 errors、74 skips；AF3 加入前後 failure／error IDs 相同 | [驗證紀錄](agent-factory3/validation.md)、[當時文件審查](documentation-update-review.md)；這是前次文件更新前的完整 suite，不能當本輪重跑結果 |
| E5 | exact upstream `metric_state.py` 保留 EOF 空白行格式警告 | [來源 manifest](../../tools/arc2_agent_factory3_bridge_20261014/source-manifest.json)、[當時文件審查](documentation-update-review.md)；不修改 vendor bytes 來隱藏 warning |
| E6 | 單一進度文件與導覽整理已於 `ec9237fc607d592ac262b9881e276d23bb06de22` 保存；tree `1c3111cfe79e8f30f93d5c7af7bc4cdacc48609f`，8檔遠端bytes核對一致 | [commit](https://github.com/Danwuoo/IRIS-X/commit/ec9237fc607d592ac262b9881e276d23bb06de22)；屬文件checkpoint，不含其後Stage1新程式；[該版本CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38600128382)結束為failure：2 jobs failure、2 cancelled；實際job115976922494仍為同6項README缺詞，unit／packaging skipped，不能沿用為新程式驗收 |
| E7 | 最終獨立 focused：Stage0 148＋AF3 25＋Stage1 60＝233 normal／233 `-O`，六次package discovery全數通過、無skip，測前後執行碼hash不變 | [本輪獨立審查](stage1-independent-review.md)；新60項為audit25、streaming21、CLI14，僅CPU與合成producer-schema；含原producer／consumer64 trajectories互通、真process timeout／SIGTERM／cleanup |
| E8 | 本輪exact66基線與最終來源各重跑完整suite，均1,583 tests／2 failures／35 errors／74 skips；37個failure／error IDs及skip-reason計數一致 | [本輪獨立審查](stage1-independent-review.md)；無新增失敗，但整體仍失敗。新工具測試由E7獨立discovery覆蓋，不能把既有root suite數目當新工具覆蓋 |
| E9 | [逐軌跡API與本地shadow規格](../../tools/arc2_abc_continuation_20261014/README.md#local-shadow-wiring-specification)完成來源→adapter→owner映射、同A／同batch／同unchanged-policy對照與全成本契約 | 實際介面仍CPU-only；未接CUDA模型、沒有真實歷史audit。安全reader16MiB不變，另做88MiB超限正常／`-O`拒絕測試，不能聲稱支援全部可能audit大小 |
| E10 | 本輪程式已發布 `8b9ca9cf915969e15339d99bc090762f349f1572`，tree `cedac0a7486685c641506335930d7f6ab429b514`，15檔遠端bytes全部一致；run008遠端仍`cc14bd1a` | [commit](https://github.com/Danwuoo/IRIS-X/commit/8b9ca9cf915969e15339d99bc090762f349f1572)；本次來源／測試／審查／交接皆已保存，核對當時本地HEAD對齊且工作區乾淨；以下文件收據更新不改執行碼 |
| E11 | E10精確CI run38602023452已結束failure：1 job failure、3 cancelled | [CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38602023452)；實際job115983374504仍為同6項README缺詞；unit／packaging skipped。這是本輪實際讀取，非沿用E3／E6；不能稱CI綠燈 |
| E12 | 文件收據已發布 `e17b6857ee6e874b2b5ed28a766f35e0b8028ea2`，tree `408182146a41cfbba7dbb9ead040b54e4790587a`，15檔遠端bytes再次相符；精確CI38602503929結束failure，1failure／3cancelled | [commit](https://github.com/Danwuoo/IRIS-X/commit/e17b6857ee6e874b2b5ed28a766f35e0b8028ea2)、[CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38602503929)；實際job115985000987仍為同6項README缺詞，unit／packaging skipped；本次之後的文件整併另驗 |
| E13 | 本次docs-only整併獨立驗收：233 normal／233 `-O`全通過；fresh root suite仍1,583 tests／2 failures／35 errors／74 skips，37個failure/error IDs、skip-reason計數與E8兩份歷史logs一致 | 本次只重跑final，沒有再跑baseline；2,388個non-Markdown檔測前後不變，20來源pins、4vendor SHA／Git blobs及14handoff hashes相符。20份Markdown的183相對links／21anchors零問題，舊AF3研究路徑已清除。normal／`-O`實際placement仍同6項README findings |

發布歷史仍保留：15:44／15:46 UTC 的 tree 發布嘗試回傳取消，15:54 重試取得 tree；
16:06 寫入前遠端研究分支仍是 `0d4d19c`。E2 才是後續 commit／branch／tree 的核對，
不能把取得 tree 當成當時已發布。歷史審查中「尚未發布」依其時間理解。

E3 的六個缺詞為 `Engineering Trials`、`Decision 0010`、`Decision 0012`、
`Decision 0014`、`Decision 0015`、`Trial 001 status page`。既有 validator 未被豁免；
CI 問題與缺失歷史 fixtures 不可由 targeted CPU 通過抵銷。


本次E13的 `final-all.log` SHA-256 為
`9695d2fae52228d07ba2456d29d939cdce43f038e4d6b3b7ff2d024c889bc355`；
normal／`-O` placement logs 均為
`4514bf93b3d3d75e03666042d91439f70c27617a47cb33ccbdcd8d5899b5522a`。
這些是本地驗收收據，不把舊CI代稱為本次CI；此次文件交付的精確Git版本與其Actions
結果由該次交付一併核對，執行端不得只依移動分支或本頁文字建立執行身分。

## 三、任務、依賴與下一步

科學實驗仍按[方法總覽第 7 節](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)推進。
下列 `S1-O` 是 Stage 1 的離線支援任務，不是新的實驗 arm；`S1-E` 才是真實證據工作。
固定 A=SFT256；B=32 個固定 training parents、最多 4 個互斥 64-slot batch；
C=從同一 A 做完整 B 額外 model-phase wall 配對的 SFT。固定 dev 選擇、no-TTT、
PUBLIC120 tasks／167 queries 不變。不得加抽樣、換 parent、改分母、加入 OPSM／entropy／async
或混入新方法。

原A/B/C仍使用凍結runtime的本地DDIS數學；本輪AF3 companion可在結果產生後分析保存的audit。
它不是原baseline的新增啟動gate。只有改動訓練runtime真正接入AF3時，才另立模型hook與
successor驗收，不把CPU-only工具限制變成原A/B/C的循環依賴。

| 任務 ID | 工作與責任範圍 | 狀態／現有證據 | 依賴 | 完成條件與下一步 |
| --- | --- | --- | --- | --- |
| S0 | 既有離線準備與 collector 解讀 | 完成；E0 | 凍結來源 | 保留既有介面與原始 bytes；不重做同功能工具 |
| AF3-0 | 實際上游元件 CPU bridge | 完成；E1、E2 | S0、固定上游 | 元件使用及 synthetic parity 已成立；模型接線另列 |
| S1-O1 | training-only audit → AF3 loss 的純 adapter 與精簡報告 | 完成；E7、E9；audit25 normal／25 `-O`，原producer／consumer互通通過 | S0、AF3-0、原 audit schema | 驗證全 64 slots、source／context／replay／recorded loss；保留 unknown／rejection；依第五節完成正負例與審查 |
| S1-O2 | 真正 upstream loss 的逐軌跡 reduction | 完成；E7；streaming21 normal／21 `-O`，原bridge25／25回歸通過 | AF3-0、全 batch 契約 | 固定 `M×8×T_i`；不保留 64 個模型 graphs；比對 frozen／full／sequential scalar、gradient 與 metric weighting |
| S1-O3 | 獨立 opt-in audit-loss CLI 與既有安全 reader 接線 | 完成；E7；CLI14 normal／14 `-O`，語意拒絕、真process timeout／SIGTERM／cleanup通過 | S1-O1、S0 安全 I/O | 原 prepare／analyze 仍只需標準函式庫；顯式檔案與獨立 hash；超限拒絕、無搜尋、無靜默放寬，完成 CLI／timeout／cleanup 測試 |
| S1-O4 | 離線整合、失敗測試與獨立審查 | 完成（有限離線範圍）；E7、E8；233／233及paired aggregate精確分類，整體suite仍失敗 | S1-O1～O3 的最終 bytes | normal／`-O` 與 CPU integration 分列；驗證 frozen source 未變、無提前 commit、graph 釋放；列實測 IDs、限制與 reviewer 結論 |
| S1-O5 | source-bound、預設不執行的本地 shadow 接線規格 | 完成（規格）；E9；[實際介面與owner邊界](../../tools/arc2_abc_continuation_20261014/README.md#local-shadow-wiring-specification)已獨立審查，模型接線未執行 | S1-O1～O4 | 以同一 A／完整 training batch／unchanged-policy replay 定義 loss、LoRA gradient 與全成本對照；本地需求、缺件與原 admission 逐項可核對 |
| S1-O6 | 來源保存與精確交付核對 | 完成（程式保存與核對）；E10已核對15檔；E11精確CI失敗已分類 | S1-O4、S1-O5 | 依已授權發布流程核對新 commit／tree／branch 與變動檔案；另讀該 SHA 的 CI，不沿用 E3；不改 main、run008、PR #9 |
| DOC-AF3 | AF3研究來源併入本資料夾，修復導覽與引用 | 完成（文件整併）；E13，三份獨特研究／驗證／審查與重要RL來源地位保留 | E1、E7、E12 | 保留pinned上游、license與元件實際採用證據；不改程式namespace／vendor／frozen source，無重複進度頁 |
| HANDOFF-CYCLE | 將既有本地交接延伸為提交、監看、有限工程修復及結果回傳流程 | 完成（交接規格）；E13，只更新既有交接文件；實際本地執行另列E1～E4 | S1-O1～O6、原執行契約 | 明列fresh remote／材料／admission、single publisher、監看到terminal、結果回傳與方法觸發條件；本文件不派發工作 |
| S1-E1 | 本地真實來源、模型材料與已存在audit接收 | 待本地核對；本環境未取得真實材料，本輪audit尚待產出 | 原執行契約、本地來源與材料 | 核對training-owned provenance／原records／排除；有既有audit即檢查原bytes與size。首次原A/B/C可在原admission通過後產生audit，不以尚未產出的結果阻擋原流程 |
| S1-E2 | 原runtime真實replay／LoRA梯度／owner狀態驗收 | 待開始／未執行 | S1-E1、本地完整原admission | E2與E3是同次原執行中的驗收，不要求先有另一場成功證據。原runtime逐步核對模型、數值、rollback、save/reload、closure與資源；CPU logp梯度不能替代。若另接AF3模型hook，才加另立successor的同模型差分驗收 |
| S1-E3 | 同 session 既有 A/B/C 比較 | 待開始／未驗證 | S1-E1、原admission／batch／時鐘；E2由該次原runtime逐步驗收 | 原 reward、replay、更新、checkpoint、全 B/C wall、固定選擇與 closure 證據完整；未完成與 zero-signal 分開 |
| S1-E4 | sealed 評分與研究判讀 | 待開始／未驗證 | S1-E3、隔離 evaluator、原 scorer | 完整 PUBLIC120／167 與相同案例 gain／loss；B 同時對 A、等成本 C 判讀；缺評分保持未知，不 promotion |

**現在的下一步：** 以此次交付的精確commit／tree接續，
由已授權的本地執行端按S1-E1核對真實來源、材料與原admission，開始原E3流程，
由原runtime在該次執行中逐步完成E2驗收並產生audit；已有audit再核對其檔案大小。
沒有材料或接收端可執行授權時，保存明確blocker，不由本環境代替提交或訓練。
S1-O1～O6只完成有限離線工具、接線規格與來源保存。本地 E1～E4 的
執行不由這份進度表啟動；取得接收端真實證據後才更新實驗狀態。S1-E4 完整前，不把
Stage 1 標成研究完成，也不提前轉向 Stage 2／TTT／Agent 新方法。

## 四、技術設計與原始來源

目標是讓已實際採用的 Agent Factory 3 元件具備可接續原 runtime 的**完整 batch
契約＋逐軌跡 shadow loss**接口，而不是直接把64條真實模型 graph 堆到記憶體。
新碼應使用獨立 successor 路徑與身分；原 run008、actor、math、plan、producer、
collector 與 scorer 保留原 bytes。不能 monkey-patch 原 frozen 模組或用新 identity 冒充舊版本。

AF3-0 的原 bridge 先驗證64個 declarations，再一次呼叫 upstream
`compute_unpacked`；它只接受 CPU replay tensors。本輪 O2 已完成完整 batch 驗證後
的逐軌跡 CPU reduction；尚待本地處理的是與真實模型 owner／device 的接點，
並非再證明同一個小 tensor 公式。

來源接點：
- [原 runtime 更新流程](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/runtime.py#L396-L496)：完整 batch、逐軌跡 replay／backward、全部 admission 後才 commit。
- [原 actor identity 與 support](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/actor.py)：原始 token、DFA、權重／cache／來源一致性。
- [目前 bridge](../../tools/arc2_agent_factory3_bridge_20261014/bridge.py)、[實際上游來源 manifest](../../tools/arc2_agent_factory3_bridge_20261014/source-manifest.json)、[CPU proof](../../tools/arc2_agent_factory3_bridge_20261014/proof.py)。

## 五、離線實作與驗收契約

以下保留由既有計畫導出的驗收要求；本輪完成狀態與證據以第三節 S1-O 表為準。

### S1-O1：完整 batch 的非機密接線契約

第一個真實來源接點是**已存在的 training-only audit 檔**，不是 stage0 compact report。
`TERMINAL-VALIDATION.json` 沒有原始 trajectories，不能由它反推或補造。原
[`experiment_flow/flow.py`](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/experiment_flow/flow.py#L220-L246)
將 `{batch, summary, update, ...}` 保存為 `experiment/audit/sweep-N.json`，其中
`update.replays[]` 保留 `log_pi`／`log_mu`／`detached_DDIS_loss`；原
[`audit_checks.py`](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer/audit_checks.py#L201-L275)
已有逐軌跡對照責任。先做明確指定檔案＋獨立來源hash的離線 audit adapter，保存原拒絕／
缺失狀態；沒有真實檔案時只交 synthetic schema 測試。

stage0 單檔上限16MiB不能直接放寬；原證據規畫的單batch audit上界約88MiB，不代表
實際檔案都如此大。先核對實際size，超限明確拒絕；若確實需要較大輸入，另審有界reader
的大小／深度／JSON／no-follow／中斷cleanup設計，不能偷偷改既有安全上限。
只使用保存的 logp 可以重算loss及 `∂loss/∂logp`，無法重建模型graph、LoRA梯度或真實replay。
這個 audit-loss companion 使用獨立 opt-in 入口；既有 stage0 prepare／analyze 保持標準
函式庫與原介面，不暗中載入 PyTorch。目前輸出僅保留不含原始tokens／grids的緊湊
batch conformance與unknown／rejection分類，對照原 recorded `detached_DDIS_loss`。
只有宣告性資料時，仍明列 provenance 未驗證；不能改名成新的 collector 成功收據。

先列出 producer 欄位→bridge 欄位→owner 核對責任的逐項映射：固定32 parents／records、
batch0–3、每批8×8完整 slots、policy identity、generation epoch、actor／cache mode、
原始 prompt/generated IDs、位置、DFA support／states、behavior logp、reward provenance。
只能以 training-owned receipt 作將來真實來源；不能從 evaluator 答案或 PUBLIC outcome
補欄位。metadata 自洽不是 provenance authentication，沒有的證據保持 missing。

交付應是獨立 adapter 契約與 fabricated 非ARC fixtures。測試覆蓋錯版本、缺／重／亂序slot、
混合 cache／prompt、fatal／stop、retokenization、source drift、未知／非法reward與 zero-signal。
不新增登入、provider 操作、檔案搜尋或秘密資料讀取功能。

### S1-O2：使用真正 upstream loss 的逐軌跡 reduction

完整 batch 必須先通過現有結構檢查，固定 advantage 與分母 `M×8×T_i`，然後逐軌跡
計算 upstream contribution；不得對單條 trajectory 重算 group baseline／M 或當成一個新batch。
本次 upstream bytes 與 license 保留，streaming 邏輯寫在新 glue。零advantage仍保留原 replay
診斷要求，整批 M=0 則不做 replay／loss／更新。

CPU 驗收：同一64-slot synthetic batch 比較 frozen local、目前 full upstream與新streaming
scalar／原始 logits gradients／metric weighting；不同長度、mixed counts、嚴格ratio邊界、
zero groups 均需通過。normal／`-O`、失敗／timeout／cleanup、graph釋放與禁止提前commit
測試分開列出。不得以 mock 成功聲稱真實 owner rollback 或模型梯度驗證。

### S1-O5：本地模型接線的 shadow 規格與交接

產出 source-bound、預設不執行的接線規格；在本地另行審查的 successor 上，從**同一A、
同一完整原始 training batch、相同 unchanged-policy replay**比較本地與上游的 loss／
LoRA各target梯度。不能用額外抽樣、不同tokenization或不同模型副本掩蓋差異。

shadow 計算不是免費：新增 forward／backward、hash、Python、同步、記憶體、保存及失敗
成本全部記錄。若接進正式 B，其整段額外 wall 必須由 C 匹配，且仍受原整場12h與各
operation／batch期限限制。若作另立診斷，不可把它的成本或結果移植成既有 A/B/C 的證據。

此階段目前只準備接口、非模型 CPU 測試與本地交接，不在本環境載入Qwen、執行LoRA、
建立新GPU工作、提交Kaggle或呼叫本地executor。真正模型驗收仍需接收端的來源與材料。

## 六、本地模型證據的驗收契約

| 項目 | 已有 | 本地真實接線仍須提供 |
| --- | --- | --- |
| 來源與數學 | 固定 upstream／frozen local hashes、合成loss／logit-gradient parity | successor封裝與實際執行source一致，不能沿用舊admission |
| reward／資料 | 完整slot與排除宣告檢查 | authenticated train-only lineage、原records與排除、實際reward；無PUBLIC答案流入 |
| actor與replay | 原IDs／prefix／DFA宣告／version一致性 | 同原模型與adapter、真實DFA support、teacher-forcing causal alignment與cache實證 |
| 數值 | synthetic零差、strict bounds | 原nonforced max≤.20／p95≤.05／unclipped=1，以及每個LoRA tensor finite gradient、至少一個非零；不能只看scalar loss |
| 狀態與失敗 | CPU負例與結構拒絕 | 零更新前權重不變、完整batch才commit、真實rollback、save/reload、owner終止與完整receipt |
| 資源與結果 | 小CPU fixture | 單訓練GPU的peak memory／全B wall；最終4×L4另驗；原完整A/B/C與PUBLIC120／167評分 |

以上重申既有契約，不另加與研究問題無關的管理門檻。缺一項不能改寫為0分、已驗證或放行。

## 七、既有決策條件

科學方法的完整次序、最低對照與推進／停止條件，只維護於
[方法總覽第7節](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)。
目前仍是Stage1既有A/B/C；只有本地回傳的實際reward、replay、checkpoint、成本、
closure與完整評分證據，才能決定是否進入2a／2b或後續TTT／Agent／selector消融。
工程失敗先處理同範圍工程問題；完整零訊號與未完成不混用，不按輪次自動換方法。

**Agent Factory 3 是重要RL方法來源及已實際採用的上游元件。**
本輪保留其pinned `a1836decb836cd52cf2b27f5022f6838cee75df3`、Apache-2.0來源、
DDIS數學與真實元件CPU整合證據，集中於[AF3整合研究](agent-factory3/integration.zh-TW.md)。
文件位置整併不代表移除該方法、換演算法或已完成模型接線；將來是否改目標／訓練機制，
仍由上述既有條件與成本對照決定，不把框架名稱當成新的實驗證據。

## 八、離線交付與後續更新驗收

1. 從根 README／research／docs 索引可直達本頁；資料夾 README 只導覽，舊計畫路徑與
   標題可繼續使用，使用說明不複製 mutable status。歷史證據與獨特科學內容完整保留。
2. S1-O4 驗收須針對實作完成後的最終 bytes，保存獨立 review、normal／`-O`、適當 CPU
   integration、source invariance 與精確失敗分類。未重跑的完整 suite 明確標示未重跑。
3. S1-O6 每次只填實際核對到的 commit／tree／branch／檔案與精確 CI；未完成的發布或
   CI 保持待驗。Git 保存不代表執行授權，CI 失敗不改寫為方法失敗。
4. 接收本地結果時，依 S1-E1～E4 補證據與剩餘缺項；每一項都保留原版本、成本和失敗。
   只有完整研究結果才能觸發第七節及方法總覽的後續實驗條件。

## 九、開發與本地執行循環

| 順序 | 責任與交付 | 轉交條件 |
| --- | --- | --- |
| 1 | 研究開發端依第七節選定仍待解答的同一問題，實作、normal／`-O`／失敗測試、獨立審查、保存完整來源與交接 | 固定commit／tree、review與缺件可核對；不得把CPU支援完成當真實實驗完成 |
| 2 | 本地執行端接收固定版本，核對原材料、現有notebook／dataset／source／mounts／status及無重複run | 原admission與目前執行授權均成立；任何歷史版本號都不能取代fresh readback |
| 3 | 單一發布者按原流程提交；持續監看至terminal，抓取原logs／結果；必要時做明確有限的工程修復 | 保存每次來源、實體成本、clock與失敗；方法／門檻／分母／budget變更回研究端審查，不當成小修 |
| 4 | 本地回傳非機密狀態、完整性與成本摘要、來源／結果hash及隔離保存位置；研究端驗證並更新本頁 | 原evaluator答案只留隔離側；無評分仍未知。再依第七節選下一個開發問題，而非任意輪換方法 |

具體材料、命令、提交／監看／修復界線與回傳格式統一維護在
[既有本地交接](OFFLINE-LOCAL-HANDOFF.md)，不再新增第二份同功能交接。
本頁只管理責任、狀態與依賴；訓練／提交必須在已授權的本地接收環境執行，
研究開發環境不替代該執行責任。若接收端不可執行、原材料缺失或遠端結果不確定，
先保留可重現交付與精確blocker，待問題解決後從同一階段續接。

### 更新紀錄

- 2026-10-14：從原 NEXT-STAGE-PLAN 與方法總覽第 7 節整理單一管理頁，納入已核對的
  E0～E5；Stage 1 離線實作進行中，真實 A/B/C／GPU／ARC 證據仍未建立。
  文件整合本身不代表 S1-O4 的程式驗收或新版本發布完成。

- 2026-10-14 16:45 UTC：E6已遠端核對；新audit／streaming／CLI進入最終離線驗收。
  審查已修正原native event_id整數相容性與float32 metric padding寬度差異，未改數學門檻。
  這些是支援程式實測，Stage1真實A/B/C仍未執行。

- 2026-10-14 16:50 UTC：最終233 normal／233 `-O`及本輪paired aggregate核對完成；
  E7～E9更新，S1-O1～O5驗收範圍明列為離線工具／規格，S1-O6仍待本次發布。

- 2026-10-14 16:55 UTC：E10已核對commit／tree／15檔bytes及未改run008；
  E11已讀取精確CI終態與實際失敗log，仍為原6項README缺詞；真正模型與完整A/B/C結果保持未驗證。

- 2026-10-14 17:01 UTC：開始DOC-AF3與HANDOFF-CYCLE，依既有方法觸發條件延續開發／本地執行循環；
  不跳過Stage1真實證據，不把AF3降為單純參考，也不在研究環境啟動訓練。

- 2026-10-14 17:09 UTC：DOC-AF3與HANDOFF-CYCLE通過獨立驗收，E13記錄本次重跑；
  原A/B/C先依原admission執行並產生audits，AF3模型hook仍是分開審查的後續接線。
