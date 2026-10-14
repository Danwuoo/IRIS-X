# ARC-AGI-2：既有研究方向與證據入口

更新：2026-10-14。來源快照：`cc14bd1a79aac1fe6135017c9e09d4834300675d`。
這是既有研究的導讀與追溯入口，不是新研究方案、實驗結果、原文替代品或執行授權。
原研究文件保留完整篇幅與原始身分；目前工程／交付狀態另見 [STATUS](STATUS.md)。

## 1. 研究主問題不是「把訓練跑完」

以下是 R1–R5 的共同脈絡整理，不另立已核准的跨實驗 protocol：
**在明確的模型、資料來源與可比資源條件下，哪些專門化訓練、候選表示／提案、
可執行示例回饋與選答機制，能增加 ARC-AGI-2 的正確候選覆蓋與實際 top-2 命中？**
研究要區分同族擬合與真實 ARC 轉移，也要分開品質、完成度與成本。

R2 主張保留完整程式／文字能力，以可執行假設與 demonstration 回饋做受控比較；
R3 將少量 program-LoRA 訊號轉為事先固定的 checkpoint portfolio／跨族面板；
R4–R5 再把當前問題收斂為 SFT256 錨點、小量 exact-reward 更新與額外 SFT 的比較。
這是不同階段的研究脈絡，不是同一實驗逐次累加的分數，也不是把所有方法一起啟用。

## 2. 原研究文件的角色與閱讀順序

| ID | 原文件 | 回答的問題／保留範圍 |
| --- | --- | --- |
| R1 | [historical-experiments.md](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/native-continuation-20261013/historical-experiments.md) | 10/13 撰寫、綜整至 10/8：哪些歷史正向訊號、負面結果與未完成比較已被記錄。不是全專案最新成績表。 |
| R2 | [architecture-memo.zh-TW.md](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/arc-next-line/architecture-memo.zh-TW.md) | 10/8：為何從 compact grid／固定宏轉向完整 vocabulary、program proposal 與 feedback repair；保留方案、限制及原文文獻分析。 |
| R3 | [qwen-portfolio PLAN.md](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/qwen-portfolio-20261012/PLAN.md) | 10/12：v18 局部訊號如何導向事先固定 base/8/16 portfolio、63-case 分層面板及獨立選答；它是方案，不是新面板結果。 |
| R4 | [primary-method-assessment.md](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/native-continuation-20261013/primary-method-assessment.md) | 10/13：外部原始研究與本地證據如何支持當前假說；哪些觀察決定下一轮研究。保留原文的文獻／推論／限制區分。 |
| R5 | [native-research-continuation.md](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/docs/plan/2026-10-13-native-research-continuation.md) | 10/13：當前 SFT256／分批 RL／等成本 SFT 的具體實驗與條件式後續；過時操作阻塞看 STATUS，不重放舊授權。 |

要理解方向，先讀本頁，再按問題讀 R4／R5 或 R2／R3；要追查結果，讀 R1 再回原實驗報告。
不能只讀 run008 handoff 就宣稱已讀完整研究。原文中的外部研究結論仍是當時評估；本導讀未重新查核外部文獻。

## 3. 既有證據如何限制方向

| 證據 | 支持的局部判斷 | 不支持的推論 |
| --- | --- | --- |
| [uncapped 完成報告](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/arc-next-line/uncapped-result/README.md)：已暴露 4 tasks／6 tests，41 個候選，top-2 與 pool oracle 均 1/6 | 該批候選中的五個缺失正解，不能只靠改排序補回；提案／表示／適應值得研究。 | 不證明所有搜尋無效、不證明新 agent 架構必勝，也不是新 14B baseline。 |
| [BASE／TTT 成對報告](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/trials/arc-agi-2-qwen35-nvarc/public-eval-notebooks-001-diagnosis.md)：變體輸入上 5/172 → 10/172 | task-local adaptation 有局部正向訊號，但需同時衡量成本及候選覆蓋。 | 不是標準 PUBLIC120／167 的新結果，不能移植成新模型的成績。 |
| R3 引用 v18：同訓練轉換族的 disjoint queries 2/6 → 5/6；事後 portfolio 6/6 | program 訓練與 checkpoint 互補值得前瞻、分層驗證。 | 事後選擇不是新確認；不能稱已證明真實 ARC 泛化或新 63-case 面板成功。 |
| R4–R5：v39 未完成方法比較，v25 只讀到成本來源、缺相關 scoring artifacts | 保留待回答的假說及明確缺件；工程失敗與科學結果分開。 | 不能說 RL 已無效、以缺失分數補零，或由 GPU／CPU 修復推定方法有效。 |

