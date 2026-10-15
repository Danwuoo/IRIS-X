# 工程歷史證據：截至 e491 的固定紀錄

本檔保存搬移前的 E0–E52、失敗／UNKNOWN、來源指紋與完整更新紀錄；不是第二份進度頁。
原文中的「目前」「下一步」「尚待」只描述當時，不代表現在仍應執行。
目前工作只見[當前進度](../DEVELOPMENT-PROGRESS.zh-TW.md)，科學問題見[研究主頁](../README.md)。

搬移來源固定為 [`e491ba4be3562d48d78f4f615a1dd155bcdc0cfc`](https://github.com/Danwuoo/IRIS-X/commit/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc)。
除標題層級與相對連結外，下列歷史證據保持原文；不回填後來的通過、不改失敗或既有時鐘。
原始私人 logs／receipts 仍在原隔離位置，本檔只有已公開的摘要與指紋。

## E0–E52 與原始證據補充

| 證據 ID | 已核對結果 | 邊界與來源 |
| --- | --- | --- |
| E0 | Stage 0 已發布 `0d4d19c71d2c84720d4956b36d8e99108e8c0a2b`；normal 148／`-O` 148 通過 | [commit](https://github.com/Danwuoo/IRIS-X/commit/0d4d19c71d2c84720d4956b36d8e99108e8c0a2b)、[獨立審查](../offline-continuation-review.md)；來源綁定 inert plan、collector 結構聚合與安全 I/O，不證明真實收集或模型成功 |
| E1 | 實際呼叫上游 `TrainingSample`、`DDISLoss`、`MeanMetricState` 三個元件；normal 25／`-O` 25 通過，合成 raw-logit loss／gradient 差為 0 | [整合說明](../agent-factory3/integration.zh-TW.md)、[驗證](../agent-factory3/validation.md)、[獨立審查](../agent-factory3/independent-review.md)；僅 synthetic CPU，沒有真實 Qwen／LoRA graph |
| E2 | 2026-10-14 16:10 UTC 最終發布核對：`66e54c90febd4d7f1a1e08f1f8b0e8d6c7c671ca`；tree `d74130a4f20ba45998fbf0d73858608536ffc824`；33 個變動檔案 readback | [commit](https://github.com/Danwuoo/IRIS-X/commit/66e54c90febd4d7f1a1e08f1f8b0e8d6c7c671ca)；包含 E1 與原導覽／計畫。run008 維持 `cc14bd1a`；本頁後續工作尚需自己的新版本核對 |
| E3 | E2 的精確 [CI run38595816563](https://github.com/Danwuoo/IRIS-X/actions/runs/38595816563) 已結束：failure；1 個 job 失敗、3 個 cancelled | repository invariants 的 6 項既有 README 缺詞；unit／packaging 步驟 skipped，不能稱 CI 通過 |
| E4 | 歷史本地完整 suite：1,583 tests、2 failures、35 errors、74 skips；AF3 加入前後 failure／error IDs 相同 | [驗證紀錄](../agent-factory3/validation.md)、[當時文件審查](../documentation-update-review.md)；這是前次文件更新前的完整 suite，不能當本輪重跑結果 |
| E5 | exact upstream `metric_state.py` 保留 EOF 空白行格式警告 | [來源 manifest](../../../tools/arc2_agent_factory3_bridge_20261014/source-manifest.json)、[當時文件審查](../documentation-update-review.md)；不修改 vendor bytes 來隱藏 warning |
| E6 | 單一進度文件與導覽整理已於 `ec9237fc607d592ac262b9881e276d23bb06de22` 保存；tree `1c3111cfe79e8f30f93d5c7af7bc4cdacc48609f`，8檔遠端bytes核對一致 | [commit](https://github.com/Danwuoo/IRIS-X/commit/ec9237fc607d592ac262b9881e276d23bb06de22)；屬文件checkpoint，不含其後Stage1新程式；[該版本CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38600128382)結束為failure：2 jobs failure、2 cancelled；實際job115976922494仍為同6項README缺詞，unit／packaging skipped，不能沿用為新程式驗收 |
| E7 | 最終獨立 focused：Stage0 148＋AF3 25＋Stage1 60＝233 normal／233 `-O`，六次package discovery全數通過、無skip，測前後執行碼hash不變 | [本輪獨立審查](../stage1-independent-review.md)；新60項為audit25、streaming21、CLI14，僅CPU與合成producer-schema；含原producer／consumer64 trajectories互通、真process timeout／SIGTERM／cleanup |
| E8 | 本輪exact66基線與最終來源各重跑完整suite，均1,583 tests／2 failures／35 errors／74 skips；37個failure／error IDs及skip-reason計數一致 | [本輪獨立審查](../stage1-independent-review.md)；無新增失敗，但整體仍失敗。新工具測試由E7獨立discovery覆蓋，不能把既有root suite數目當新工具覆蓋 |
| E9 | [逐軌跡API與本地shadow規格](../../../tools/arc2_abc_continuation_20261014/README.md#local-shadow-wiring-specification)完成來源→adapter→owner映射、同A／同batch／同unchanged-policy對照與全成本契約 | 實際介面仍CPU-only；未接CUDA模型、沒有真實歷史audit。安全reader16MiB不變，另做88MiB超限正常／`-O`拒絕測試，不能聲稱支援全部可能audit大小 |
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
| E20 | 2026-10-15官方registry wheel靜態比對：Kaggle2.2.4／SDK0.1.37的170個Python來源全部符合原sdk-lock，missing／extra／mismatch皆0；兩wheel均宣告Python>=3.11 | [精確wheel來源與hash](../../../tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/SDK-WHEEL-PROVENANCE.json)。未import SDK、登入或呼叫provider；不代表已完成目的端安裝、全相依鎖定或認證 |
| E21 | 目的環境離線修復完成：獨立POSIX successor以真實HOME、明確venv／executable SHA／Python patch／SDKroot取代歷史wrapper；原mutation／collector／官方session行為由AST等價回歸核對，active-wire獨立綁定精確numeric versions | [介面與來源邊界](../../../tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/README.md)。獨立審查無剩餘新blocking finding；90個受保護來源與286fdb3完全一致，7個原transport來源亦符合cc14bd1 Git objects。實際提交仍需目的端認證、材料與admission |
| E22 | Portability final106 normal／106 `-O`全部通過、零skip；獨立reviewer另跑同106／106。另以實際copied venv各模式核對runtime boundary及170個已安裝官方source，未import SDK／讀credentials／呼叫provider | [固定驗收收據及逐檔hash](../../../tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/VALIDATION.json)。真process lock／timeout／cleanup、FIFO／symlink替換、四條TLS路徑及frozen producer互通均涵蓋；source probe是刻意未裝全Kaggle相依的測試venv，不代稱目的端環境可用 |
| E23 | 本次完整repo suite實跑1,583 tests／2 failures／35 errors／74 skips；37個failure/error IDs與E13歷史log完全相同，新增／缺少均0 | 本輪未重跑baseline，不能稱paired新比較。獨立normal／`-O` placement仍同6項README缺詞；沒有新placement finding。失敗與初次缺Requests、synthetic proxy expectation、numeric回讀producer不符的修正前logs皆保留；focused通過不能抵銷aggregate或CI失敗 |
| E24 | POSIX successor 已發布 `b09e442fe706f06545be2cb4aa3363e04f807a71`，tree `746cc76943dea5913975fc4dcbd271b6424eeffc`；19檔Git取回逐byte與最終reviewed index／worktree相符 | [commit](https://github.com/Danwuoo/IRIS-X/commit/b09e442fe706f06545be2cb4aa3363e04f807a71)；只完成E21／E22離線來源保存，不代表Windows橋、原認證、材料重建或provider admission完成 |
| E25 | E24精確CI38688413326終態failure：1 job failure／3 cancelled | [CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38688413326)；實際job116268483868仍是同6項README缺詞，unit／packaging skipped；沒有稱CI成功 |
| E26 | Windows／WSL整合的本地合成能力前置：executor實際命令成功；Windows目前已在existing job內，仍可將suspended合成子程序指派新Job Object。關閉job handle及強制終止controller兩種情境，已持有handle的root／leaf均signaled且controller已wait | 此為固定合成程序的有限觀察；job accounting在清理前為4個active processes，測試只逐一追蹤root／leaf，不宣稱完整job inventory、跨OS取消或production closure通過。未載入Kaggle／認證，未改ACL ；來源為本地獨立紀錄 [b51c4ae3](https://github.com/Danwuoo/IRIS-X/commit/b51c4ae3b0f81e0823a3db731a21d68047967c57)，此處重新編號保留其範圍 |
| E27 | 固定script endpoints的Windows→WSL→Windows Python／PowerShell→WSL→Windows管線4／4通過：2,067 bytes含UTF-8／NUL／binary，stdout逐byte一致、stderr分離，exit0／7均正確傳遞 | 先前雙層inline `-c`形式產生`SyntaxError: unterminated string literal`，失敗保留；不是auth錯誤。未驗證正式framing、oversize、超時／取消與大型串流。既有profile／store／credential ACL與reparse僅查metadata；profile根目錄的owner／Allow不同於credential檔，不能混同為POSIX0600／UID gate；沒有改任何權限 ；來源為本地獨立紀錄 [b51c4ae3](https://github.com/Danwuoo/IRIS-X/commit/b51c4ae3b0f81e0823a3db731a21d68047967c57)，此處重新編號保留其範圍 |
| E28 | 原生diagnostic `8f2a6d032e01b02aa0563c851cbb1be60946bd67`、tree `41520ec7a3297573d521b0c72e26c187dd5fbf8a` 已逐byte回讀；本地Windows3.12.10 `-I -B`實際exit0、約7.01秒、stderr0，原8案例全通過 | stdout SHA256 `622d3651d30cf212a37df0665b19618179306dfa493ab33c3cd3d08cfe70a98f`；實際native parent死亡、Job owner強殺、deadline／EOF均觀察完整outer Job歸零，metadata負例與mutex亦通過。只適用該三檔來源及當時global Python；尚未測目前新framing／phase watchdog／venv／正式CLI／OAuth，不重標為新來源PASS |
| E29 | E28精確CI38689806693終態failure：1 job failure／3 cancelled | [CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38689806693)；實際job116272866733仍同6項README缺詞，unit／packaging skipped；與本地native測試各自記錄 |
| E30 | 本地新建單一Windows Python3.12.10 venv，官方Kaggle2.2.4／SDK0.1.37，完整35套件安裝；`pip check` exit0、170-source lock全數一致 | ENV-RECEIPT SHA256 `ec2daea5687f0feae32fcc0d7675baf2649d35da7f156ab38ed975713f3593fc`。官方wheel hashes與E20一致；初次Temp失敗保留，同venv改用project Temp後完成。沒有import SDK／登入／讀credential或修改HOME／ACL；原global SDK0.1.36保留。只證明安裝／靜態來源，尚未執行新版native probe或provider |
| E31 | Windows／WSL bridge最終離線232 normal／232 `-O`、zero skips；獨立reviewer對同一snapshot另跑232／232，25個source／test檔前後不變，22個dependency pins吻合 | [固定來源與驗收收據](../../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。涵蓋實際binary pipe DTO／fsync／opaque upload／404及503／unknown不重送／15檔Git與review closure、十案例及pre-auth harness的合成負例。原collector所有function／class AST不變；transport僅update_code、review_gate、git_publication_gate三項有界差異。尚未有新版native／WSL／正式pre-auth實測或provider admission |
| E32 | 最終code凍結後再次執行完整repo suite：1,583 tests／2 failures／35 errors／74 skips；37個failure/error IDs與保存的POSIX baseline相同，未重跑baseline | [本輪精確收據](../../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。workspace TMPDIR及offline flags齊備；root suite不涵蓋E31獨立232 tests。既有6項README finding仍失敗；初次錯誤TMPDIR的partial run保留，不能當合格比較 |
| E33 | Bridge來源正式發布 `d684f63cf6c52044dee4359f84f6cc75527db734`，tree `03ecf14a07ad584803aebb94954a5c59f24b4476`；remote branch／29檔Git、index與worktree逐byte一致 | [固定commit](https://github.com/Danwuoo/IRIS-X/commit/d684f63cf6c52044dee4359f84f6cc75527db734)；分支`fix/arc2-abc-portable-publication-20261015`，本地三項驗收固定這個程式版本。公開payload只有source／tests／非秘密handoff，沒有credential／evaluator答案或raw logs；發布完成不等於provider放行 |
| E34 | E33精確CI38693296388已completed／failure：1 job failure、3 cancelled | [CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38693296388)；實際job116283954687仍為6項既有README缺詞，unit／packaging skipped。新bridge focused與完整suite結果分別見E31／E32；不混同為CI成功 |
| E35 | 本地對d684f63的新Windows venv native十案例實測**失敗**：exit1、13.02秒、6／10通過。job_tree／parent_death為`probe_output_invalid`，framed_operation_deadline為`probe_native_watchdog_failed`，framed_official_rpc_deadline為`probe_internal_error` | stdout SHA256 `fa8b025996e538431f2bf090b0ab39f1af89650b752343f8d6290b596021e069`，capture SHA256 `1fc039a61d7fada28231108f94c306427800786cddbdc499fff2218e105a74bf`；27個module檔及runtime hashes符合。deadline、metadata含reparse、mutex、pipeEOF、source_unchanged、supervisor_kill通過，相關outer Job歸零；缺失原因尚未證明。WSL caller-death與pre-auth未執行，沒有auth／provider／upload／RUN；保留失敗並先增加精確合成診斷，不放寬門檻 |
| E36 | no-auth diagnostic successor完成244 normal／244 `-O`、zero skips；獨立reviewer另跑相關58／58並核對兩檔hash；僅native_probe與其測試有程式差異，production所有source／pins維持d684f63 | [分開標示的diagnostic_revision收據](../../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。回傳固定錯誤碼、數值Job flags與分階段結構資訊，無原始stderr／路徑／credentials；先證明Job歸零再有界讀取合成診斷。短operation timer移到合成open後，原overall lease不重設。新版native實測尚待本地，不把244離線測試當native PASS |
| E37 | 本地f998839診斷重跑exit1、13.58秒、仍6／10；job_tree實際membership true、兩query成功、immediate flags為12288（0x3000），被`windows_worker_job_limits_invalid`拒絕。parent_death三段handshake完整，最終receipt為0-byte EOF；兩framed案例為supervisor的`windows_worker_incomplete_command`及parent的`bridge_eof_or_invalid_read` | stdout SHA256 `8d3f02f3b161fd146a2f9f9687088975bfc2e778e0bf378643cc8018267b30e8`，capture SHA256 `2e1f4da6ed962061cbba118e974996c089fc4b61794a5af0cb2988350d3171c5`；原六案例及完整outer Job歸零仍通過。production bytes仍同d684，未auth／network。framed錯誤是在worker_exit後檢查未完成request產生，是否隨guard修正消失仍待實測 |
| E38 | 狹窄venv修復通過251 normal／251 `-O`、zero skips；獨立reviewer同251／251且25檔前後hash不變；production function差異只有`require_worker_job`，owned JobProcess與supervisor／SDK worker所有function／class AST保持原樣 | [venv_repair_revision完整來源收據](../../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。exact immediate 0x2000／0x3000及誠實flags分列，outer仍exact0x2000；parent-watch只換合成控制器拓樸，驗證base／venv bytes與雙方PID／完整membership。依賴pins同步更新；新版native／WSL／pre-auth與provider仍待本地，不能將離線測試當原生放行 |
| E39 | 本地對01ca4f14三項真實no-auth驗收全部通過：07:18:03–19 UTC native十案例10／10；07:20:24–27 WSL caller SIGKILL後8 members停止、observer Job 0；07:22:42–46正式CLI pre-auth valid ready、故意不ACK、nonce-bound Job 0 | [原生與interop收據摘要](../../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。三者outer exit0／stderr0，pre-auth inner exit124／caller_pipe_eof為預期拒絕繼續auth；parent-watch追蹤9 members、framed兩deadline均通過。27來源及runtime／config bytes不變，INDEX SHA256 `165c4d16cd5778ce45e1275980c9b6f714a1df31a65cc419833cf1ddfc13e467`。原始captures留本地；未SDK import／讀credential內容／provider call，20→21及39→40→41僅diagnostic配置、未保留版本 |
| E40 | 2026-10-15本地重新建立283／426／311材料、三份獨立review與8-binding LOCAL_CONTRACT_PASS；08:10:41.497818–08:10:55.955410 UTC正式readiness exit0，原生session closed且closure verified | 使用01ca4f14來源與原Windows官方登入；fresh observation仍code Dataset v20、notebook v39 ERROR及原source a3076380…。沒有新code／notebook版本、RUN或A/B/C結果；該成功receipt只適用readiness本次session |
| E41 | 隨後08:11:34.117961–08:11:35.537807 UTC update-code outer exit2、bridge_eof_or_invalid_read；停在新session sequence1 open，mutation_attempted=false，session UNKNOWN且native_process_closure_verified=false | 原29份state已封存，無retention inventory／codeclaim／upload／versionintent；原source／config／interop environment未變。實際native exit／stderr receipt／READY與phase未持久保存，不能推論未開始認證或Job已清空。FAILURE-HANDOFF SHA256 `21d7174e4fb8c0d7895052ce7e883663d2fb26ce17805e252b74882e7e4a991c`只識別本地封存證據；根因未知，舊UNKNOWN保持阻擋，不改寫history／namespace或重送 |
| E42 | failed-open診斷successor通過269 normal／269 `-O`、zero skips；獨立reviewer同269／269、22個static pins相符，無blocking finding。fresh完整suite仍1,583 tests／2 failures／35 errors／74 skips | [open_failure_diagnostic_revision](../../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。37個failure/error IDs與保存POSIX baseline相同，未重跑baseline；6項README findings未變。保留固定診斷／真實已取得closure，不改UNKNOWN、auth、deadline或mutation admission；新版native未測，E41原closure缺失不可回填。另行設計獨立recovery epoch仍需明確審查，沒有執行或放行 |

| E43 | ca8f0dca本地三項no-auth全部PASS：08:52:21–36 UTC native10／10；08:53:15–18 WSL caller-death八members停止／Job0；08:54:24–28 pre-auth READY有效、ACK=false、nonce-bound Job0 | 27來源Windows／WSL／Git相符且前後不變；SDK／credential／provider／network均未使用。INDEX SHA256 `62c18de1b4c2fdbc133669957968e81acb317857dc7a8b4ff52a8730c4d20222`；這些是新合成session，不能回填E41 closure。ca8[CI38708124018](https://github.com/Danwuoo/IRIS-X/actions/runs/38708124018)為failure，同6項README缺詞，unit／packaging skipped |
| E44 | 09:42:39 UTC本地完整枚舉原29檔：4根claim／journal＋25events、僅events子目錄；集合／大小／SHA均與封存相符，無hidden／tmp／link／special／JSON異常 | 精確01ca原碼要求refresh intent先經WSL exclusive claim、event及journal fsync，ACK後才controlled original_refresh。在固定source正常執行、可信主機且無外部刪改／rollback前提，未dispatch受控refresh；不等於auth未載入或外部grant狀態已知。原closed readiness無raw receipt，僅按原closed predicate、source及event驗證，不要求不存在的檔案 |
| E45 | 獨立recovery epoch離線完成：355 normal／355 `-O`及38 observer normal／38 `-O`全部通過、zero skips；獨立reviewer同數通過且來源前後不變，無剩餘offline blocking finding | 同STATE／publisher lock、原29檔不變；full Windows Restart為新的當前process boundary，challenge／host／boot／來源與runtime綁定；一次性read-only dataset→kernel→status→kernel→dataset及新Job0後保存固定completion seal。正常publication仍須原admission；無Restart／provider執行證據，不能標為已恢復 |

| E46 | 最終recovery executable source完整suite：1,621 tests／2 failures／35 errors／74 skips；新增38 root observer tests通過，37個failure/error IDs與保存ca8 baseline完全相同，未重跑baseline | 正確PYTHONHASHSEED=0、workspace TMPDIR、offline flags、CUDA_VISIBLE_DEVICES空值；仍同6項README findings，整體FAIL，bridge355 focused另行驗收。沒有新增failure/error IDs；來源及詳細logs hashes見[recovery_epoch_revision](../../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json) |
| E47 | 固定[f5f780cb](https://github.com/Danwuoo/IRIS-X/commit/f5f780cb5823579288385158ce6da70a1ca33899)已完成真實本地恢復：客觀Windows新boot為2026-10-15 11:20:51.500 UTC；同host/install與request時序通過。11:46:14.525285 UTC一次性官方唯讀reconciliation成功，entry exit0／entry外層stderr0／真Job0／proxy exit0 | remote仍code20、notebook39 ERROR、原a307來源；沒有refresh／upload／RUN。原29份證據與原failed-open UNKNOWN／closurefalse保持不變，總61 state及31-row completion seal完整保存。eligibility SHA `bdf522126b1d7d8e7128cb1b0f229917cf23dd836f004818dddbeb600165659b`；新session receipt `14627f4e2f1fb495570ce0aef083e845ff8bbc940486d2ec6aa82cbd5cff8b05`；seal `9ed49137330ca36535379a376e99cce96449163936c68bb082d8b319ac3e353b`；result index `e9ef4c4d073ec0027e4b31178781e2ec552fdce6c0d4594ca4ede98fa4d9e10d`。新closure只屬新session，沒有補造舊receipt |
| E48 | E47 wrapper正常結束後，下一個真實WSL context的 `WSL_INTEROP` selector改變；正常入口在任何publisher／provider之前拒絕。遞迴比對實際normal config，其餘欄位相同；f5 eligibility又要求完整封存template SHA，故context重綁受阻 | blocker原件SHA `3b216b03eb8aadd852289c95c71a018c7239458701ad7cb85a0b8f464e97bf49`；先前 `1dedc658…`只識別其nested context check。未建立新版current config、未注入舊env、未延長expiry或重播恢復。進行受限同boot context successor；原f5核心與sealed evidence保留。這是工程續接問題，A/B/C仍未執行 |
| E49 | 同boot context／source-location successor完成離線驗收：395 normal／395 `-O`全部通過、零skip；獨立審查再各395通過。只允許已審查實際新版repository_root與當前WSL_INTEROP兩欄；20來源review／Gitgate涵蓋adapter與固定f5 manifest | 原18歷史來源及13個native/core/config/probe檔逐byte保留；完整repository 1,621 tests／2 failures／35 errors／74 skips，37個failure/error IDs與保存f5 log相同、無新增／缺失，仍6項README findings，整體FAIL。normal、`-O`、來源及獨立審查log hashes見[context_continuation_revision](../../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。此結果不代稱真實同owner no-auth驗收或provider放行 |


| E50 | 固定[a7245eff](https://github.com/Danwuoo/IRIS-X/commit/a7245eff47719769ed83d564668c9b0e920863b5)本地同owner no-auth context與20來源／配置獨立review通過；2026-10-15 12:44:49 UTC正式readiness成功，新native session closed／closure verified | 官方原Windows登入取得fresh code Dataset v20、notebook v39 ERROR、原a307來源且無active conflict；原61檔不變，合法追加22檔成83。沒有upload／RUN。原29 UNKNOWN不改，E48 context blocker已由實際結果解除 |
| E51 | 本地在upload前發現collector閉包仍綁舊SHA117baa17…，a724實際collector為8db1b754…；proposal／runtime／material／consumer與固定owner必須整體canonical重建 | 這是source-proven guard不成立，尚未執行prepare-active，不能寫成其實際exception。完整路徑審查另發現原f5根目錄parser不接受後續合法readback目錄／大wire；新增唯讀publication view保留原native／recovery predicate，避免只修下一個gate |
| E52 | Collector-only canonical lineage、原STATE的bounded publication view與前置整條閉包預檢完成；作者及獨立reviewer各472 normal／472 `-O`通過、零skip；完整審查與aggregate結果見同次[material_successor_revision](../../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json) | 原assembler／259 runtime／source archive／21helpers與科學條件不變；22來源pin鏈固定後才可在本地重組。真實canonical candidate、完整83 frontier receipt、同owner no-auth與原60秒JIT成本驗收尚待本地，沒有新provider／Kaggle／訓練／分數 |

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

## 原更新紀錄

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
  [使用方式](../../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/README.md#early-native-diagnostic)。
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

- 2026-10-15 12:06 UTC：E47記錄已完成的真實本地recovery；E48明確定位其後context rollover。
  以來源與配置差分做窄續接，保留原recovery核心及全部歷史檔案；不再要求重啟或重跑一次性reconcile。

- 2026-10-15 12:19 UTC：E49完成兩欄遷移的395／395與獨立review；完整suite精確failure/error集合
  與保存f5一致。原checkout不可更新，另部署新root；真正same-owner驗收及fresh provider核對仍由本地執行。

- 2026-10-15 13:22 UTC：E50／E51記錄真實context成功與其後collector材料pin阻礙。E52離線逐階段
  覆蓋upload、readback、inactive、JIT、active及新增UNKNOWN／refresh／race負例；兩個純helper不執行
  candidate或provider。來源先完整固定，再交本地canonical重建；原owner依既有finish正常退出，不搶expiry。

- 本次完整repository重跑仍1,621 tests／2 failures／35 errors／74 skips；37個failure/error IDs與保存a724
  完全相同，無新增／缺失，仍6項README findings，整體FAIL。最初新增的doc EOF空白警告已修正；
  最終diff檢查乾淨。這與472項focused bridge測試、未執行的真實canonical candidate驗收分開記錄。

## 原 Stage 1 與 transport 交付指紋

2026-10-14原交接所檢查的 checkout 是 `e17b6857ee6e874b2b5ed28a766f35e0b8028ea2`，tree
`408182146a41cfbba7dbb9ead040b54e4790587a`。程式驗收版本是
`8b9ca9cf915969e15339d99bc090762f349f1572`，tree
`cedac0a7486685c641506335930d7f6ab429b514`；兩者只有進度文件差異，執行碼相同。
這些是歷史Stage1來源 anchors，**不是目的環境修復或本文最終文件 commit**。協調者會在發布核對後
另行交付最終完整 SHA／tree／變動清單，本頁不預填或自指尚不存在的 commit。
接收端先核對那份精確交付及工作區差異；不能只 checkout 移動中的分支便執行。

下列 SHA-256 在上述 checkout 重新核對。完整 Stage 1 檔案指紋及 CPU 範圍見
[獨立審查](../stage1-independent-review.md#reviewed-source-fingerprints)；20個 frozen／bridge
來源的逐檔 pins 見 audit manifest。這些 hashes 只識別程式，不是生產 admission。

| 路徑（相對 repository root） | SHA-256 |
| --- | --- |
| `tools/arc2_abc_continuation_20261014/audit.py` | `fb7ede3a20f4921842f637f6cd32465a22ecfe61b0ffa7bbe9c4bb8627c825d0` |
| `tools/arc2_abc_continuation_20261014/streaming.py` | `4c7ea1d1c00f13329a7cd2491880b269e02d04cd169336aa3926751626328b81` |
| `tools/arc2_abc_continuation_20261014/cli.py` | `c41bccf7a36920a55bddd0e682798be1243aa9d7fec5633e683f930af647419d` |
| `tools/arc2_abc_continuation_20261014/audit-source-pins.json` | `015e2549da2ab445b30273fa62e106d98510b26c2f130866eae393418531b8cd` |
| `tools/arc2_agent_factory3_bridge_20261014/bridge.py` | `68e09ed7c01bc51a32a7ddf31eaceb16d928dc3f20069d3f53967a9d70ab74a3` |
| `tools/arc2_agent_factory3_bridge_20261014/source-manifest.json` | `9810243f51001318e5d08c608358092c12895e81e76dfcd82ec08f500ce439e1` |
| `tools/arc2_sft_rl_continuation_20261014/source-pins.json` | `220640c4f5a963d38153633040a0428ae2174e827b41f4dc466b119b1cf0c062` |

原 run008 的 frozen runtime identity 是
`c61025e67354272099e40941cadcd77202964846d9a4c42c51a1817f77bb661b`；source archive 是
`4d8b414bd35ca79a2eaaec7042880966879ed13bdeaf96762eaee7932ee1de4c`；loader overlay manifest
是 `1d3aabee0419acd2b42a4343d36028b0ba296f14f30341e5be8e6c83e42600f0`。
歷史候選 manifest `beda6a5647df0431ac2ac8da26db170d84776be8f59181b5fee537e87423a857`
及 inventory `bb096f6d53967523961f894c954daa1b4b1f956d54af3586d89bf544aea90cf2`
只供對照；新 numeric pins、路徑或 trainer 變更都需要新的候選與對應審查，不能沿用其放行。

原 native transport 的歷史 byte 核對如下，路徑前綴均為
`tools/arc_qwen_rlvr004_20261013/publication_run008/`。launcher 含後續既有 CA 傳遞修正，
應併讀 [TLS 審查](../../native-continuation-20261014/independent-native-tls-review.json)，
不能把更早 launch review 的舊 launcher hash 當成本版。

| 檔案 | SHA-256 |
| --- | --- |
| `launch.py` | `e1794056b20dd1c143cb8ea23b1e985f579ab008260ef6b9d1f50c451301e48b` |
| `config.py` | `a4492c5a7b4d6cb42b2ee212f35b788fc70730fbd2fc13bf8b5cac03b48091fc` |
| `native_auth.py` | `b9b5aec37385f7a5de37ae92bbf0bfb3b7b664f0bc31c3fcc044532cb46a19de` |
| `sdk-lock.json` | `3d447ab7fad280fcc378fd18b57c3792c5b39798127f583679646027ab73288d` |
| `operator_common.py` | `f9b2acad7816b4af97baa877821ce4c9e3d16831fa340caf02d3e8c00b3f2805` |
| `rl_transport.py` | `a4da4850d7a2e44af2d85d4be65e55913a746ddeb66a26238500457911261bac` |
| `rl_collect.py` | `71603a1eb47b1b7656f2ca6a8f2b2eb6faa99469a27aef63d4f0446828ef3a78` |

`source-pins.json` 固定五個公開來源，總共118,615 bytes；Python原始碼只雜湊，
不import、不執行。它驗證選定來源bytes，不驗證完整checkout、Git HEAD、
私人材料、原始review或實際遠端版本。


## 其他固定來源身分

- 原離線半成品 `0451441727e8aea602873902ebccbf6b38576e03`：當時輸出路徑 race 與最終 integration review 尚未完成；後續修復不能回填為該版本已通過。
- Portability 修復起點 `286fdb302771e81e9deaf40f948cea264abacbe5`：本地移轉補證來源；後續 successor 與原接手分支保持分開。

## 固定版本的原操作說明

歷史命令與恢復步驟只在原版本查閱，不複製成現在的執行流程：

- [原進度全文與已完成任務表](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/DEVELOPMENT-PROGRESS.zh-TW.md)：包含當時 S0、AF3-0、S1-O1～O6、DOC-AF3、HANDOFF-CYCLE、S1-P1／P2 與 S1-E1～E4 的狀態。
- [原 Stage 0 CLI 與檔案安全](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#1-產生不會啟動工作的計畫)。
- [原 Windows／WSL 安裝與驗收](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#631-沿用既有windows登入的本地橋接驗收)。
- [E41 原 29 檔 failed-open 恢復](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#632-原failed-open的獨立恢復邊界)：一次性人工 Restart／reconciliation 已有後續證據，不因閱讀舊文件重做。
- [已完成恢復後的同 boot context](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#633-已完成恢復後的同boot-context續接)。
- [collector-only canonical 重建與預檢](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#634-collector-only-canonical-material續接與完整發布預檢)：原 assembler SHA256 `ba1b94cfcf4ff55d52a85e9508490039accb66f67f8d323085fd7df64b9d489e`；精確 14 檔差異、83 檔歷史子集與 22 來源限制適用該版本，不推定任何新 successor 已驗收。

較早分支、來源或操作路徑保留其歷史身分；新的 local readiness 失敗與後續修復以當前進度及各次正式收據為準。
