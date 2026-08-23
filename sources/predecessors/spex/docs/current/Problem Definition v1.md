# Problem Definition v1

**版本：** v1.0  
**狀態：** Current project problem definition  
**證據截止：** Evidence Base v1.1 與 Evidence Adjudication v1  
**文件角色：** 定義目前可由已裁決證據支持的 empirical problem；不提出架構、解法、正式假說、roadmap 或實驗設計。

---

## 1. 文件權威與歷史邊界

本文件取代 `Problem Definition v0.md`，作為目前專案對研究問題的正式表述。

本文件的直接依據是目前專案的 evidence base、contradiction mapping、DR2 primary-source verification 與 evidence adjudication。Vanta 相關文件僅可作為歷史經驗、先前假設、失敗案例與工程教訓的來源；其架構、術語、模組、研究命題或實作選擇不構成本專案的需求，也不得用來填補本文件仍標記為未知的部分。

---

## 2. Revised observation

目前最穩定的觀察不是「specialists 很少勝過 generalists」這個未分層命題，而是下列三組彼此不同的 empirical patterns：

1. **Model-level specialization 的 same-backbone relative gain 經常成立。** 以同一個或緊密對應的 base model 為基準，continued pretraining、domain instruction tuning、preference alignment、task-specific RL 等模型參數介入，常能提高目標任務或目標 benchmark family 的表現。這是目前證據中置信度最高的部分。

2. **Model-level relative gain 較少被可靠地證明可轉化為 broad、contemporary、resource-matched frontier superiority。** 已知存在 SaulLM、MMedIns 等 benchmark-level counterexamples，但它們多受 comparator snapshot、benchmark ownership、protocol parity、independent replication、task-distribution breadth 或後續 frontier drift 限制。現有證據不足以支持 model-level specialist advantage 是普遍、廣泛或持久的現象。

3. **System-level、hybrid 與 formal/verifier-bound specialization 可在有界環境中形成強優勢。** PaperQA2、Aviary、FinTral 類系統與 AlphaProof／AlphaGeometry 類 formal solvers 顯示，retrieval、tools、environment、workflow control、search、verification 與 test-time compute 能使 specialized capability systems 在特定工作流或正式問題空間中超過一般系統、frontier agents 或人類基準。但這些結果不能歸因為 specialized weights alone，也不能自動外推為 broad domain capability。

因此，現有證據同時支持「專門化常有用」與「其優勢通常高度依賴比較單位、能力構念、資源配置與時間索引」。兩者並不矛盾。

---

## 3. Revised empirical discrepancy

### 3.1 核心 empirical puzzle

目前應保留的核心 empirical puzzle 是：

> **為什麼 model-level specialization 所產生的 recurring same-backbone relative gains，只有少數案例被可靠地證明能轉化為相對於當代強 general-purpose comparators 的廣泛、穩定且持久 superiority；同時，為什麼 system-level、hybrid 與 formal/narrow solvers 又能在若干有界工作流或正式問題空間中形成明顯優勢？**

這個 puzzle 是一個**轉換缺口與邊界差異**，不是「specialization 是否有效」的二元問題：

- 第一個待解釋的差距，是 **relative gain → contemporary frontier superiority** 的轉換缺口。
- 第二個待界定的差距，是 **benchmark-local superiority → broad domain or professional workflow capability** 的外推缺口。
- 第三個待觀察的差距，是 **historical/contemporary superiority → persistent superiority** 的時間持續缺口。
- 第四個待拆分的現象，是 **model-level 優勢稀少**與**system/formal bounded wins 明確存在**之間的 unit-of-analysis divergence。

本文件不預設上述差距由何種機制造成。資源不對稱、domain 切分方式、general capabilities、benchmark validity、data overlap、tools、verification、inference compute、frontier drift 等目前都只能是待後續判別的可能因素，不能在問題定義階段被當成已成立的原因。

### 3.2 不再採用的總括命題

以下命題不再被視為可接受的問題前提：

