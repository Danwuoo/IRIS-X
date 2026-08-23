# IRIS-X：下一版 IRIS 的 Agentic AI System / Runtime 假設設計草案

**Document Type:** Hypothetical Research Design Note (Non-normative)  
**Status:** Draft v0.1  
**Supersedes:** `IRIS-R.md` as the primary forward-looking concept note for the next version of IRIS  
**Normative Boundary:** This note does **not** override `docs/01_Architecture_Constitution.md` ~ `docs/08_Training_Run_Governance.md`  
**Purpose:** 在保留 IRIS 架構憲法與治理框架的前提下，將下一版 IRIS 從「更強的小模型構想」重構為「以可執行推理、可驗證行動、可管理 context、可審計 side effects 為核心的 agentic AI system / runtime 假設」。

---

## 1. 問題重述（Problem Reframing）

IRIS 目前最完整、最穩固的部分，並不是某個特定 benchmark 的技巧，而是一套相對完整的系統級約束：

- single trunk
- canonical State IR
- learned routing / gating / control
- failure taxonomy 與 credit routing
- regression / phase gate
- segment transaction / resume governance

這些文件已經形成一個相當成熟的**治理、可觀測性、與防漂移框架**。但如果下一版 IRIS 的目標是 **breakthrough agentic AI system**，那麼僅僅把核心模型變得更會推理、更多 latent recurrence、或更會 adaptive halting，仍然不夠。

現行主流路線，不論是 CoT、CoT + synthesis、LRM、LRM + CoT 或各種 inference-time search 變體，雖然能提升能力，但仍共享幾個根本侷限：

1. **能力高度依賴參數量與推理時計算量**，且邊際效益遞減明顯。
2. **推理過程不可形式化執行與驗證**，通常缺少嚴格的 verifier、evidence model、以及 action-level audit trail。
3. **planning / search / recovery 常由外部技巧補丁構成**，而非模型—系統一體化的原生機制。
4. **context engineering 成為主要瓶頸**，但缺乏系統層級的 working set、memory hierarchy、compression、and provenance discipline。
5. **agent action semantics 與 runtime side effects 沒有被納入第一級設計**，導致模型再強，也常只能停留在“會想”而不是“會可靠行動”。

因此，下一版 IRIS 的核心問題不應再只是：

> 如何讓 IRIS 變成更強、可變 test-time compute、可驗證的小模型？

而應改寫成：

> **如何在不違反 single trunk 與 learned control 憲法的前提下，構造一個具有可執行推理、可驗證行動、可管理 context、可審計 side effects、並可持續擴展的 agent runtime / system platform？**

這個問題比單純的 reasoning frontier 更接近 IRIS 的真正目標。

---

## 2. 核心命題（Core Thesis）

**IRIS-X 的核心命題是：**

下一版 IRIS 的主增益不應主要來自「更像 reasoning model 的 core」，而應來自**模型、執行、記憶、驗證、與治理五者的共同結構化設計**。

也就是說，IRIS-X 不是 IRIS-R 的否定，而是對其重新降階定位：

- **IRIS-R 解的是 core cognition / latent reasoning kernel 問題**
- **IRIS-X 解的是 agent execution / context operating system / platform governance 問題**

在 IRIS-X 中，模型仍然重要，但模型只是整體 agentic substrate 的一部分。真正的突破，不是來自單一 trunk 想得更久，而是來自：

- 想法能形成**可執行的 action plan**
- action 能產生**可驗證的 evidence**
- context 能被**系統性編譯與管理**
- side effects 能被**交易化與審計**
- failure 能被**形式化地局部歸因、回退、再嘗試**

換言之，IRIS-X 的核心不是 “think longer”，而是 **“think, act, verify, commit, recover” 成為同一套可學習、可治理的閉環**。

---

## 3. 設計原則（Design Principles）

IRIS-X 必須保留以下既有非談判性原則：

1. **Single trunk remains non-negotiable**
   - 不引入第二個高容量語義大腦。
   - 外圍模組可存在，但不得形成「理解 → 推理 → 決策 → 輸出」的語義閉環。

2. **State IR remains canonical**
   - State IR 仍是跨 Level、跨模組、跨 artifact 的 canonical exchange / attribution interface。
   - 不允許 private semantic side-channel 繞過 State IR 成為隱性標準。

