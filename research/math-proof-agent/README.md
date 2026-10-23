# IRIS-X Math：證明導向的工具增強 Agent

建立日期：2026-10-18。分支：`feat/math-proof-agent-20261018`；起點：`develop@9389f433a1fbe41d25f8ce1248fde07f7ce9250d`。

本線研究 **AI 如何在有限計算下，同時提高答案正確性、完整證明能力與可靠的自我修正**。IMO／Putnam 是能力觀察面，不是獎金交付目標。研究數學、形式化驗證和數學工具是長期方向；是否延伸到研究輔助或自主提出新猜想，留待有能力證據後另定。

## 閱讀順序

| 文件 | 用途 |
| --- | --- |
| [DIRECTION.zh-TW.md](DIRECTION.zh-TW.md) | 主問題、方法優先順序、架構與決策條件 |
| [LITERATURE.zh-TW.md](LITERATURE.zh-TW.md) | 第一輪原始來源評估，包含 Yi-Chia Chen 相關公開實作 |
| [EVALUATION.zh-TW.md](EVALUATION.zh-TW.md) | 答案／證明雙軸、資料隔離、等成本對照與錯誤分類 |
| [TPU-PLAN.zh-TW.md](TPU-PLAN.zh-TW.md) | Kaggle TPU v5e-8 的可行性與尚待實測項目 |
| [ROUND001-RESULTS.zh-TW.md](ROUND001-RESULTS.zh-TW.md) | 已執行的證書與數值檢查反例實驗；不是模型成績 |
| [ROUND002-RESULTS.zh-TW.md](ROUND002-RESULTS.zh-TW.md) | MATH-002 實作、真實本地 Lean／數值控制與 Kaggle 提交阻塞；尚無模型比較 |
| [round002/](round002/) | 固定模型 adapter、受限 Lean worker、有界 controller、監看與預算狀態入口 |
| [sources.json](sources.json) | 原始來源、讀取範圍、版本／blob 與限制 |
| [round001/](round001/) | 可重跑的標準函式庫實驗與預先記錄的 protocol |
| [實作計畫](../../docs/plan/2026-10-18-math-proof-agent-round01.md) | MATH-001 驗收及下一輪實作邊界 |
| [開發交接](../../docs/verification/MATH-001/HANDOFF.md) | 精確程式／執行指紋、環境與未驗證項目 |

## 工作線身分

人類可讀名稱是 **Math / proof-oriented tool-augmented agent**。本輪沿用既有管理 ID `line-b`，不偷偷修改 `core/arc-agi-2/line-b` 的硬編碼 schema，也不建立第二套管理系統。`docs/workstreams/line-b/STATUS.md` 是此研究的工作線入口。原 `src/irisx/domains/line_b/` 六案例 lookup fixture 保持原樣；其成功不等於數學能力。後續正式 production adapter 命名／schema 泛化須用獨立小型共用變更，不在研究文件 PR 混入。

## 本輪邊界

完成公开原始來源研究、研究方案及 CPU 精確有理數證書 pilot。沒有調用目標模型、沒有 Lean kernel 執行、沒有 TPU／Kaggle 操作、沒有 SFT／RL／TTT、沒有下載模型／移轉封包。所有研究結果都要區分這些範圍；不因建立 branch 或 CI 綠燈而宣稱方法有效。未聯絡任何外部研究者；潛在合作留待使用者日後決定。