- 「specialized systems 普遍無法擊敗 general-purpose systems」；
- 「general-purpose learning 在本質上優於 specialization」；
- 「任何 specialist win 都是 model-level specialization 的勝利」；
- 「domain-labeled benchmark leadership 等同 broad domain expertise」；
- 「某一時間點勝過 GPT-4 或其他命名模型，即構成持久的 frontier superiority」；
- 「更真實的 evaluation 一定有利或不利於 specialists」。

---

## 4. Unit of analysis

任何 evidence record、superiority claim 或 counterexample 都必須先指定下列 unit；不同 unit 的結果不得直接聚合成一個 specialist/generalist 結論。

| Unit | 暫定定義 | 可支持的最窄命題 | 不可直接推出 |
|---|---|---|---|
| **Model-level specialization** | 主要介入發生於模型參數，包括 continued pretraining、finetuning、instruction tuning、preference alignment、LoRA 或 RL。附加工具與特殊 inference 必須另行揭露。 | 參數介入相對 own base 的增益；在資源與 comparator 規則滿足時，可討論 model-level frontier superiority。 | 不能把 retrieval、agent scaffold、verifier 或額外 search 的效果歸因於 weights。 |
| **System-level specialization** | 主要介入發生於模型外部，包括 RAG、資料庫、工具、workflow、agent scaffold、environment、search、routing 或 verification。 | 完整 capability system 在指定工作流或環境中的優勢。 | 不能推出 underlying model weights 具有 broad domain superiority。 |
| **Hybrid specialized capability system** | 模型參數與系統資源同時被專門化，且目前無法由 evidence 將各自貢獻乾淨拆開。 | 整體配置在明確條件下的 system-level outcome。 | 不能把結果單獨歸因於 model-level 或 system-level 任一側。 |
| **Formal or narrow solver** | 針對固定格式、狹窄任務分布、formal language、exact verifier 或特定搜尋空間建立的 solver。包括 narrow classifiers 與 formal/verifier-bound systems；兩者須標記 subtype。 | 在該窄任務或 formalized problem space 中的 solver superiority。 | 不能直接推出 broad domain capability、open-ended workflow capability 或一般自然語言模型 superiority。 |

「generalist」也必須使用對稱單位：model-level specialist 應優先與 general-purpose model configuration 比較；system/hybrid specialist 應與具相同工具、存取與 inference boundary 的 general-purpose capability system 比較。

---

## 5. Provisional definitions

### 5.1 Domain

**Domain** 是一個明確陳述的 target problem distribution。它可能由知識／語料、語言／司法轄區／制度、任務家族、工作流或工具環境界定。每個研究主張必須記錄 domain subtype；不能把 biomedical text、臨床工作流、法律分類、repo-level engineering 與 scientific literature search 視為同一類 domain。

### 5.2 Specialization 與 specialist

**Specialization** 是對指定 target distribution 的有意優化。其機制必須拆分為 model-level、system-level、hybrid 或 formal/narrow solver，而不能只以 `specialist` 作為充分分類。

**Specialist** 是經過上述有意優化的 model、capability system 或 solver。該標籤本身不包含 superior、generalizable 或 efficient 的意義。

### 5.3 General-purpose comparator

**General-purpose comparator** 是面向多領域、未針對該 target distribution 做同等專門化的 model 或 capability-system configuration。必須明確記錄其 unit、版本、evaluation date、工具／資料存取、context、inference policy 與可得的資源資訊。

### 5.4 三種 advantage

1. **Same-backbone relative gain**  
   同一 underlying base 或緊密對應的 base family，在相同 evaluation 與 inference configuration 下，specialized variant 相對未專門化 variant 的增益。額外的 specialization training data 與 training compute 是介入的一部分；此結果不等於 compute efficiency，也不等於 frontier superiority。

2. **Contemporary frontier superiority**  
   在明確 evaluation date，specialist unit 相對當時最強且相關的 general-purpose comparator，在相同 capability construct 與可比較 system boundary 下形成優勢。此主張必須是 time-indexed，不能延伸到後續 frontier generation。

3. **Persistent superiority**  
   已成立的 superiority 在後續至少一個具有實質 frontier 更新或時間位移的 evaluation checkpoint 中，仍能相對當時的 contemporary comparator 保持。單一時間點、單一 leaderboard 或後續未重測的歷史勝利不能稱為 persistent。

