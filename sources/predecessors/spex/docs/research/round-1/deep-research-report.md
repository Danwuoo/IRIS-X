# 領域專門化與通用前沿系統之間的實證版圖

## 執行摘要與概念稽核

**Executive Evidence Summary。** 依截至 2026 年 7 月 24 日可取得的主要證據看，最初現象不是「普遍成立」，也不是「明顯錯誤」；較準確的結論是：**它在多個重要領域中有相當程度的支持，但高度依賴領域、任務型態、比較是否同代、以及把「模型級專門化」與「系統級專門化」分開看待**。更具體地說，醫療、金融、軟體工程這三個領域最能支持「專門模型通常能超越自己的通用基底，但較少穩定超越當代最強通用前沿系統」；法律則呈現混合圖景，既有 GPT-4 類通用模型長期領先的證據，也有 SaulLM 這類真正擊敗強通用比較器的專門模型；科學領域最不適合被單一句子概括，因為一旦把比較單位從「裸模型」換成「具工具、檢索、規劃、驗證的專門系統」，反例會顯著增加，例如 PaperQA2、Aviary，以及形式化數學中的 AlphaProof/AlphaGeometry 2。整體置信度可分三層：**高置信**的是「同 backbone 下的專門化通常有助於提升自己的域內表現」；**中等置信**的是「這種提升往往不足以穩定擊敗同時代最強通用前沿系統」；**較低到中等置信**的是「這個現象可被視為普遍規律」，因為最強反例恰好集中在真實工作流、工具使用、或正式化搜索明顯重要的任務。citeturn0academia13turn1academia37turn21view1turn14academia1turn4academia14turn17academia16turn19view3turn20academia0turn5academia12turn27view0turn9search0turn23view0turn24view0turn10search0turn10search2

**最重要的保留條件。** 現有文獻中，許多「specialist vs generalist」比較其實不是乾淨的專門化比較，而是同時混入了世代差距、參數規模差距、對 proprietary post-training 的未知、工具與檢索權限不對稱、test-time compute 不對稱、以及 benchmark 分布接近作者訓練資料的問題。另一方面，很多被稱為「domain benchmark」的評測，其實較像是**一般推理 + 領域詞彙 + 少量程序知識**的混合代理指標，而不是真正的專家工作能力。這一點在醫療的 MedS-Bench / HealthBench、法律的 LegalBench / LegalBench-RAG、金融的 FinanceBench / Look-Ahead-Bench、以及科學的 LAB-Bench / LitQA2 文獻裡都被明確或隱含指出。citeturn21view1turn15academia20turn28view2turn5academia12turn6academia0turn12academia15turn23view0

**Definition and Classification Audit。** 文獻中的 **domain** 至少有三種用法：第一，指**語料與知識領域**，例如 biomedical text、legal text、financial text；第二，指**制度／語言／司法轄區子域**，例如 Brazilian legal decisions、Taiwanese law、Chinese labor law；第三，指**工作流或工具環境**，例如 repo-level software engineering、scientific literature search、bioinformatics analysis、point-in-time finance workflow。這三種用法若不分開，會讓「專門化是否有效」的問題在一開始就失焦。citeturn21view1turn17academia17turn3academia3turn7search2turn23view0turn26academia1turn6academia0

**specialist** 也至少有三種用法：第一是**模型級專門化**，例如 continued pretraining、instruction tuning、domain RL、classifier fine-tuning；第二是**系統級專門化**，例如 RAG、資料庫、工具、search、verifier、formalizer、agent scaffold；第三是**極窄任務解算器**，例如法律分類 LoRA、合約理解 BERT、形式化數學證明系統。這些機制在資源需求、泛化目標、可比較性上完全不同，把它們都放進同一個「specialist」桶裡會嚴重高估或低估專門化的價值。相對地，**generalist** 在多數論文裡通常指廣泛預訓練、面向多任務的前沿 foundation/chat model，但在 coding 或 science agent 文獻中，有時又只表示「未加領域工具的裸模型」。**domain capability** 則常被混用成 benchmark score、專家偏好、流程正確率、真實工作流完成率，這四者不應視為同義。citeturn0academia13turn11academia0turn3academia0turn3academia2turn17academia14turn16academia0turn23view0turn24view0turn10search0

**建議後續研究必須保留的區分。** 後續若要把問題定義收斂，至少要保留四組區分：**模型級專門化 vs 系統級專門化**、**同 backbone 提升 vs 擊敗當代前沿比較器**、**benchmark 表現 vs 真實專家工作能力**、**同代比較 vs 跨世代比較**。不保留這些區分，文獻中的正反例會互相抵銷，無法形成可測的研究命題。citeturn19view3turn21view1turn15academia20turn28view2turn24view0

## 逐領域證據地圖

**Medicine / Healthcare。** 醫療領域最清楚支持兩件事。第一，**專門化通常能顯著提升自己的基底**：例如 MEDITRON-70B 以 Llama-2 為基礎做醫療 continued pretraining，在四個主要醫療 benchmark 上相對同級公開 baseline 有明顯提升，且比作者對 Llama-2 的強化 baseline 高約 3 個百分點；BioMistral、PMC-LLaMA 也都把醫療語料與醫療指令調教轉化成對開源基底的穩定增益。第二，**這種增益經常仍不足以穩定壓過最強通用前沿系統**：MEDITRON-70B 雖勝過 GPT-3.5 與 Med-PaLM，但自述仍落後 GPT-4 約 5 個百分點、落後 Med-PaLM 2 約 10 個百分點。這使醫療成為最支持原始現象的領域之一。citeturn0academia13turn0academia12turn11academia0

