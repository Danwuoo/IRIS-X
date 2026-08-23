# Evidence Adjudication v1

## 1. Executive Adjudication Summary

本輪在不覆寫歷史版本的前提下，對 **24 筆既有 Evidence_ID** 做了實質更新，並新增 **10 筆** DR2 experiment-level records（E0056–E0065）。既有 claims 中有 **7 筆狀態改變**，另新增 C0021–C0022 以顯式處理 evaluation realism 與 frontier drift。

Counterexamples 的裁決為：**1 筆在精確命題層級獲得較強來源支持**（SaulLM）、**2 筆弱化**（FinTral、Aviary）、**4 筆重分類**（MMedIns、PaperQA2、AlphaProof/AlphaGeometry、Gemini Deep Think）、**2 筆無實質變化**，以及 **1 筆新增的 boundary/generalist-dominance record**（Nature Medicine 2026）。

共有 **8 筆 contradiction records 改變或明顯縮窄解讀**。原先四個最可能成為真正衝突的 K0007、K0009、K0010、K0013 中，**沒有任何一筆被證據完全解決**：前三者主要被重分類為單位、測量或時間問題；K0013 的獨立 replication 衝突仍然開放。

12 個既有 gaps 中，**0 個完全解決、2 個部分解決、3 個縮窄、5 個仍開放、2 個重要性上升**。

## 2. What DR2 Actually Changed

DR2 的主要貢獻不是增加更多「成功案例」，而是重新界定哪些結果可以支持哪一種命題：

- MMedIns 的核心結果保留，但降為 **same-program、benchmark-local、partially matched**。
- Nature Medicine 2026 使原本來源不清的 clinical-tools result 變成當代、獨立、同題比較的核心 generalist-dominance evidence，並加入真實醫師查詢階段 E0056。
- SaulLM 的 LegalBench-Instruct 結果獲得直接數字支持，但 DR1 的 exact GPT-4 date 無法由 DR2 一手資料成立，已改回 Unknown。
- FinTral 不再支持乾淨 model-level finance superiority；它是包含 tools、retrieval、multimodality 的 hybrid/system result。
- SWE-RL 保留 same-backbone gain，但 frontier claim 改成 historical near-parity；SWE-bench Verified 的 contamination 使當代 ranking 解讀失效。
- PaperQA2、Aviary 與 AlphaProof/AlphaGeometry 分別落入 scientific workflow system、bounded environment system、formal/verifier-bound solver。
- 新增 FinRetrieval、法律/金融 specialization-scaling、AlphaGeometry data/search ablations、較廣法律評估與 GPT-5.2 coding context。

## 3. Verification Outcomes

### Confirmed

- Nature Medicine 2026 的 benchmark 與 real clinical query 排名。
- SWE-RL 的 41.0% same-backbone result，以及後續 frontier scores 與 contamination warning。
- PaperQA2、Aviary 與 formal solver 的主要 system components 和邊界。

### Confirmed with qualification

- MMedIns：強 benchmark-local win；缺 comparator snapshots、外部 replication 與跨 benchmark durability。
- SaulLM：可信 legal benchmark counterexample；缺 exact GPT-4 snapshot 與 broad workflow replication。
- PaperQA2/Aviary：強 system outcomes；缺 matched-budget component attribution。

### Reclassified

- SWE-RL frontier claim → historical near-parity。
- AlphaProof/AlphaGeometry → formal/verifier-bound solver。
- Gemini Deep Think → frontier-drift context，而非 specialist counterexample。
- Look-Ahead-Bench → temporal-validity evidence。

### Weakened

- FinTral 的 model-level / frontier 解讀被弱化；原始 task-family result 仍保留。

### Unsupported or unidentified

- E0037 的 broad biology frontier claim 仍無法可靠對應 exact primary source，不應支持 substantive claim。

## 4. Claim-Level Adjudication

### Same-backbone benefit

**Supported（High confidence）。** MMedIns、SaulLM、SWE-RL，加上 E0059–E0060 的局部 scaling evidence，持續支持 specialization 通常能改善 adapted base。這仍不等於 contemporary frontier superiority。

### Model-level frontier superiority

**Partially/conditionally supported at most。** SaulLM 是最可信的 benchmark-level model counterexample；MMedIns 仍受 author-program benchmark 與 replication 限制。現有證據不足以支持 broad、persistent model-level frontier superiority。

### System-level frontier superiority

**Conditionally supported。** PaperQA2、Aviary 與 formal solvers 證明 bounded specialized capability systems 可以在特定 workflow/environment 中取得強結果，但 system resources 必須保持可見。

### Generalization and durability

**Partially supported as a limitation。** 最強 specialist wins 多半受 task distribution、environment、retrieval/access、verifier 或 benchmark ownership 限定。這不等於已估計出普遍的 durability failure rate。

### Evaluation realism

**Indeterminate。** Realism 會使 retrieval、tools、workflow 與 verifier 更重要，但 Nature Medicine 與 scientific system evidence 的 ranking 方向不同，不能推成「越真實越有利 specialist」。

### Specialization scaling

**Unsupported as an independent scaling law。** E0059–E0062 支持局部 size interaction、early gains、diminishing returns 與 saturation；它們不足以建立跨 domain、獨立於 total compute 的 scaling axis。

### Frontier drift