### 5.5 三種 capability construct

1. **Benchmark proxy**  
   特定資料集、題型、metric 或 benchmark family 所測得的表現。它只能支持對該測量構念的窄解讀。

2. **Broad domain capability**  
   跨多個實質不同的 task families、資料分布或 evaluation contexts，仍保有與該 domain 相關的能力。單一作者建立的 multi-task suite 或同一資料生成程式內的 task count，不足以單獨證明 broad capability。

3. **Professional workflow capability**  
   在接近實際專業程序的工作流中，完成 retrieval、evidence integration、procedure、tool use、生成、verification 或 execution，並以工作流結果、程序正確性、專家 rubric 或其他具外部效度的 outcome 評估。文字 benchmark 高分不能直接替代此構念。

### 5.6 Generalization、stability、repeatability 與 persistence

- **Generalization**：優勢在明確標記的 held-out task、OOD task family、temporal shift、不同制度／語言／環境或其他分布位移下仍存在。若這些證據不存在，狀態應是 `Unknown / not evaluated`，而不是自動判為成功或失敗。
- **Stability**：在同一時間索引下，結果不只依賴單一資料集、單一 prompt/protocol、單一 metric 或單次 run；至少需要在一個實質不同的 evaluation condition 或獨立評估中維持相同方向，否則只能稱為 single-setting result。
- **Repeatability**：主要結果能由獨立團隊、獨立 evaluation 或可重建 protocol 重現。作者自建 benchmark 上的結果在未有外部驗證前，只能稱為 author-linked evidence。
- **Persistence**：優勢跨時間與 frontier 更新仍然存在；它與當下 stability、OOD generalization 不同。

上述為最低分類規則，不是已由文獻驗證的普遍數值門檻。

---

## 6. Minimum adjudication rules

### 6.1 Comparator rule

一個 superiority claim 至少必須記錄：

- specialist 與 comparator 的 unit；
- exact model/system version 或明確 snapshot；
- evaluation date；
- comparator 為 own base、一般公開 generalist，或 contemporary frontier；
- benchmark/workflow capability construct；
- prompt、scaffold、tool、retrieval、context 與 inference configuration。

若 comparator 版本未知，或 unit 不對稱，結論不得標記為乾淨的 contemporary frontier superiority，只能標記為 `historical`, `partially matched`, `system-configuration advantage` 或 `not interpretable`。

### 6.2 Time rule

- 所有 frontier claim 必須 time-indexed。
- 跨世代比較只能證明對被測 snapshot 的歷史 superiority，不能證明 contemporary superiority。
- 後續更強 frontier system 出現時，舊結果不代表 specialist capability 消失，但其 frontier status 必須改為 historical，除非重新評估。
- 若 benchmark 已被可信 evidence 指出污染、飽和或時間洩漏，該 benchmark 不得單獨支持 contemporary 或 persistent superiority。

目前不設定固定的月份或年份窗口；缺少 exact date/version 時，一律保守降級。

### 6.3 Resource-matching rule

至少應揭露並盡可能對齊以下四類資源：

1. **Model/training resources**：base family、parameter scale、training data、specialization data、training compute 與 post-training stages。
2. **Information access**：retrieval corpus、database/API、data cutoff、point-in-time constraint、private data 與 human-provided information。
3. **System configuration**：tools、environment、workflow scaffold、context window、memory、verifier、formalizer 與 human intervention。
4. **Inference resources**：token budget、model calls、rollouts、search width/depth、wall-clock、ensemble、test-time compute 與 retry policy。

若上述資源未匹配，結果仍可支持「完整 capability system 在該配置下較強」，但不能把差異歸因於 specialization mechanism 本身。`Unknown` 必須保留，不得用合理猜測補值。

### 6.4 Evaluation-construct rule

每個結果都必須明確標記為 benchmark proxy、broad domain capability 或 professional workflow capability。不同構念的 ranking 不構成直接 contradiction，也不能相互替代。