但醫療也有兩個不能忽視的反向證據。其一，**Med-PaLM 2 本身就是「在前沿 backbone 上做醫療專門化」後拿到強結果的案例**：它把 PaLM 2 的基礎能力、醫療 finetuning、ensemble refinement 與 chain-of-retrieval 結合，在 MedQA、MedMCQA、PubMedQA、MMLU clinical topics 上報告接近或超過當時 SOTA 的成績，且在 1,066 個 consumer medical questions 的長答人工評比中，醫師在 9 個臨床效用維度裡有 8 個更偏好 Med-PaLM 2 的答案。其二，**MedS-Bench 的 MMedIns-Llama 3** 在作者的 11 類臨床任務 benchmark 中，報告稱可在近乎所有任務上超過既有模型，包括 GPT-4 與 Claude-3.5。這兩者告訴我們：醫療專門化並非沒有頂級成功案例；更準確的說法是，**若想超越前沿通用模型，往往需要要嘛以本來就很強的前沿 backbone 作專門化，要嘛把 benchmark 從 MCQ 拉向臨床工作流型任務**。citeturn1academia37turn1search4turn21view1

然而，若改看更接近真實醫療互動的評測，通用前沿模型的優勢又重新浮現。HealthBench 不是考醫師考題，而是 262 位醫師撰寫 rubric 的 5,000 個多輪健康對話；其結果顯示，從 GPT-3.5 Turbo 到 GPT-4o 再到 o3，分數穩定上升，而且 o3 的整體分數到 0.60，HealthBench Hard 也只有 0.32，代表 frontier generalists 仍持續進步且尚未飽和。更直接地，2025 年一篇獨立研究把 OpenEvidence 與 UpToDate Expert AI 這類臨床工具，拿去和 GPT-5、Gemini 3 Pro、Claude Sonnet 4.5 比較，在結合 MedQA 與 HealthBench 的 1,000 題 mini-benchmark 上，通用前沿模型一致優於這些臨床專用工具。**[Inference]** 因此，在醫療裡最接近原始謎題的表述不是「專門化無效」，而是「多數醫療專門系統能提升自己，但常難以穩定超過最強通用前沿系統；真正的例外通常來自前沿 backbone 上的高資源專門化，或任務更貼近真實臨床工作流時」。citeturn15academia20turn22view1turn22view2turn22view3turn14academia1

**Law。** 法律領域的證據比醫療更混合。支持原始現象的證據很強：LegalBench 這個由法律專家共同建構、含 162 tasks、對應多種法律推理型態的 benchmark，在 2023 年的比較中由 GPT-4 大致領先；中國法律的 LawBench 也直接報告 GPT-4 仍是整體最佳，而法律專用模型雖有進步，但距離可靠實用還很遠。若只看這兩個早期到中期的大型 benchmark，會得到一個明確印象：**大型通用前沿模型在法律 benchmark 上非常難被超越**。citeturn4academia14turn17academia16

但法律也是本輪研究裡最重要的**模型級反例**來源之一。SaulLM-54B 與 SaulLM-141B 在 Mixtral backbone 上做大規模 legal continued pretraining、法律 instruction tuning 與 preference alignment，作者在 LegalBench-Instruct 上明確寫出：SaulLM-medium 勝過 Mixtral-54B，SaulLM-large 勝過 Mixtral-141B，而且其 smaller 專門模型甚至能勝過 GPT-4 與 Llama3-70B；文中比較器日期也明示 GPT-4 是 2024 年 5 月 10 日版本。換言之，在至少一個重要法律 benchmark family 上，**法律專門化不只提升基底，還擊敗了強通用比較器**。這不是可以被忽略的小反例。citeturn19view2turn19view3

再往更窄任務看，專門化優勢更明顯。Brazilian Legal Decision Classification 上，一個只更新 0.3% 參數的 BERTimbau-LoRA 就能大幅勝過 Claude 3.5 Haiku 與 GPT-4o mini；合約理解任務上，Legal-BERT、Contracts-BERT 也可勝過多個 general-purpose LLM。**[Inference]** 這意味著若把法律任務收窄到特定語言、司法機關、文件型態、標籤任務，專門化可以非常有效，甚至比大型通用 LLM 更穩。但這類結果常不是在與「當代最強 frontier generalist」比較，也常不是 open-ended legal work。於是法律領域最合理的判斷是：**現象只「部分成立」**。在廣泛 benchmark 上，通用模型常領先；在 matched subdomain 或窄任務分類上，法律專門化已有實質優勢；在中間地帶，證據仍不足。citeturn17academia14turn16academia0turn17academia17

**Finance。** 金融是最容易被評測偏誤誤導的領域之一。早期專門模型例如 BloombergGPT 顯示，混合大量金融語料與一般語料訓練，可以在金融任務上大幅贏過既有模型，同時不傷一般 benchmark；後續 FinGPT 提供更開放的金融資料管線；FinTral 則報告其帶有 DPO、tools、retrieval 的多模態金融系統可在 9 類任務中的 5 類超過 GPT-4。**[Observed]** 這說明金融專門化確實可以有效，甚至能做出看似很強的 specialist > generalist 結果。citeturn2academia12turn5academia13turn20academia1

但金融的核心問題是：**很多比較不是同代，也很難排除時間洩漏與 workflow 偏差**。FinanceBench 針對上市公司文件的 open-book QA 顯示，即便是 GPT-4-Turbo 加上 retrieval，在公開 150 題樣本上的人工審核中仍有 81% 答錯或拒答；而 2025 年的 BizFinBench 又顯示，在更接近實務的中文金融任務上，ChatGPT-o3、Gemini-2.0-Flash、Claude-3.5-Sonnet、DeepSeek-R1 這類通用或近通用前沿模型常在推理、計算、抽取等維度領先，且**沒有任何模型壟斷所有任務**。Finance Agent Benchmark 也指出，在需要用近期 SEC filings 做真實金融研究任務時，即便最強的 o3 也只有 46.8% 準確率。這組證據更像是在說：**金融工作流真的難，而當代最強通用前沿模型目前仍比多數公開金融 specialist 更接近前排，但整體依然不夠好**。citeturn5academia12turn20academia0turn26academia1

