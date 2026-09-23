# Prompt pilot 離線失敗分析

日期：2026-09-23。這是既有結果的分析，不是新的執行授權。
九個候選沒有超過 B1；下一輪應先拆開輸出容量與推理模式，再決定如何繼續 GEPA。
本次沒有新的模型呼叫、Kaggle 操作或 holdout 評分。

## 證據與重現

在開發 worktree 保留的 ledger、outbound、result 與 score 上，重新計算 B1 及九個
候選的 train/dev 評分；十份報告均與保存的 JSON 完全一致。ZIP 依報告綁定的
SHA-256 尋找，不以相同檔名視為相同結果。基本分數、執行量和失敗身份見
[control review](control-review.md)。

從 repository root 執行：

```powershell
python tools/analyze_prompt_results.py --pilot-root C:/Users/wurre/.codex/worktrees/e34a/IRIS-X/.irisx/arc-agi-2/prompt-pilot --output .irisx/prompt-pilot-analysis/diagnostics-v2.json
```

輸出若已存在請換新檔名。工具會驗證原始評分並產生各候選的錯誤分類、相對 B1
得失題、長度和時間統計；生成資料留在 `.irisx/`。它只分析 optimization-train
與 selection-dev，不對 locked-holdout 產生評分或診斷。評分器會載入原有 truth
容器，但本工具只使用 train/dev score records。

本次 `diagnostics-v2.json` 的 SHA-256：
`e4daeb2c8e7a1089dbd06b933700ae5c0eac0888894e7f25e3931760341a6f08`。

## 1. 有截斷問題，但最大問題仍是答案內容

下列為 B1 的互斥分類。384 是 train 與 dev 的合計，用於工程診斷，不能當成
ARC-AGI-2 public evaluation 分數。

| 結果 | Train / 256 | Dev / 128 | 合計 / 384 |
| --- | ---: | ---: | ---: |
| 完全正確 | 18 | 12 | 30 |
| 尺寸正確、內容錯誤，未撞 token 上限 | 180 | 84 | 264 |
| 尺寸錯誤，未撞 token 上限 | 36 | 20 | 56 |
| 尺寸錯誤，撞 token 上限 | 18 | 12 | 30 |
| 無效 grid，撞 token 上限 | 4 | 0 | 4 |

34/384（8.85%）撞上 512 new-token 上限，而且全部答錯。其中 **30 題仍通過
rectangular-grid parser**。所以「380 valid / 384」只證明大多數輸出可解析，
不能證明答案完整，更不能證明解題能力。

350 個正常 EOS 結束的有效輸出，其實測 generated tokens 都等於 raw completion
字元數加一。28 個正解的 digit-row 字元數加一超過 512；這是容量問題的線索，
不是已用精確 tokenizer 驗證的正解 token 數。本次本機未找到該 revision 的
tokenizer，不能把字元估算說成精確 token 證明。

按正解 grid 大小診斷：

| 正解 cells | 題數 | 正確 | 撞上限 |
| --- | ---: | ---: | ---: |
| ≤64 | 147 | 23 | 1 |
| 65–256 | 168 | 7 | 4 |
| 257–480 | 40 | 0 | 2 |
| >480 | 29 | 0 | 27 |

目前 30 題正確答案全部不超過 256 cells。但即使所有截斷題都修好，仍有 320 題
未撞上限卻答錯。增加輸出預算值得測試，不能當成完整解法。

## 2. 候選退步不能歸因於截斷

B1 dev 為 12/128（9.375%），最好的候選 G7/G8 為 10/128（7.8125%）。
所有候選相對 B1 丟失的 dev 正確題，都在未撞 token 上限的情況下答錯。
例如 G8 新增兩題、失去四題；失去的四題是三題內容錯、一題尺寸錯。

B1 instruction 為 107 字元；候選為 643–1,106 字元，加入大量物件、對稱、
分區、尺寸與規則檢查指示。不同候選加入了不同全局偏好，而模型固定使用
greedy、thinking disabled、512 tokens。較長提示可能引入不適用於部分題目的
先驗；目前是觀察與假說，沒有控制實驗證明「長 prompt 本身造成退步」。
也不能從 thinking disabled 推論模型完全沒有隱式推理。

