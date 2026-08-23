# Project Evaluation Definition v0

**版本：** v0.1
**狀態：** Draft for project-level evaluation architecture
**日期：** 2026-08-05
**上位文件：** `Problem Definition v1`
**證據依據：** `Evidence Base v1.1`、`Evidence Adjudication v1`
**文件角色：** 將 Problem Definition v1 的 empirical propositions 操作化為跨 domain 共用的 evaluation、comparison、aggregation 與 claim-decision rules。

---

## 1. Document status and role

本文件位於下列繼承鏈；下位文件可增加 domain-specific 要求，但不得放寬本文件的共同約束：

```text
Problem Definition v1
        ↓
Project Evaluation Definition v0
        ↓
Domain Evaluation Definitions
        ↓
Experiment preregistrations
        ↓
Run manifests / reports / decision records
```

本文件不是 `ARC Evaluation Definition v0` 的擴張，也不選擇 domain、benchmark、winning hypothesis、mechanism、roadmap、compute tier 或未有證據支持的數值門檻。它定義什麼必須測量、哪些比較有 claim eligibility、缺失資料如何降級，以及何種證據會支持、限制或迫使 `Problem Definition v1` 改寫。

建立本文件本身不改變 empirical adjudication、ARC stage 或 winning hypothesis；global experiment-design readiness 維持 `Not ready`。

## 2. Authority and inheritance

| 問題 | 控制來源 | 本文件的處理 |
|---|---|---|
| 研究問題、scope、術語、F1–F6 | `Problem Definition v1` | 直接操作化，不改寫實質內容 |
| claim、counterexample、boundary、gap、decision status | `Evidence Adjudication v1` workbook；Markdown 為摘要 | 保留 current status 與 uncertainty |
| record IDs、provenance、benchmark metadata | `Evidence Base v1.1` | 僅在 record-level 判讀時查詢 |
| domain metrics、資料治理、stage gate、實際 threshold | 各 Domain Evaluation Definition | 必須遵守本文件，且不得反向改寫上位命題 |
| ARC implementation precedent | `ARC Evaluation Definition v0` | 只作 domain-specific precedent；ARC-only 規則不得升格為跨 domain 規則 |

來源衝突時，按上述職責與 `PROJECT-STATE.md` 的 authority rules 處理並顯式記錄；不得用 archive、外部記憶或推測填補 `Unknown`、`TBD`、`Indeterminate`。

## 3. Evaluands and empirical propositions

每個 evaluation record 必須先指定 target distribution、evaluation unit、advantage type、capability construct、comparator/time/resource boundary 與 generalization status。核心 evaluation families 為：

| Family | 被操作化的 proposition | 最低設計與分開報告 | 最窄可支持結果 |
|---|---|---|---|
| Same-backbone gain | model-level specialization 是否 recurring 地改善 own base | 同一或緊密對應 backbone、paired tasks、相同 evaluator 與 system/inference boundary；揭露 specialization data/compute | 該 `M` intervention 相對 own base 的 target-task gain |
| Transition gap | relative gain 是否轉化為 contemporary frontier superiority | 對同一介入分開判定 intervention、paired gain、contemporary frontier win；frontier comparator 必須 time-indexed | 在指定時間、construct 與 boundary 下的轉換結果 |
| Construct gap | benchmark-local win 是否延伸至 broad domain 或 professional workflow | 各 construct 使用各自 target distribution、metric 與 validity evidence，不以名稱或 task count 替代 | 被實際測量 construct 內的結果 |
| Unit and boundary divergence | `M` 與 `S/H/N` 的優勢來源是否不同 | unit 對稱比較；full system 對 bare model 只支持 configuration-level；component claim 需 matched boundary 或 ablation | 指定 unit／configuration／component 的 outcome |
| Generalization and durability | 優勢是否跨 task、distribution、time、version、evaluation 與 run 保留 | held-out、OOD、temporal、cross-version、replication、stability、persistence 分欄裁決 | 已直接測得的 generalization/durability 類型 |
| Cross-domain prevalence and scaling | 上述 pattern 的 prevalence 或 scaling 是否跨 domain 成立 | 預先定義 sampling frame、完整 denominator、resource normalization、分層 aggregation 與 missingness | 合格樣本範圍內的分層估計；現階段 scaling law 為 `Unsupported`，設計細節為 `TBD` |

