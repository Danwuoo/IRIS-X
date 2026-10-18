# 第一輪公開原始來源研究

研究日期：2026-10-18。本輪不建立「目前最強」排行榜。以下保留來源的任務、方法與證據層級；未下載模型、原始答案庫或大型訓練資料。可追溯連結／blob 見 [sources.json](sources.json)。

## 1. 形式化證明與修復

**DeepSeek-Prover-V2 [S01] — 來源所述。** 使用遞迴分解子目標、合成已完成子證明建立 cold start，再做強化學習，結合非形式與形式數學推理。這提供「草圖不是最終證明、子目標必須真的完成」的工程先例。本輪讀取原論文 HTML；其大模型／資料生成與採樣條件不是 Kaggle TPU pilot 的可預期效果。

**我們的設計推論。** 記錄原 theorem 與子目標 DAG；所有引理閉合後才接受根目標。不可把有 `sorry` 的 skeleton 或證明片段標成完成。先測無訓練修復，不能把整個訓練系統的文獻效果歸因於我們的 orchestration。

**Goedel-Prover-V2 [S02,S03] — 來源所述。** 原摘要提出 scaffolded synthesis、Lean feedback self-correction 與 checkpoint averaging。公開模型卡提供 8B 版本及修復模式，適合作為形式化子線候選。

**版本限制。** 本次 arXiv 摘要與 model card 的 8B MiniF2F 數字分別為 84.6% 與 83.0%（均標 pass@32）；Putnam 的報告預算／解出數也不同。本輪沒有重現以解決差異，不混成一個 benchmark 成績，也不依較大的數字選模型。正式使用前須固定 checkpoint、prompt、Lean／Mathlib、資料清單、輪數和計費方式。這是候選基線，不是對 v5e-8 的相容性保證。

**LeanDojo [S04] — 來源所述。** 強調可用 premise 的選擇、與 proof state 互動，以及 novel-premise split 的評估。這支持把引理檢索與解題分開測量。

**我們的設計推論。** 首輪只檢索允許的定理庫與定義；不檢索評估题解答。random split 與按來源／family／dependency 分割可能測到不同問題，須公開分母及暴露標籤。

## 2. Yi-Chia Chen 相關公開成果：可借鑑但不照搬

官方 AIMO Proof Pilot 公告將 Yi-Chia Chen 列為第一名，29/42 [S05]。這是來源事實；本輪不以重現比賽名次或領獎為目標，也沒有聯絡本人。

目前可讀的 Fields Model `pochi-imo26` 固定來源為 `4b74d98ef1f31363c53f0dd0b2d7fbeed42bffc8` [S06-S08]。這個 repository 是後續 IMO26 系統，不能把它所有後續增量都稱作六月 Proof Pilot 冠軍當時的實作。其 training 說明另區分原始 OPD200 路徑與後續 64×B200 warm-start；本輪只據該公開說明歸因，沒有獨立確認私有原始訓練現場。

可學習的是 **prove／verify／refine 的題內 artifact pool、候選 lineage、有界修復、選擇與完整成本保存**。角色使用的評論／分數不能自動取得人工評審或 Lean kernel 的地位。

特別注意：該公開 OPD v2 文件說，學生在自己的 rollout tokens 上對凍結教師做 JSD(β) 蒸餾，verifier 分數用於 curriculum／候選組織，**不是 reward，方法不是 RL**。因此不能拿這個成功案例主張「小算力 reward RL 已證實能提升 IMO 證明」。我們也沒有採納文件關於無界 staleness 的理論延伸主張作為本地安全保證。

當前推論 README 使用 8×H200/B200、TP2×DP4、SGLang、DFlash 與特殊 attention-sink kernels；數值正確性依賴指定 patch。這不是一般 Qwen/JAX checkpoint 可以直接取代的路徑。對 TPU 的決策是借鑑搜尋與回饋機制，不移植 CUDA binary、不宣稱移植成功，也不預先複製 128k 輸出／大型候選池。

## 3. 什麼才算證明

Lean 官方 axioms 說明 [S09] 指出 `sorryAx` 可證任何型別，不應出現在完成證明；native evaluation 會擴大信任基礎。故「編譯 exit 0」不是單一驗收条件。

我們的嚴格形式子線要求固定 theorem／imports，檢查最終 proof term 的 axioms／unresolved obligations，採預先宣告的 axiom allowlist；若接受 native computation，另列較大 trust base，不與純 kernel 檢查混列。禁止模型加入新 axiom、用錯誤形式化偷換問題或改 evaluator。Lean tactic elaboration 可執行程式，須在無網路、無 credentials、有限 CPU／memory／時間的 worker 執行；不是只靠找字串 `sorry`。

CAS／Python 在允許的代數語義下產生完整證書可以支持特定命題，但隨機代入、浮點近似和 LLM 自評不是普遍證明。R001 將這個差異做成可重現反例，而非把所有 Python `True` 都升級為 formal proof。

## 4. 題庫與污染

PutnamBench 官方 README [S10] 區分「已給定數值答案再證明」與「找答案並證明」；兩者不可同分母合併。現讀取版本列 1,724 個跨語言 formalizations，其中 Lean 672；這不是 1,724 個不同題目，也不能和舊 paper 的 658 題直接比較。

維護者要求避免公開 proof 以減少污染，並請先討論正式撰寫其子集證明。本輪未產生或發布 PutnamBench 解答，只有閱讀政策。未來評估計畫先核對政策；公開報告提供 aggregate／題目 ID／環境，不把 withheld proofs 放到 Git。本輪32案例全部自編且公開暴露，不冒充未知題。

## 5. 第一輪研究判斷

來源支持把 **命題對齊、證明搜尋、可靠回饋、有限算力與資料暴露** 當作共同問題；不支持「只接 agent 就能達到 IMO 水準」。我們最先需要區分計算錯誤、缺少假設、完整性缺口和形式化失敗。R001 已證明某些有限數值檢查會放行具精確反例的命題；下一個有效研究問題是，真實模型取得這類可信回饋後是否能以比追加採樣更低的成本修復它。這個能力尚未量測。
