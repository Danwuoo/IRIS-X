# Budget ablation 總控分析

日期：2026-09-23。核對開發 commit `e8868c6`，工作目錄為
`C:/Users/wurre/.codex/worktrees/918a/IRIS-X`。
結論：**diagnostic-complete-no-validation；沒有設定通過擴大評估門檻，不提升候選**。
本次總控只做本機驗證、分析與文件更新，零新模型呼叫、零 Kaggle 操作。
開發實作仍在 `codex/arc-budget-ablation`，本報告不代表已合併其程式碼。
完整 repository validation 在開發 worktree 通過 156 tests；總控 main 的
文件更新亦通過現有 151 tests。這些是本機驗證，不消耗實驗生成次數。

## 已核對的結果

重新計算歷史 baseline score、64 題 cohort、192-job score、qualification 與
512 題 visible-source audit，全部與開發 task 保存的 JSON 一致。另從原始
completion 使用獨立的 digit-row parser 和 exact match 重算三個 arm，分數
仍為 18、18、7。Result/outbound 的 membership、digest、run binding 和
checkpoint/prediction 一致性也經驗證。

Result SHA-256：`65e2d694e7268815d1b7d594218dea2012c1a7694d108048c1cb543f878edeea`。
本機總控診斷為 `.irisx/budget-ablation-review/review.json`，SHA-256：
`dad5e2a3a136a1c51e06aa8f34d9302b20fa6857997c87250310090b6010662c`。
精確 tokenizer 分析另存 `.irisx/budget-ablation-review/token-check.json`。

| 設定 | 正確 /64 | 保留 B1 正確 /18 | 新增 / 失去 | 撞 token 上限 | 每題 p50 / p95 秒 |
| --- | ---: | ---: | ---: | ---: | ---: |
| B0：off / 512，既有 cache | 18 | 18 | — | 22 | 6.8 / 31.5 |
| A1：off / 1,024 | 18 | 18 | 0 / 0 | 4 | 7.3 / 59.3 |
| A2：off / 4,096 | 18 | 18 | 0 / 0 | 4 | 6.7 / 210.5 |
| A3：on / 4,096 | 7 | 6 | 1 / 12 | 57 | 237.7 / 240.4 |

這 64 題刻意以歷史 train 結果選取，包含全部 18 題成功和 22 題截斷案例。
18/64 與 7/64 **不是代表性準確率**，不可與先前 12/128 dev 或官方 public
evaluation 分數直接比較。總生成 192 次，無 retry、timeout 或 warm-up；
沒有任何 arm 達到「淨增至少 4 題、保留至少 16 題」，所以沒有再跑 384 題。

## 1. 輸出容量問題被確認，但解決容量沒有增加正確答案

本次已有精確 pinned-revision tokenizer，可把上輪字元估算提升為實測。
384 個 train/dev 正解以原 digit-row 格式編碼，含一個 EOS 最多 930 tokens；
其中 28 題超過 512，沒有一題超過 1,024。診斷 64 題中有 15 題超過 512。

因此對這批題目，1,024 足以裝下正確 final grid。A1 把 22 次 cap 降至 4 次，
卻沒有解對原本截斷的任何一題：模型把錯誤答案寫完了，並非原本只差幾行
正確答案。A1/A2 各有 23 題完整但內容錯、14 題完整但尺寸錯、5 題無效輸出。

原始 completion 的逐題比較尤其有說服力：

- B0→A1：42 題完全一致，22 題 A1 是 B0 的嚴格前綴延伸，沒有其他變化。
- A1→A2：60 題完全一致，僅 4 題繼續延長，仍無新增正確答案。
- 那 4 題中，三題在 1,024-token cap 時仍是單一超長行，一題重複同一行
  256 次。再給到 4,096 只是延長無效輸出，不能解讀成正常答案容量不足。

這也提供了 cached B0 可比性的實際證據；不需要為了對照再跑一次 B0。
後續新 solver 可依精確編碼保留合理 final 容量，但不應再把提高到 4,096 的
純輸出上限當成主要研究方向。原 B1 身份與 512 設定保持不變。

## 2. Thinking 測到的是低完成率，不是能力上限

