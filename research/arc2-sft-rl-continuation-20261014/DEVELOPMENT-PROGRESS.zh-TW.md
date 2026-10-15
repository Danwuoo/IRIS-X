# ARC-AGI-2 當前開發與實驗進度

更新：2026-10-15 UTC。本頁只維護目前狀態、阻礙與下一步；研究問題與固定設計見
[研究主頁](README.md)，歷史 E0–E52、來源指紋及更新時間線見[工程歷史](archive/engineering-history.zh-TW.md)。

**本輪真實 A/B/C 尚未完成，沒有新的 PUBLIC120 分數。**
現在的狹窄執行修復，是為了取得同一個 ARC-AGI-2 比較的證據，不是更換研究方法。
使用者已授權依既有 run007／run008 離線 notebook 模式持續開發、Kaggle 執行、分析 terminal／結果，
再按既有研究條件進入下一輪；本地端維持唯一 publisher，code 與 weights／wheels／資料 Dataset 分離鎖版。
同範圍例行續接不逐輪重新詢問，但現有 UNKNOWN 與各次 admission 不因此豁免。

## 一、文件責任與更新規則

- 研究主頁說明問題與假設；[方法總覽](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)保存唯一實驗順序。
- 本頁記當前事實；[交接](OFFLINE-LOCAL-HANDOFF.md)記單一路徑；固定驗證與歷史審查不回寫成新結果。
- 每次只寫實際驗證的 source／scope／結果；本地回報、CPU、native、Git、CI、模型與分數分開。
  舊失敗、UNKNOWN、來源與時鐘保留；尚未取得的結果不補 0 或 PASS。

## 二、目前基線與證據索引

