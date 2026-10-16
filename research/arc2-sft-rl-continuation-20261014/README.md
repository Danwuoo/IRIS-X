# ARC-AGI-2：SFT、可驗證 reward 與等成本學習比較

這條研究線要回答：**在同一個離線 Qwen3-14B 起點與有限算力下，可驗證 reward 的學習，
能否比既有 SFT 與同成本的額外 SFT，更有效地解決 ARC-AGI-2 的新規則任務？**

v43 已完成並取回真實輸出：A 完成 SFT256；B 首批 64 條中 12 條未通過原數值檢查，
沒有提交 RL 更新；C 在匹配 B 整段成本下額外 SFT203。固定規則選 A，原 scorer 的完整
PUBLIC120 觀察為 0/167，334 個視圖均有效，但正式 consumer admission 仍有缺件。
這不是有效 RL 更新的比較，也不是官方或獨立重評分數。[證據與下一步](DEVELOPMENT-PROGRESS.zh-TW.md)

## 一、研究假設與可反駁的結果

1. **訊號假設：** 固定 training parents 的 demonstration-LOO exact reward，能產生 mixed groups，
   並在 unchanged-policy replay 通過後形成有限、非零的真實 LoRA 梯度。完整全零／全一是
   無相對訊號；缺資料、replay 失敗或未執行則是未知，兩者不能混用。
2. **學習價值假設：** 在完整比較上，B 不只優於 A，也優於匹配整段額外模型階段耗時的 C。
   只有 B>A 仍可能只是多做了訓練；B>A 且 B>C 才值得安排下一個獨立確認實驗。
3. **轉移假設：** 訓練 reward 改善能轉移到非訓練題。一次小型比較與已重用的 held32 不足以
   證明廣泛泛化；正訊號仍需新的未使用 parents／families 重複驗證。

這是訓練介入組合的比較：B 與 C 的資料流程、學習率、更新次數與算量組成不同。
不能把結果描述成只改 objective 的純因果證明，也不以框架名稱或外部高分代替本地證據。

## 二、凍結的首輪 A/B/C