精選成功案例、leaderboard leaders 或已發表正結果不得用來估計普遍頻率。

## 4. Evaluation-unit rules

| Code | Evaluation unit | 操作定義 | Attribution boundary |
|---|---|---|---|
| `G` | generalist baseline | 未針對 target distribution 做同等專門化的 model 或 capability-system configuration | 必須與 specialist 使用對稱 model/system boundary；`G` 不等於 bare model |
| `M` | model specialist | 主要介入在 weights：continued pretraining、finetuning、instruction/preference tuning、LoRA、RL 等 | 只有 system boundary 匹配時，差異才可歸因於 model-level intervention |
| `S` | system specialist | weights 固定；介入在 prompt、retrieval、tools、search、memory、routing、verifier、context、scaffold 或 environment | 只支持完整 system 或已隔離 component 的結果 |
| `H` | hybrid specialist | weights 與 system stack 同時專門化，且貢獻未乾淨拆分 | 只支持 configuration-level outcome，除非有 matched ablation |
| `N` | narrow／formal／verifier-bound solver | 固定格式、DSL、handcrafted primitives、exact verifier 或 bounded search/problem space；須記 subtype | 只支持明確 formalized／bounded task space |

每個 run 與 claim 指定一個 primary unit。不同 unit 不得合併計數、平均或形成單一 specialist/generalist 結論。工具、retrieval、search、memory、verifier、context、scaffold 與 environment 的效果不得歸因於 specialized weights。

## 5. Advantage-type eligibility

| Advantage type | Eligible comparison 與最低 evidence | 不可推出 |
|---|---|---|
| same-backbone relative gain | specialized variant 對 own base；paired evaluation；backbone family、evaluator、prompt/system、information access 與 inference policy 匹配；training intervention 完整揭露 | contemporary superiority、persistence、broad capability、compute efficiency |
| contemporary absolute superiority | 在 evaluation date 相對當時最強且相關的 general-purpose comparator；unit、construct、evaluator、exposure 與 system boundary 可比；resource parity 可判讀 | 後續世代 superiority、component causality、persistent superiority |
| persistent superiority | 已合格的 superiority 在後續具有實質 frontier 更新或時間位移的 checkpoint，仍相對當時 comparator 保留；各 checkpoint 都滿足 comparator validity | stability、OOD 或 universal durability |
| configuration-level superiority | exact specialist configuration 對 exact comparator configuration；允許 system boundary 不完全對稱，但所有差異與資源必須可見 | weights-alone 或單一 component attribution |
| cost／efficiency advantage | 同一 construct/evaluator 下比較 matched quality 或 matched budget；完整記錄 cost、tokens、calls、rollouts、search、wall-clock、hardware 與 uncertainty | 絕對 superiority、較少 training compute、跨硬體或跨價格時點的無條件效率 |

一種 advantage 成立不使其他種類自動成立。若比較只超過 named snapshot，表述必須是 time-indexed historical 或 contemporary claim，而不是無時間限定的 superiority。

## 6. Capability-construct rules

| Construct | 最低涵義與 evidence | Prohibited extrapolation |
|---|---|---|
| benchmark proxy | 指定 dataset、task family、metric、evaluator version 與 exposure status 的測量結果 | 不得由高分直接推出 broad domain 或 professional workflow capability |
| broad domain capability | 橫跨實質不同 task families、distributions 或 evaluation contexts；breadth 與 aggregation rule 預先定義 | 同一作者 suite、同一生成程序內的多任務數量不得單獨充當 breadth |
| professional workflow capability | 接近實際程序的 retrieval、evidence integration、tool use、procedure、generation、verification 或 execution；以 workflow outcome、程序正確性或具外部效度 rubric 評估 | 文字 benchmark 排名不得替代 workflow outcome |
| formalized／bounded task capability | 對明確 formal language、exact verifier、固定 interface 或 bounded environment 的能力 | 不得推出 open-ended workflow、broad domain、chat-model 或一般 capability |

不同 construct 的 ranking 不構成直接 contradiction。跨 construct claim 只有在 paired construct-validity design 中才有 eligibility，且仍須分開報告原始結果。

## 7. Comparator, time and resource eligibility

任何 superiority、frontier、SOTA、efficiency 或 generalization claim 必須具備下列 claim card；domain 文件可增加欄位，不得刪除：