金融還有一個特殊問題：**時間偏差本身就是能力與 benchmark validity 的一部分**。Look-Ahead-Bench 專門用 point-in-time workflow 去測 look-ahead bias，發現標準 LLM 會明顯出現 alpha decay，而 point-in-time specialist family 則展現較好的 generalization；另一篇 2026 position paper 回顧 164 篇金融 LLM 論文，強調 look-ahead bias、survivorship bias、narrative bias、objective bias、cost bias 共同造成「看起來有效」的假象。**[Inference]** 所以金融領域對原始問題的結論應是：**基本現象大致存在，但金融文獻的比較品質整體偏低，很多結果在沒有先做時間對齊與偏差稽核前，根本不應拿來支持任何大論點。**citeturn6academia0turn6academia3turn26academia3

**Software Engineering / Coding。** 若只看短程 coding benchmark，專門化的效益很清楚。Code Llama 表明 Python-specialized 7B 版本能勝過 Llama 2 70B 在 HumanEval 與 MBPP 上的表現；DeepSeek-Coder 也在多個程式 benchmark 上超過既有開源 code model，甚至勝過 Codex 與 GPT-3.5。這一層面上，coding 是「同 backbone 專門化很有效」的經典例子。citeturn7academia12turn8academia1

但一旦把任務升級到 repo-level software engineering，情況就更像原始謎題。SWE-RL 在 Llama-3.3-70B-Instruct 上做來自開源軟體演化資料的 RL，讓 Llama3-SWE-RL-70B 在 SWE-bench Verified 拿到 41.0%，明確超過自己的 Llama baseline，並達到中型模型中領先、與 GPT-4o 相當的水準。這是很強的「專門化 > 自己基底」與「專門化接近強通用模型」證據。可是到 2025 年 4 月，OpenAI 官方報告 GPT-4.1 在 SWE-bench Verified 已達 54.6%，顯著高於 GPT-4o 的 33.2%；2026 年針對 SWE-bench leaderboards 的分析也指出，當時 state of the art 主要由 proprietary LLM 主導，尤其是 Claude 4 Sonnet。換言之，**在現代 repo-level coding 上，專門化能把公開模型推近前沿，但前沿位置本身仍由通用前沿模型或以其為核心的系統主導**。citeturn27view0turn9search0turn7academia15

更麻煩的是，軟體工程 benchmark 本身也在快速失效。SWE-bench 官方持續維護 leaderboard，但 OpenAI 在 2026 年 2 月已公開表示 SWE-bench Verified 日益受到污染，不再適合作為衡量前沿 coding capability 的主要指標；同時，2026 年的回顧研究也把這個生態描繪成由產業主導、專有模型主導的 leaderboard 生態。**[Inference]** 因此，coding 領域對原始現象的支持是**相當強但不穩定**：在現有 benchmark 上，專門化確實通常提升基底；但若把比較器換成最新一代融合強 post-training 與 test-time reasoning 的 frontier generalists，穩定 specialist advantage 仍然罕見，而且 benchmark contamination 讓近期 superiority claims 需要大幅打折。citeturn7search0turn9search5turn7academia15

**Science and adjacent domains。** 如果把 science 僅理解成多選題科學知識，通用前沿模型非常強。GPQA 起初設計成 biology、physics、chemistry 的 graduate-level Google-proof QA，2023 年最強 GPT-4 baseline 只有 39%，顯示科學多選題仍很難；但到 2025–2026，前沿模型在 biology benchmark 上已被報告可達到甚至超過專家水準。若只看這種 benchmark，會很容易得出「generalist scaling 正在吃掉 specialist space」的印象。citeturn10academia12turn11academia3

然而，科學是對原始問題最危險的反例來源，因為**一旦 benchmark 接近真實研究工作流，system-level specialization 的優勢會急劇上升**。LAB-Bench 明確指出它要測的是 literature、database navigation、protocol planning、sequence manipulation 等 practical biology research capabilities，而不是教材式 trivia；其初始結果顯示 frontier models 在多數任務仍深度落後人類，而且很多子任務如果不給工具模型本來就吃虧。BixBench 更把任務推向開放式 bioinformatics analysis，連 GPT-4o 與 Claude 3.5 Sonnet 都只有 17% 左右的 open-answer 準確率。這些結果其實不是支持 generalists，而是說：**真實科學工作非常難，裸通用模型遠未等於科研助手。**citeturn12academia15turn25view1turn25view2turn25view3turn13academia1

同時，科學領域也提供了本輪最強的 specialist counterexamples。PaperQA2 這個為科學文獻搜尋與摘要設計的 agent，在 LitQA2 上做到 85.2% precision、66.0% accuracy，precision 超過生物學 PhD / postdoc 人類基準，並在摘要和矛盾檢測任務上也達到或超過專家水準；Aviary 則進一步顯示，以 open-source、non-frontier LLM 為基底的 agent，透過環境、訓練與 inference-time scaling，可在 LitQA2、SeqQA、protein stability 等多任務上匹配或超過 frontier LLM agents 與人類專家，而且某些設定成本低很多。再往形式化數學看，AlphaProof 與 AlphaGeometry 2 在 IMO 2024 達到銀牌水準，而 Gemini Deep Think 在 IMO 2025 已經拿到官方認證的金牌水準。**[Inference]** 這些案例強烈說明：**只要把「專門化」理解為更廣義的能力系統設計，而不是單純 domain-finetuned chat model，原始現象就不再普遍成立。**citeturn23view0turn24view0turn24view1turn24view2turn10search0turn10search2

## 專門化分類、直接比較與反例檔案