3. **Routing / gating / control remain learned-by-default**
   - planning、branching、termination、recovery、memory usage、verification escalation 都必須以 learned signals 為主。
   - hard-coded policy 只能作為 technical debt guardrail。

4. **Failure credit remains explicit and level-addressable**
   - failure 不得只以單一 scalar blame 表示。
   - attribution 必須可被 verifier、recovery policy、training signals 與 regression artifacts 共用。

5. **Benchmark remains instrumentation, not intelligence substrate**
   - ARC-family、domain benchmark、tool benchmark 都是 probe，不是 architecture invariant。

6. **Agent side effects must become first-class governed objects**
   - 外部 action、tool effect、state mutation、memory write、episode commit 不可再視為附屬工程細節。

---

## 4. IRIS-X 的三層架構（Three-Layer Architecture）

IRIS-X 將下一版 IRIS 明確拆成三層：

### 4.1 Layer A: Core Cognition Kernel

這一層對應 IRIS-R 的核心價值，但不再代表整個系統。

其職責包括：

- single trunk computation
- latent workspace maintenance
- recurrent reasoning
- adaptive halting / budget allocation
- verification-in-the-loop
- credit-routed recovery signals

這一層回答的問題是：

> 模型如何形成假設、更新假設、停止推理、並對失敗產生可學習的局部診斷？

### 4.2 Layer B: Agent Execution Substrate

這一層是 IRIS-X 新增的重心。

其職責包括：

- action representation
- executable plan / branch / rollback semantics
- verifier evidence pipeline
- tool / environment interaction contracts
- commit / abort / retry discipline

這一層回答的問題是：

> 想法如何變成可執行、可回放、可驗證、可審計的 agent 行為？

### 4.3 Layer C: Context & Runtime Governance Platform

這一層將 context engineering 與 runtime side-effect management 提升為架構原語。

其職責包括：

- working set compilation
- memory hierarchy governance
- provenance-aware retrieval and context packing
- episode journaling
- exactly-once / replay-safe external action semantics
- runtime manifest / environment lock / reproducibility discipline

這一層回答的問題是：

> agent 在長時程、多步、外部互動場景中，如何保持 context integrity、execution integrity、以及 auditability？

---

## 5. 概念性資料流（Conceptual System Flow）

```text
Raw Input / External Events
  -> Boundary Encoder / State IR Builder
  -> Canonical State IR
  -> Trunk Internal Workspace
  -> Recurrent Reasoning Loop
       |- Hypothesis / Plan Update
       |- Verifier / Calibration Update
       |- Credit Routing Update
       |- Halt / Continue / Escalate Decision
       |- Context Compiler Request
       |- Optional Memory / Procedure / Abstraction Request
  -> Action / Execution Projection
  -> Execution IR / Episode Step
  -> Tool / Environment Interaction
  -> Evidence Packet
  -> Commit / Abort / Retry / Rollback Decision
  -> Memory / Context Update
  -> External Output + Confidence + Failure Credit + Audit Artifact
```

重點不是多了一條 tool pipe，而是：

- **推理**不再直接等價於最終輸出
- **行動**不再是 opaque side effect
- **驗證**不再只在最後發生
- **memory / context**不再只是 retrieval 附件
- **episode**成為被交易化管理的單位

---

## 6. 新增的關鍵系統原語（New First-Class Primitives）

IRIS-X 提議新增四個第一級設計原語。這些原語目前均為**假設性設計方向**，不是已生效規格。

### 6.1 Execution IR（Proposed, outside State IR）

IRIS-X 提議引入 **Execution IR**，用以表示 agent 的可執行行為結構，例如：

- candidate action
- subgoal transition
- branch point
- environment effect expectation
- verifier attachment point
- commit boundary
- rollback boundary

**Boundary rule:**

- Execution IR 不屬於 State IR token inventory。
- Execution IR 不得拼接進 canonical State IR sequence。
- Execution IR 是 system-level execution substrate，不是 trunk-shared representational substrate。
- 若需要跨 Level / artifact 對齊，必須投影回 State IR summary、evidence packet、或 episode journal fields。

