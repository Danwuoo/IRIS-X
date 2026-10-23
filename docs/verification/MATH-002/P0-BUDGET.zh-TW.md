# MATH-002 P0：正式對照的預算與排程設計

日期：2026-10-23（Asia/Taipei）。文件狀態：**待審設計，未採用、未執行**。
文件基線為 `73544d6156775f9525129e3fcd4fb55cbfddae25`；現有實作身份仍為
`fedf3a0ac60365fc840b7ae9aefac84a9ba7ba2d`。本文件不改寫原協定、panel proposal、
執行 manifest、舊收據或 remote ledger，也不授予模型、Lean／WSL、測試或 Kaggle 操作。

本次文件工作的單一成果是：讓正式 M-SAMPLE／M-REPAIR 對照具備可審閱的資源
可行性規則及停止條件；文件查核以既有上限、算式、相依介面及原證據的一致性為準，
不以尚未執行的驗收案例宣告通過。原研究問題、成功定義及固定資格門檻維持不變。

## 1. 預算所服務的研究範圍

唯一研究問題仍是：相同資源上限下，M-REPAIR 相對於 M-SAMPLE，是否提高完整
證明率及「找答案且證明」共同成功率；M-DIRECT 保留為一次生成的低成本參考。
零或負增益都可以是有效研究結果。題目不足、缺少 joint 題型、資格未通過或成本
不可行時，結論須保持相應的 `not_estimable`，不能用 authored 控制題取代正式分母。

原 [panel proposal](../../../research/math-proof-agent/round002/panel-proposal.json)
仍是 24 題提案：三個 family 各 8 題、12 題答案發現加證明及 12 題純證明，
`selected_problems=[]`，尚未凍結。seed 順序仍為 0、1、2，先做 seed0，seed1／2
僅在資格及預算具備後進行。本文件的 8 題算例只是條件式可行包絡，不選定題目、
不改採 8 題，也不將尚未完成的 replication 宣告取消或完成。

若未來評分前決定縮小面板，須先依原面板規則產生新 protocol／panel 版本、列明
family 與 proof／joint 的實際構成及結論限制，完成適用審查後才 freeze。較窄的
ProofNet proof-only pilot 可以另案設計，不能算原 joint 目標已完成，也不能從該
pilot 的模型輸出挑選、替換正式對照題。

## 2. 固定的資源與資格邊界

