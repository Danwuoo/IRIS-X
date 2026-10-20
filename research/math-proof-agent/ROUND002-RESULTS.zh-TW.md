# R002 結果：工程控制與缺陷修正，TPU 提交無法確認

日期：2026-10-19。Task：MATH-002；branch：`feat/math-proof-agent-20261018`。
首次遠端封裝 code SHA：`ae051a79359c4e0be9658d89452c05793d64d831`。
其交付 SHA：`3fcb8410a4bf8dacb374e3cb3d42e7b881314af2`；前次受審 code
`d6e4309607936b66d34573350b9697e5fddc7b0f`、delivery `fb5cc667a2971f53a3fe3a6c387b02a0ff08f3fa`。
本次工程修正 code SHA：`fedf3a0ac60365fc840b7ae9aefac84a9ba7ba2d`。
原 smoke manifest 保持原樣，未重送修正版。
後續 delivery SHA 由本次最終回覆與 Draft PR #10 提供；文件不嵌入自身 commit。
完整命令、環境與機器可讀紀錄見 [HANDOFF](../../docs/verification/MATH-002/HANDOFF.md)
及 [run-summary](../../docs/verification/MATH-002/run-summary.json)。

**本輪尚不能回答回饋修復是否優於獨立採樣。** 沒有取得可綁定版本的 TPU
模型輸出，正式面板也未凍結。證明率、找答案且證明共同成功率、配對增益與
區間皆為 `not_estimable`，不是零分、零增益或負面模型結果。

## 獨立 review 後的工程修正

PR10 review5567278465 的 normal/-O 各48項、38通過/10失敗原樣保留，沒有改成
修正版通過。新工程自測修復全模式 proof receipt 綁定、成本 schema 與 analyzer
獨立重驗、遠端歷史 terminal 與當前派送資格分離，以及 research executable 的窄
納管。R1 20+20、R2含回歸84+84、R3 47+47均通過；新 line-b 整合163+163通過。
shared runner31+31、gate30+30通過；本地repository18+18各留1項歷史tag缺失。
新SHA的遠端CI target與結果見交接的CI讀回收據，不以本地局部通過推定全CI成功。
PR workstream run39209591512 的34 jobs為28成功/6失敗；四個line-b各163通過，
四個integrity各18項/1失敗，gate亦失敗。實際comparison target
`a5b2795fb91ea8b5ab6a7ce5efbe6623a3496812`與新code tree相同。
artifact只提供failure ID、沒有assertion trace；本地直接診斷與遠端tag404
支持歷史archive tag缺失的解釋，但遠端完整issue清單仍未直接觀察，不稱全CI綠。