- benchmark-local win 只能反駁對該 benchmark family 的普遍否定命題；
- workflow win 必須保留工具、資訊存取、流程與 verification 的 system boundary；
- formal/narrow solver win 只能外推到其明確 problem space。

### 6.5 Generalization and stability rule

- 多任務不等於 OOD；同一作者、同一資料生成程式或同一 benchmark family 的 breadth 不等於 independent generalization。
- 沒有 held-out/OOD/temporal/independent evidence 時，不得使用 `broad`, `generalizable`, `stable`, `repeatable` 或 `persistent` 等未限定詞。
- 若優勢只出現在單一 metric 或單一 protocol，應標為 `single-setting`。
- 若結果在不同 task family、protocol 或獨立評估中方向不一致，應保留為 heterogeneous evidence，不得以平均值消除差異。

---

## 7. Scope boundaries

### 7.1 本問題包含

- 不同 specialization units 的 empirical performance pattern；
- same-backbone gain、contemporary superiority 與 persistent superiority 的區分；
- benchmark proxy、broad domain capability 與 professional workflow capability 的區分；
- comparator、時間、資源、generalization、stability、replication 與 benchmark validity 對結論可解釋性的最低要求；
- 能精確指出其所反駁命題的 counterexamples；
- 仍無法裁決的 prevalence、durability、scaling 與 component-attribution 問題。

### 7.2 本問題不包含

- 新系統架構、模組邊界、runtime、training recipe 或 deployment design；
- 哪一種 specialization 方法「應該」被採用；
- 正式機制假說或 winning explanation；
- roadmap、milestone、實驗 protocol 或 benchmark 建設計畫；
- 由 Vanta 架構反推本專案需求；
- 將單一領域案例外推成跨領域普遍定律。

---

## 8. Evidence status

### 8.1 已支持（Supported）

1. **Same-backbone relative gain 是 recurring observation。** Model-level specialization 經常能提高 adapted base 在目標任務上的表現。
2. **Unit-of-analysis split 是必要條件。** Model-level、system-level、hybrid、formal/narrow solver 的證據不能聚合成單一命題。
3. **Same-backbone gain 不等於 frontier superiority。** 兩者使用不同 comparator，並可同時成立。
4. **Benchmark score 通常只是 domain capability 的部分 proxy。** Leaderboard dominance 不能單獨證明 broad expertise 或 professional workflow capability。
5. **Cross-generation comparison 不能證明 contemporary superiority。** Frontier claim 必須帶版本與日期。
6. **Tool、retrieval、access、environment 與 inference-resource asymmetry 是實質 confounders。** 在未匹配時不能將全部效果歸因於 specialization。
7. **普遍的 generalist dominance 命題已被反例否定。** 至少存在可信的 benchmark-level model counterexample、bounded system-level counterexamples 與 formal-solver boundary conditions。
8. **金融時間控制與公共 benchmark contamination 會改變 ranking 的可解釋性。** 未控制的結果不能支持強結論。

### 8.2 條件式支持（Conditionally supported）

1. **Model-level same-backbone gains 經常不會自動轉化為 contemporary frontier superiority。** 此 pattern 目前較強，但 prevalence 仍缺少大量 matched comparisons。
2. **Model-level frontier superiority 可以在 benchmark-local 條件下發生。** SaulLM 是最可信案例；MMedIns 仍屬 author-program、partially matched evidence。
3. **System-level specialization 可以在 bounded workflows/environments 中超過 frontier agents 或 experts。** 其優勢必須歸屬完整 capability system。
4. **Formal/verifier-bound solver superiority 可以非常強。** 其適用範圍受 formalization、verifier、search 與 test-time compute 明確限制。
5. **目前最強 specialist wins 多半是 bounded，而非已證明 broad and durable。** 這是現有 corpus 的描述性結論，不是普遍失敗率估計。
6. **Frontier generalists 有時會在後續世代反超既有 specialist milestones。** 這支持 frontier drift，但不能推出 specialist capability 必然衰退或所有優勢都短暫。

### 8.3 仍未知（Unknown / indeterminate）