也就是說，IRIS-X 不試圖把所有 execution semantics 硬塞進 State IR，而是明確區分：

- **State IR = canonical reasoning state representation**
- **Execution IR = canonical action / execution representation**

### 6.2 Evidence Packet

每一個重要 action / branch / verification event，都應產生標準化 **Evidence Packet**。

其最小內容可包括：

- proposed action / branch id
- pre-state summary
- post-state summary
- verifier result
- confidence / disagreement
- violated constraints (if any)
- failure-category logits / credit hints
- external observation provenance
- runtime / tool provenance

Evidence Packet 的角色不是 human-readable explanation，而是：

- verifier consumption
- episode audit
- rollback diagnosis
- regression attribution
- training-time credit routing material

### 6.3 Context OS / Working Set Compiler

IRIS-X 將 context engineering 視為系統原語，而非 prompt 技巧。

這個模組的職責包括：

- active goal stack 管理
- working memory selection
- episodic memory recall
- semantic memory retrieval
- provenance-aware ranking
- context compression / summarization
- eviction / retention policy
- branch-specific context packing

其輸出不是單純 “more context”，而是**經編譯的 working set**。

### 6.4 Episode Journal

IRIS-X 提議把 agent 行為單位正式化為 **Episode Step / Episode Segment**，並參考現有 training governance 的 segment journal 思路，建立：

- `PENDING`
- `APPLIED`
- `ABORTED`
- `ROLLED_BACK`
- `RECONCILED`

等 episode 狀態。

這使 agent 的 side effects 不再只是“執行過了”，而是可被 transaction semantics 管理的對象。

---

## 7. IRIS-X 中各 Level 的重新角色（Role Alignment）

IRIS-X 保留 L0-L6 的 Level 架構，但重新強化其在 agent system 中的角色含義。

### L0: Boundary Representation

- 將外部輸入、工具輸出、環境事件轉為 State IR-aligned observation fields
- 維持 schema-safe canonicalization
- 不承擔 execution policy

### L1: Local Dynamics / Short-Horizon Consistency

- 維持局部狀態轉移與短期一致性
- 支持 environment transition expectation 與 local simulation
- 不承擔高層規劃 authority

### L2: Latent Procedure Induction

- 產生 procedure candidates、subgoal sketches、action schemas
- 可以影響 Execution IR proposal，但不能演化成 symbolic-first executor

### L3: Adaptive Compute / Search / Halting / Recovery Control

- 決定是否繼續計算、是否分支、是否升級 verifier、是否調整資源
- 決定 recovery sequence，但不得以硬流程圖主導

### L4: Memory / Context Retrieval and Write Discipline

- 負責 memory read / write / consolidation
- 在 IRIS-X 中也承擔 Context OS 的部分執行接口
- 但 memory 仍不得取代 reasoning 本體

### L5: Abstraction / Compression / Semantic Boundary Management

- 不再只被視為 macro 管理
- 升格為壓縮與語義邊界控制的重要層
- 可能成為 future scaling axis

### L6: Verification / Calibration / Credit Routing

- 不只驗 final answer
- 而是持續驗 branch、action、episode transition、rollback legitimacy
- 產生可被 episode runtime 與 regression harness 共用的 diagnosis outputs

---

## 8. 核心機制（Key Mechanisms）

### 8.1 Recurrent Core as Kernel, not Whole System

IRIS-X 接受 IRIS-R 的一個核心洞見：

- 單一 trunk 的 recurrent latent reasoning 是值得保留的方向
- adaptive halting 與 verification-in-the-loop 是合理的 kernel mechanism

但在 IRIS-X 中，這些不再被當作最終答案，而是作為 **core cognition kernel**。

### 8.2 Hypothesis -> Action -> Evidence -> Commit Loop

IRIS-X 的基本閉環為：

1. hypothesis formation
2. candidate action / branch proposal
3. verifier/evidence attachment
4. execution or simulated execution
5. commit / abort / retry / rollback decision
6. memory / context / state update

agent intelligence 不再只體現在「形成更長的 latent reasoning path」，而體現在這整個 loop 的品質。

### 8.3 Verification Becomes a Continuous Runtime Service

verification 不再是終局裁判，而是持續存在的 runtime service：