已有Lean僅重跑既有受限常數：7/7、實際5次candidate Lean、isolation19/19；
Windows mock/stdlib與WSL kernel證據分開。原R001、MATH-001、WSF-R5及舊收據
未改寫。本修正零Kaggle操作，原ledger/heartbeat/stop/manifest hash不變，
submission_unknown/version null及1/4、1800/21600秒預留維持。沒有新模型、
新面板、推論或科學實驗；研究仍not_estimable，工程只到review_ready。
完整正負控制、環境、命令、hash、舊失敗與新CI見
[本次工程交接](../../docs/verification/MATH-002/HANDOFF.md#current-delivery-independent-review-repairs-2026-10-19)。

2026-10-20 續作記錄（見 [第二次獨立審核](../../docs/verification/MATH-002/independent-review-02.json)、
[Archive 修復與新 Checkout 全套件驗證](../../docs/verification/MATH-002/archive-ci-restoration.json) 及
[本地 Qwen3-4B 真實權重與 WSL2 Lean 驗證](../../docs/verification/MATH-002/local-qwen3-4b-lean-validation.json)）：
- 獨立重審 `5568170709` 確認 `fedf3a0ac60365fc840b7ae9aefac84a9ba7ba2d` 的 `M002-R1`、`M002-R2`、`M002-R3`
  通過有界獨立回歸且 `M002-CI1` 目錄准入已補齊；本輪保持 `fedf3a0a` 程式碼零修改。
- 經唯讀核對 `658cdd6ccc33ffd32ced70e0834726c8e30d0a7d` 原始 tag/commit/tree 位元組及 CI `39210749319`
  全 34 jobs（28 成功／6 失敗，Windows 3.11 management 已通過 214/214）後，依 owner 授權將遠端與本地
  `refs/tags/archive/pre-product-transition-2026-09-17` 恢復指向同一原始 annotated tag object，
  並在全新 `git clone` 上驗證 `repository_check.py` 及 7 個公開套件（共 602 項測試）100% 通過（`attestable=true`）。
- 在忽略目錄下完成 10 項本地 CPU/WSL2 端對端驗證與 `Qwen/Qwen3-4B`（`1cfa9a7208912126459214e8b04321603b3df60c`，
  8.04 GB 真實權重）+ WSL2 `Lean 4.19.0`（`Mathlib v4.19.0` + `closed_exists_nat_v1`）實測：36 層 JAX 與
  PyTorch BF16 greedy tokens 100% 一致（`[64, 293, 272, 151645]`，`"a b c"`）、`relative_l2_logit_error = 0.01750 <= 0.03`、
  `max_absolute_logit_error = 0.58885`（峰值 logit `56.25` 下為 `2.36` 個 BF16 ULP）；自製 `find_answer` 題
  `real_qwen3_find_nat_witness`（`: ∃ n : Nat, n * 19 = 437`）由真實 `Qwen/Qwen3-4B` 零樣本輸出
  `{"answer": "23", "proof_body": "by\nnorm_num"}` 並通過 WSL2 `Lean 4.19.0` 核心驗證（`0.770s`，
  `kernel_verified`，`verified_receipt_matches=true`）；兩筆 `proof_only` 的 `invalid_format` 觀察（提示詞
  `\n` 跳脫截斷與單行 `"by ring_nf"` 換行限制）及 WSL2 冷啟動 `RLIMIT_NPROC=64` 觀察完整保留。
  本地 CPU/WSL2 結果不替代 Kaggle TPU v5e-8 資格或正式面板科學結論。

## 實際完成的工程工作

建立一個 BF16、八路 tensor sharding 的 Qwen3 JAX adapter、一個受限 Lean
worker、一個 DIRECT/SAMPLE/REPAIR controller、原子候選與工具事件、隔離
答案 evaluator、保留未完成分母的 analyzer，以及單一 task 監看／預算入口。
沒有 trainer、參數更新、模型 API 或 ARC 資源操作。

模型 revision、tokenizer、檔案 SHA256、模板及依賴已固定為技術候選：

| 候選 | 完整 revision | 本輪狀態 |
| --- | --- | --- |
| Qwen/Qwen3-4B | `1cfa9a7208912126459214e8b04321603b3df60c` | 未取得 TPU qualification |
| Goedel-LM/Goedel-Prover-V2-8B | `dfd02e6271a58375dfbf3ece0175277cf6b6a89a` | 未取得 TPU qualification |

正式比較未選定模型。微型隨機權重與官方 Transformers 的數值回歸只能支持
adapter 的受測轉換，不是這兩個公開 checkpoint 的實測成績。未下載本地模型
權重；遠端是否啟動／耗用計算沒有可綁定證據，故成本保持 unknown。

## 真實測試與限制

| 檢查 | 實際環境及結果 | 可支持的範圍 |
| --- | --- | --- |
| R5/source/runner/gate/no-training 定向安全基線 | Windows 11 / Python 3.12.10，normal/-O 各92，全部通過 | 有效seed、來源綁定及受測安全防線 |
| R001 controls | 同環境 normal/-O 各12，全部通過 | 原證書 checker 回歸 |
| R001 cases | normal/-O 各32，各12 verified/16 rejected/4 unknown，mismatch0 | 原R001指紋與決策保存；不是Lean或模型成績 |
| controller/evaluator/budget | normal/-O 各19，全部通過 | scripted工程控制，不是模型研究 |
| 遠端版本／預算／取回防線 | normal/-O 最終各28，全部通過，全部mock | 防版本混淆、未確認重送、指紋與分母錯誤 |
| adapter 數值控制 | Windows CPU，8個虛擬CPU devices，9/9，exit0 | 微型隨機Qwen3；不代表TPU可行性 |
| Lean 正負控制 | WSL Ubuntu24.04 / Python3.12.3 / Lean4.19.0，7/7，exit0 | 真正Lean core與遞移axiom檢查 |
| parser／隔離 | 13/13 parser；19/19 Linux隔離控制 | 受測WSL bubblewrap，不代表Kaggle隔離 |

Lean 第一個控制執行因不支援的 `-T` 參數失敗，移除後的新嘗試才通過。
監看加入每次新 slug 防線後，中間26測試有5 failure/1 error；舊mock仍重用
slug，改為獨立嘗試並新增防線控制後，最終28/28通過。失敗raw logs與摘要保留。
兩個紀錄都沒有改標成一開始就成功。上述本地工程測試是實作者／子代理自測。

後續唯讀回查仍為HTTP403／submission_unknown，沒有新增提交。離線稽核發現
第一版工程控制尚未涵蓋的缺陷，因此補上以下修正；原19個controller測試、
9個adapter測試及原Lean core報告留存，不回寫成較強資格：

- solver view改為逐層欄位白名單，防止statement內的額外gold/reference/rubric
  隨整個dict進入prompt；執行須核對來源bytes、完整身分、固定面板成員與
  adapter/verifier身分。canonical評分指紋與smoke原始檔案指紋明確分開。
- 超時截斷JSON先記timeout；context不足和工具故障分開記錄。工具、setup、
  整體wall及缺漏／部分模型成本收據均列出，缺資料不補零當完整總成本。
- 單獨答對答案加上一個證明，不能證明該答案受到驗證。第一個離線修正版
  因缺少answer-proof binding，把find_answer在生成前擋住、joint_rate回傳null。
  下述第三次續作以自製控制補上窄範圍Nat binding；正式來源與面板仍未准入。
- 8192 context容納不了4096-token舊候選、提示及另4096輸出。共同輸出／context
  上限仍需TPU成本實測後預登記，不截斷某一臂或事後調整。

新版controller一般與-O模式各45項測試通過（共90次；中間各42項通過紀錄保留），
新版adapter的16/16 CPU工程測試通過。固定mathlib
`c44e0c8ee63ca166450922a373c7409c5d26b00b` 的Ring/NormNum傳遞閉包，
在WSL／4GiB限制下10/10控制通過（7次真正Lean編譯，3次格式／綁定拒絕），
另有19/19隔離與6/6合成process-exit分類控制。總wall22.442秒，Lean候選
合計8.042秒。2GiB首次7個編譯均exit139的故障保留；該嘗試不算語意負控制
成功。bubblewrap編碼的128+signal現在記infrastructure_error。
詳見新增的[mathlib報告](../../docs/verification/MATH-002/mathlib-tests.json)、
[adapter補驗](../../docs/verification/MATH-002/adapter-followup-tests.json)與
[controller補驗](../../docs/verification/MATH-002/controller-followup-tests.json)。

第三次續作補上 `closed_exists_nat_v1`：受信任wrapper把候選回傳的canonical
Nat固定為**原始存在命題**的witness，模型proof body證明該數值的剩餘性質。
命題沒有改寫，最終定理仍經kernel與遞移axiom檢查；controller、evaluator及
analyzer核對answer/proof、statement、binding spec各自的hash。不能把較強的
原問題弱化成存在題來使用此介面。不同類型、外層參數、巢狀存在或未登錄題目
均不准入；private key只在選擇後做一致性檢查，衝突會阻擋共同成功結論。
另外修正「工具status寫accepted蓋過信任失敗」、null binding登錄繞過，以及
未生成配對被誤列平手的問題；planned分母保持，缺觀察改列no_generation_pair。

[答案綁定實測](../../docs/verification/MATH-002/answer-binding-tests.json)最終
44/44控制通過，其中6次真正Lean執行；helper7/7、isolation19/19、core7/7、
parser13/13與mathlib10/10均通過，合成process分類另列。自製題目不代表正式
benchmark成績。並行core/mathlib回歸曾出現thread建立失敗（候選exit1、版本
探測exit134），原始收據保留；修正分類及版本探測-j1後循序重跑。最後答案
控制wall6.336秒，mathlib13.519秒。[答案流程控制](../../docs/verification/MATH-002/answer-pipeline-tests.json)
包含normal/-O各20項新測試及原45項相容回歸，共130次全數通過；先前124與126次
收據留存，未把scripted收據驗證算成真實Lean或模型成績。

[固定tokenizer測量](../../docs/verification/MATH-002/context-tests.json)23項控制、
34筆觀察通過，兩候選prompt編碼相同；僅取得22,866,285 bytes的tokenizer/config，
沒有模型權重或推論。最短4096舊稿＋4096新輸出案例需要9209 tokens；2048方案
在64組參數題＋512-token回饋時為7011，但4000字元回饋時達8136，只剩56。
2048仍只是候選，未改正式上限或凍結protocol。需逐題精確token容量、預登記
回饋／overflow規則及實際TPU成本；不能把此測量當成整套研究已可執行。

## 唯一一次遠端提交

命令是本地實際 CLI 2.2.4 支援的：

```text
kaggle kernels push -p .irisx/line-b/MATH-002/staging --accelerator TpuV5E8 --timeout 1800
```

目標 notebook：`danielwuu/irisx-math-m002-20261019-a7f91c`。
run_id：`m002-smoke-20261019-a7f91c`。版本：**unknown / null**。
CLI exit code：**0**，但實際訊息是：

```text
Kernel push error: Maximum batch TPU session count of 1 reached.
```

沒有把 exit0 當成成功。後續僅唯讀回查：exact source HTTP403；搜尋得到
沒有 ref/version 的 private placeholder。未確認本次版本或終止快照，狀態
保留 `submission_unknown`，不重送、不刪 notebook、不終止其他工作。
第三次Goal續作再次reconcile仍為版本null；wrapper exit0、底層SDK exit2／HTTPError。
該helper沒有回報新HTTP狀態碼，上述403是先前捕獲的證據。

預留 **1/4次、1800/21600秒**（整套v5e-8），未退還未知預留。剩餘數值上限
為3次／19800秒，但 dispatch 被阻塞，並非可直接使用的新授權。實際TPU秒數、
prompt/output tokens、編譯、推論、遠端Lean與wall成本均未知。
沒有下載本任務輸出或取得 checkpoint；沒有執行中的背景監看程序。

提交使用 commit-bound 自足 notebook，沒有假設相鄰 `.py` 自動上傳。
來源總指紋：`984ec856c441da75001fa0b25264c310bebebbae57daa8063e91198bc7ade937`。
其餘 protocol/panel/model/notebook 指紋及精確檔案表見
[run manifest](round002/run-manifest-smoke001.json)。面板指紋綁的是**未凍結提案**，
不能冒充已登記的評分題目。

## 尚未完成的科學驗收

24題仍為提案，selected problems=0；沒有把作者控制題挑成成功面板。來源補查
發現miniF2F-v2c與ProofNet-Verified具有可歸屬的上游人工核對證據，**不必要求
owner親自重做核對**。仍需安全取得精確statement與相符runtime，不能由metadata
直接宣告面板合格。ProofNet版本需要Lean4.28；目前4.19控制不能移用其資格。
公開暴露、答案已給定題不能計為找答案。PutnamBench暫選其他來源避開政策
歧義；「任何私下自動評估都先要聯絡」是先前過強推論，禁止公開proofs則明確。
詳見[來源修正](round002/source-feasibility-notes.json)。未產生目標模型答案，
未讓benchmark gold/reference/rubric進入solver；新防漏控制僅用合成sentinel。

[第三次來源稽核](round002/source-feasibility-audit-03.json)發現miniF2F-v2c欄位中
含內容未確認的formal_proof/informal_proof，尚無可核實的statement-only投影。
部分答案slot也不是單純固定存在命題的proof body；不得默默重寫來符合Nat介面。
未取得整份dataset或reference-proof archive。方法論論文搜尋意外展開圖例，
稽核子代理看見`amc12b_2021_p3`的範例答案；已記錄曝光、停止延伸搜尋，不抄錄
答案值、不傳給solver，也沒有據此挑選或更動面板。

本地僅固定mathlib的受測import閉包資格化，並非完整mathlib或上述題庫runtime。
Kaggle隔離／Lean正負控制、實際v5e-8、冷編譯、
熱推論、公開模型短輸出parity、正式三臂比較及seed複驗均未完成。
R001、MATH-001與WSF-R5的歷史範圍及獨立驗證狀態維持原樣。

本次交付停在 `review_ready`，Goal科學部分未達成。本修正scope不授權Kaggle操作。
平台／權限有實際變更後，原研究task才依原scope另行記錄唯讀回查，釐清未知提交／
帳號權限與TPU可用性，再完成來源准入、真實題目的answer binding、
共同context可行性與相符runtime技術smoke；不能以重複push或換帳號解決，也
不能直接跑未凍結面板。