| 類別 | Required fields |
|---|---|
| Identity | evaluation unit；exact specialist configuration；exact comparator configuration；model/system snapshot；evaluation date |
| Measurement | benchmark、workflow 或 evaluator version；capability construct；domain subtype；target distribution；primary metric |
| Model/training | base family、scale、training/specialization data、training compute、post-training stages |
| Information/system | information access；tools、retrieval、context、memory、verifier、scaffold、environment；human intervention |
| Inference/resources | token、call、rollout、attempt、retry、search width/depth、wall-clock、hardware、cost；resource parity |
| Validity | public、sealed、semi-private 或 private status；contamination/exposure status；data/rule snapshot |
| External validity | generalization、independent replication、stability 與 persistence status |
| Decision boundary | 最窄可支持的 proposition；prohibited extrapolation；known deviations |

`frontier`／`SOTA` 必須同時指明 comparator set、snapshot、evaluation date 與 leaderboard/evaluator status。若「當時最強且相關」的 comparator 無法確認，結果不得升格為 contemporary frontier claim。未匹配 resources 仍可支持 configuration-level outcome，但不得隔離 specialization mechanism 或 algorithmic efficiency。

## 8. Generalization, replication and persistence

| Status dimension | 最低分類規則 |
|---|---|
| held-out task | task 在 preregistered selection、training、prompt/tool tuning 與 error-driven iteration 之外，且 split/firewall 可稽核 |
| out-of-distribution | 預先陳述與 development distribution 實質不同的 task family、制度、語言、環境或資料生成機制；不得只以同 benchmark 內 task count 宣稱 |
| temporal shift | point-in-time cutoff 後或明確 later-period evaluation；資料、retrieval 與 comparator 均遵守相應時間邊界 |
| cross-version transfer | frozen configuration 或只做預先允許的 interface port，在新 model/system/benchmark version 重測；adapted result 必須另列 |
| independent replication | 非原 author-linked team／evaluation 對預先陳述的主要結果進行重現或外部驗證，並可核對 protocol 與 configuration |
| stability | 同一 time index 下，在至少一個實質不同 condition、protocol、metric 或獨立 evaluation 中維持同方向；否則標記 `single-setting` |
| persistence | 在後續 materially stronger frontier generation 或實質時間位移下，仍對當時 comparator 保持已定義 superiority |

`Not evaluated` 表示沒有執行對應測試；`Unknown` 表示必要資訊或結果不可得；`Indeterminate` 表示已有 evidence 但互相衝突、精度不足或不能識別方向。三者都不是成功或失敗。`TBD` 只用於尚未決定的 design choice。

## 9. Cross-domain sampling and aggregation

未來 prevalence 的 sampling unit 至少包含 `(domain subtype, target distribution, unit, intervention, comparator snapshot, evaluation date, construct)`。sampling frame、inclusion/exclusion、study selection、missingness 與所有正／零／負結果必須預先記錄；author-linked case collection 或 leaderboard top-k 不是 prevalence sample。

三個 denominator 必須分開：

- **Intervention prevalence：** 發生合格 specialization intervention 的 sampled opportunities／全部 eligible sampled opportunities。
- **Gain prevalence：** 產生預先定義 positive paired effect 的合格 same-backbone comparisons／全部合格 same-backbone comparisons。
- **Frontier-win prevalence：** 產生合格 contemporary frontier win 的 comparisons／全部合格 contemporary frontier comparisons。

缺失、`not interpretable` 與不合格比較須作 attrition 分層報告，不得默認為 win、loss 或靜默排除。Aggregation 必須按 `G/M/S/H/N`、advantage type、construct、domain subtype、resource parity、exposure、time 與 replication status 分層；heterogeneous evidence 不得以單一平均消除。只有 estimand、metric direction、resource boundary 與 sampling 權重可比較時，才可進行統合估計，並報告 uncertainty 與 sensitivity analysis。

Cross-domain specialization scaling 另需：預先取樣的獨立 domains/model families、可比較的 specialization-intensity 軸、total training/inference resources normalization、重複觀測、held-out validation 與預先指定 aggregation model。局部 curve、size interaction、diminishing returns 或 saturation 不足以建立獨立 scaling law。現階段 project claim 維持 `Unsupported`；sampling frame、normalization 與 scaling estimand 為 `TBD`。