1. Model-level specialization 在 contemporary、resource-matched、broad evaluation 中形成 frontier superiority 的實際頻率。
2. High-resource、strong-backbone model-level specialization 是否能跨領域穩定關閉 frontier gap。
3. 是否存在獨立於 total compute、model scale 與 system resources 的 cross-domain specialization scaling law。
4. Evaluation realism 是否具有一致的 specialist/generalist ranking 方向；目前醫療與科學證據方向不同。
5. Specialist advantage 的 OOD、cross-task、cross-jurisdiction 與 longitudinal durability 分布。
6. PaperQA2、Aviary、FinTral 與 formal solvers 中 weights、retrieval、tools、environment、search、verifier 與 inference compute 的個別貢獻。
7. MMedIns、SaulLM 與其他 author-linked wins 在獨立、當代、跨 benchmark/workflow evaluation 中是否重現。
8. Proprietary comparators 的完整 training、post-training、prompt 與 inference metadata。
9. 「domain」是否是最適當的 capability partition；目前僅能要求 subtype 被明確記錄。

---

## 9. Unresolved questions

1. 在 model-level specialization 中，same-backbone relative gain 在什麼範圍內能轉化為 contemporary frontier superiority，而不是只縮小差距？
2. 當 specialist 與 generalist 的 model scale、資訊存取、tools、context、scaffold 與 inference budget 可比較時，現有 ranking 會保留多少？
3. Model-level、system-level 與 hybrid specialization 的優勢分別落在哪些 capability constructs，且哪些結果只在特定 benchmark 或 environment 中成立？
4. Benchmark proxy、broad domain capability 與 professional workflow capability 之間的 ranking 是否存在可重複的分化模式？
5. 已知 specialist wins 在 held-out task families、OOD distributions、不同制度／語言、獨立 replication 與後續 frontier generations 中能維持到何種程度？
6. Formal/verifier-bound 與 narrow task solvers 的成功，在哪些邊界內可被視為 specialization evidence，而不被誤解為一般 domain intelligence？
7. 現有局部 specialization curves 是單一研究設定中的收益與飽和，還是跨領域可重複的獨立 scaling effect？
8. Public benchmark contamination、temporal leakage、author-owned evaluation 與 proprietary metadata 缺失，對目前 specialist/generalist prevalence 判斷造成多大偏差？

這些問題描述目前的未知空間，不構成正式研究假說或實驗設計。

---

## 10. Falsification conditions

本文件的核心 empirical framing 應在下列證據出現時被推翻或重大修訂：

### F1 — Same-backbone gain 前提被反駁

若跨多個獨立領域與 model families 的可重建比較顯示，model-level specialization 相對 own base 並不具有 recurring positive target-task gain，或其零／負效果與正效果同樣普遍，則「relative gain 是穩定起點」必須撤回。

### F2 — Model-level transition gap 被反駁

若多個獨立領域出現 contemporary、unit-matched、resource-visible comparisons，並一致顯示 model-level specialists 在 broad domain 或 professional workflow capability 上經常超過最強 general-purpose comparators，且結果能被獨立重現，則「relative gains 較少轉化為 broad contemporary frontier superiority」必須撤回或大幅縮窄。

### F3 — Boundedness 判斷被反駁

若目前最強的 model/system/formal specialist wins 在獨立建立的 OOD task families、不同環境／制度、不同 evaluation constructs 與後續 frontier checkpoints 中持續保留，則「最強 wins 多半 bounded」的描述必須改為 broad/persistent advantage。

### F4 — System-level attribution 邊界被反駁

若 matched component evidence 顯示 PaperQA2、Aviary、FinTral 或類似系統的主要優勢可由 specialized weights alone 重現，且 retrieval、tools、environment、search、verifier 與 inference scaling 不再提供實質增益，則其 system/hybrid classification 必須改寫。

### F5 — Benchmark/workflow construct split 被反駁

若成對、獨立的 evaluation 持續顯示 benchmark proxy 與 professional workflow capability 測得相同能力構念、產生一致 ranking，且額外 workflow components 不改變判斷，則將兩者強制拆分的必要性應被重新評估。

### F6 — Frontier-drift framing 被反駁