**Observed specialization taxonomy in the literature。** 從文獻本身看，最穩定的分類法不是「specialist model / specialist system」兩桶而已，而是至少六類：**continued pretraining / domain-adaptive pretraining**（MEDITRON、BioMistral、SaulLM、BloombergGPT）；**instruction tuning / preference alignment**（MMedIns-Llama 3、FinTral-DPO-T&R、SaulLM-DPO）；**task-specific RL 或 reward shaping**（SWE-RL、某些 point-in-time finance 和 formal math systems）；**narrow classifier-style adaptation**（BERTimbau-LoRA、Legal-BERT、Contracts-BERT）；**retrieval / tool / database specialization**（LegalBench-RAG、PaperQA2、Finance Agent Benchmark）；以及**formalization / search / verifier heavy systems**（AlphaProof、AlphaGeometry 2、Aviary 類 agent）。這些類型之間的邊界不是理論先驗，而是實作層次、資源配置、與 evaluation target 的不同。citeturn0academia13turn11academia0turn19view3turn2academia12turn21view1turn20academia1turn27view0turn17academia14turn28view2turn23view0turn24view0turn10search0

**Direct specialist-vs-generalist comparison map。**  
**High comparability** 的證據多半回答的是「專門化有沒有幫自己的 backbone」，而不是「有沒有擊敗前沿 generalist」。例如 MEDITRON 對 Llama-2 基底、BioMistral 對 Mistral 基底、SaulLM 對 Mixtral 基底、BloombergGPT 對一般金融／通用 baseline、Code Llama 對 Llama 2、SWE-RL 對 Llama-3.3-70B base，這些比較的意思都比較清楚：**在 matching backbone 或近似 matching backbone 下，專門化通常有效。**citeturn0academia13turn11academia0turn19view3turn2academia12turn7academia12turn27view0

**Moderate comparability** 的證據才開始觸及原始問題。SaulLM-large 對 GPT-4 / Llama3-70B、MMedIns-Llama 3 對 GPT-4 / Claude-3.5、FinTral-DPO-T&R 對 GPT-4、Llama3-SWE-RL-70B 對 GPT-4o，這些都可拿來問「專門化會不會擊敗強通用模型」，但都受至少三個問題干擾：比較器未必是同代最強版本；closed models 的 post-training 與推理 budget 不透明；評測 often 由建 benchmark / 建模型同一團隊主導。這些實驗很重要，但不應被當成乾淨因果證明。citeturn19view3turn21view1turn20academia1turn27view0

**Low comparability 或幾乎不可直接解釋** 的，反而常是最令人印象深刻的成功案例。PaperQA2 勝人類與 non-RAG frontier models，Aviary 超越 frontier LLM agents 與人類，AlphaProof/AlphaGeometry 2 拿到 IMO 銀牌，Gemini Deep Think 拿到 IMO 金牌——這些都不是單純「domain-finetuned model 比通用 chat model 強」；它們比較的是**具專門工具、搜索、形式化、環境回饋、或高 test-time compute 的能力系統**。它們非常重要，但問題已從「專門模型 vs 通用模型」變成「專門能力系統 vs 裸通用模型或較弱系統」。citeturn23view0turn24view0turn10search0turn10search2

**Counterexample dossier。**  
**SaulLM-large。** 這是本輪最強的法律模型級反例之一。被專門化的是 Mixtral-family MoE backbone，加入 520B 級法律 token 的 continued pretraining、法律 instruction tuning 與 legal preference alignment；被擊敗的是 GPT-4 與 Llama3-70B；比較器對 GPT-4 至少有具體日期；勝利橫跨 LegalBench-Instruct 多類法律推理。**主要 confounders** 是：GPT-4 不是 2024 下半年的最強前沿版本，closed-model prompt / alignment 細節未知，benchmark 仍以法律推理題型為主。**證據強度：中等偏強。**citeturn19view2turn19view3

**MMedIns-Llama 3。** 被專門化的是 Llama 3 醫療 instruction-tuned 모델；被擊敗的是 GPT-4、Claude-3.5 等；優勢宣稱涵蓋多種臨床任務而不只是 MCQ。**主要 confounders** 是：MedS-Bench 與 MedS-Ins 出自同一研究脈絡；只抽樣約 1,500 test cases 以控制成本；few-shot 設定可能影響結果；真實臨床外部效度仍未建立。**證據強度：中等。**citeturn21view1

**FinTral-DPO-T&R。** 被專門化的是以 Mistral-7B 為基礎的金融 multimodal LLM，加上 tools 與 retrieval；被擊敗的是 GPT-4，在 9 類任務中報告勝出 5 類。**主要 confounders** 是：系統級增強與模型級專門化綁在一起；GPT-4 版本較早；benchmark 由作者建立；任務異質性高。**證據強度：低到中等。**citeturn20academia1

**PaperQA2。** 被專門化的是 scientific literature RAG agent，而不是單純參數內化的 science model；它在文獻檢索、摘要、矛盾檢測等多個真實任務上匹配或超越 subject-matter experts，且 LitQA2 的 precision 超過人類。**主要 confounders** 是：它靠完整工具鏈、文獻解析、citation traversal、RAG ranking / summarization；比較對象若無同等工具就不是純 specialization test。**證據強度：對「系統級專門化可以贏」非常強；對「模型級專門化可以贏」則弱。**citeturn23view0

**Aviary。** 被專門化的是 language-agent 訓練框架與科學環境，基底模型甚至不是 frontier；它可以在多個任務上匹配或超越 frontier LLM agents 和人類，且成本更低。作者同時強調這些是**task-specific environments**，不應誤讀成一般生物學能力。**主要 confounders** 是環境特化、訓練資料型態、online training 與 inference scaling。**證據強度：對「狹窄但真實工作流的專門系統可穩定贏」很強。**citeturn24view0turn24view1turn24view2