G8 的錯誤原樣複製輸入由 B1 的 train 32 題增至 61 題，dev 17 題增至 23 題。
這與候選要求保留畫布的傾向相容，但仍不能單靠此關聯確立因果。

十組輸出在 dev 的事後正確題聯集只有 16/128；這需要答案 oracle 才能選對輸出，
**不是可部署 ensemble 的分數**。現有提示變體的互補性有限。

## 3. GEPA 的反思資訊與可稽核性不足

實作使用真實 `dspy.GEPA`，不是手寫 prompt loop 冒充 GEPA。不過 ledger 的
十個 proposal attempts 都以 B1 為 parent：實際得到九個 B1 變體與一次中斷，
沒有產生一路改善的十代候選。這不代表 GEPA 一般性失效，也不能假定每輪已
將之前全部候選的失敗綜合到新提案。

`build_codex_proposal_request` 對 GEPA 提供的 reflective examples 依序列化大小
排序，最多放三個完整範例，受 32 KiB 限制。`deterministic_train_feedback`
提供尺寸差異、錯誤 cells 數與 train 正解，卻未提供 stop reason 和實際 token 數。
因此被截斷的 grid 可能被反思模型當成尺寸推理錯誤；proposer 又無權改 token
上限，只能修改 instruction。

保留了 input digest、proposal 與 CLI events，但沒有保存完整 request payload
與可直接稽核的所選 task IDs。不能證明十輪共覆蓋了三十個不同案例，也不能
重建精確的反思覆蓋率。下輪應保存 evaluator-side 的 train-only request，
記錄案例覆蓋、失敗類型、成功回歸保護與每次更動的單一假說。

## 4. 目前主要時間成本在候選評估

九次完成的反思合計 519.078 秒（8.65 分鐘）；九批候選 runner 合計
10,001.013 秒（166.68 分鐘），約 19 倍。這是四卡 session wall time 的加總，
不是 GPU busy time。B1 runner 另為 1,313.260 秒。G2 中斷的時間量測缺失，
不能把其記錄的零解讀為零使用量；排隊、上傳及下載時間也未完整分列。

因此本輪的數據不支持優先縮減反思模型規模。更有價值的是先用小樣本淘汰假說，
只讓有訊號的設定跑完整 384 題，並重用模型 Dataset 與四卡 worker。

## 5. Holdout 是來源相容性失敗，不是模型零分

2026-09-23 後續校正：[budget ablation 總控分析](../arc-agi-2-budget-ablation/control-review.md)
已核對全部 512 題來源相同。根因是舊 gate 把單一 test-index 視圖與完整
multi-test case 比較，不是實際 source drift。下文保留取得完整 snapshot 前的診斷。

最終 kernel 在模型載入前回報 `runtime competition case differs: f3e62deb`。
四卡硬體 gate 已通過，但沒有 generation、checkpoint 或 result.zip。
holdout 準確率不可得；不能填零，也不能宣稱最終泛化比較完成。

既有本機 stage 沒有對完整 512 題做 competition visible-content parity，
runtime 的防線正確拒絕了不相符資料。此次本機未找到當次完整 competition
challenge snapshot，尚不能離線判定 `f3e62deb` 具體差在哪些欄位，或有多少
其他差異。下一次應在 GPU 提交前核對全體可見 inputs / demonstrations；
不需要讀取 holdout answers。不能悄悄替換來源或刪題來修飾原失敗。

## 下一步

依[輸出與推理預算對照計畫](../../docs/plan/2026-09-23-arc-reasoning-budget-ablation.md)，
先做離線 preflight 與小規模模型設定對照，再決定是否恢復 GEPA。
本輪負面結果只回答固定模型、固定無 thinking 解碼與 instruction-only 搜尋的
問題，尚未測量 NVARC 的訓練／適應路線，也沒有提供 85 分目標的進度證據。
