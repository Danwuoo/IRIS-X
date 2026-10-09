# N4分析與N5–N14交付摘要

## 結論

N4確實執行了93次模型呼叫，但program arms沒有進入真正的demo驗證：61份source格式都正確、45份可parse、0份符合原本的受限語言。主要問題是模型重寫已提供的components/copy_grid，帶入while與list methods並浪費tokens。A direct-grid為1/8；B與C皆0/8；C另有3個context exclusions。

本次以相同61份原始source做CPU重播。保留原runtime8，另外建立有gas與OS限制的bounded-v2。結果從0提高到29份AST-admitted、23份完成demonstration執行，但仍沒有任何source通過全部demos，也沒有正確query答案。因此已確認「介面不相容」與「規則推理不足」是兩個不同問題；不能把admission改善當成agent accuracy提升。

## 十份notebooks

1. N5：同一批source的新舊語言CPU重播
2. N6：明確的host-owned toolbox，對照完整語言說明
3. N7：typed composition IR，對照bounded Python
4. N8：精確syntax/AST診斷，對照generic static feedback
5. N9：deterministic objects，對照raw grids
6. N10：真正demo feedback，對照redacted feedback
7. N11：best-parent repair與有界記憶，對照independent roots
8. N12：uniform／smoothed neural feature prior／hard-pruned CPU synthesis
9. N13：512筆自寫family的F/G/P/R curriculum製作與驗證
10. N14：在N3已測過的32題上整合比較direct-grid與預先定義方式選出的agent

N5與N13是CPU-only工程實驗。其餘notebooks是可手動執行的分階段模型實驗，不是已完成的GPU結果。全套若每個gate都通過，上限672次model calls、1,376,256新tokens。現在全部是private inactive QUICK_SAVE，GPU／TPU／Internet關閉，manual switch為False。

## 已完成的實測

- N5：122次真實隔離CPU驗證；每個language各61個reservation，完整保留分母
- N13：512個episodes、1,024次真實隔離CPU驗證，0未知usage，3,832,550步
- F與P/R使用相同raw-source target格式；F只複製已提供的程式，不能冒充semantic learning
- 成功witness／相同repair target共用一次驗證，另一個call驗證確實會出錯的semantic mutation
- 八個明確family在augmentation之前固定分成六個train、兩個validation；不是ARC泛化證據，也不是primitive-disjoint保證
- 每份notebook的停用路徑、embedded hashes、source symlink防護、前置gate與錯誤prior的BLOCKED路徑都有CPU測試

詳細測試数量、確切hash與獨立review在VALIDATION.md與evidence目錄。Harness使用mock model回應的測試只證明調度／隔離／記帳，不證明模型能力；program verifier則真的執行隔離CPU子程序。

## 邊界與下一步

N5–N12固定使用原8題已曝光工程題。N14使用tuning[8:40]，與這8題不重疊，但這32題已被N3測過，仍不能稱為新holdout。136題confirmation完全保留。

N9 object view在33067df9必定超過6144-token prompt cap，因此4個slots會保留為excluded；若N14選到object policy，a096bf4d亦同。所有raw grids都保留，不截斷、不換題。N14只有完整取得所有指定來源reports或合法admission-BLOCKED收據，且至少一個qualifying agent確實解出題目時才會開始。

沒有進行新的GPU、SFT、TTT、RL、付款或competition submission。Granite仍是唯一已驗證的offline模型；Qwen3.5-9B、Seed-Coder8B與4×L4 deployment留待真正檢查assets與執行條件後再研究。本次的F/G/P/R資料也不能當成訓練效果。

程式time limits不是VM計費停止器。未來手動跑完後，仍須自行停止VM。