**AlphaProof / AlphaGeometry 2 / Gemini Deep Think。** 這些是數學／定理證明方向最強反例。它們不只是領域語料 adaptation，而是把 formal language、search、proof verification、長時間推理結合起來，分別達成 IMO 2024 銀牌與 IMO 2025 金牌。**主要 confounders** 是任務 formalization、測試時間大幅增加、與一般 LLM 對話模型不屬同一比較空間。**證據強度：對「專門能力系統能超越一般系統」極強；對原始 puzzle 的模型層版本，只能作為邊界條件反例。**citeturn10search0turn10search2

## 基準有效性與比較混淆地圖

**Benchmark Validity Map。**  
在醫療裡，MedQA、MedMCQA、PubMedQA、MMLU clinical topics 這類 benchmark 的主要訊號仍是**知識回憶、一般語言理解、多步推理與測驗技巧**；它們能證明模型具備醫療相關知識與推理，但不能直接推出模型具備安全、完整、可校準的臨床能力。MedS-Bench 之所以重要，正是因為它明確批評 MCQ benchmark 不足以反映臨床實務，轉而涵蓋摘要、治療建議、診斷、NER 等 11 類臨床任務；HealthBench 更進一步用 5,000 個帶 physician rubrics 的多輪對話測量 accuracy、completeness、communication、context awareness、instruction following。即便如此，HealthBench 仍然是**text-only、rubric-scored 單回應評估**，不是完整醫院工作流。**[Inference]** 所以醫療 leaderboard dominance 最多只能被解讀成「在某些醫療語言任務上更強」，不能直接等同「具備臨床專家能力」。citeturn1academia37turn21view1turn15academia20turn22view1turn22view2

法律也類似。LegalBench 由法律專家主導建構，是目前最認真的法律推理 benchmark 之一，但它本質上仍是**很多短任務的集合**；LegalBench-RAG 更直接指出，LegalBench 其實主要測 generation phase，沒有測大型法律語料庫中的 retrieval。TW-LegalBench 雖把考題、論述題和法律判決預測結合起來，更接近制度內能力，但其結果也顯示模型在精確法條引用與可靠法律文本生成上仍有明顯短板。**[Inference]** 在法律中，benchmark 高分常可以合理解讀為「有法律知識與若干推理能力」，但若沒有 retrieval、citation accuracy、jurisdiction alignment、長文件處理與開放式寫作評估，其實離「可作為可信法律專家系統」仍差很遠。citeturn4academia14turn28view2turn17academia17

金融 benchmark 的代理問題甚至更嚴重。FinanceBench 自身就把它定位為 open-book financial QA 的**minimum performance standard**，其主要測的是從長公司文件中找到證據並回答明確問題；BizFinBench 雖覆蓋數值計算、推理、抽取、預測辨識、知識問答等較廣項目，但仍主要是 benchmarkized query sets。Look-Ahead-Bench 和金融 bias position paper 則提醒：在金融裡，若沒有 point-in-time 控制，很多「表現」可能只是看了未來資料。**[Inference]** 因而金融 leaderboard 尤其不應被直接當成「投研專家能力」。它經常測的是**時間敏感檢索、基本金融知識、數值計算與問答遵循**，而非可部署的決策能力。citeturn5academia12turn20academia0turn6academia0turn6academia3

Coding 也需要分層看。HumanEval、MBPP 測的是短程程式合成；SWE-bench 則更貼近 repo-level issue resolution，確實比一般 codegen 更接近真實工程。但到 2026 年，OpenAI 已明確表示 SWE-bench Verified 日益污染，不再適合作為前沿 coding capability 的核心衡量；回顧研究也指出 leaderboard 生態由專有模型與工業系統主導。**[Inference]** 因此，SWE-bench 上的高分依然比 HumanEval 更像真實軟體工程能力，但它也不應再被當作唯一或穩定的 gold standard。citeturn7search0turn9search5turn7academia15

科學 benchmark 的差異更大。GPQA 很適合測「高難度科學知識 + 推理」，但不測實驗規劃、文獻搜尋、資料分析或 tool use；LAB-Bench 與 BixBench 則刻意往研究工作流靠攏，但 LAB-Bench 仍多是 multiple-choice，而且作者自己承認某些高分可能來自 test-taking strategy，tool access 對模型和人類也不對等。這使得 **domain-labeled benchmark performance ≠ demonstrated scientific expertise** 幾乎是科學領域最明顯的結論。citeturn10academia12turn12academia15turn25view1turn25view2turn25view3turn13academia1

**Comparison Confounder Map。**  
**Scale asymmetry** 幾乎到處存在。很多 specialist 建在 7B–70B 開源 backbone 上，卻被拿去和封閉前沿模型比較；即便 specialist 輸了，也不能直接當成反對專門化的證據。相反地，SaulLM 與 MMedIns-Llama 3 一類結果說明：當 backbone 本身夠強時，專門化的上限會明顯提高。citeturn0academia13turn11academia0turn19view3turn21view1

**Generation mismatch** 是第二大問題。BloombergGPT 對的是 2023 年的 ecosystem；FinTral 對的是當時版本的 GPT-4；SaulLM 對的是 2024-05-10 的 GPT-4；而 2025–2026 的 frontier 又已推進到 GPT-4.1、Claude 4、o3、Gemini 2.5/3。若不做同代比較，很多「specialist superiority」或「specialist failure」都可能只是世代差。citeturn2academia12turn20academia1turn19view3turn9search0

**Tool / retrieval / environment asymmetry** 在法律、金融、科學特別致命。LegalBench-RAG 之所以存在，就是因為 generation benchmark 沒有測 retrieval；PaperQA2 的成功高度依賴 paper search、citation traversal、evidence ranking；Finance Agent Benchmark 直接把 search 與 EDGAR access 納入；LAB-Bench 也承認一些子任務本來就需要工具。**[Inference]** 若 specialist 擁有檢索、資料庫和 environment API，而 generalist 沒有，測到的往往是「系統設計優勢」，不是狹義專門化。citeturn28view2turn23view0turn26academia1turn25view3

