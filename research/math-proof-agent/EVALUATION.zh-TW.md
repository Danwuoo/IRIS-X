# 評估協定：答案、證明與成本分開記錄

日期：2026-10-18。這是下一輪實驗設計，不是已取得的模型結果。背景來源 [S01-S04,S09,S10] 見 sources.json。

## 1. 兩個軸，不用一個「答對」欄位

`answer_status = correct / incorrect / unknown / not_applicable`。

`proof_status = kernel_verified / certificate_checked / expert_audited / refuted / incomplete / unsupported`。

每個項目另記 statement-fidelity status 與 trust base。自然語言→Lean 命題需核對量詞、型別、定義域、假設、目標及 vacuity；不能只因一個不同定理獲得 proof term，就接受原題。初期命題轉換由固定、經人核對的 formal statement 提供，避免同一輪同時測翻譯和推理；另建形式化準確率子實驗。

主指標為完整原題證明率（分 trust level）及 answer-and-proof joint success。數值正確但證明 incomplete 不算 joint success。純證明題在 answer rate 中為 not_applicable，另有固定分母；不能先餵答案再宣稱找到了答案。

初期 formal panel 只把 kernel_verified 且 statement fidelity 合格視為嚴格成功；Python certificate_checked 另表，不與 kernel 指標合併。未形式化題目的 expert_audited 需外部盲評，模型自評不能填寫。找不到 proof 不等於題目為假；精確反例才支持反證對應命題。

## 2. 下一轮主要配對：獨立採樣 vs 檢查後修復

| Arm | 模型呼叫 | 用途 |
| --- | --- | --- |
| M-DIRECT | 1次、最多4,096 completion tokens | 低成本參考；不是與4次搜尋等算力 |
| M-SAMPLE | 最多4個獨立提案，每個最多4,096 tokens；用同一 verifier 選第一個合格候選 | 追加計算的強對照 |
| M-REPAIR | 1個初稿＋最多3次帶工具錯誤的修復，每次同樣最多4,096 tokens | H1 主研究變因 |

主比較只宣稱 M-REPAIR vs M-SAMPLE 的**相同資源上限**，不是假稱實際成本完全相等。两臂相同模型／tokenizer／prompt framing／retrieval policy／工具版本、輸出 cap、工具 cap 和預先固定 wall ceiling；prompt、critique、工具時間與編譯都計入。解出即停，無須空等。以 actual cumulative token／wall cost 曲線及固定預算截點比較；不得只比較 C 的四輪與 A 的一次呼叫後歸因於 feedback。

第一個資料面板提案為24題，按代數、數論、組合各8題，12題需找答案且證明、12題純證明；題目來源／難度／親緣關係／數值答案可見性須在模型輸出前記入 immutable manifest。這個面板**尚未選出、沒有對外 preregister**。如果既有合法 formal 題無法滿足配額，先改版並凍結協定，不在結果出現後換題。miniF2F 舊公開題只能作公開暴露回歸；Putnam stretch panel 等來源政策處理後另報，不用挑中的易題代表整庫。

主輪先1固定seed做機制pilot，再以另外2個事先登錄seed重複；相同題目seed不是獨立樣本，統計以題目／family為單位。報告 paired gain/loss、完整證明率差、分層結果与適當不確定區間；24題不作廣泛效能或顯著提升保證。要主張可推廣增益，另凍結未用 task/family confirmation panel。

## 3. 公平的回饋與最終驗收

工具回饋只可以讀題目、候選與允許庫；gold answer、reference proof、裁判 rubric 不進 proposer／refiner context。Compiler errors 和合法 search evidence 可用。LLM critique 中沒有外部驗證的推論標為建議，不能直接當成 reward。

每個候選保留 problem/formal-statement digest、模型版本、父候選、prompt/template版本、工具與retrieval快照、必要輸出及成本。最終評估在候選／方法選定後讀封存結果；不要以 oracle 選生成策略。Candidate-pool oracle 僅作 evaluator-only 瓶頸診斷，不供 agent 選答。

非形式證明的審查至少盲化方法與候選順序，有分歧時保留審查與裁定來源。沒有合適審查者就記 unknown，不讓 proposer 同時當唯一裁判。

## 4. 必須公開的失败分母

列出 planned / generated / tool_checked / proof_accepted / refuted / unsupported / timeout / invalid_format / context_exhausted / infrastructure_error。排除条件預先固定；超時與解析失敗不能從能力分母消失。工具不可用和「模型沒解出」分開報，但兩者都影響 end-to-end completion。

錯誤類型至少包含：錯題／量詞、漏假設、無效計算、錯誤引理、循環論證、案例不完備、Lean elaboration、axiom漏洞、錯誤選答、budget過高。成功也須檢查來源污染：同題改寫／解答、相同生成模板、前輪review、檢索索引或teacher資料都計為相關暴露。

## 5. 安全與信任

形式化worker把題目與固定庫唯讀掛載，只接受受控proof body；無網路／密鑰，限制時間、記憶體、程序數及輸出。這是工程要求而非本輪已做好的沙箱。`#print axioms` 類檢查要針對最終聲明與相依，不能以黑名單字串掃描代替。

SymPy／Python 工具優先使用結構化算式與精確數；對任意模型程式需獨立 sandbox。沒有實測工具覆蓋率前，不把工具的 unknown 解讀成錯誤。R001 自製checker不是一般Python沙箱，也未經形式化驗證。