若 specialist advantages 在後續 materially stronger frontier generations 出現後仍持續保持，或歷史 ranking 變動主要可由 benchmark invalidity，而非 comparator progression 解釋，則「frontier drift 是條件式時間 pattern」需要縮窄。

單一 benchmark win、單一 system-level counterexample 或 formal solver milestone，不足以單獨反駁 model-level transition-gap framing；反駁必須針對相同 unit、capability construct 與 superiority type。

---

## 11. 相對 `Problem Definition v0` 的主要修改

| 修改 | v0 的表述問題 | v1 的處理 |
|---|---|---|
| **核心現象由單一句改為分層 pattern** | `specialized systems` 同時包含 weights、RAG、agents、tools 與 formal solvers。 | 明確拆分 model-level、system-level、hybrid、formal/narrow solver。 |
| **保留 puzzle，但改成 transition gap** | 原 puzzle 暗示所有 specialization 都較少形成 superiority。 | 聚焦 model-level relative gain 到 broad contemporary/persistent superiority 的轉換缺口，並把 system/formal wins 作為另一個有界現象。 |
| **拆分三種 advantage** | relative improvement、absolute superiority、stable superiority 混用。 | 定義 same-backbone relative gain、contemporary frontier superiority、persistent superiority。 |
| **拆分三種 capability construct** | domain benchmark 與 domain expertise 接近同義。 | 分為 benchmark proxy、broad domain capability、professional workflow capability。 |
| **加入 time-indexed frontier rule** | `strong general-purpose comparator` 未要求 snapshot/date。 | 所有 frontier claim 必須含 exact version、evaluation date 與 temporal status。 |
| **加入 resource/system-boundary rule** | 工具、retrieval、context、inference compute 只被列為可能 confounder。 | 將 access、system configuration 與 inference resources 納入最低判讀欄位；未匹配時只支持 configuration-level outcome。 |
| **收窄 specialist advantage** | stable、generalizable、repeatable 未具體區分。 | 將 stability、generalization、repeatability、persistence 分開，缺證據時標為 Unknown。 |
| **Counterexample 必須指定精確命題** | 可靠反例被視為同一類。 | SaulLM、MMedIns、PaperQA2、Aviary、formal solvers 等各自只反駁其 unit 與 scope 內的命題。 |
| **降低 causal language** | v0 列出 coherence、resource concentration、domain structure 等可能理由，容易被誤讀為基礎假設。 | 保留為未裁決候選因素，不構成問題前提或 explanation。 |
| **明確 legacy boundary** | v0 未明示 Vanta 與新專案的權威關係。 | Vanta 僅為歷史經驗，不決定本問題、術語或系統方向。 |
| **新增 falsification conditions** | v0 有問題與 provisional definition，但缺少何種證據會迫使問題改寫。 | 對 same-backbone premise、transition gap、boundedness、system attribution、construct split 與 frontier drift 分別設定可反駁條件。 |

---

## 12. 最短表述

> **目前可支持的問題不是「specialization 是否有效」，而是：model-level specialization 為何經常改善自己的 base，卻較少被可靠證明能在 broad、resource-comparable、contemporary 且跨時間的條件下維持 frontier superiority；同時，system-level、hybrid 與 formal/narrow solvers 又為何能在明確有界的工作流或問題空間中形成強優勢。**

---

## 13. Evidence basis

本文件依據下列 current-project artifacts：

- `[PD0]` `Problem Definition v0.md`
- `[EB11]` `Evidence-Base-v1.1.xlsx`，尤其是 `Definitions`、`Specialization_Taxonomy`、`Claims`、`Counterexamples`、`Evidence_Gaps`
- `[EA-XLSX]` `Evidence-Adjudication-v1.xlsx`，尤其是 `Problem_Definition_Impact`、`Claim_Adjudication`、`Counterexample_Adjudication`、`Boundary_Conditions`、`Evidence_Gaps`
- `[EA-MD]` `Evidence-Adjudication-v1.md`
- `[CM1]` `Contradiction Map v1.md`
- `[DR2]` `DR 2 report.md`

若上述 current-project artifacts 後續更新，本文件應依新的 adjudicated evidence 修訂；歷史 Vanta 文件不得覆寫 current-project decisions。