**Inference-compute asymmetry** 同樣常被低估。Aviary、PaperQA2、AlphaProof/AlphaGeometry、Gemini Deep Think 都把多步 search、majority vote、formal verification 或延長推理時間轉成額外表現；SWE-RL 與 frontier coding systems 也常透過 agent scaffold 和多輪 rollout 提升分數。這些不是無效，而是意味著比較單位應稱為「capability systems」，不能再簡化成「模型本體」。citeturn24view0turn23view0turn10search0turn10search2turn27view0

**Contamination / leakage / temporal bias** 是目前最嚴重且最常未被充分控制的混淆因子之一。SWE-bench Verified 已被公開承認污染日增；Look-Ahead-Bench 與金融 bias paper 系統性指出金融評估中的時間洩漏；LAB-Bench 則用 recent paper、abstract-unanswerable、private test set、open-answer spot checks 等方式減緩科學 benchmark 污染。這些都意味著：若沒有明確的 contamination control，benchmark superiority 只能視為弱證據。citeturn9search5turn6academia0turn6academia3turn25view2

## 文獻中的候選解釋、證據缺口與問題定義壓力測試

**Candidate explanations found in the literature。**  
**候選解釋一：強通用模型其實早已在預訓練中見過大量域內資料，所以「專門化紅利」被壓縮。** SaulLM 明言其大部分法律資料來自公開來源，這些資料很可能已出現在 base model 的預訓練裡；MEDITRON、SaulLM 也都加入 replay / math / general data 去避免 forgetting。**支持證據** 是觀察性、非因果。**反證** 是 SaulLM 仍能勝 GPT-4，說明即便 base pretraining 已涵蓋域內文本，額外專門化仍可能提供可觀增益。citeturn19view3turn0academia13

**候選解釋二：很多域內 benchmark 主要獎勵的是一般推理、語言能力與 instruction following，而非真正的專家工作。** MedS-Bench、HealthBench、LAB-Bench、LegalBench-RAG 都是在原有 benchmark 不足的前提下新建的；FinanceBench 也把自己定位成 minimum bar。**支持證據** 很強，但多為 benchmark design 論證與描述，不是嚴格因果。**反證** 來自那些已更接近工作流的專門系統，在這些更真實評測上反而更容易勝出。citeturn21view1turn15academia20turn28view2turn5academia12turn12academia15

**候選解釋三：真正決定域內表現的常不是模型內化的領域知識，而是檢索、工具、formalization、search 與 verifier。** 這是 LegalBench-RAG、PaperQA2、Aviary、Finance Agent Benchmark、以及形式化數學系統共同暗示的方向。**支持證據** 對系統層非常強；**反證** 是 SaulLM、MMedIns-Llama 3 這樣的模型級專門化仍然能在某些 benchmark 上擊敗強 generalists。故更精確的版本應是：這個解釋在 workflow-heavy task 上較強，在 text-only benchmark 上較弱。證據性質主要是相關與系統 ablation，而非統一因果識別。citeturn28view2turn23view0turn24view0turn26academia1turn10search0

**候選解釋四：通用前沿模型的 post-training、RL、推理模式與 test-time compute 升級速度，往往快於多數 specialist project 的資源增長速度。** BizFinBench 顯示 reasoning 類任務由 ChatGPT-o3、Gemini-2.0-Flash 等前沿系統主導；HealthBench 也顯示從 GPT-3.5 到 o3 的進展很快；coding 領域則有 GPT-4.1 對 GPT-4o 的大幅跳升。**支持證據** 強，但仍屬相關性。**反證** 是中等甚至小模型經過高度任務化訓練與系統設計後，有時仍能超過前沿通用系統在窄任務上的表現。citeturn20academia0turn15academia20turn9search0turn24view0

**候選解釋五：專門化常成功於窄任務，但不一定能形成可遷移、可持久的「專家優勢」。** 這在法律分類、合約理解、Brazilian court classification、以及許多 coding / science narrow benchmarks 上最明顯。**支持證據** 是這些模型常在單一任務家族上很強，但缺少跨新任務與 OOD 驗證。**反證** 是 Aviary、PaperQA2、SaulLM 這些案例都至少跨過多個 task family。證據性質多為觀察性與部分跨任務泛化。citeturn17academia14turn16academia0turn24view0turn23view0turn19view3

**Evidence gaps。**  
最關鍵的第一缺口，是**matched-backbone、matched-generation、matched-tool-budget 的當代比較**仍然過少。現有文獻多能回答「專門化是否幫助自己的基底」，卻較少能回答「若通用前沿模型也給同工具、同 context、同 inference budget，專門化還剩多少純增益」。這個缺口若被補上，會最大程度改變問題定義。citeturn19view3turn28view2turn24view0

第二缺口，是**專門化 scaling experiments** 幾乎不足。SaulLM、MEDITRON、Code Llama、SWE-RL 都提供某種程度的 scaling hint，但系統性地控制 in-domain token 比例、general replay 比例、alignment 深度、RL budget、context/tool availability 的研究仍少。若沒有這種實驗，專門化是否構成獨立 scaling axis 仍無法判斷。citeturn19view3turn0academia13turn7academia12turn27view0

第三缺口，是**將 benchmark 知識題與真實專家工作拆開量測**。HealthBench、LAB-Bench、BixBench、Finance Agent Benchmark 已開始往這方向走，但法律與金融的真實 workflow benchmark 仍不足，醫療的 text-only 占比也仍高。這個缺口若補上，很可能會讓「generalist 在 domain benchmark 很強」與「能否成為 domain expert system」兩件事被完全拆開。citeturn15academia20turn12academia15turn13academia1turn26academia1

第四缺口，是**污染與時間偏差控制**。SWE-bench Verified 的污染、金融的 look-ahead、科學題目的 recent-paper construction，都在提醒評測設計本身會改變結論。若不補這個缺口，任何對 specialist/generalist 的宏大結論都會被 benchmark artifact 汙染。citeturn9search5turn6academia0turn25view2