## 10. Claim taxonomy and evidence downgrades

| Decision status | Operational use |
|---|---|
| `Supported` | 合格 evidence 直接支持最窄 proposition，且無未處理的 decisive conflict |
| `Conditionally supported` | 結果在明確 unit、construct、time、resource 或 boundary 條件內成立 |
| `Partially supported` | proposition 只有部分範圍或部分 evidence dimensions 成立 |
| `Contradicted`／`Refuted` | 合格 evidence 反駁已精確界定的 proposition；須列明不受反駁的命題 |
| `Unsupported` | 現有 evidence 不足以支持該 claim；不得改寫為負面結果 |
| `Indeterminate` | evidence 存在但衝突、不精確或不可識別 |
| `Needs split` | claim 混合 unit、advantage type、construct 或 boundary，必須拆分後重判 |

可疊加的 downgrade labels：`historical`、`partially matched`、`configuration-level`、`single-setting`、`author-linked`、`public-exposed`、`not independently replicated`、`not interpretable`、`Unknown`、`Not evaluated`、`Indeterminate`、`Source does not support`。缺 exact configuration、snapshot/date、evaluator、construct 或關鍵 resource/exposure metadata 時，不得自行補值；若已無法判定比較對象或測量內容，標記 `not interpretable`。

## 11. Falsification mapping

| ID | 被測 proposition | 最低合格 evidence pattern | 支持目前 framing 的結果 | 迫使問題改寫的結果 | 未能裁決 | 不允許的外推 |
|---|---|---|---|---|---|---|
| F1 | same-backbone gain 是 recurring 起點 | 多個獨立 domains 與 model families 的可重建、paired、boundary-matched `M` comparisons | 正向 target-task gain recurring，並保留 null/negative cases | 零／負效果與正效果同樣普遍，或不呈 recurring positive gain | `Indeterminate`／`Not evaluated` | 單一 gain 不證明 frontier、broad 或 efficiency |
| F2 | model-level relative gain 較少轉化為 broad contemporary frontier superiority | 多個獨立 domains；contemporary、unit-matched、resource-visible；broad/workflow construct；independent replication | relative gains recurring，但 qualified frontier wins 不常見或不穩定 | `M` specialists 經常、一致、可獨立重現地超過最強 contemporary `G` | sampling 不足時維持 `Unknown` | 不得以 `S/H/N` wins 或精選案例估計 model-level prevalence |
| F3 | strongest wins 多半 bounded | 獨立建立的 OOD task families、不同環境／制度、不同 constructs 與後續 frontier checkpoints | 優勢在已測邊界外不保留，且 failure 可判讀 | 現有 strongest `M/S/H/N` wins 跨上述 checkpoints 持續保留 | evidence sparse/conflicted 時 `Indeterminate` | 不得把一個 bounded failure 推成普遍 durability failure rate |
| F4 | PaperQA2、Aviary、FinTral 或類似 system/hybrid wins 不可歸因於 weights alone | fixed/matched boundary 的 weights、retrieval、tools、environment、search、verifier、inference ablation | system components 提供實質且可重建增益 | specialized weights alone 重現主要優勢，且列舉 system components 不再提供實質增益 | 缺 ablation 時 `Unknown` | full system 對 bare model 不支持 weights causality |
| F5 | benchmark proxy 與 professional workflow construct 必須拆分 | 同 system 的 paired、independent benchmark/workflow evaluations，且 workflow components 可檢驗 | ranking、error pattern 或 outcome 對 construct 敏感 | 兩類 evaluation 持續測得相同 construct、ranking 一致，且 workflow components 不改變判斷 | construct validity 不足時 `Indeterminate` | 單一 domain 的一致或分歧不構成 universal law |
| F6 | frontier drift 是條件式 temporal pattern | 同 specialist milestone 在有效 benchmark 上，對 materially stronger later comparators 重測；分開 benchmark validity | later comparator 超越歷史 milestone，而非宣稱 specialist capability decay | specialist advantage 持續保留，或 ranking 變動主要由 benchmark invalidity 而非 comparator progression 解釋 | comparator/validity metadata 缺失時 `Unknown` | 不得推出所有 advantage 短暫或 specialist capability 必然衰退 |

F1–F6 的結果只裁決其精確 proposition；單一 benchmark win、單一 system counterexample 或 formal solver milestone 不足以反駁 model-level transition-gap framing。

