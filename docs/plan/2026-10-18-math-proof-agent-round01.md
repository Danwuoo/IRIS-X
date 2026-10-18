# MATH-001：研究方向與第一輪可執行反例研究

Owner direction 2026-10-18：研究數學、形式化驗證與數學工具，以AI進步為目的；聚焦證明導向工具增強Agent，同時改善證明與答對率，不以prize為開發目標。預定硬體Kaggle TPU v5e-8，合作聯絡延後。

Base `develop@9389f433a1fbe41d25f8ce1248fde07f7ce9250d`。新branch `feat/math-proof-agent-20261018`。不修改或合併main、develop、ARC或歷史分支。本輪使用相容管理ID `line-b`，任務為MATH-001；不為領域命名大改共用schema。

## 第一輪交付與驗收

- M1-DIRECTION：主問題、方法順序、明確瓶頸決策；不把ARC的SFT/RL比較複製成數學科學契約。
- M1-SOURCES：讀原文／原repo，區分来源事實與設計推論。Yi-Chia相關方法保持OPD／蒸餾原術語，後續Pochi版本不冒充冠軍當時版本。
- M1-PILOT：先記protocol，再執行32個自編精確證書／反例案例及normal/-O控制。產生source／protocol／panel指紋，保留實際結果，不宣稱模型增益或Lean形式化完成。
- M1-EVAL：答案、證明、形式化對齊、錯誤放行、成本及不確定性分開；下一輪主要比較同資源上限的independent sampling與repair。
- M1-HARDWARE：v5e-8記憶體是分散晶片，不誇大吞吐或模型可行性；列出实际preflight而不是啟動Kaggle。
- M1-PRESERVE：catalog與task/BOARD連通，原task/reviews不改寫；原src/tools/tests/CI/ARC研究保持不動。任何完整checkout/CI未驗證項目如實記錄。

此任務先做public source review和stdlib CPU pilot；不下載權重、未公開資料或移轉封包、不訓練、不執行原aggregate、不聯絡研究者。Code checkpoint記錄研究程式和protocol；delivery追加結果、交接與review_ready，不自行填獨立review。

## 下一個實作，不在此輪假稱完成

MATH-002的工程目標是一個固定Lean/Mathlib worker＋單一TPU模型adapter，先8題自己編寫的integration cases，再凍結24題機制pilot（詳EVALUATION；目前未選題，非已登記benchmark）。以Qwen3-4B作runtime候選、Goedel-Prover-V2-8B作formal候選；須先核對checkpoint/template/license與數值相容，不能用純fixture代替模型輸出。

主要三臂為M-DIRECT（低成本參考）、M-SAMPLE（4獨立提案）和M-REPAIR（1初稿＋3修復）。兩個4-call臂有相同輸出／工具／wall上限並報實際成本；不是與DIRECT的一次呼叫假裝等算力。

先建立反例、missing assumptions、sorry/axiom、wrong theorem、timeout、unsupported和非法工具輸入控制。沒有Lean或TPU環境時只交付離線部分及BLOCKED說明，不偽造性能結果。取得模型輸出後以題目層級配對統計和新family複驗決定是否提升為SFT／蒸餾／RL研究，不先建立trainer。

## 本地閱讀啟動

保留既有未提交檔案，fetch遠端後在獨立worktree讀取此branch；不要在ARC/main/develop上直接開始修改。先讀AGENTS、line-b STATUS/RESEARCH、research/math-proof-agent及MATH-001 HANDOFF，再為MATH-002建立task與必要小型程式PR，base為本數學線。所有merge維持明確授權，不自動整合。