第五缺口，是**模型級與系統級專門化的清楚分拆**。當前最強反例多是系統級；若下一輪研究不把這兩者分開，問題會一直含混。citeturn23view0turn24view0turn10search0

**Problem Definition Stress Test。**  
我把這裡要壓力測試的「問題定義」理解為你在本輪提示中明確陳述的核心命題，而不是去推導任何舊案架構。就目前證據看：

- **「通用前沿系統經常在多個專業領域 benchmark 上領先」：Supported。** 特別是在醫療早期 MCQ benchmark、法律大型 benchmark、金融 reasoning benchmark、以及現代 coding benchmark 上，可以找到大量支持。citeturn17academia16turn4academia14turn20academia0turn9search0turn15academia20
- **「專門系統常能超過自己的通用基底，但較少穩定打敗最強通用前沿系統」：Partially supported。** 這在醫療、金融、coding 很強；但法律的 SaulLM、科學的 PaperQA2 / Aviary、數學的 Alpha 系列與 Gemini Deep Think 都構成重要反例。citeturn0academia13turn27view0turn19view3turn23view0turn24view0turn10search0turn10search2
- **「這現象可能是廣泛而非偶然」：Partially supported。** 它跨領域出現，但不是普遍規律；最不穩定的是工作流與工具密集任務。citeturn14academia1turn20academia0turn27view0turn24view0
- **「現有 domain benchmarks 未必測到真正 domain expertise」：Supported。** 這幾乎是跨領域共識之一。citeturn21view1turn15academia20turn28view2turn5academia12turn12academia15
- **「specialist / generalist 類別當前並不穩定」：Supported。** 文獻確實把模型 adaptation、工具系統、窄分類器、agent scaffold 都放進 “specialist” 裡。citeturn17academia14turn23view0turn24view0
- **「不應先回答 why」：Supported as methodology。** 目前最主要瓶頸是比較品質與 benchmark validity，而不是缺少候選機制。citeturn6academia3turn9search5turn25view2

**總結判定。** 目前這個問題不應被**原樣保留**，也不應被**直接否定**；最合理的處理是：**narrowed and reformulated**。最需要修正的是把問題拆成兩個版本：其一是**模型級專門化為何常只帶來 same-backbone gains，而少有 stable frontier superiority**；其二是**為何在 workflow-heavy tasks 上，系統級專門化反而經常構成明顯反例**。若不做這個拆分，原始 problem framing 會同時把被支持的現象與最強反例都塞進同一句話裡。citeturn19view3turn24view0turn23view0turn10search0

## 證據矩陣附錄與來源書目

**Evidence Matrix Appendix。** 下表聚焦最有決策價值的實驗級證據，而不是把整篇 paper 當成單一證據單位。

