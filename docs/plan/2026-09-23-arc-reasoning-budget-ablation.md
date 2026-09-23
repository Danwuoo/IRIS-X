# ARC solver：先量測輸出容量與推理模式

日期：2026-09-23。狀態：**總控建議稿，尚未啟動新 task 或外部執行**。
Owner 本次指示為「先分析吧，然後規劃下一步」。這份計畫不延長已消耗的
Decision 0019 執行授權，不修改原 trial 的分數、身份或 acceptance criteria。

## 問題與優先順序

[離線分析](../../trials/arc-agi-2-prompt-pilot/failure-analysis.md) 顯示 B1 有
34/384 次 token-cap failure，但更大的問題是 264/384 次尺寸正確、內容錯誤。
九個 instruction 候選均未超過 B1，且其 dev 回歸都不是 token-cap failure。
下一輪先回答兩個可分辨的問題：

1. 放寬輸出預算，能修復多少被截斷的答案？
2. 在相同總生成預算下，開啟模型原生 thinking 是否改善解題？

不直接再做十輪相同 GEPA 搜尋。先讓可測量的 solver 能力進步，再優化提示。
85+ 仍是長期目標；這個局部 public-training dev 的 9.375% 不是官方 public
evaluation 成績，不能拿來估計距離 85 分還需要幾輪。

## A. 離線準備：沿用成功 runtime，補上缺少的檢查

- 沿用成功的模型 Dataset、精確 model revision、四卡常駐 worker、動態 queue、
  checkpoint/result、CLI transport 和本機 scorer；只修改配置、thinking 分段
  處理及觀測欄位。避免重建依賴環境與重傳大型權重。
- 在 evaluator 端取得並固定 competition challenge snapshot 後，先比對全部
  256 train + 128 dev + 128 holdout 的可見內容，產生逐題差異報告。若本機
  缺少 snapshot，列為未完成的 preflight；未通過前不啟動 GPU。
  未來來源下載應是明確、獨立的 materialization 步驟。
- 對 `f3e62deb` 說明差異的欄位與來源。若需要換 source binding，另建 run 與
  split identity，公開列出與原實驗不可直接比較的部分；不覆寫舊資料、不刪題
  讓原 holdout 過關。這份計畫沒有授權修改原 holdout。
- 使用精確 revision 的 tokenizer 和 chat template 離線驗證長 grid 的編碼
  容量；不能用別的 Qwen tokenizer 或字元估算代替。合成完整 grid 與截斷
  fixture 應驗證 parser、EOS、thinking 分隔與 token counter，不需模型生成。
- 記錄總 tokens、reasoning/final tokens（若可可靠分隔）、stop reason、final
  是否完整、parse status、尺寸、exact match、每題 elapsed、每批 p50/p95、
  model load、queue、upload/download 和 proposer elapsed。未知值用 null。
- 保存 train-only reflection request、input digest、案例 IDs、parent、所選
  失敗類型及 coverage。這是之後 GEPA 的稽核準備，本輪不呼叫 proposer。

## B. 固定 64 題 train 診斷集，三個新設定

從舊 B1 的 256 optimization-train 建立互斥四組：18 題原本答對、22 題撞上限、
12 題未撞上限的尺寸錯誤、12 題未撞上限的內容錯誤。前兩組全取，後兩組依
`SHA256("arc-budget-diagnostic-20260923:" + task_id)` 排序取前 12。
在新生成前保存完整 cohort manifest 與 digest；若 source parity 未通過，
先處理 A，不替換案例。

這是按已知結果選取的診斷樣本，刻意包含成功與截斷；**不是代表性測試集**。
其整體正確率不能外推至 dev、public evaluation 或 competition。

| Arm | Instruction | Thinking | Max new tokens | 新生成數 |
| --- | --- | --- | ---: | ---: |
| B0 | 原 B1 | off | 512 | 0，讀取既有 cache |
| A1 | 原 B1 | off | 1,024 | 64 |
| A2 | 原 B1 | off | 4,096 | 64 |
| A3 | 原 B1 | on | 4,096 | 64 |

A1/B0 量測輸出容量；A2/A1 量測額外上限是否還有影響；A3/A2 在相同總 token
上限下量測 thinking 模式差異。A3 的 4,096 包含 reasoning 和 final answer，
不是另加 4,096 個 answer tokens；若思考用光預算，記為失敗，不補第二次生成。
這是有限預算的能力探測，不是模型能力上限測試。

固定 `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`、
demonstrations、digit-row final parser 與 greedy decoding。只透過該 revision
chat template 的正式 thinking 開關切換，保留原始 completion；從明確的
reasoning/final 分隔取出 final 後才使用同一 strict grid parser。沒有 final
分隔或只有 reasoning 的輸出必須明確失敗，不能從任意數字片段猜答案。
Thinking-off 路徑需用既有結果與模板 fixture 做回歸驗證。

