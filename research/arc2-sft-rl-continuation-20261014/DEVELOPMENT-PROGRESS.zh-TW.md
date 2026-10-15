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

研究分支只有 `feat/arc2-sft-rl-continuation-20261014`。啟動修復已發布為
[`0af57780d61cc72c759fa9b67330bb655abcb761`](https://github.com/Danwuoo/IRIS-X/commit/0af57780d61cc72c759fa9b67330bb655abcb761)，本地已核對部署／pins，但尚未提交 successor；實際 Kaggle v41 使用 84a5。
多輪發布修復已發布為 `0d3524caba46a4d3944d2f1686dd388f0833dc61`。本頁與歷史／即時
context 分離修復同一 commit 保存，交付 SHA 由接收時 HEAD／遠端 readback 核對。歷史 fix refs、
f5／a724／e491 checkout 與原 UNKNOWN 保留；[前輪進度](https://github.com/Danwuoo/IRIS-X/blob/84a5a1f870c42899f3bea79996d1b9360c4bfee9/research/arc2-sft-rl-continuation-20261014/DEVELOPMENT-PROGRESS.zh-TW.md)
保存 lease 失敗與修復前的精確證據，不在本頁重複累積。

| 項目 | 最後已確認的事實 | 證據範圍與限制 |
| --- | --- | --- |
| Stage 0／Stage 1 | 離線計畫、report analysis、training audit adapter 與 upstream 逐軌跡 loss 已交付 | [Stage 0](offline-continuation-review.md)、[Stage 1](stage1-independent-review.md)；無模型 hook 或 ARC 分數 |
| AF3 真正元件 | `TrainingSample`、`DDISLoss`、`MeanMetricState` 實際 CPU 呼叫及合成 loss／gradient parity 成立 | [整合與 proof](agent-factory3/integration.zh-TW.md)；真實 Qwen／LoRA／GPU 效益仍未知 |
| 84a5 本地與發布 | 本地 native10、WSL caller-death、pre-auth、真實 90 檔 disposition、canonical admission 通過；code Dataset v21 的 269 檔／15,849,580 bytes numeric readback 相符 | inactive40 → active41 真正提交；所有 9 個 native sessions closed，原 995／ddd UNKNOWN 原件不變 |
| v41 真實終態 | 2026-10-15 15:58:28 UTC 首次觀察 ERROR；Internet OFF、RTX Pro 6000、private | [原 notebook](https://www.kaggle.com/code/danielwuu/iris-x-learning-agent-20261011)，kernel ID 138123872 不是 scriptVersionId；native closure 不證明遠端 VM teardown |
| 啟動原因 | notebook 的 ambient interpreter 在離線環境建立前查固定 cuDNN，distribution 存在但 version 不等 9.10.2.21；停於 parent-environment-policy | ambient 實際版本與 backend 是否載入未知；prepare caller 同排序風險尚未執行。`preparation_failure:null` 另使 collector 拒絕 schema |
| 已取回證據 | 五份 numeric41 outputs 各有 HTTP200、bytes／SHA receipt：startup diagnostic、preparation request、original request、operator、outer notebook | 五份不是全 inventory；outer notebook 無 execution outputs，不能當官方 execution log。模型／audit／score／cost 其他檔存在性未知 |
| 已發布的啟動修復 | 兩個 deployment-only callers 改用無模型準備環境；真正 installed parent／worker exact-byte gates 保留。collector 只多接受原 schema 加 null 欄位 | [修復範圍與 CPU 測試](../../tools/arc_qwen_rlvr004_20261013/preparation_environment_repair/README.md)；新增 runtime policy 一檔及衍生 self-pin 一檔，其餘 257／259 與 A/B/C 不變；新 source/archive 正規重綁，canonical／GPU 待本地驗收 |
| 多輪續接 | 0d3524 已隔離每輪 publication／collector 目錄，native STATE 與全域鎖共用；本地18:03 fresh no-auth 停於舊f5永久 same-boot 字串 gate | 原1,686檔完全不變，未新建 native claim／canonical／run、未 provider。CIM boot值變1.802125秒，host／Windows／source／runtime相同；符合校時漂移但未證明 same boot，不拿猜測當PASS |
| 歷史／即時 context 修復 | 原封存Restart＋reconciliation在原completion time重驗；fresh host／source／runtime／closure另核對，封存events及live STATE前後綁定 | 只支援現有f5原件的12.629秒歷史間隔，保留原120秒限制；later UNKNOWN／refresh／publication變更仍阻擋，不加BootID框架、容差或重啟 |
| Repository／CI | 0af 精確 CI 失敗：6 項既有 README invariants 缺詞，unit／packaging skipped | 本次 focused 驗證見 [VALIDATION](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)；新遠端 CI 依最終 commit 另核對，未重跑不變完整 suite |
| 真實研究結果 | 原 A/B/C 已提交但未進模型階段；training audit、更新、B/C 成本匹配及 PUBLIC 評分均未取得 | PUBLIC 固定 120 tasks／167 queries；未知不是 0 分，也不是 RL 無效的結果 |

v41 startup diagnostic SHA256：`0ba5efaf361da5336338a0ff170728ea7cf96aa1af447d74d5f770e0ff0de069`。
CPU 另以真正 pinned offline guard 重現子程序增加 6 個固定環境鍵、與舊 loader 全等檢查不相容；
新 policy 在 exec 前綁定同樣固定值，保留全等與所有 byte/map 檢查。這是下一邊界的 CPU 發現，並非 v41 已執行到此。
原 epoch `1792079687`、global deadline `1792122887` 保留，不重設；去敏投影不能替代原件。
現有 competition metadata association 沿用較早版本；材料仍是固定 training/1 與 PUBLIC120/1，
沒有把研究改成 ARC-AGI-3，也不為這項既有掛載新增修改。

## 三、任務、依賴與下一步

| 工作 | 目前狀態 | 下一個完成條件 |
| --- | --- | --- |
| 兩 caller／guard 契約／collector schema 修復 | 0af 已發布；作者與獨立 reviewer 各 613 normal／613 `-O` 通過（46 準備、9 組裝、558 bridge） | 科學 runtime／archive 與 native 七件來源在本次 bookkeeping 修復中沿用，不重做未變驗收 |
| 多輪 publication／collector 續接 | 0d3524 的作者／獨立review每模式599項PASS維持歷史證據；本次最終bridge每模式600項、獨立context每模式70項PASS，精確hash見VALIDATION | 固定新commit後，本地以真正舊manifest／1,686檔驗收一次，fresh no-auth及remote bracket成立才沿原程序提交；已驗證且未變元件不重做 |
| 原 A/B/C 下一輪 | 沿原 run007／run008 notebook 模式；未提交新 run | fresh remote versions/status → code 與 inactive 回讀 → 一次 JIT RUN → 持續監看到 terminal／可取得結果；版本由真實觀察推導，不預先保留 22／42／43 |
| v41 官方 log／inventory | 現有 bridge 尚未支援；SDK 0.1.37 可送 numeric version_label，但 response 無 version/source echo | 另作最小唯讀支援，不阻擋已確定的啟動修復；完整分頁與 numeric bodies／log attribution 分開，不能靠 latest CLI 補稱 exact41 |
| 科學判讀 | 待真實模型結果 | reward、replay、checkpoint、全成本與完整 scorer 成立後，才按[既有方法決策](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)決定下一變因 |

研究設計仍為 SFT256 A、固定互斥 64-slot RL batches B、匹配完整 B model-phase wall 的 extra-SFT C；
no-TTT、dev 選擇與 PUBLIC120／167 不變。AF3 companion 在原 audit 產生後分析；
真正 AF3 模型 hook 仍需另立受審查 successor，不能偷換 frozen trainer 或阻擋首次原 A/B/C。

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