- pre-execution sanity check
- post-execution validity check
- branch consistency check
- evidence sufficiency check
- rollback legitimacy check

### 8.4 Context Compilation Replaces Naive Context Stuffing

IRIS-X 將 context engineering 改寫為：

- what must be present
- what may be compressed
- what must remain attributable
- what can be reconstructed on demand
- what must be pinned for replay / audit

這表示系統未來的主要限制不再只由 context window 決定，而由 **working set compiler quality** 決定。

### 8.5 Transactional Side-Effect Governance

對外部世界的 action 必須具有：

- idempotency expectations
- precondition checks
- postcondition checks
- journaled provenance
- replay / reconciliation semantics

這並不是把 agent 變成資料庫，而是避免 agent system 在真實環境中退化成不可審計的 script runner。

---

## 9. 預期收益（Expected Gains）

若 IRIS-X 的方向成立，理論上的主要收益不只會出現在 reasoning benchmark，而會出現在以下幾個更本質的面向：

### 9.1 Better reasoning-to-action fidelity

模型內部形成的高分 hypothesis，較能穩定轉譯成外部可執行行為，而不是停留在 verbal competence。

### 9.2 Better verifier-grounded behavior

系統不再只靠 intuition-like confidence 決定行動，而能在關鍵節點上使用 evidence-based acceptance / rejection / rollback。

### 9.3 Better context scaling

主要瓶頸從 token window size 轉移到 context compilation quality，讓系統更有機會在有限 context 下支撐長時程 agent episodes。

### 9.4 Better auditability and reproducibility

episode journal、evidence packet、runtime manifest、action provenance 將使 agent behavior 更容易被追蹤、比較、與重現。

### 9.5 Better failure localization

failure 不再只表現為 “答錯了”，而是能在：

- representation
- procedure
- search / halting
- memory / context
- abstraction / compression
- verification
- execution / runtime governance

等面向上被形式化區分。

---

## 10. 驗證路線（Validation Roadmap）

IRIS-X 的驗證不應從「先把所有模組做滿」開始，而應分層進行。

### Stage 0: 規格對齊與去漂移

先處理現有規格張力：

- 統一 Level ontology
- 統一 credit vector 維度與責任邊界
- 明確區分 State IR 與 trunk-internal workspace 的邊界
- 明確宣告 proposed Execution IR 不屬於 State IR

### Stage 1: Core cognition kernel validation

在固定資料、固定參數級別、固定訓練 budget 下，比較：

- plain baseline
- current IRIS-style baseline
- recurrent kernel variant

只回答：

> 在不破壞既有 regression discipline 下，是否能得到更好的 accuracy-latency-effective-FLOPs frontier？

### Stage 2: Execution substrate validation

建立最小 episode runtime：

- branch proposal
- verifier attachment
- evidence packet
- commit / abort / retry / rollback

先在封閉、可 replay 的 toy environment 驗證，而不是直接上真實開放工具鏈。

### Stage 3: Context OS validation

驗證 working set compiler 是否能在長 episode 中顯著降低：

- irrelevant context load
- provenance loss
- stale memory reuse
- failure masking by overstuffed context

### Stage 4: Runtime governance validation

將既有 training governance 思想部分遷移到 agent runtime：

- action journal
- runtime lock / environment manifest
- replay-safe external action protocol
- crash / resume / reconciliation coverage

### Stage 5: Vertical domain pressure test

只選一個高價值狹域進行端到端測試，檢查：

- reasoning-to-action fidelity
- verifier-grounded acceptance quality
- context scalability
- auditability
- regression stability

---

## 11. 需要新增或修改的文件方向（Proposed Spec / Doc Work）

IRIS-X 若要落地，至少需要新增幾份文件；它們應以 **Change Proposal** 形式出現，而不是直接修改既有 RO 契約。

### 11.1 Proposed: `State IR v2 Boundary Clarification`

目的：
- 明確界定 canonical State IR、trunk workspace、以及外部 execution substrate 的邊界
- 消除 “State IR 是否為唯一微觀推理介質” 的歧義

### 11.2 Proposed: `Execution IR and Agent Episode Semantics`

目的：
- 定義 action / branch / commit / rollback / evidence attachment 的 canonical semantics
- 明確宣告其不屬於 State IR token inventory