[Qwen 官方 model card](https://huggingface.co/Qwen/Qwen3.5-4B#instruct-or-non-thinking-mode)
說明原生 thinking 開關，並非以 `/think` 文字切換。官方另有 sampling 和較長
輸出預算建議；本實驗保留 greedy 以隔離變因，所以陰性結果僅限本次設定。
執行前仍需以 pinned revision 的實際 template 驗證支援，不能只依最新版文件。

192 jobs 在同一個 private kernel 內以預先固定的交錯順序排程，四卡各自載入
一份同模型、依 job 設定 mode/token budget，共用動態 queue。每題最多 300 秒，
無隱藏 warmup generation、retry 或多次取樣。超時需能中止該工作並保存 checkpoint，
不能只在回傳後標註超時。300 秒全用滿時，192 jobs / 4 workers 的純工作上界
約四小時，另加載入與調度；不能把上輪 18–20 分鐘推估成這輪保證。

Kaggle metadata 必須保留：

- `competition_sources: ["arc-prize-2026-arc-agi-2"]`
- `machine_shape: "NvidiaL4"`、private、Internet disabled。
- 硬體 gate 要求四個不同 L4 GPU identities；四個 model-ready 和各卡 dispatch
  都有實測紀錄。不得以 CLI accepted 或兩卡執行充當成功。

## C. 只讓有訊號的設定跑完整 384 題

以下是**待採用的新實驗篩選規則**，不是改寫舊 trial 的 promotion 標準：

- 在 64 題診斷集相對 B0 淨增至少 4 題，且保留原本 18 題中的至少 16 題，
  才進入完整評估。這是工程篩選，不是統計顯著性或泛化證明。
- 多個 arm 過關時先取 exact-match 較高者；同分取 p95 elapsed 較低者，再以
  較少 token 上限作為 tie-break。只允許一個設定進入下一階段。
- 凍結設定後做一次完整 256 train + 128 selection-dev；全部 384 題重跑以
  形成單一新 run 的完整觀測，診斷 cache 僅供比較，避免拼成混合結果。
- 新生成總上限為 192 + 384 = **576**；若沒有 arm 過關，止於 192。
  所有失敗呼叫也計入。這個上限不含任何 GEPA、TTT 或 holdout 呼叫。
- 分別報告 train/dev、四類診斷子組、paired wins/losses、截斷率、p50/p95、
  每個新增正確答案的額外時間。dev 已經過多輪選擇，不能宣稱為未見測試集。
- 若四卡、model binding、來源或輸出驗證失敗，保存失敗並停止，不能自動
  增開 notebook 填補配額。最終 holdout 保持 unscored，本輪不重試。

未來若 owner 採用此範圍，開發 task 可連貫完成 A→B→條件式 C→報告，不在
每批模型載入後停下等人工交接。沿用原子 ledger、低頻 terminal 狀態檢查、
完成後單次取回與本機 checkpoint 修復；不做高頻 log 輪詢。

## D. 得到結果後如何決定研究方向

1. **只有容量改善**：採用能容納完整 final grid 的最小預算；不把補完 grid
   描述成推理能力躍升。GEPA 下一輪先測短 instruction 的單一變更。
2. **Thinking 有穩定淨收益**：固定新 solver 配置後再做 GEPA。反思仍用
   `gpt-5.6-sol / xhigh`，記錄方案使用量與 elapsed；先提三個有不同可驗證
   假說的候選，經 train 小樣本篩選才評估完整 dev，不預設再跑十批。
3. **兩者都無訊號**：停止全局 prompt 擴寫。下一條獨立實驗轉向 NVARC 衍生
   task-local adaptation 或可用 demonstrations 驗證的程式求解路線，先選一條，
   固定來源／checkpoint／資料污染標籤並另訂訓練預算。不能把過去 inference-only
   smoke 當成 NVARC 方法已經正式評估。

後續 GEPA 的三例 feedback 應區分截斷、尺寸、內容失敗，涵蓋成功保留案例，
並保存跨輪 coverage；不能把 dev case-level answers 放入 proposer。
採樣改善、NVARC、程式求解和 public evaluation 都是後續獨立變因，這輪不混入。

## 交付與驗證

總控保留計畫、研究判斷與結果核對；後續獨立開發 task 承接實作與經授權的
執行。交付包括 source parity 報告、固定 cohort/config manifests、獨立 ledger、
truth-free outbound/checkpoint/result、逐題評分與配對分析、時間報告和推薦。
新外部範圍採用時再建立 governing decision，不挪用原 trial 剩餘數字當成授權。

只對有失敗後果的變更增加測試：thinking/final 分隔、截斷識別、全體可見資料
parity、generation ledger 與 resumability。交付前執行
`python tools/repository_check.py --all`。原有 notebook、result、score、ledger
與 trial terminal status 保持原樣。
