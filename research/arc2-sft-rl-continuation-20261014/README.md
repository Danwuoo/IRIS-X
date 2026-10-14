# ARC-AGI-2 研究續接：進度與文件入口

更新：2026-10-14 UTC。工作分支：`feat/arc2-sft-rl-continuation-20261014`。
來源基準：[`cc14bd1a79aac1fe6135017c9e09d4834300675d`](https://github.com/Danwuoo/IRIS-X/tree/cc14bd1a79aac1fe6135017c9e09d4834300675d)。
本頁整合目前狀態；歷史研究／執行文件仍按各自日期解讀。

## 已完成與未完成

| 範圍 | 目前證據 | 尚未建立 |
| --- | --- | --- |
| 方法與實驗次序研究 | repo 固定來源與第一手文獻；SFT／RL／TTT／Agent 條列和決策條件 | 研究候選的本地效益 |
| Stage 0 離線續接 | 來源綁定 inert plan、既有 collector 結構聚合、race-safe JSON I/O；148 normal＋148 `-O`，獨立 review | 原 consumer 完整成功路徑的真實 fixture、完整執行真實性或方法效益 |
| Agent Factory 3 實際套用 | 固定上游三個元件；25 normal＋25 `-O`，獨立 review；CPU 合成 raw-logit loss／gradient 差為0 | production 接線、Qwen／LoRA model replay、optimizer、GPU／成本或 ARC 分數 |
| 下一階段 | [具體開發計畫與驗收項](NEXT-STAGE-PLAN.zh-TW.md) | 新 shadow／streaming successor 尚未實作；沒有訓練啟動 |

### 保存狀態

- Stage 0 已提交並逐檔核對遠端：
  [`0d4d19c71d2c84720d4956b36d8e99108e8c0a2b`](https://github.com/Danwuoo/IRIS-X/commit/0d4d19c71d2c84720d4956b36d8e99108e8c0a2b)。
- 本次後續來源保存單位包含 Agent Factory 3 完整元件、驗證／審查、導覽與下一階段
  計畫。取得本頁所屬的完整 commit，確認其中含有上述模組；`0d4d19c` 僅包含較早stage0。
  最終對外交付須以新的 commit／branch／tree 真實 readback 核對，不能以 tree object
  已保存代替分支已更新。
- 保存歷程：15:44及15:46的 Agent Factory 3 tree 發布嘗試回傳取消；15:54同一操作
  重試後取得 tree。16:06 UTC 的寫入前核對，遠端研究分支仍是 `0d4d19c`，run008 最近
  核對為 `cc14bd1a`。這些是發布前的歷史檢查點，後續 commit 交付另有精確 readback。
- 不更改 main、run008、PR #9 或工程管理支線；本次只改新研究分支的文件與新增模組。

## 文件地圖

1. [方法總覽與固定實驗次序](method-landscape.zh-TW.md)
2. [Agent 架構與來源](agent-architectures.zh-TW.md)、[RL 方法與數學](rl-methods.zh-TW.md)、[研究來源審查](research-source-review.md)
3. [Stage 0 使用說明](../../tools/arc2_sft_rl_continuation_20261014/README.md)、[本地 executor 交接](OFFLINE-LOCAL-HANDOFF.md)、[獨立審查](offline-continuation-review.md)
4. [Agent Factory 3 整合說明](../arc2-agent-factory3-20261014/integration.zh-TW.md)、[可重跑 API／CPU proof](../../tools/arc2_agent_factory3_bridge_20261014/README.md)、[驗證紀錄](../arc2-agent-factory3-20261014/validation.md)、[獨立審查](../arc2-agent-factory3-20261014/independent-review.md)
5. [下一階段準備與驗收](NEXT-STAGE-PLAN.zh-TW.md)

## 不變的研究問題

A=SFT256；B=32 個固定 training parents、最多4個互斥64-slot batch；
C=從同一A做整段 B 額外 model-phase wall 配對的 SFT。固定 dev 選擇、no-TTT，
PUBLIC120 tasks／167 queries，缺 scoring 保留未知。不能因元件更換而增加抽樣、
換 parent、加入 OPSM／entropy／async 或改分母。既有決策觸發條件見方法總覽第7節。

## 驗證分類

- 已發布 stage0 的 [CI run38589963576](https://github.com/Danwuoo/IRIS-X/actions/runs/38589963576)
  在 repository invariants 因原有7項 README findings 失敗；其他3個 matrix jobs cancelled。
  後續測試與 packaging steps 未執行，不算通過。
- 本地歷史完整 suite：1,583 tests、2 failures、35 errors、74 skips。Agent Factory 3
  加入後的 failure/error IDs 與 stage0 相同；環境差異與早期錯誤環境的收據另見驗證紀錄。
- exact upstream `metric_state.py` 帶有 EOF 空白行，新增 vendor diff 有一項格式警告；
  保留原始 bytes，不把 staged whitespace check 說成綠燈。
- 本次文件更新的相對連結與 repository placement 已實測：沒有新的 findings；
  README 原7項缺詞中，`ARC-AGI-2` 已由實際研究標題補齊，現在剩6項既有缺詞。
  沒有更改或豁免 validator。[獨立文件審查](documentation-update-review.md)另列；新 commit CI 只能在真實發布後核對，
  不能沿用 stage0 CI 為新版本結果。上述完整 suite 是文件更新前的實測，未冒稱再次全跑。

目前沒有新的 Kaggle 執行、完整 A/B/C 結果或 PUBLIC 分數。這裡進行離線開發；
本地端後續若執行，仍需自己的來源／材料／權限與完整原始 admission。