**Conditionally supported as a temporal pattern。** SWE-RL 與 formal mathematics 顯示 specialist milestones 可被後續 frontier systems 超越；必須把 capability decay 與 moving frontier 分開。

## 5. Counterexample Reassessment

- **SaulLM** 現在反駁：「frontier generalists 在所有 legal benchmarks 都必勝。」它不反駁：「frontier generalists 可能在更廣 legal workflows 或後續世代反超。」
- **MMedIns** 現在反駁：「medical specialists 不可能在 author-built multi-task clinical benchmark 擊敗 frontier comparators。」它不證明 broad、independent medical frontier superiority。
- **FinTral** 只反駁：「compact finance capability systems 不可能在 author suite 的部分任務超過 generalists。」它不隔離 model-level specialization。
- **PaperQA2** 反駁：「general-purpose systems 或 experts 必然支配 scientific literature workflows。」它不支持 specialized weights alone。
- **Aviary** 反駁：「較弱 backbone 在 specialized environments 中無法達到 frontier performance。」它不支持 environment-external scientific capability。
- **AlphaProof / AlphaGeometry** 反駁：「general systems 在 formalized exact-verifier domains 自然佔優。」它不構成 matched chat-model comparison。
- **Nature Medicine 2026** 是 specialist-dominance 命題的 counterexample／generalist-dominance example，也同時是 interface/access validity boundary；它不證明所有 medical specialization 無效。

## 6. Contradiction Map Delta

- **K0007 medicine**：由可能直接衝突縮窄為不同單位與 evaluation construct；仍需 MMedIns 的獨立當代 replication。
- **K0009 finance**：FinTral 弱化、FinRetrieval/Look-Ahead-Bench 加入後，主要成為 resource-access 與 temporal-validity measurement issue。
- **K0010 coding**：SWE-RL same-backbone result 保留，frontier 衝突重分類為 temporal drift 加 compromised benchmark。
- **K0013 replication**：仍 unresolved；primary verification 只使命題更精確，沒有替代 independent replication。

沒有任何 contradiction 因為「有合理解釋」就被標成 empirical resolution。

## 7. Boundary Conditions After DR2

最強的 boundary conditions 為：

- **Strong boundary conditions**：model/system/formal unit split、time-indexed frontier、author-built benchmark、finance temporal control、public benchmark contamination、formalizable exact-verifier tasks。
- **Experimentally supported moderator**：matched information access（FinRetrieval）。
- **Suggestive moderators**：task-distribution width、inference/search budget、specialization intensity 與 diminishing returns。
- **Descriptive only / indeterminate**：workflow realism 的 ranking 方向、closed-browser interface penalty、OOD durability frequency。

目前沒有足夠證據把任何跨案例 boundary condition 升級為普遍 causal law。

## 8. Remaining Evidence Gaps

### Problem-definition blockers

- contemporary matched model-level comparisons；
- matched tools/access and explicit comparator metadata；
- benchmark proxy versus workflow construct；
- OOD durability and independent replication；
- remaining primary-source extraction。

### Hypothesis-formation blockers

- controlled specialization scaling across domains；
- full model-versus-system component ablations。

### Experiment-design gaps

- matched inference/search budgets；
- fresh/private/post-cutoff coding evaluation；
- point-in-time finance evaluation。

最高優先項目仍包括：MMedIns independent contemporary replication、SaulLM broader legal-workflow replication、PaperQA2/Aviary matched-budget ablations、fresh coding tasks、matched specialization-intensity curves、clean contemporary model-level comparisons 與 OOD durability。

## 9. Problem Definition Impact

### Stable

- specialization 常能改善 own base；
- leaderboard dominance 不能證明 general-purpose learning 的內在優越；
- prevalence 仍需分層驗證。

### Must be split

- model-level、system-level、hybrid、formal/verifier-bound solver；
- same-backbone relative gain、contemporary absolute superiority、persistent superiority；
- benchmark proxy、broad domain capability、professional workflow capability。

### Terminology and comparator rules

- 每一個 frontier-superiority claim 必須包含 model snapshot、evaluation date 與 persistence status。
- 「generalizable」必須分別標記 held-out task、OOD、temporal shift 與 independent replication；目前不設定無證據支持的門檻。

### Still unresolved

- 是否存在跨 domain 的 independent specialization scaling law；
- high-resource model-level specialization 是否能穩定關閉 contemporary frontier gap；
- strongest counterexamples 是否能獨立 replication 並跨時間持續。

## 10. Readiness Assessment

| 下一階段 | 判定 | 原因 |
|---|---|---|
| Problem Definition v1 | **Ready with conditions** | 結構性修訂方向已足夠清楚；需依 PDI0001–PDI0014 明確拆分 unit、advantage、capability 與 temporal/generalization rules。 |
| Formal Research Questions | **Ready with conditions** | 可以依 model/system/formal、matched resources、durability 與 scaling 分題；不得把 unresolved gaps 當前提。 |
| Competing Hypothesis Formation | **Ready with conditions** | 可以形成相互競爭的機制假說，但必須保留 G0004、G0007 等 blocker。 |
| Experiment Design | **Not ready** | 尚未確定 matched comparator、private coding tasks、point-in-time finance data、inference budget 與 generalization thresholds。 |

本任務停在 Evidence Adjudication，不自動改寫 Problem Definition v0，也不選擇 winning hypothesis。
