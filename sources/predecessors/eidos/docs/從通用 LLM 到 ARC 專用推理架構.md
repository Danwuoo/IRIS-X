ARC 的高分方法目前多半建立在通用大型語言模型之上，但 ARC 本身的問題結構，未必需要一個擅長自然語言與廣泛世界知識的通用模型。另一條值得研究的路線，是從底層 sequence architecture、tokenizer、資料生成與 pretraining objective 開始，設計一個真正針對 ARC 的專用模型。

核心假設是：ARC 最重要的能力不是長上下文建模，而是**可修改的推理狀態**。模型看到第一組 input-output example 時，可能形成數個候選規則；看到後續 examples 後，必須保留仍然成立的假說，同時刪除被反例否定的部分，最後再將剩餘規則套用到 test input。這比一般 next-token prediction 更接近「假說形成、修正與執行」。

因此，RWKV-7、Mamba-3、Gated DeltaNet-2，以及 Titans/MIRAS 這類架構值得重新從 ARC 的角度研究。重點不是把這些模型直接堆疊在一起，而是抽取它們不同的 recurrent memory 機制，作為候選 backbone。RWKV 類模型提供動態 recurrent state；Mamba 類 SSM 提供更具表達力的狀態演化；Gated DeltaNet 類模型則允許對 associative memory 做較精細的 erase/write 更新。對 ARC 而言，後者尤其適合測試「hypothesis revision」是否能成為一種自然的內部計算。

第一個實際原型可以非常簡單：使用 ARC-specific 2D tokenizer，加上一個單一 recurrent backbone，例如 Gated DeltaNet-2，再加入可重複執行數次的 recurrent reasoning loop。Tokenizer 不應只把 grid 當作一串數字，而應明確編碼 color、row、column、train/test pair、input/output role 等資訊，同時保留加入 learned object slots 或 relational representations 的空間。

真正關鍵的另一部分是資料。與其主要依靠現有 ARC 題目，可以建立一個 synthetic latent-program universe：先隨機產生抽象 transformation program，再生成大量不同 grid world 執行該 program。透過顏色置換、位置變化、object 數量、orientation、distractor 等方式消除 shortcut，使模型只能依靠抽象規則完成任務。訓練 objective 也不應只有 output-grid prediction，而可以加入 same-rule contrastive learning、program inference、inverse transformation、execution prediction，以及刻意設計的 hypothesis-revision tasks。

另一個重要方向是 recurrent test-time compute。同一組權重可以對一道 ARC task 重複執行 4、8、16、32 甚至更多 reasoning iterations。如果 accuracy 能隨 inference compute 穩定提高，就代表模型找到了一條不同於單純增加 parameter count 的 scaling law。

Titans 或 MIRAS 類 test-time memory 則比較適合放在第二階段。ARC-AGI-1/2 通常並不需要超長 context，因此它們最有價值的地方不是 long-context efficiency，而是允許模型在解一道題的過程中建立與修改 task-specific memory。可以把 recurrent backbone 視為 fast working state，而把 MIRAS/Titans-style memory 視為較慢的 task-level rule memory，形成兩個不同時間尺度的推理系統。

因此，較合理的研究順序不是一次創造一個複雜混合模型，而是先固定 tokenizer、data、parameter count 與 training budget，只比較 Transformer、RWKV-7、Mamba-3、Gated DeltaNet-2 等 backbone，測試它們在 rule induction、state tracking、hypothesis revision、compositionality 與 OOD generalization 上的差異。確定哪種 recurrent memory primitive 最適合 ARC 之後，再加入 recurrent-depth reasoning 與 test-time learned memory。

整體上，這條研究路線可以概括為：

**ARC representation + mutable recurrent state + iterative reasoning + synthetic program induction。**

它真正想驗證的問題不是「哪個新架構比 Transformer 強」，而是更具體的一個假說：**如果模型從 tokenizer、內部狀態更新、訓練資料到 inference computation 都針對抽象規則歸納而設計，一個遠小於通用 LLM 的專用模型，是否能更有效率地學會 ARC 所要求的假說形成、反例修正與程序執行能力。**

這在工程上是可實作的；目前真正不確定的，是這種 inductive bias 能否轉化成顯著的 ARC-AGI 泛化優勢。這也正是它值得被系統性實驗驗證的原因。