研究來源固定為 [`cc14bd1a79aac1fe6135017c9e09d4834300675d`](https://github.com/Danwuoo/IRIS-X/tree/cc14bd1a79aac1fe6135017c9e09d4834300675d)。
工程 successor 可以修正已定位的執行問題，不能暗中改寫以下比較。

| 項目 | 固定安排 | 要回答的問題 |
| --- | --- | --- |
| **A：SFT256** | 同一 session 的 Qwen3-14B、BF16 base／FP32 rank-8 LoRA，完成 256 次 SFT，保存並重載 | 共同起點是否真實、可重載、可比較 |
| **B：有限 RL** | 從 A 出發；32 個固定 training parents，最多 4 個互不重疊 batch，每批 8 parents×8 samples＝64 slots；最多 256 attempts／4 次完整 batch 更新 | exact reward 是否提供有效訊號及轉移收益 |
| **C：等成本額外 SFT** | 從同一 A 出發，fresh optimizer；匹配 B 整段同步 model-phase wall，不靠 idle padding | RL 是否比同成本繼續 SFT 更值得 |

B 的 reward 是 training demonstration-LOO 的 binary exact match；使用原始 token、
DFA-conditioned log-probability、group mean baseline 與嚴格雙側 DDIS 遮罩。
B 的學習率為 1e-6；A/C 為 2e-4。沒有 advantage std normalization、critic、reference KL、
entropy bonus、OPSM 或 async。完整無訊號批次不更新、不換 parent、不補抽樣；
後續失敗不能抹除較早完整 batch 已提交的更新或其成本。[精確公式與來源](rl-methods.zh-TW.md#22-精確-objective)

C 配對的是 B 的 setup、抽樣、reward、replay、hash／Python、失敗／rollback、
save／reload／verification 全部額外模型階段耗時，不能只配 optimizer 或 GPU kernel 時間。
整場 43,200 秒包含 queue、setup、學習、推論、評分與 closure；既有成本和時鐘不重置。
本輪採 grid-only、固定可逆視圖、no-TTT。

### 評估順序、分母與資料曝光

1. A/B/C 在 dev16 選一次；平手固定 A→B→C，之後凍結所選 arm。
2. 先產生所選 arm 的 PUBLIC 預測，再產生 A/B/C 的 held32 預測；關閉模型並封存預測後，
   由隔離 evaluator 使用原 scorer 評分。PUBLIC 不是三個 arm 各自反覆試分的選擇集。
3. **PUBLIC120＝120 tasks／167 queries**，兩個固定視圖共 334 planned views；micro pass@2
   分母固定 167。尚無評分保持未知／null；只有原 scorer 已評分的缺失或非法答案才算錯。
4. dev16 是選擇資料；held32 已被專案重複使用，不是全新確認集。訓練 parent／ancestor／alias
   排除、SFT 與 reward 實際曝光、選擇時序都要留證。PUBLIC／held 答案不進 solver、訓練、
   prompt、selector 或記憶；既有公開開發觀察也不能重新宣稱為未曝光驗證。

固定依據：[policy](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/design/MEASURED-POLICY.json)、
[plan](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/plan.py)、
[batched consumer](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer/validate_owned_outputs.py)。
舊 A64／full-sweep schema 只保留歷史用途。

## 三、已有證據能支持什麼

| 證據層次 | 已有支持 | 尚不能推出 |
| --- | --- | --- |
| 凍結來源與離線支援 | inert plan、collector 報告解讀、完整 batch audit adapter、逐軌跡 reduction 與失敗測試 | 原模型執行、真實 audit provenance 或新分數 |
| **Agent Factory 3 實際整合** | 真正執行上游 `TrainingSample`、`DDISLoss`、`MeanMetricState`；合成 CPU loss／raw-logit gradient parity | 已接入 Qwen／LoRA graph、GPU 更新或 ARC-AGI-2 效益 |
| 本地材料與執行邊界 | code22／active43 真實接受與 COMPLETE；獨立唯讀取回 31 個必要／選用檔案，原 evidence archive 通過容器驗證 | 舊 native session closure、正式 collector context 與 checkpoint tensor 驗證仍不能由新取檔收據代替 |
| 真實研究結果 | 封存輸出有 reward15/64、RL commit0、B/C 整段耗時匹配、A 的完整 PUBLIC pool 全錯觀察 | 數值 gate 失敗不證明 RL 方法無效；來源評分尚未正式 admission，不是官方分數或未曝光確認集結果 |

AF3 是重要 RL 來源，也是已實際採用的上游元件。固定來源、Apache-2.0、實際呼叫、
CPU proof 與模型接線缺口集中在[AF3 整合研究](agent-factory3/integration.zh-TW.md)。
目前 frozen runtime 仍使用原本本地 DDIS 公式；CPU companion 不成為首次原 A/B/C 的新增啟動門檻。
真實 audit 由原 A/B/C runtime 產生，回收後離線分析；v43 正式 consumer admission 尚未成立。

歷史 native TTT、uncapped 候選搜尋與 v39 失敗各自有不同來源、曝光和分母；
它們可協助定位問題，不能換算為本輪 PUBLIC120 效果。
[歷史研究的適用範圍](method-landscape.zh-TW.md#32-已有歷史證據)

## 四、如何決定下一個實驗

**實驗順序、最低對照與觸發條件只維護在[方法比較與決策表](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)。**
先取得可解讀的既有 A/B/C，再依實際訊號決定是否研究資料／verified trajectories、
目標函數差異、demo-only TTT、程式提案／修復或 selector。工程失敗不是改研究方法的證據。

TTT 需要穩定可重載 baseline、同 checkpoint 的有／無 TTT 對照及完整成本；
Agent 機制需要同總預算的 grid／program／repair 比較。多角色與 selector 只有在
候選互補或 evaluator 顯示 pool-oracle 到 top2 確有損失時才有理由推進，答案仍不回灌。
這些都是條件式後續研究，沒有混入本輪 no-TTT A/B/C，也不新增流行方法清單。

## 五、閱讀路徑與文件責任

1. **研究主線：** 本頁的問題、假設、凍結比較與證據界線。
2. **方法選擇：** [方法總覽](method-landscape.zh-TW.md)；深入公式看 [RL 附錄](rl-methods.zh-TW.md)，深入機制與原始來源看 [Agent 附錄](agent-architectures.zh-TW.md)。
3. **實際 RL 元件整合：** [AF3 整合](agent-factory3/integration.zh-TW.md)、[元件驗證](agent-factory3/validation.md)、[元件獨立審查](agent-factory3/independent-review.md)。
4. **現在做到哪裡：** [當前進度](DEVELOPMENT-PROGRESS.zh-TW.md)，只記目前狀態、阻礙與下一步。
5. **如何接手：** [單一交接流程](OFFLINE-LOCAL-HANDOFF.md)；詳細 CLI／schema 保留各工具 README，不複製多套命令。
6. **當時發生過什麼：** [工程歷史 E0–E52](archive/engineering-history.zh-TW.md)；固定 [Stage 0 審查](offline-continuation-review.md)、[Stage 1 審查](stage1-independent-review.md)、[研究來源審查](research-source-review.md)、[前次文件審查](documentation-update-review.md) 按其原日期解讀。

[NEXT-STAGE-PLAN](NEXT-STAGE-PLAN.zh-TW.md)保留為舊連結的轉址入口，不另維護計畫。
根目錄、research 與 docs README 只指向這條研究閱讀路徑。

## 已完成與未完成

見[當前進度與證據](DEVELOPMENT-PROGRESS.zh-TW.md#二目前基線與證據索引)；離線完成與真實研究結果分開判定。

### 保存狀態

見[當前來源](DEVELOPMENT-PROGRESS.zh-TW.md)及[固定歷史收據](archive/engineering-history.zh-TW.md)。

## 不變的研究問題

見本頁第一、二節；不因操作環境或發布修復而改成另一個研究目標。

## 驗證分類

CPU、實際模型／GPU、成本匹配、完整評分、方法收益與 CI 各自需要證據，不能互相代替。
