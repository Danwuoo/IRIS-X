# ARC-AGI-2 開發進度管理

更新：2026-10-15 UTC；本頁為持續更新的唯一進度管理文件。
研究交付分支：`feat/arc2-sft-rl-continuation-20261014`；本地接手紀錄分支：
`fix/arc2-abc-local-execution-20261015`。
本次狹窄 portability 修復另在 `fix/arc2-abc-portable-publication-20261015`，
起點為本地補證 commit `286fdb302771e81e9deaf40f948cea264abacbe5`；不覆寫前兩條線。
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
| E14 | 2026-10-15本地接手：獨立checkout與遠端研究HEAD均為`fe21075521aa7305f2f5361f68cd301ea2b0d83b`，tree `6ba90e18bfe419d06c4bfc65212af21e647194d2`；凍結來源遠端仍`cc14bd1a` | 實際PowerShell／Git／Python與WSL命令可執行；未改原工作區、main或PR #9。原歷史snapshot `e951604b829497e81bc6e18b32662ff050bd54db`的tree已核對為`f9b10d12b912f3a92238375451c0ad56d4cb7efb` |
| E15 | 2026-10-15 04:57:11 UTC官方唯讀觀察：code Dataset **v20**、[notebook](https://www.kaggle.com/code/danielwuu/iris-x-learning-agent-20261011) numeric **v39** status為**ERROR**；source SHA256 `a3076380789de383c1df7c710023d8ca9e9a64a37405547bcebf0e066405d4b9` | Dataset與notebook前後身分／版本及source一致，六件SDK解碼後觀察留在ignored側；並非HTTP wire bytes或run008 admission。現有登入可讀，沒有resource／credential mutation、quota查詢、新RUN或新PUBLIC分數；不能把歷史v39當本輪A/B/C結果 |
| E16 | 本地實測與獨立portability來源審查確認無可直接使用的run008入口：Windows Kaggle2.2.4／SDK0.1.36；既有WSL venv為SDK0.1.36且缺Kaggle，均不符鎖定2.2.4／0.1.37與完整source closure | 原launcher／config綁定原wrapper、venv及wrapper HOME；不能偽造它們或整個換回舊抽取token的adapter。需目的環境狹窄successor、原source-lock、官方內部認證、real HOME／Windows ACL及其相依action／collector／active-wire審查；尚未產出放行收據 |
| E17 | 本地transfer控制流程10 normal／10 `-O`通過；Stage0在WSL ext4 scratch為148 normal／148 `-O`通過 | 先前DrvFS scratch的148 tests各有14 failures／21 errors，涉及0700、FIFO與rename語意，失敗logs保留；只更換支援的scratch，沒有改gate。沒有安裝Torch或重跑AF3／Stage1，E7／E13的233／233仍是雲端歷史證據，不能代稱本機通過 |
| E18 | 接手後executor transport中斷兩次，後續於2026-10-15 05:01 UTC恢復並以實際命令核對；WSL原程序已不在，該次位於ext4 `/tmp`的scratch目錄亦不在 | ext4重建未取得結果，本地`repository_check.py --all`只留部分unit log而無終態，均列interrupted／unknown，沒有補造通過。第一份invariants另有本地clone未帶archive tag的缺件；從原本機Git取回該tag後，獨立invariants重跑仍為同6項README缺詞、exit1，沒有其他finding。沒有Kaggle RUN在本輪等待監看，封包／提交仍未完成 |
| E19 | 移轉補證：原`launch.py publish --help`安全前置檢查實際exit1，在第45行讀取不存在的`[checkout-parent]/kaggle_setup/kaggle.sh`時拋出`FileNotFoundError: [Errno 2] No such file or directory`，未進認證或建立provider | 只核對環境／來源／本地錯誤，不安裝依賴、不改發布器、不呼叫Kaggle。Windows Python3.12.10、WSL舊operator venv Python3.12.3；SDK差異仍同E16。等待協調者交付Astra修復commit後才續接 |
| E20 | 2026-10-15官方registry wheel靜態比對：Kaggle2.2.4／SDK0.1.37的170個Python來源全部符合原sdk-lock，missing／extra／mismatch皆0；兩wheel均宣告Python>=3.11 | [精確wheel來源與hash](../../tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/SDK-WHEEL-PROVENANCE.json)。未import SDK、登入或呼叫provider；不代表已完成目的端安裝、全相依鎖定或認證 |
| E21 | 目的環境離線修復完成：獨立POSIX successor以真實HOME、明確venv／executable SHA／Python patch／SDKroot取代歷史wrapper；原mutation／collector／官方session行為由AST等價回歸核對，active-wire獨立綁定精確numeric versions | [介面與來源邊界](../../tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/README.md)。獨立審查無剩餘新blocking finding；90個受保護來源與286fdb3完全一致，7個原transport來源亦符合cc14bd1 Git objects。實際提交仍需目的端認證、材料與admission |
| E22 | Portability final106 normal／106 `-O`全部通過、零skip；獨立reviewer另跑同106／106。另以實際copied venv各模式核對runtime boundary及170個已安裝官方source，未import SDK／讀credentials／呼叫provider | [固定驗收收據及逐檔hash](../../tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/VALIDATION.json)。真process lock／timeout／cleanup、FIFO／symlink替換、四條TLS路徑及frozen producer互通均涵蓋；source probe是刻意未裝全Kaggle相依的測試venv，不代稱目的端環境可用 |
| E23 | 本次完整repo suite實跑1,583 tests／2 failures／35 errors／74 skips；37個failure/error IDs與E13歷史log完全相同，新增／缺少均0 | 本輪未重跑baseline，不能稱paired新比較。獨立normal／`-O` placement仍同6項README缺詞；沒有新placement finding。失敗與初次缺Requests、synthetic proxy expectation、numeric回讀producer不符的修正前logs皆保留；focused通過不能抵銷aggregate或CI失敗 |
| E24 | POSIX successor 已發布 `b09e442fe706f06545be2cb4aa3363e04f807a71`，tree `746cc76943dea5913975fc4dcbd271b6424eeffc`；19檔Git取回逐byte與最終reviewed index／worktree相符 | [commit](https://github.com/Danwuoo/IRIS-X/commit/b09e442fe706f06545be2cb4aa3363e04f807a71)；只完成E21／E22離線來源保存，不代表Windows橋、原認證、材料重建或provider admission完成 |
| E25 | E24精確CI38688413326終態failure：1 job failure／3 cancelled | [CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38688413326)；實際job116268483868仍是同6項README缺詞，unit／packaging skipped；沒有稱CI成功 |
| E26 | Windows／WSL整合的本地合成能力前置：executor實際命令成功；Windows目前已在existing job內，仍可將suspended合成子程序指派新Job Object。關閉job handle及強制終止controller兩種情境，已持有handle的root／leaf均signaled且controller已wait | 此為固定合成程序的有限觀察；job accounting在清理前為4個active processes，測試只逐一追蹤root／leaf，不宣稱完整job inventory、跨OS取消或production closure通過。未載入Kaggle／認證，未改ACL ；來源為本地獨立紀錄 [b51c4ae3](https://github.com/Danwuoo/IRIS-X/commit/b51c4ae3b0f81e0823a3db731a21d68047967c57)，此處重新編號保留其範圍 |
| E27 | 固定script endpoints的Windows→WSL→Windows Python／PowerShell→WSL→Windows管線4／4通過：2,067 bytes含UTF-8／NUL／binary，stdout逐byte一致、stderr分離，exit0／7均正確傳遞 | 先前雙層inline `-c`形式產生`SyntaxError: unterminated string literal`，失敗保留；不是auth錯誤。未驗證正式framing、oversize、超時／取消與大型串流。既有profile／store／credential ACL與reparse僅查metadata；profile根目錄的owner／Allow不同於credential檔，不能混同為POSIX0600／UID gate；沒有改任何權限 ；來源為本地獨立紀錄 [b51c4ae3](https://github.com/Danwuoo/IRIS-X/commit/b51c4ae3b0f81e0823a3db731a21d68047967c57)，此處重新編號保留其範圍 |
| E28 | 原生diagnostic `8f2a6d032e01b02aa0563c851cbb1be60946bd67`、tree `41520ec7a3297573d521b0c72e26c187dd5fbf8a` 已逐byte回讀；本地Windows3.12.10 `-I -B`實際exit0、約7.01秒、stderr0，原8案例全通過 | stdout SHA256 `622d3651d30cf212a37df0665b19618179306dfa493ab33c3cd3d08cfe70a98f`；實際native parent死亡、Job owner強殺、deadline／EOF均觀察完整outer Job歸零，metadata負例與mutex亦通過。只適用該三檔來源及當時global Python；尚未測目前新framing／phase watchdog／venv／正式CLI／OAuth，不重標為新來源PASS |
| E29 | E28精確CI38689806693終態failure：1 job failure／3 cancelled | [CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38689806693)；實際job116272866733仍同6項README缺詞，unit／packaging skipped；與本地native測試各自記錄 |
| E30 | 本地新建單一Windows Python3.12.10 venv，官方Kaggle2.2.4／SDK0.1.37，完整35套件安裝；`pip check` exit0、170-source lock全數一致 | ENV-RECEIPT SHA256 `ec2daea5687f0feae32fcc0d7675baf2649d35da7f156ab38ed975713f3593fc`。官方wheel hashes與E20一致；初次Temp失敗保留，同venv改用project Temp後完成。沒有import SDK／登入／讀credential或修改HOME／ACL；原global SDK0.1.36保留。只證明安裝／靜態來源，尚未執行新版native probe或provider |
| E31 | Windows／WSL bridge最終離線232 normal／232 `-O`、zero skips；獨立reviewer對同一snapshot另跑232／232，25個source／test檔前後不變，22個dependency pins吻合 | [固定來源與驗收收據](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。涵蓋實際binary pipe DTO／fsync／opaque upload／404及503／unknown不重送／15檔Git與review closure、十案例及pre-auth harness的合成負例。原collector所有function／class AST不變；transport僅update_code、review_gate、git_publication_gate三項有界差異。尚未有新版native／WSL／正式pre-auth實測或provider admission |
| E32 | 最終code凍結後再次執行完整repo suite：1,583 tests／2 failures／35 errors／74 skips；37個failure/error IDs與保存的POSIX baseline相同，未重跑baseline | [本輪精確收據](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。workspace TMPDIR及offline flags齊備；root suite不涵蓋E31獨立232 tests。既有6項README finding仍失敗；初次錯誤TMPDIR的partial run保留，不能當合格比較 |
| E33 | Bridge來源正式發布 `d684f63cf6c52044dee4359f84f6cc75527db734`，tree `03ecf14a07ad584803aebb94954a5c59f24b4476`；remote branch／29檔Git、index與worktree逐byte一致 | [固定commit](https://github.com/Danwuoo/IRIS-X/commit/d684f63cf6c52044dee4359f84f6cc75527db734)；分支`fix/arc2-abc-portable-publication-20261015`，本地三項驗收固定這個程式版本。公開payload只有source／tests／非秘密handoff，沒有credential／evaluator答案或raw logs；發布完成不等於provider放行 |
| E34 | E33精確CI38693296388已completed／failure：1 job failure、3 cancelled | [CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38693296388)；實際job116283954687仍為6項既有README缺詞，unit／packaging skipped。新bridge focused與完整suite結果分別見E31／E32；不混同為CI成功 |
| E35 | 本地對d684f63的新Windows venv native十案例實測**失敗**：exit1、13.02秒、6／10通過。job_tree／parent_death為`probe_output_invalid`，framed_operation_deadline為`probe_native_watchdog_failed`，framed_official_rpc_deadline為`probe_internal_error` | stdout SHA256 `fa8b025996e538431f2bf090b0ab39f1af89650b752343f8d6290b596021e069`，capture SHA256 `1fc039a61d7fada28231108f94c306427800786cddbdc499fff2218e105a74bf`；27個module檔及runtime hashes符合。deadline、metadata含reparse、mutex、pipeEOF、source_unchanged、supervisor_kill通過，相關outer Job歸零；缺失原因尚未證明。WSL caller-death與pre-auth未執行，沒有auth／provider／upload／RUN；保留失敗並先增加精確合成診斷，不放寬門檻 |
| E36 | no-auth diagnostic successor完成244 normal／244 `-O`、zero skips；獨立reviewer另跑相關58／58並核對兩檔hash；僅native_probe與其測試有程式差異，production所有source／pins維持d684f63 | [分開標示的diagnostic_revision收據](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。回傳固定錯誤碼、數值Job flags與分階段結構資訊，無原始stderr／路徑／credentials；先證明Job歸零再有界讀取合成診斷。短operation timer移到合成open後，原overall lease不重設。新版native實測尚待本地，不把244離線測試當native PASS |
| E37 | 本地f998839診斷重跑exit1、13.58秒、仍6／10；job_tree實際membership true、兩query成功、immediate flags為12288（0x3000），被`windows_worker_job_limits_invalid`拒絕。parent_death三段handshake完整，最終receipt為0-byte EOF；兩framed案例為supervisor的`windows_worker_incomplete_command`及parent的`bridge_eof_or_invalid_read` | stdout SHA256 `8d3f02f3b161fd146a2f9f9687088975bfc2e778e0bf378643cc8018267b30e8`，capture SHA256 `2e1f4da6ed962061cbba118e974996c089fc4b61794a5af0cb2988350d3171c5`；原六案例及完整outer Job歸零仍通過。production bytes仍同d684，未auth／network。framed錯誤是在worker_exit後檢查未完成request產生，是否隨guard修正消失仍待實測 |
| E38 | 狹窄venv修復通過251 normal／251 `-O`、zero skips；獨立reviewer同251／251且25檔前後hash不變；production function差異只有`require_worker_job`，owned JobProcess與supervisor／SDK worker所有function／class AST保持原樣 | [venv_repair_revision完整來源收據](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。exact immediate 0x2000／0x3000及誠實flags分列，outer仍exact0x2000；parent-watch只換合成控制器拓樸，驗證base／venv bytes與雙方PID／完整membership。依賴pins同步更新；新版native／WSL／pre-auth與provider仍待本地，不能將離線測試當原生放行 |
| E39 | 本地對01ca4f14三項真實no-auth驗收全部通過：07:18:03–19 UTC native十案例10／10；07:20:24–27 WSL caller SIGKILL後8 members停止、observer Job 0；07:22:42–46正式CLI pre-auth valid ready、故意不ACK、nonce-bound Job 0 | [原生與interop收據摘要](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。三者outer exit0／stderr0，pre-auth inner exit124／caller_pipe_eof為預期拒絕繼續auth；parent-watch追蹤9 members、framed兩deadline均通過。27來源及runtime／config bytes不變，INDEX SHA256 `165c4d16cd5778ce45e1275980c9b6f714a1df31a65cc419833cf1ddfc13e467`。原始captures留本地；未SDK import／讀credential內容／provider call，20→21及39→40→41僅diagnostic配置、未保留版本 |
| E40 | 2026-10-15本地重新建立283／426／311材料、三份獨立review與8-binding LOCAL_CONTRACT_PASS；08:10:41.497818–08:10:55.955410 UTC正式readiness exit0，原生session closed且closure verified | 使用01ca4f14來源與原Windows官方登入；fresh observation仍code Dataset v20、notebook v39 ERROR及原source a3076380…。沒有新code／notebook版本、RUN或A/B/C結果；該成功receipt只適用readiness本次session |
| E41 | 隨後08:11:34.117961–08:11:35.537807 UTC update-code outer exit2、bridge_eof_or_invalid_read；停在新session sequence1 open，mutation_attempted=false，session UNKNOWN且native_process_closure_verified=false | 原29份state已封存，無retention inventory／codeclaim／upload／versionintent；原source／config／interop environment未變。實際native exit／stderr receipt／READY與phase未持久保存，不能推論未開始認證或Job已清空。FAILURE-HANDOFF SHA256 `21d7174e4fb8c0d7895052ce7e883663d2fb26ce17805e252b74882e7e4a991c`只識別本地封存證據；根因未知，舊UNKNOWN保持阻擋，不改寫history／namespace或重送 |
| E42 | failed-open診斷successor通過269 normal／269 `-O`、zero skips；獨立reviewer同269／269、22個static pins相符，無blocking finding。fresh完整suite仍1,583 tests／2 failures／35 errors／74 skips | [open_failure_diagnostic_revision](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。37個failure/error IDs與保存POSIX baseline相同，未重跑baseline；6項README findings未變。保留固定診斷／真實已取得closure，不改UNKNOWN、auth、deadline或mutation admission；新版native未測，E41原closure缺失不可回填。另行設計獨立recovery epoch仍需明確審查，沒有執行或放行 |

| E43 | ca8f0dca本地三項no-auth全部PASS：08:52:21–36 UTC native10／10；08:53:15–18 WSL caller-death八members停止／Job0；08:54:24–28 pre-auth READY有效、ACK=false、nonce-bound Job0 | 27來源Windows／WSL／Git相符且前後不變；SDK／credential／provider／network均未使用。INDEX SHA256 `62c18de1b4c2fdbc133669957968e81acb317857dc7a8b4ff52a8730c4d20222`；這些是新合成session，不能回填E41 closure。ca8[CI38708124018](https://github.com/Danwuoo/IRIS-X/actions/runs/38708124018)為failure，同6項README缺詞，unit／packaging skipped |
| E44 | 09:42:39 UTC本地完整枚舉原29檔：4根claim／journal＋25events、僅events子目錄；集合／大小／SHA均與封存相符，無hidden／tmp／link／special／JSON異常 | 精確01ca原碼要求refresh intent先經WSL exclusive claim、event及journal fsync，ACK後才controlled original_refresh。在固定source正常執行、可信主機且無外部刪改／rollback前提，未dispatch受控refresh；不等於auth未載入或外部grant狀態已知。原closed readiness無raw receipt，僅按原closed predicate、source及event驗證，不要求不存在的檔案 |
| E45 | 獨立recovery epoch離線完成：355 normal／355 `-O`及38 observer normal／38 `-O`全部通過、zero skips；獨立reviewer同數通過且來源前後不變，無剩餘offline blocking finding | 同STATE／publisher lock、原29檔不變；full Windows Restart為新的當前process boundary，challenge／host／boot／來源與runtime綁定；一次性read-only dataset→kernel→status→kernel→dataset及新Job0後保存固定completion seal。正常publication仍須原admission；無Restart／provider執行證據，不能標為已恢復 |

| E46 | 最終recovery executable source完整suite：1,621 tests／2 failures／35 errors／74 skips；新增38 root observer tests通過，37個failure/error IDs與保存ca8 baseline完全相同，未重跑baseline | 正確PYTHONHASHSEED=0、workspace TMPDIR、offline flags、CUDA_VISIBLE_DEVICES空值；仍同6項README findings，整體FAIL，bridge355 focused另行驗收。沒有新增failure/error IDs；來源及詳細logs hashes見[recovery_epoch_revision](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json) |

本地去敏觀察收據 `OBSERVATION.json` 的SHA256為
`faffc10ca4325726b95f3a99bbc4a2d30b3cad26d20d91ef0e355d28c9413123`。
E17的ext4 Stage0 normal／`-O` logs分別為
`25a239970b17dc9752550345d1aa53e7d67a4f35e0333e20d17ba90a892e483a`／
`2371e5ca9c6dc2204529e19be801fe3abbb5644f8c8a1835978e17a829e22c45`；
transfer normal／`-O` logs分別為
`4c14f4ba99df152d55cf43accf219e99278b6746ee1a72699951f46f1c507a0d`／
`a09f6b0ce19bcbea600a03c4e84d8c1ce9c1946600c298595cd4fa073bc7009f`。
這些只識別上述本地觀察與CPU測試，原始檔均留在ignored側，不能當成production放行或GPU結果。

E19的移轉接點均在`tools/arc_qwen_rlvr004_20261013/`：
`publication_run008/launch.py:14–56`綁定wrapper／venv／HOME；
`config.py:76,97–98,127–136`強制POSIX及原環境；
`native_auth.py:21–34`綁定Python3.12的site-packages及完整SDK來源鎖。
`operator_common.py:7,52`另使用fcntl／SIGALRM，不能直接改成Windows interpreter。
更新config／auth時，須傳遞common、transport、collector、launcher及當次review的來源pins；
`rl_transport.py:263`亦有`official_native_wrapper_required`，不能只改launcher。
舊`publication_local/config.py:79–109,132–194`可提供real HOME、Windows ACL／reparse設計；
其`operator_common.py:325–326`的抽取token路徑不能整體搬回run008。
獨立審查確認沒有現成drop-in，要求目的環境successor及新的相依review，不構成執行放行。

重建尚待：以原Git objects、Python3.12及正確原始LF bytes，在可持續的POSIX/ext4工作目錄
重新執行既有`transfer_run008/rebuild_engineering.py`，保留原輸入及失敗。必須實際取得
283檔source-rebuild、426檔candidate-rebuild與原REBUILD-REPORT，再取得311檔inert
independent-reviewed-proposal及工程重建report；portable components子集不能代替。
其後才是目的環境binding／fresh官方bracket與owner／proposal及原admission；本次沒有補造。
本機操作路徑與原始錯誤log另由當次回報提供，不把私人帳號設定或原始log放入公開Git。

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
| S1-P1 | 本地publisher的狹窄POSIX portability successor | 完成（離線交付）；E19～E25，106 normal／106 `-O`、獨立審查與19檔遠端readback | 純POSIX使用仍需本地native OAuth；本輪選擇S1-P2沿用Windows登入 | 保存此可重現版本；不因選擇Windows橋而改寫POSIX已測來源，也不把來源保存當provider放行 |
| S1-P2 | WSL durable owner＋Windows官方SDK bounded bridge | 受阻；E39三項no-auth與E40正式readiness已通過，但E41新open失敗，舊UNKNOWN缺原生closure證據；E43診斷已實測，E45獨立recovery epoch離線驗收完成；本機前置驗收待執行 | S1-P1、精確SDK0.1.37、native Job／ACL／pipe驗收、原材料與全部新hash-bound reviews | bounded IPC／DTO、refresh前fsync握手、獨立每RPC watchdog、全Job清空、未知結果不重送；先離線與本機合成驗收，再依原admission進既有A/B/C流程 |
| S1-E1 | 本地真實來源、模型材料與已存在audit接收 | 材料與原admission重建完成（E40）；發布在E41 open UNKNOWN受阻，本輪audit尚未產出 | 原執行契約、本地來源與材料 | 先完成目的環境portable successor與原admission，核對training-owned provenance／原records／排除及exact numeric materials。首次原A/B/C可在原admission通過後產生audit，不以尚未產出的結果阻擋原流程 |
| S1-E2 | 原runtime真實replay／LoRA梯度／owner狀態驗收 | 待開始／未執行 | S1-E1、本地完整原admission | E2與E3是同次原執行中的驗收，不要求先有另一場成功證據。原runtime逐步核對模型、數值、rollback、save/reload、closure與資源；CPU logp梯度不能替代。若另接AF3模型hook，才加另立successor的同模型差分驗收 |
| S1-E3 | 同 session 既有 A/B/C 比較 | 待開始／未驗證 | S1-E1、原admission／batch／時鐘；E2由該次原runtime逐步驗收 | 原 reward、replay、更新、checkpoint、全 B/C wall、固定選擇與 closure 證據完整；未完成與 zero-signal 分開 |
| S1-E4 | sealed 評分與研究判讀 | 待開始／未驗證 | S1-E3、隔離 evaluator、原 scorer | 完整 PUBLIC120／167 與相同案例 gain／loss；B 同時對 A、等成本 C 判讀；缺評分保持未知，不 promotion |

**現在的下一步：** 原E41 UNKNOWN與29份state保持不變。E43完成forward-only診斷的
三項本地no-auth驗收；E44提供完整原狀態與原碼順序的條件性補證。E45新增獨立recovery epoch，
已完成離線測試／審查；固定來源後交本地驗證新boot observer、recovery-mode pre-auth及純validate。
依[本地恢復步驟](OFFLINE-LOCAL-HANDOFF.md#632-原failed-open的獨立恢復邊界)，保存前置證據並確認
使用者可手動Windows「重新啟動」後，才可能建立新的process termination boundary與一次性唯讀核對。
這不補造原receipt、不改寫原UNKNOWN；新的closure只屬新session。尚未執行Restart／recovery／新provider。
根因仍未知；目前沒有新的dataset版本、notebook RUN或A/B/C結果。真實PUBLIC120／167保持未評分，
原Windows登入留原profile，不建立WSL OAuth，不提前轉向Stage2／TTT／Agent新方法。

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

- 2026-10-15：本地完成E14～E17接手檢查。官方唯讀確認仍code20／v39 ERROR，未提交新版本；
  獨立審查定位目的環境wrapper／SDK差異。先前Windows checkout的autocrlf另使歷史LICENSE
  與Git blob只差CRLF而遭原重建工具拒絕；失敗保留，另嘗試用原Git來源的WSL ext4 checkout
  驗證，但executor中斷，未取得結果。不改原blob或放寬exact-byte gate。
  A/B/C、真模型／GPU、audit、成本與新分數仍未取得。

- 2026-10-15移轉補證：E19記錄原launcher在provider前的實際缺wrapper錯誤、source gate位置及
  尚缺重建步驟；協調者已交Astra處理portability，本地只補證據，等待修復commit，不平行改發布器或提交。

- 2026-10-15 portability修復：從286fdb3另開修復分支。選擇保留Linux/POSIX的flock、SIGALRM、
  fsync及owned-process契約；不擴成Windows核心移植。原SDK官方source確認OAuth依真實HOME，
  KAGGLE_CONFIG_DIR不能轉移OAuth；沒有native WSL store時保留明確登入阻擋，不建立跨環境憑證通路。
  此阻擋只針對純POSIX publisher；另評估WSL持有state／claims、Windows官方SDK原地認證的
  bounded bridge是否能保留同等timeout／cleanup／auth／傳輸完整性。該bridge尚未實作或放行，
  不能把已完成POSIX測試代稱為Windows登入重用可執行。

- 2026-10-15 05:54 UTC：E24／E25保存POSIX交付與精確CI結果；本地b51c4ae3能力紀錄併入E26／E27。
  目前選擇S1-P2重用既有Windows官方登入，先完成獨立bounded bridge與本機失敗清理驗收。
  原12h是實驗時鐘，不是停止查明terminal的監看上限；read-only worker lease須完整清理後才可輪替，
  不重置原JIT／訓練clock或重送mutation。Windows橋仍未完成，不以Linux mock或有限PID觀察代稱可執行。

- 2026-10-15原生diagnostic checkpoint：新增三檔no-auth probe，獨立source review確認固定合成範圍；
  以實際supervisor PID、完整observer Job membership／清空與失敗cleanup取代兩個PID的不足證明。
  [使用方式](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/README.md#early-native-diagnostic)。
  該歷史checkpoint其後完成E28原生實測。當前source binding／IPC／phase watchdog已實作，
  正在最終來源審查與新原生驗收，不能把E28沿用為當前production放行。

- 2026-10-15 06:16 UTC：E28／E29補入實際原生與CI結果。新bridge已接通WSL owner、binary protocol、
  native SDK worker及durable refresh handshake；獨立審查補強Windows base Python／pyvenv綁定、
  native副本與WSL Git來源一致性、全15檔publication closure。新版十案例、WSL caller-death、
  完整官方venv、正式入口與既有OAuth仍待本地實測；尚未有新provider call、upload、RUN或A/B/C分數。

- 2026-10-15 06:37 UTC：E31～E34保存最終232／232、獨立審查、完整suite、來源發布及精確CI。
  固定d684f63交本地三項no-auth驗收：新版native十案例、WSL caller-death、正式CLI pre-auth。
  原Windows登入仍留原profile；通過後仍須fresh remote observation、原材料及完整review，才依既有循環繼續。

- 2026-10-15 06:44 UTC：本地E35回傳新版native 6／10，立即停止後續WSL／pre-auth與provider。
  job_tree及兩個framed案例共用新的NULL-handle Job guard，這是source相關性而非已證實根因；
  parent_death另查handshake。只做合成錯誤碼／query flags／分階段輸出診斷，保留完整Job與deadline要求。

- 2026-10-15 06:52 UTC：核對官方CPython 3.12.10的
  [venv build](https://github.com/python/cpython/blob/v3.12.10/PCbuild/venvlauncher.vcxproj#L91-L105)
  與[launcher Job設定](https://github.com/python/cpython/blob/v3.12.10/PC/launcher.c#L739-L770)：
  venv redirector確實會另建KILL_ON_JOB_CLOSE＋SILENT_BREAKAWAY_OK的內層Job。
  [Windows API](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject)
  的NULL query讀取immediate Job，因此目前exact flags檢查可能遇到該內層；尚待本機numeric flags證明。
  只補安全診斷與合成open完成後才起算的短operation測試時鐘；production guard／outer Job規則未改。

- 2026-10-15 07:04 UTC：E37證實官方venv的0x3000 immediate Job。修復只辨識exact0x2000／0x3000，
  owned outer Job仍要求exact0x2000與原子指派；不得把inner silent breakaway誤報為outer可逃逸。
  parent-watch合成案例改以已hash綁定的base Python控制器啟動原venv supervisor，明確監看控制器PID，
  避免殺redirector時其KILL_ON_CLOSE先帶走supervisor。原receipt與全Job零程序門檻保留；
  framed案例仍需新原生實測確認，不因source解釋便改記為成功。

- 2026-10-15 07:25 UTC：收到E39真實本地三項PASS；01ca4f14程式來源不再改動。
  下一步只用既有admission：本地獨立核對實際config／genuine candidate／material及15檔operator，
  先以publish validate確認LOCAL_CONTRACT_PASS且provider_calls0；再把readiness單一動作納入
  真實review，透過官方Windows登入取得fresh notebook／dataset observation。診斷配置不是版本reservation，
  不可把合成review改標為provider批准；若缺原始candidate材料，先完成既有重建，不跳過gate。
  尚未dataset upload／notebook run／A/B/C訓練或新分數。

- 2026-10-15 08:38 UTC：E40／E41區分成功readiness與後續failed-open。現有來源在
  `_failed`未保存native finish／receipt拒絕原因，supervisor也可能在已查得Job-zero後因
  command completion檢查失敗而丟失closure；這是確認的診斷缺口，不是已證實E41根因。
  修補只保存固定安全欄位及真實已取得closure，失敗仍UNKNOWN；不新增自動recovery或重送路徑。

- 2026-10-15 recovery epoch：以實際29檔projection校準事件模型；3bracket與failure輔助檔沒有nonce，
  不因時間鄰近補綁到session。原readiness的七步與failed-open兩次UNKNOWN各自驗證。新recovery必須
  綁原材料／現行18檔operator來源、純no-auth boot觀察與受審查的手動Restart證據；精確唯讀核對、
  同grant refresh的原雙ACK、當次真Job0均通過後才建立歷史failed-open disposition。
  原Journal仍UNKNOWN／closurefalse，失敗或torn seal保持阻擋；不自動重送或改研究方法。

- 最終recovery離線審查補強：18個reviewed來源必須等於實際執行sibling bytes；open acceptance後
  必須先authenticated才可下一request；重複UNKNOWN不得改原proof；proxy kill錯誤仍關閉pipes；
  ancestor鄰檔churn只檢type／dev／inode，原檔與STATE完整metadata／集合檢查保留。
  共355 bridge＋38 observer各normal／`-O`通過；它們是CPU synthetic驗收，不是本機recovery成功。