A3 有 57/64（89.1%）在 4,096 tokens 用完時仍沒有 `</think>`，沒有 final。
原始輸出沒有被記錄長度裁切，因此不能把這些失敗歸因於 log 遺失或 parser
漏掉已生成的 final。這些案例屬於本次預算內未完成，不是 300 秒 timeout。

另外 7 題有完整 final，7 題全對：6 題 B1 原本會，1 題是新解。
這表示不能由本次結果推論「thinking 沒有能力」；也不能拿完成的 7 題宣稱
100% 準確率，因為排除了 57 題失敗，有嚴重選擇偏差。

本次以 greedy、原 B1 prompt 和單一 reasoning+final 共用上限隔離變因。
[Qwen 官方 model card](https://huggingface.co/Qwen/Qwen3.5-4B#best-practices)
提供的是 sampling 設定與更長輸出建議；本輪不是那些設定的測試。
所以結論是「這個有時限的 thinking 配置不合用」，不是模型的無限制推理上限。
沒有理由直接把 64 題全量升到 32K：若保留此支線，應另做很小的完成率／
reasoning 與 final 預算分配診斷，先證明能交付答案再擴大。

注意 `analysis.json` 中 reasoning/final token totals 是已知欄位的加總。
A3 的 57 個缺 separator 案例分段 token 數為 null，因此其中 18,906
reasoning tokens 不是 A3 全部思考量；完整總生成量是 252,556 tokens。
未來報告應明列 known/missing coverage，不能把缺失當零。

## 3. 等待主要由 thinking 生成造成

整個四卡 session 4,732.345 秒，即 78.87 分鐘。各 arm 的逐題 generation
elapsed 加總為 A1 1,299.594 秒、A2 2,008.178 秒、A3 14,672.746 秒。
A3 佔三者總和 **81.6%**。這是跨 worker 的工作時間加總，不能直接等同
session wall time 或 GPU 硬體利用率。

四張 L4 都有載入及派工證據，完成量為 40/50/53/49 jobs；模型各只載入一次，
約 30 秒。Dataset create 約 22 秒；kernel accepted 到 runner start 約 22 秒。
本輪長等待主要來自模型生成，而非重新上傳大型權重或四卡沒有排程。

未達門檻就停止，確實省下了另外 384 次生成。這個分階段流程值得保留。
開發／反思 profile 是 GPT-6 Sol xhigh，但本輪 proposer calls 為零，不能
把此結果解讀成 GPT-6 反思效果的測量。

## 4. 修正上輪 holdout 失敗的解釋

完整 512 題可見資料逐題相符，包括 `f3e62deb`。舊
`arc_prompt_pilot.validate_competition_mount` 固定取 competition 的 test index 0，
卻與 holdout outbound 保留的兩個 test inputs 比較，因形狀不一致而拒絕。

因此先前「來源不相容」是對錯誤訊息的初步解讀；根因是 **full-task 與
selected-test 視圖比較錯誤**，不是 Kaggle 與 pinned upstream 的題目內容不同。
保留原失敗證據，補上這項更精確的診斷即可；不需要改來源或偷偷刪題。
Holdout 仍無推論／分數。未來比較必須明確區分 task、test-index 和評分分母，
不能把 test-index-0-only 的 pilot 宣稱為完整官方 task 評估。

## 研究判斷與下一步

保留 B1 作歷史比較，暫停全局 prompt 擴寫與更大的純 token-budget sweep。
當前證據指出要改進的是 **ARC 專用解題能力**，不是單純容量或反思模型級別。

下一條主線建議回到原定 NVARC source：先盤點可取得的 ARC-trained checkpoint、
精確 tokenizer/模型架構與可執行路徑，再設計小規模的相同 checkpoint、
適應關／開對照。不能把 generic Qwen3.5-4B 加上一段 LoRA 當作 NVARC 復現。
[NVARC 原始碼說明](https://github.com/1ytic/NVARC) 的 ARChitects 路線是 Qwen3 4B；
[訓練說明](https://github.com/1ytic/NVARC/blob/main/ARChitects/README.md) 還包含
專用 tokenizer、16 embeddings、SFT 與 `arc2_evaluation6` 訓練子集。
因此 checkpoint 來源、曾看過的資料和相容性必須先核對；public score 的污染
標籤與乾淨對照仍需分開。這是下一輪研究建議，本次未啟動新實驗或下載權重。