## 12. Domain Evaluation Definition inheritance contract

每份 Domain Evaluation Definition 至少必須提供：

| Required element | Domain-level obligation |
|---|---|
| Scope | domain subtype、target distribution、out-of-scope boundary |
| Constructs | domain-specific benchmark、broad、workflow、formal/bounded constructs 與其 validity argument |
| Units | eligible `G/M/S/H/N` configurations、subtypes 與 attribution boundary |
| Comparator | comparator-selection rule、own-base pairing、contemporary/frontier rule |
| Time/resources | temporal rule、model/training/information/system/inference resource-parity rule |
| Data governance | dataset tiers、public/sealed/semi-private/private、exposure、contamination、firewall 與 point-in-time controls |
| Measurement | domain-specific metrics、uncertainty、failure analysis；實際 benchmark 與 threshold |
| External validity | held-out、OOD、temporal、cross-version、replication、stability、persistence checkpoints |
| Execution | run-manifest extensions、preregistration requirements、deviation handling、reproducibility package |
| Claims | allowed/prohibited claims、downgrade path、decision record、reversible-if condition |
| Open items | unresolved decisions、`TBD`、unavailable sources 與 v1/domain acceptance criteria |

Project-level 文件只提供共同約束，不替 domain 文件決定 benchmark、threshold、compute tier、metric 或 stage gate。Domain-specific exception 若與上位規則衝突，必須停止該 claim、記錄 conflict，並先修訂上位文件或縮窄 claim。

## 13. Required preregistration and result fields

Preregistration 至少記錄：被測 proposition/F-ID、domain/target distribution、construct、primary unit、exact configurations、comparator selection/date、dataset/evaluator snapshot、exposure/firewall、resource budgets、primary/secondary metrics、sampling unit 與 exclusions、paired/ablation/replication design、analysis 與 missingness rule、generalization/persistence checkpoints、allowed/prohibited claims、decision rule 與 deviations policy。

Run manifest/result 至少記錄：run/config IDs、model/weights/prompt/policy/tool/data/evaluator versions 或 hashes、training/information/system/inference resources、hardware/cost、outputs、failures、seeds、deviations、contamination status、effect 與 uncertainty、resource parity、七項 generalization/durability status、最窄 supported proposition、downgrade labels、decision status、claim prohibited 與 reversible-if。無 machine-readable manifest 或逐項結果時，不得支持 attribution、efficiency、frontier、SOTA 或 generalization claim。

## 14. Unresolved decisions and v1 acceptance criteria

### 14.1 Unresolved decisions

- cross-domain sampling frame、domain weighting、missingness sensitivity 與 prevalence estimand：`TBD`；
- 「strongest relevant general-purpose comparator」的 domain-specific selection procedure：`TBD`；
- resource-parity encoding 與可跨 domain 比較的 cost normalization：`TBD`；
- independent replication governance、persistence checkpoint cadence 與 global generalization threshold：`TBD`；
- project owner／decision authority 與 state maintainer：`TBD`；
- global experiment-design readiness：`Not ready`。

### 14.2 v1 acceptance criteria

本文件可升級為 v1，須至少：

1. current Problem Definition／Adjudication 的後續變更已完成 traceable alignment；
2. inheritance contract 已由具實質不同 constructs 的 domain definitions 實際使用並通過 conflict audit；
3. claim card、preregistration、run manifest 與 decision schema 已在正式 evaluation artifact 中驗證；
4. prevalence sampling、resource normalization、missingness 與 aggregation procedures 已具可執行定義；
5. F1–F6 mapping、downgrade labels 與 prohibited extrapolations 已通過跨文件 consistency review；
6. 所有未決門檻有 evidence-backed domain rule，或繼續明確保留 `TBD` 而不阻礙其餘架構。

升級本規格不自動使任何 domain experiment ready；readiness 必須由相應 authoritative artifacts 另行裁決。

## 15. Short operational statement

> 每個 specialization 結果先按 `G/M/S/H/N`、advantage type、capability construct、time、resources、exposure 與 generalization boundary 分類，再只對合格 comparator 支持最窄 proposition。缺失資訊即顯式降級；跨 domain prevalence 或 scaling 只有在預先取樣、resource-normalized、分層 aggregation 後才可裁決，現階段不得宣稱 cross-domain scaling law。