### 11.3 Proposed: `Context OS and Memory Hierarchy`

目的：
- 將 context compilation、working set management、provenance-aware retrieval、compression / eviction policy 正式化

### 11.4 Proposed: `Agent Runtime Governance`

目的：
- 將 segment transaction、replay discipline、runtime manifest、resume consistency 等既有治理思想，遷移到 agent runtime 場景

### 11.5 Proposed: `Verifier and Evidence Pipeline Spec`

目的：
- 將 verifier 從 final-output judge 升格為 branch / action / episode runtime service
- 定義 Evidence Packet 的最小欄位與 artifact 關聯

---

## 12. 非目標（Explicit Non-Goals）

IRIS-X 不是以下任一方向：

1. **不是 tool-first dispatcher**
   - 工具仍是可調用 substrate，不是 intelligence locus。

2. **不是 symbolic executor disguised as agent**
   - 不接受「neural proposal + symbolic executor as semantic authority」的退化路徑。

3. **不是只把 IRIS-R 放大**
   - 更多 recurrence、更長 latent thought、更多 halting head，本身不足以構成 agent system。

4. **不是只做 workflow engineering**
   - Episode / evidence / runtime governance 雖重要，但不得替代 trunk-learned cognition。

5. **不是為單一 benchmark 打磨 platform**
   - platform semantics 必須是 task-agnostic、benchmark-agnostic 的。

---

## 13. 主要風險（Major Risks）

### 13.1 系統複雜度暴增

IRIS-X 明顯比 IRIS-R 更複雜。若邊界沒畫清楚，容易退化成：

- 什麼都想做
- 什麼都沒正式定義
- 最後變成一堆附屬流程拼接

### 13.2 邊界錯置風險

若 Execution IR、Evidence Packet、Context OS 與 State IR 的邊界未嚴格定義，系統很容易重新滑回 side-channel drift。

### 13.3 Runtime semantics 過早工程化

若在核心 cognition 還未驗證前就過度堆疊 execution/runtime 層，可能造成研究訊號稀釋。

### 13.4 Governance overhang

治理框架若過重，可能變成研究速度的主要阻力。因此需要分 phase 啟用，而不是一次性全上。

### 13.5 False agentic progress

最危險的情況不是失敗，而是系統看似更像 agent，實際上只是：

- 更多 prompt choreography
- 更多 hard-coded retries
- 更多 external tool dependence
- 更少真正的 learned control

這必須被明確防範。

---

## 14. 對 IRIS-R 的重新定位（What Survives from IRIS-R）

IRIS-X 並不否定 IRIS-R。IRIS-R 中至少有三個核心方向應被保留：

1. **single trunk + recurrent kernel 是合理的 cognition direction**
2. **adaptive halting / verification-in-the-loop 是必要機制**
3. **credit-routed recovery 應直接進入學習與運行迴路，而不只存在於事後分析**

但在 IRIS-X 中，這三者只構成 **Layer A: Core Cognition Kernel**，不再被誤認成完整下一代 IRIS 的全部。

---

## 15. 未來工作（Future Work）

1. 正式提出 `Execution IR` 的 change proposal
2. 正式提出 `Agent Episode Governance` 的 change proposal
3. 正式提出 `Context OS / Working Set Compiler` 的 change proposal
4. 將 verifier artifact 從 final-score object 升格為 runtime-wide evidence object
5. 研究 recurrent kernel 與 execution substrate 的耦合點
6. 研究 compression / abstraction 是否可成為新的 scaling axis
7. 研究 operator-level redesign 是否能在不破壞憲法下，支援更原生的 executable reasoning

---

## 16. 核心結論（Compressed Thesis）

**IRIS 下一版不應只追求「更會推理的小模型」，而應追求「以 single trunk 為 cognition kernel、以 Execution IR 為行動語義、以 Context OS 為工作集管理、以 Episode Governance 為 side-effect discipline 的 agentic AI system」。**

IRIS-R 若回答的是：

> 模型如何想得更深？

那麼 IRIS-X 回答的是：

> **系統如何在想、做、驗、記、退、審之間形成可學習、可治理、可擴展的閉環？**

這才更接近 IRIS 作為下一代 agentic AI 系統的真正方向。