資源上限來自 [MATH-002 單一計畫](../../plan/2026-10-19-math-proof-agent-round02.md)，
現況來自 [NEXT-ADMISSION G5](NEXT-ADMISSION.zh-TW.md#g5未知提交與評分前交付)。
以下是文件中的歷史狀態與算術，沒有本輪遠端查詢或 ledger 讀寫。

| 項目 | 原上限／現況 | 本設計的約束 |
| --- | --- | --- |
| 全 task 提交次數 | 最多 4 次；失敗、smoke、未知均計次 | 剩餘最多 3 次；不能把 seed 當成必須獨占一次提交，也不能因此免除提交計次 |
| 整套 v5e-8 預留總額 | 最多 21,600 秒 | 以每次完整 timeout 預留，不能依預期早停折扣 |
| 唯一既有未知提交 | `submission_unknown / version=null`，預留 1 次及 1,800 秒 | 預留維持；實際 TPU 耗用仍 unknown，不視為零、不退款 |
| 扣除既有預留後的包絡 | `4 - 1 = 3` 次；`21,600 - 1,800 = 19,800` 秒 | 是剩餘上限，並非 dispatch 資格或新增 allowance |
| 單次提交 | timeout 不超過 10,800 秒；平台較低限制優先 | 每次都須滿足，不得以全 task 餘額覆蓋單次超限 |
| 活躍執行及 publisher | 同時最多一個本 task TPU run；單一 publisher | worktree／子程序／新 slug 都不提供額外併行或預算 |
| 主比較臂 | 各最多 4 次生成、4 次工具，解出即停 | 兩臂使用相同的 completion／工具／wall 上限及可信 verifier |
| 每臂 wall | 現 draft 為 600 秒，仍屬 provisional | 本算例保留 600；正式 freeze 前仍須資格化，不能宣告已測得可行 |
| 每次輸出及 context | 目前 `O=4096`、`C=8192`，修復容量不合格 | 較小共同 O 或較大 C 需另版、審查及資格；本文件不採用 2048 |
| 模型 parity | shape 相同、全有限、所有 greedy continuation tokens 相同；`max_abs <= 0.5` 且 `relative_l2 <= 0.03`；既定 warm-repeat／非 deadline 條件 | 原 `0.588851 > 0.5` 失敗保留；不得以節省預算或相對誤差通過覆蓋 |

表內秒數是**整套 v5e-8 提交的 timeout 預留**，不把 8 個 device 分別當成可重用
額度。實際資源報告另列硬體、wall、model／tool／setup 成本與完整性；未知的實體
耗用不得用帳面預留代填。若平台改變硬體或 timeout 限制，原包絡需重新審查。

## 3. 24 題提案的保守算術

令每題每 seed 的臂數為 A，每臂預留 W=600 秒。以下只計臂內預算，尚未計入
環境準備、載入、編譯、信任控制、隔離及結果保存。

| 題數／seeds／臂 | 臂內最壞情況算式 | 秒數 | 對剩餘 19,800 秒的判定 |
| --- | --- | --- | --- |
| 24 題、seed0、兩個主臂 | `24 × 1 × 2 × 600` | 28,800 | 已超限 9,000 秒，尚未計 overhead／資格 |
| 24 題、seed0、含 M-DIRECT 三臂 | `24 × 1 × 3 × 600` | 43,200 | 已超限 23,400 秒，尚未計 overhead／資格 |
| 24 題、seed0／1／2、兩個主臂 | `24 × 3 × 2 × 600` | 86,400 | 不可排入既有包絡 |
| 24 題、seed0／1／2、三臂 | `24 × 3 × 3 × 600` | 129,600 | 不可排入既有包絡 |

M-DIRECT 通常會較早停止，但本設計不依尚未觀察的成功率、早停率或 decode 速度
預借時間。上述數字不是實測耗用，也不是要求臂必須耗滿上限，而是完整 timeout
可承擔性的檢查。因此「先凍結 24 題，再盡量跑完」不構成可行預算方案。

## 4. 共同預算模型與時間邊界

未來排程文件應列出每個提交 j 的完整 timeout `T_j`、用途、全部 planned
`(problem_id, seed, arm)`，及環境／版本身份。以 N_j 表示該提交的題目與 seed
配對數，三臂俱全時的保守可行性條件為：

```text
historical_unknown_reservation = 1800
remaining_attempts <= 3
Q + sum(T_score_j) <= 19800
T_j <= min(10800, applicable_platform_limit)
T_score_j >= H_j + N_j * 3 * 600
H_j >= 0
```

`Q` 是所有未來非評分資格提交的完整 timeout 總和，也消耗提交次數；`H_j` 是
不在臂內 wall 計時範圍的全部開銷上界。若資格需要兩次提交，或一次失敗／未知
用掉原定 slot，必須重新證明餘額與可完成的 planned 面板，不能維持原排程假設。

H_j 必須包含：冷啟動、依賴／cache 準備、模型／tokenizer 載入、JAX 編譯及
warm-up、Lean／Mathlib runtime 準備、可信控制與 isolation preflight、排程初始化、
臂外的工具 setup、結果與成本收據原子寫入、terminal manifest／hash 完成，以及
終止及保存所需餘量。網路取得若仍是合法且必要的步驟，其 remote wall 同樣納入。
無法從本地 CPU／WSL 觀察推估為目標 TPU 已通過。

現行 controller 的 verifier preflight／setup 在各臂 wall 起算前進行；H_j 必須
按該提交所有 planned arms 計入這些重複開銷，不能只留一次 run-level preflight。
若兩個來源需要不同 Lean／Mathlib runtime，切換／載入／隔離準備亦按實際次數
納入 H_j，不假定同一 run 只有一次工具環境準備。

每筆時間須依固定 clock 邊界歸屬：臂內已計的生成、工具與編譯不能再次作 H_j
加總，臂外開銷也不能消失；分項成本與整體 wall 同時保存。依賴準備或可信控制
若耗盡 H_j，不能啟動預算已不足的下一個臂／配對，不能借用預定終止保存時間。
實際早停仍報實際成本，但不在已提交排程中把省下的時間轉成未凍結題目或額外
seed。預算是硬上限；證明／joint 成功的定義不因時間不足而放寬。

## 5. 一個具體且有條件的可行包絡

以下以剩餘三個 slot 建立可算的審查對象，**不是已採用執行計畫**：

| slot | 提議用途 | 完整 timeout 預留 | 臂內預算 | 臂外預留 | 必須先成立的條件 |
| --- | --- | --- | --- | --- | --- |
| 既有 1 | 歷史未知提交 | 1,800 秒 | 未知 | 未知 | 既有預留維持，未解除 dispatch gate |
| 未來 1 | 非評分、真實目標鏈的資格驗證 | 1,800 秒 | 非評分控制，沒有正式觀察值 | 全部包含在 1,800 秒內 | 全部所需 parity、runtime、isolation、context／成本及保存控制能在此 cap 完成 |
| 未來 2 | seed0，4 題，各 M-DIRECT／M-SAMPLE／M-REPAIR | 9,000 秒 | `4 × 3 × 600 = 7,200` 秒 | 1,800 秒 | 這 4 題為事前凍結同一面板的固定分片；H_2 已證明不超過 1,800 秒 |
| 未來 3 | seed0，另 4 題，同三臂 | 9,000 秒 | `4 × 3 × 600 = 7,200` 秒 | 1,800 秒 | 同一身份、另一固定分片；H_3 已證明不超過 1,800 秒 |
| 合計 | 歷史加未來，最多 4 次 | `1,800 + 1,800 + 9,000 + 9,000 = 21,600` 秒 | 正式臂內合計 14,400 秒 | 正式臂外合計 3,600 秒；資格 1,800 秒 | 新增預留正好 19,800 秒，沒有額外 retry slot |

本包絡保留 600 秒臂上限和三臂比較，8 題 seed0 共 24 個 arm observations；
兩個主臂形成 8 個問題層級配對。三個 seeds 在同題上是重複測量，不能視為增加
三倍獨立問題數。題目分片不是新題目選擇：全 panel、分片、臂順序、seed、
來源與 runtime／model／code／protocol 身份必須在任何正式輸出前一併固定。

這個包絡只有在下列條件全部成立時，才可能成為後續採用候選：

- 有足夠合法、忠實、人工核對且 runtime 合格的來源，包含能估計原 joint 指標的
  `find_answer` 題；純證明或答案已給定題不能補 joint 題型。實際 family 與題型
  構成需另版列明，不能聲稱仍具原 24 題提案的代表性或精度。
- 共同 context／completion／feedback 政策先通過資格。4096／8192 原組合未合格；
  本包絡沒有暗含已採用較小 O、較短 proof 或縮減修復回饋。
- 剩餘一次 1,800 秒非評分資格真的足以完成所需目標 gate，且 9,000 秒評分
  timeout 內全部 cold／setup／finalization 開銷各不超過 1,800 秒。這些都是待測
  gate，並非把既有局部證據拼接成已資格化的全鏈路。
- 未知提交已依適用條件完整 reconcile；單一 publisher、exact source／version／
  latest／status 與當前 dispatch 資格均可建立。只讀 reconciliation 本身不執行
  模型，但本輪連此操作亦未啟動。
- 適用獨立審查、protocol／panel 版本及 freeze 完成；不得把本預算文件或 smoke
  manifest 當成 scoring manifest。

由於本包絡耗盡剩餘三個 slot 與全部保守預留，seed1／2 **沒有已保留的執行資源**。
它們仍是預算條件式 replication，報告須標明未執行；不能聲稱三 seeds 對照完成。
同樣不能把未來第一次資格失敗後的再跑算作免費修正。若任何條件不成立，本方案
即為不可採用，需在評分前提交新的可行方案或明列阻塞，不默認新增資源。

## 6. 可審查的替代配置與不得暗改的部分

在三臂、600 秒及每個評分 run 保留 H_j 的前提下，可用下式檢查其他題數配置：

```text
N_total <= floor((19800 - Q - sum(H_j)) / 1800)
```

該式只提供總題目×seed 上界，仍需逐 run 驗證 `T_j <=10800`、提交次數、
來源／題型與固定分片。上例代入 `Q=1800`、`sum(H_j)=3600`，得上界 8。
例如改成更多非評分資格、不同 runtime 的分開載入或更高可信控制成本，會降低
正式對照可承擔數量。若每個評分 run 的 H_j 高於 1,800 秒，即使實際模型很快，
上例也不能稱已證明可行。

優先調整的是評分前的可行題數／分片與資格安排；任何變更均須保持可估計的
proof 與 joint 目標並揭露小樣本限制。降低 600 秒、降低共同輸出 cap、改大 context、
刪除 M-DIRECT、改變 seed 政策或將 joint 改為 proof-only，都屬需明列及適用審查的
設計變更，不由算式自動採用。現有 24 題、seed 順序、原 context 與控制門檻的
proposal／protocol bytes 繼續保存，不以文件附件直接覆寫。

## 7. 停止與失敗記帳

1. 遠端未知身份未解，或 exact source／version／latest／status 任一不完整：
   不 dispatch；離線文件與工程設計仍可準備。不得換 slug 來繞過 gate。
2. 任一資格 gate 不合格、arm/context 上限未固定、來源／answer binding 未准入：
   不生成正式模型輸出；不能將測得的失敗改成 scoring 通過。
3. 失敗、preflight failure、smoke 或未知提交都占已預留 slot 及 timeout。保留原
   unknown、實體 charges 和 clocks；不因 CLI exit0 或估計未開機退款。
4. 連續兩次同根因遠端失敗，停止同類重試。更早用盡 slot／總額或資格不符時，
   先觸發該停止條件；此條不是保證提供兩次 retry。
5. 評分開始後，保留所有 frozen planned 題目、seed、arm 分母。run 中止、
   timeout、context／format／infra failure 及 not_reached 都保留；缺一臂的配對
   不能變成 tie、gain 或 loss，已生成失敗不能被刪除。
6. 不自動恢復部分生成、不依正式輸出換題／刪題／加樣本。任何恢復決策都需要
   原 snapshot／身份／預算的明確 reconciliation，並保留未完成觀察。
7. 終止保存所需餘量不足即停止派發新工作，保存可得原始成本／候選／收據。
   缺失成本報 observed lower bound 與缺項，不能記為零或完整。

## 8. P0 驗收案例索引與後續交付

下表是**待實作／待執行的驗收案例設計**；本輪沒有執行任何案例、測試程式或
模型／Lean／WSL／Kaggle 操作。案例的預期判定不是現有系統通過的證據。

| ID | 審查輸入／未來案例 | 預期判定 |
| --- | --- | --- |
| BUD-01 | 4 次／21,600 秒；既有 unknown 1 次／1,800 秒；新增完整 timeout 清單 | 餘額為 3 次／19,800 秒；總額、單次與平台上限都需通過；不退款 unknown |
| BUD-02 | 24 題、1 或 3 seeds、2 或 3 臂，W=600 | 產生本文件 28,800／43,200／86,400／129,600 算式；全部判不可排入剩餘包絡 |
| BUD-03 | 資格 1,800；兩個 9,000；各 4 題三臂及 H=1,800 | 僅標 conditional_feasible；任一額外提交、timeout 超限或 H 超限均拒絕採用 |
| BUD-04 | 兩主臂共同四次生成／四次工具／600 秒；不合格 4096／8192 修復 context | 公平上限保留，但 context gate 仍拒絕 freeze；2048 未資格不能自動替代 |
| BUD-05 | unknown 身份／缺 version、失敗重試、CLI exit0、預留退款請求 | 拒絕 dispatch／退款；新失敗照計次，兩次同根因停止；不另造 ledger |
| BUD-06 | 固定面板跨兩 runs；缺臂／未到達；seed1／2 無預留 | planned 分母不變；缺配對單列；replication 未執行且非獨立新增問題 |
| BUD-07 | 冷啟動／載入／編譯／信任／隔離／保存的完整 clock map 與目標量測 | 無漏計與重計；足額 reserve 才可採用；本地與腳本控制不能代替目標成本資格 |
| BUD-08 | 只有本設計文件而無新 protocol／panel、適用審查及所有 gate | 保持未採用／未執行／not_estimable；不取得 scoring 或 remote authority |

P1／P2 的介面、預計變更及依賴見 [介面設計](P1-P2-DESIGN.zh-TW.md)，
更完整正負案例與證據要求見 [驗收案例](P1-P2-ACCEPTANCE.zh-TW.md)。
預算選項的採用需要這些介面能表達完整身份、共同上限、time boundaries、planned
分母及停止原因；實作與資格證據仍是未來工作。

後續審閱應先決定哪些方案值得進入實作，並把尚缺的來源、context、parity、
runtime／isolation、正式 runner／analyzer 及遠端 readback 證據逐項列出。
沒有新 target-model 配對觀察，現有科學狀態仍為 `not_estimable`；工程維持
`review_ready`，不以開發者或實作子代理自行審查代替獨立 acceptance。