原始結果與研究判斷都要保留。早期報告是歷史證據，但不因日期早就失去對當前研究的價值。

## 4. 眼前待回答的實驗：保留 R4–R5，不另換題

研究問題：**少量可驗證 exact-reward policy 更新，是否勝過相同 SFT 錨點，
並且勝過花費可比額外時間的 SFT？** 這是小量 intervention-package pilot，不是對所有 RL 的一般性判決。

| 當前訓練比較 | R5 指定內容 |
| --- | --- |
| A | 同一 session 真正完成、保存並重載的 SFT256 錨點。 |
| B | 從 A 還原，32 個 training parents；最多四個互不重疊的 64-slot batches，最多四次更新。 |
| C | 從 A 還原的額外 SFT，對照 B 整段額外 model-phase wall time，不靠空等湊成本。 |

dev16 選一次，保留固定 tie order；selected arm 的 PUBLIC 與 A/B/C reused held32 選答先封存，
模型關閉後計分。PUBLIC120 固定 120 tasks／167 queries；本次比較不加入 TTT。
B／C learning rates 不同，不能叫 objective-only 因果比較；reused held32 不是 pristine confirmation。
R5 的 >90%／151-of-167 是目標，不是預測或結果。

**不要混用兩組 A/B/C：** R2 的 A/B/C 是 direct-grid／open-loop program／feedback repair；
R5 的 A/B/C 是 SFT256／RL／額外 SFT。它們的模型、資料、預算與驗收必須各自綁定。
舊 SFT64／完整 256-slot sweep 草案不能覆蓋 R5 明列的後續 SFT256／分批設計。
真正恢復執行時仍以原凍結來源、適用規則及新的實際環境核對為準；本頁不重定義 runtime。

## 5. 取得證據後如何選下一步

以下沿用 R4 第 4 節與 R5 第 5 節的條件，不是本次整理啟動的工作：

| 觀察 | 下一個能區分原因的研究方向 |
| --- | --- |
| 尚未進模型或數值 replay 不合格 | 修已定位的工程／數值問題；不換方法掩飾，也不放寬原閾值。 |
| 完整 audit 沒有 mixed reward groups | 分清全零／全一與未完成；乾淨零訊號時 B=A，後續研究 training-only 提案覆蓋／資料，而非盲目加 RL steps。 |
| B 有更新但沒有勝過 A／等成本 C | 保留無增益結果與局部條件；由成對得失、訊號及覆蓋判讀，不宣稱全面能力突破。 |
| 候選 oracle 低；或 demo-perfect 程式轉移差 | 研究表示、提案、多樣性、verified trajectories 與適當的示例留出驗證。 |
| oracle 高但 top-2 低；或 repair 代價高 | 對同一 sealed pool 研究選答；repair 必須與同 checkpoint、可比預算的額外獨立提案比較。 |
| B 同時勝過 A／C | 視為待複驗的局部訊號，在預先固定的新 task／family 面板重驗，不把 reused held32 改叫全新驗證。 |

## 6. 在本次重整中的位置

ARC 是有既有研究方向、結果與待答問題的工作線，不是只剩雲端修復的 legacy 目錄。
`arc-next-line` 是 ARC 內部技術演進，不能拿來替尚未指定領域的 `line-b` 命名。
共用工程整理不授權新科學實驗；第二線也不必讀完 ARC 研究才能開發。

[PR 2–4 計畫](../../plan/2026-10-14-workstream-pr2-pr4-local-development.md) 要驗收的是：
研究問題 → 原方向文件 → 既有結果／限制 → 下一個凍結實驗 → 條件式決策，都能清楚追溯。
本頁是上述關係的閱讀入口；文件 catalog 索引原文，task records 管工程進度，不再複製第二份科學成績帳本。
