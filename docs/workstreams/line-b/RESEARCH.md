# Math：研究入口

本線目的：推進 AI 的數學推理與可靠驗證，**不是以領獎作開發目標**。初期聚焦證明導向的工具增強 Agent，同時衡量答案正確性及完整證明；IMO／Putnam是能力觀察面。研究輔助與自主數學發現留待基礎能力可測後另議。

主問題：在固定模型與計算上限下，命題對齊、證明分解和可信錯誤回饋，是否比追加獨立採樣更有效？

| 讀取順序 | 文件 |
| --- | --- |
| 方向 | [DIRECTION](../../../research/math-proof-agent/DIRECTION.zh-TW.md) |
| 原始來源與方法判斷 | [LITERATURE](../../../research/math-proof-agent/LITERATURE.zh-TW.md) |
| 答案／證明／成本的評估 | [EVALUATION](../../../research/math-proof-agent/EVALUATION.zh-TW.md) |
| 預定TPU限制 | [TPU-PLAN](../../../research/math-proof-agent/TPU-PLAN.zh-TW.md) |
| 第一輪已執行結果 | [ROUND001-RESULTS](../../../research/math-proof-agent/ROUND001-RESULTS.zh-TW.md) |
| 第二輪實作與執行阻塞 | [ROUND002-RESULTS](../../../research/math-proof-agent/ROUND002-RESULTS.zh-TW.md) → [MATH-002 HANDOFF](../../verification/MATH-002/HANDOFF.md) |
| 任務與交接 | [MATH-001](../../management/tasks/MATH-001.json) → [HANDOFF](../../verification/MATH-001/HANDOFF.md) |

方法優先順序：固定現成模型＋數學工具＋verify/repair；基線成立後再按瓶頸選SFT／蒸餾、RL或TTT。不能把學姊相關公開OPD方法改稱RL，也不能把LLM verifier分數當成形式化證明。

首輪只取得有限代入與精確證書的受限反例證據；尚未取得模型增益或Lean核驗。第一個真正模型對照會保留獨立採樣強基線，並對數值正確但證明不完整分開計分。

管理ID暫用`line-b`；舊lookup fixture不改寫成數學成果。此處只路由研究，任務state以統一task record為準，不新增第二份進度看板。ARC既有研究問題、實驗與分支完全不變。