| 來源 | 領域與任務 | Specialist / comparator | 觀察到的主要結果 | 專門化是否勝自己基底 | 是否勝強通用比較器 | 比較器是否同代前沿 | 主要混淆與比較品質 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MEDITRON-70B 2023 citeturn0academia13 | 醫療；醫療 QA benchmark | MEDITRON-70B vs Llama-2 baselines, GPT-3.5, GPT-4, Med-PaLM 2 | 勝公開同級 baseline、勝 GPT-3.5 / Med-PaLM，但仍落後 GPT-4 與 Med-PaLM 2 | 是 | 否，對最強比較器否 | 部分同代 | **Moderate comparability**；closed comparators 細節未知，但 same-backbone gain 清楚 |
| Med-PaLM 2 2023/2024 citeturn1academia37turn1search4 | 醫療；MedQA 與長答臨床問答 | Med-PaLM 2 vs Med-PaLM、醫師答案、其他當時模型 | 相對前代大幅提升，部分 benchmark 接近 / 超過 SOTA，醫師偏好高 | 是 | 部分是 | 當時是 | **Moderate comparability**；本身建在前沿 PaLM 2 上，且含特殊 prompting / retrieval |
| MMedIns-Llama 3 / MedS-Bench 2024 citeturn21view1 | 醫療；11 類臨床任務 | MMedIns-Llama 3 vs GPT-4 / Claude-3.5 / MEDITRON 等 | 作者報告在近乎所有臨床任務上超過既有模型 | 是 | 是，按作者報告 | 大致同代 | **Moderate to low comparability**；自建 benchmark、抽樣評估、few-shot 設定 |
| LegalBench 2023 citeturn4academia14 | 法律；162 task legal reasoning | 多 model 比較，GPT-4 為通用對照 | GPT-4 整體大致領先多數法律推理類別 | 不適用 | 通用贏 | 當時是 | **Moderate comparability**；強 benchmark，但多為短任務 |
| LawBench 2023 citeturn17academia16 | 法律；中國法律 20 任務 | 51 LLM，含 9 個 legal-specific LLM | GPT-4 仍是最佳；法律專用模型有提升但距可用仍遠 | 多數是 | 多數否 | 當時是 | **Moderate comparability**；多語與法域差異仍在 |
| SaulLM-54B / 141B 2024 citeturn19view2turn19view3 | 法律；LegalBench-Instruct | SaulLM vs Mixtral base、GPT-4、Llama3-70B | SaulLM-medium 勝 Mixtral-54B；SaulLM-large 勝 Mixtral-141B，且小模型可勝 GPT-4 / Llama3-70B | 是 | 是 | 近同代，但非後續前沿 | **Moderate comparability**；強反例，但 benchmark 與 closed model 細節限制 |
| BloombergGPT 2023 citeturn2academia12 | 金融；金融 NLP + 一般 benchmark | BloombergGPT vs 既有模型 | 金融任務顯著提升，且一般 benchmark 不降 | 是 | 未對最強當代 frontier 做乾淨比較 | 已過時 | **High comparability for base improvement**, **low for frontier superiority** |
| FinTral 2024 citeturn20academia1 | 金融；9 類多模態金融任務 | FinTral-DPO-T&R vs ChatGPT-3.5 / GPT-4 | 報告全勝 ChatGPT-3.5，並在 5/9 任務勝 GPT-4 | 是 | 部分是 | 部分同代 | **Low to moderate comparability**；tools / retrieval / multimodal 全混在一起 |
| BizFinBench 2025 citeturn20academia0 | 金融；實務導向金融任務 | 25 models 含通用與金融模型 | reasoning 由 ChatGPT-o3 / Gemini 領先；無模型壟斷全部任務 | 混合 | 專門模型未見穩定領先 | 是 | **Moderate comparability**；benchmark 新，但 বিচার與任務異質性高 |
| Code Llama 2023 citeturn7academia12 | Coding；HumanEval / MBPP | Code Llama-Python 7B vs Llama 2 70B 等 | Python 專門版 7B 可勝自家通用 70B | 是 | 對部分舊通用模型是 | 當時部分是 | **High comparability** for same-family gain；低工作流真實度 |
| SWE-RL 2025 citeturn27view0 | 軟體工程；SWE-bench Verified | Llama3-SWE-RL-70B vs Llama-3.3-70B base, GPT-4o | 41.0%，勝同基底、接近 GPT-4o | 是 | 接近但未勝後續 frontier | 對 GPT-4o 屬近同代 | **Moderate comparability**；agent scaffold 與 evaluation harness 重要 |
| GPT-4.1 / SWE-bench Verified 2025；SWE-bench 2026 生態分析 citeturn9search0turn7academia15turn9search5 | 軟體工程；repo-level issue resolution | GPT-4.1、Claude 4 Sonnet 等前沿通用 | GPT-4.1 54.6%，且 2026 回顧稱 SOTA 主要由 Claude 4 Sonnet 主導；但 benchmark 漸遭污染 | 不適用 | 通用領先 | 是 | **Moderate comparability**；但 benchmark validity 在 2026 已明顯惡化 |
| PaperQA2 2024 citeturn23view0 | 科學；文獻搜尋 / 摘要 / 矛盾檢測 | PaperQA2 vs subject-matter experts、frontier non-RAG models | LitQA2 precision 超過人類，multiple tasks 匹配 / 超過專家 | 不適用 | 是，但屬系統級 | 同代 | **Low comparability for pure model question**；對 system-level specialization 證據很強 |
| Aviary 2024 citeturn24view0turn24view1turn24view2 | 科學；LitQA2 / SeqQA / protein stability | 非前沿開源 agent vs frontier LLM agents / humans | 多任務匹配或超過 frontier 與人類，且有成本優勢 | 是 | 是，但屬窄環境專門系統 | 同代 | **Low comparability for pure model question**；高任務真實度、作者也明示不可泛化解讀 |
| AlphaProof / AlphaGeometry 2；Gemini Deep Think citeturn10search0turn10search2 | 數學；IMO | formal proof / geometry systems vs human medal thresholds | 2024 銀牌，2025 金牌 | 不適用 | 是 | 是 | **Not directly comparable** to chat-model specialization；但為最強能力系統反例 |

**Source Bibliography。**

**Primary experimental sources。** Meditron; Med-PaLM 2; PMC-LLaMA; BioMistral; MedS-Bench / MedS-Ins; SaulLM-7B; SaulLM-54B & 141B; BloombergGPT; FinGPT; FinTral; Code Llama; DeepSeek-Coder; SWE-RL; PaperQA2; Aviary; LAB-Bench; BixBench; AlphaProof / AlphaGeometry 2 materials; Gemini Deep Think IMO report。以上來源中，**SaulLM-54B & 141B、Meditron、MedS-Bench、SWE-RL、PaperQA2、Aviary** 對下一輪研究最重要，因為它們分別代表高價值的 matched-backbone gain、frontier-over-frontier exception、workflow-specialist exception、以及 system-level specialist exception。citeturn0academia13turn1academia37turn0academia12turn11academia0turn21view1turn3academia0turn3academia2turn2academia12turn5academia13turn20academia1turn7academia12turn8academia1turn27view0turn23view0turn24view0turn12academia15turn13academia1turn10search0turn10search2

**Benchmark / evaluation sources。** LegalBench; LawBench; LegalBench-RAG; FinanceBench; BizFinBench; Finance Agent Benchmark; Look-Ahead-Bench; SWE-bench / SWE-bench Verified; HealthBench; HealthBench Professional; GPQA; LAB-Bench; TW-LegalBench。對下一輪最重要的是 **HealthBench / HealthBench Professional、LegalBench-RAG、FinanceBench / Look-Ahead-Bench、SWE-bench contamination note、LAB-Bench**，因為它們直接影響「benchmark 到底測了什麼」這個核心問題。citeturn4academia14turn17academia16turn28view2turn5academia12turn20academia0turn26academia1turn6academia0turn7search0turn15academia20turn15academia23turn10academia12turn12academia15turn17academia17

**Major laboratory technical reports / official evaluations。** OpenAI GPT-4.1 coding report；OpenAI SWE-bench Verified introduction；OpenAI SWE-bench contamination note；Google DeepMind AlphaProof / AlphaGeometry 2 IMO report；Google DeepMind Gemini Deep Think IMO 2025 report。這些來源的重要性在於它們提供確切版本日期、官方比較器選擇、以及 benchmark validity 更新訊號。citeturn9search0turn9search3turn9search5turn10search0turn10search2

**Surveys / synthesis / position sources。** 金融偏差與安全評測的兩篇 2025–2026 position papers、SWE-bench 生態分析，以及必要時可追蹤到各 benchmark 官方 repository 的說明文件。這些來源不應取代原始實驗，但對辨認 recurring confounders 很有價值。citeturn6academia3turn26academia3turn7academia15