研究分支為 `feat/arc2-sft-rl-continuation-20261014`；本地與遠端已成功 fast-forward 到
[`e491ba4be3562d48d78f4f615a1dd155bcdc0cfc`](https://github.com/Danwuoo/IRIS-X/commit/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc)。
這是本次修復的已保存 parent 基準；本頁隨新修復同一 commit 保存，
確切交付 SHA 以接收時 Git HEAD／遠端 readback 為準。較早 `fix/arc2-abc-local-execution-20261015`、
`fix/arc2-abc-portable-publication-20261015` 與 f5／a724 checkout 保持歷史身分；不覆寫其證據。
本次修復另有 CPU 證據；不得沿用 e491 的本地驗收結論。

| 項目 | 最後已確認的事實 | 證據範圍與限制 |
| --- | --- | --- |
| Stage 0／Stage 1 離線工具 | inert plan、report analysis、training audit adapter、upstream 逐軌跡 loss 與 shadow 規格已交付 | [Stage 0 審查](offline-continuation-review.md)、[Stage 1 審查](stage1-independent-review.md)；不是模型 hook 或 ARC 分數 |
| AF3 真正元件 | `TrainingSample`、`DDISLoss`、`MeanMetricState` 實際 CPU 呼叫及合成 loss／gradient parity 已成立 | [整合與 proof](agent-factory3/integration.zh-TW.md)；無真實 Qwen／LoRA／GPU 效益證據 |
| e491 本地材料與 no-auth | 本地回報：425 檔 canonical candidate 兩次重建逐 byte 相同；真實獨立 reviews、lineage、純 validate 與同 owner no-auth 通過，實測 12.6506 秒 | 僅適用該來源與當次材料；不證明之後 readiness、完整 JIT、upload 或 RUN 成功 |
| 最新 readiness 阻礙 | 本地回報，2026-10-15 14:20:33 UTC：在 worker 啟動前以 `supervisor_lease_failed` 拒絕 | 新 ddd session 為 UNKNOWN、closure false；STATE 共 90 檔，原 83 檔逐 byte 未變；沒有 upload、RUN 或 A/B/C |
| 既有歷史恢復 | 原 29 份 STATE 證據及原 failed-open 的 UNKNOWN／closure false 保留；先前 f5 恢復與 a724 readiness 只支持各自當次結果 | [E41–E52 原紀錄](archive/engineering-history.zh-TW.md#e0e52-與原始證據補充)；舊恢復不能消除新 UNKNOWN |
| 本次雲端驗收 | 作者與獨立 reviewer 各自 545 normal／545 `-O` 通過；28 靜態 pins 正確、47 檔 review 前後不變。未重跑無變更的完整 suite | [固定 VALIDATION](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json) 的 `streamlined_release_revision`；前版完整 suite 的 1,621 tests／2 failures／35 errors／74 skips 與 37 個既有 failure/error IDs 留在 `material_successor_revision` |
| Repository／CI | 仍有 6 項既有 README invariants 缺詞；先前精確 CI 失敗，unit／packaging skipped | [歷史 CI 與失敗收據](archive/engineering-history.zh-TW.md)；focused 通過不表示完整 suite／CI 綠燈；本次 layout 仍同 6 項；遠端 CI 需按最後精確 commit 另核對 |
| 真實研究結果 | A/B/C、原始 training audit、真實 replay／LoRA 更新、B/C 成本匹配及 sealed PUBLIC 評分仍未取得 | PUBLIC120 固定 120 tasks／167 queries；未知不是 0 分，不能宣稱 RL 有效或無效 |

14:20:33 本地去敏 failure report SHA256：
`1364f2dade49a8de44d3e8663b1d21e0d8ecdd30be7979d671b2528548ae8c98`；capture SHA256：
`69d2004240191cfeac995add924633dfa0123f1c16f87f288910ac784dcdd79f`。
原件留在本地，未公開；上述 hashes 只識別回報，不等於新的 closure 或放行收據。

## 三、任務、依賴與下一步

| 工作 | 目前狀態 | 下一個完成條件 |
| --- | --- | --- |
| 狹窄跨 OS lease 修復、歷史恢復／目前 release 分離、穩定 collector bootstrap 與 pre-worker disposition | 離線實作與獨立審查完成；545／545 測試通過。本地新版本 native、90 檔 disposition 與 canonical 尚未驗收 | 固定 commit readback 後交本地一次受影響驗收；重用不變元件，不再要求額外 material-lineage／雙 candidate 交接門檻 |
| 本地接收與新 UNKNOWN 處置 | 受阻於上列 readiness 失敗 | 以新版本的真實證據處理精確事件；保留原 90 檔及歷史子集，不重跑已完成的舊恢復、不補造 closure |
| 原 A/B/C 執行 | 未執行／未驗證 | 當次授權、全部原 admission 與目的端驗收成立後，依[單一交接流程](OFFLINE-LOCAL-HANDOFF.md#63-唯一-publisher-的有限提交與監看路徑)續接至 terminal 與完整可取得結果 |
| 科學判讀與下一輪 | 待真實結果 | 驗證 reward、replay、checkpoint、全成本、closure 與完整 scorer，再按[方法決策表](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)續接已授權研究；ERROR 不代表方法成功 |

下一步交本地驗收固定修復，再依既有 notebook 路徑執行與監看到真實結果。研究設計仍為 SFT256 A、固定互斥 64-slot RL batches B、
匹配完整 B model-phase wall 的 extra-SFT C；no-TTT、dev 選擇與 PUBLIC120／167 不變。
AF3 companion 可在原 audit 產生後分析；真正 AF3 模型 hook 仍需另立 successor，
不能成為首次原 A/B/C 的循環依賴，也不能偷偷換掉 frozen trainer。

## 四、技術設計與原始來源

完整 batch／逐軌跡 loss 的設計已集中至 [AF3 Stage 1 整合](agent-factory3/integration.zh-TW.md#7-stage-1完整-batch與逐軌跡續接)，不在進度頁重複維護。

## 五、離線實作與驗收契約

見 [AF3 的 audit／reduction／shadow 契約](agent-factory3/integration.zh-TW.md#離線實作與驗收契約)與 [Stage 1 工具介面](../../tools/arc2_abc_continuation_20261014/README.md)。

## 六、本地模型證據的驗收契約

見 [AF3 模型驗收表](agent-factory3/integration.zh-TW.md#本地模型證據的驗收契約)；來源宣告與 CPU 梯度不能替代真實模型證據。

## 七、既有決策條件

只見[方法總覽第 7 節](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)。本頁不另立方法計畫。

## 八、離線交付與後續更新驗收

只在來源、測試、獨立審查與精確發布結果可核對後更新對應狀態；本次新文件與未發布程式不自稱已通過舊審查。

## 九、開發與本地執行循環

依[單一交接流程](OFFLINE-LOCAL-HANDOFF.md)取得實際結果，更新本頁；完成事件移入固定歷史，保留失敗與成本。

### 更新紀錄

舊時間線完整移至[工程歷史](archive/engineering-history.zh-TW.md#原更新紀錄)；不再於此累積第二份歷史表。
