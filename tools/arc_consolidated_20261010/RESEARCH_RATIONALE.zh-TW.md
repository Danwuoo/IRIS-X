# 研究方向與判讀規則

## 為何先測表示，再測搜尋

上一輪 N12 的完整 1,277 候選 × 八個暴露工程题檢查沒有全部示範吻合的候選；合法 typed IR 與實際搜尋 inventory 的範圍也不一致。增加 feedback、memory 或搜尋預算之前，應先區分「候選存在但找不到」與「此有限表示/資源域內沒有候選」。這是本輪工程診斷，不是從八題推估 ARC-AGI-2 的整體能力。

本輪固定 5,965 個候選，加入物件 partition/selector/render、受限 anchor recolor、等分面板 Boolean/copy；正負控制先驗證語義，再完整檢查示範。無語義可達性的 `same_normalized_mask` 與 unique-extreme anchor 組合已移除 260 個候選，而非為保留原數量填補無用項。

## 與研究來源的關係

- [ARGA：Graphs, Constraints, and Search for the Abstraction and Reasoning Corpus](https://ojs.aaai.org/index.php/AAAI/article/view/25527) 使用物件圖抽象與 DSL 搜尋，並以約束、狀態 hashing 與 Tabu search 控制搜尋。它支持「表示與搜尋應共同設計」這個方向；本輪沒有重製其完整演算法，也不借用它的成績。
- [HySynth](https://arxiv.org/html/2405.15880v2) 從 LLM 候選近似 task-specific 的 context-free prior，再引導符號合成。本輪保留 uniform、smoothed、hard-pruned 三個對照，共享相同候選池與 tie seeds，明列零支持排除；這是針對本系統的可檢验假說，並非 HySynth 的完整複現。
- [CodeIt](https://arxiv.org/html/2402.04858v2) 探索以程式執行產生的 hindsight replay 自我改善。本輪只實作獨立控制、可驗證的資料/候選接口與研究帳本；沒有 hindsight 訓練、finetuning 或模型能力提升證據。

以上原始來源於 2026-10-10 再次核對。不同資料、模型與预算下的論文结果不作本輪預期分數或效能保證。

## 後續階段

1. 表示可測性：完整候選 inventory、獨立正負控制、八題全部保留。報告 fit、mismatch、out_of_domain、unknown、missing，不能把資源排除或未訪問候選合併成錯誤答案。
2. 介面一致性：模型產生的合法、最多三步 IR 可以加入各 arm 共用的小型增補池；每題最多兩個新 root，duplicates、拒絕與 overflow 都要有 receipt。不能用 grammar 沒有表示的合法提案推論模型沒有想法。
3. 有 witness 後才比較策略：true/redacted feedback 使用同一父候選；memory off/on 使用固定相同父候選與歷史；三種 search 使用相同 pool、相同 tie order 與 64-expansion 上限。報告按 witness-feasibility 分層，不把已知不可達題當成模型能力比較的同質样本。
4. 新資料上的檢驗：下一輪應先凍結不同於這八個暴露工程題的開發集合與假說，再測候選表示與搜尋。不要依本輪答案反覆修改 operator，然後把同一批示範的提升當成泛化。查詢與 held-out gold 持續隔離。

## 本輪的停止規則

SMOKE 永遠不開模型。FULL 若缺少完整覆蓋、控制失敗、存在未知帳或少於兩題有 witness，就保留 no-go 結果，不自動增加候選、提高 gas、延長時間或開始模型安裝。程式碼與 notebook 的發布只表示工程交付；科學結論、實機模型接受與正式競賽分數分開記錄。
