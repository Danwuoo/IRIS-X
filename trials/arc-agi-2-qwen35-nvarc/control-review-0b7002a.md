# 階段 4–5 獨立驗收：0b7002a

日期：2026-09-25。基準：main `0b7002a1d066ad4f598f88bcd5d14be8eb590c01`。
範圍：真實 ARC-SFT checkpoint 接入 TTT／搜尋／排序，以及 SDG sandbox、
teacher 小批次、TRM 訓練／TTT／推論與聯合候選。

結論：**階段 4–5 尚未完成；接受四 L4 的 4B 全參數更新可行性里程碑，
但完整驗收不通過。** 除了尚缺的 4B checkpoint 與 teacher 執行證據，
本次獨立重現兩個實作缺陷。既有文件已揭露規模與執行限制，沒有把
one-step feasibility 當作完整 SFT；本報告進一步記錄驗收發現。

## 必須修復

### F1 — P1：SDG namespace sandbox 可逃出 chroot 看見主機路徑

位置：`tools/nvarc_sdg_namespace.sh:5`、`:21`；
`src/irisx/arc_nvarc_sdg.py:310`。

launcher 以 `--map-root-user` 建立 user namespace，再讓 generated Python
直接在 chroot 內執行，未在執行前移除其再次 chroot 的能力。原始 mount
tree 仍可達。獨立 probe 只在本次驗收目錄建立無敏感內容的 canary，
於 generated `transform` 內先查詢 canary 是否可見，再以第二次 chroot
及向上切換工作目錄恢復外層 root，重查同一路徑。

實際回傳 **`[[0, 1]]`**：隔離內原本不可見的
`/mnt/c/Users/wurre/Desktop/IRIS-X/.irisx/nvarc-acceptance-0b7002a/canary.txt`
變成可見。只檢查這個 review 自建檔案的存在性，未讀取其他主機資料、
未測試主機寫入、未連線，也沒有修改既有產物。

因此 `/mnt/c/Users` 初始不可見、唯讀 `/usr` 與 network namespace 測試
不足以證明 generated-code filesystem containment。真實 teacher 程式
執行前須修復此邊界：使用能可靠限制權限與檔案系統的執行器，或完整
移除 namespace 內的逃逸權限及舊 root 可達性；以此 canary 逃逸案例
新增必須拒絕的回歸驗證，並重新跑 timeout／memory／process／network
與正常 replay。僅增加字串黑名單不構成隔離修復。

### F2 — P2：joint verifier 未套用 source-qwen profile

位置：`tools/nvarc_m2_m3.py:149`；
`src/irisx/arc_nvarc_candidates.py:340`、`:410`。

`tiny_joint` 直接建立 `QwenCandidateBackend` 後使用
`policy="source-kgmon"`，但沒有像正常 `solve_task` 入口一樣設定
`augmentation` 與 `representation`。兩者實際仍是 `irisx`，因此使用
舊 chat grammar、舊 augmentation views，以及按 token 正規化的 NLL，
而非來源流程的 answer sum NLL。

獨立重跑既有 tiny SFT export、同一 task-local adaptation 和 TRM 候選，
在同一模型上比較兩個 profile：

| verifier 設定 | 八視角平均 verification NLL | joint score |
| --- | ---: | ---: |
| 現行入口 `irisx / irisx` | 1.814300537109375 | -0.814300537109375 |
| 明確 `source-qwen / source-qwen` | 1682.2438659667969 | -1681.2438659667969 |

現行值精確重現 retained `tiny-joint-4` 結果。這是格式與計分語意錯配，
不是模型品質變化；目前只有一個 TRM 候選，不能宣稱本次已觀察到名次
翻轉，但多候選時此差異會影響比較尺度及可能的排序。修復需共用來源
設定入口、在 report 綁定 verifier profile，並增加真實模型的 joint
入口對來源 verifier 差分測試。不能只改報告中的 policy 名稱。

## 已完成與尚缺

| 項目 | 獨立驗收判定 |
| --- | --- |
| 公開 ARC 資料 | 已固定 8 train / 8 dev parents，128 train episodes；與模型工程驗證分開，不作準確率宣稱 |
| Tiny Qwen SFT | 真實 Qwen3.5 架構、303,928 trainable parameters、2 steps，含中斷／resume、export／reload；接受本機工程路徑 |
| Tiny SFT → solve | 同一 export 接入 1-step TTT 與 4 次 generation；0 個完整 Qwen 候選、0 次 verifier、缺少 2 個 attempts，尚未實際走完成功候選排序 |
| 真實 4B FSDP | `003` 的 4 個不同 L4 UUID、1 次全參數 optimizer step、240 input tokens、有限梯度及權重更新均通過；沒有 export／resume 4B checkpoint |
| 階段 4 完整鏈 | 尚缺真實 4B ARC-SFT checkpoint 保存／reload，及該 checkpoint 的 TTT → 搜尋 → 有效候選排序證據 |
| SDG replay | 真實 WSL executor 的 10 次執行、5 accepted pairs、saved-response 流程已跑；F1 使 sandbox 驗收失敗 |
| 真實 teacher | 唯一 kernel 實配 2 張 T4，於 4-L4 gate 停止；0 calls、0 tokens，尚未完成 teacher 小批次 |
| TRM 小型路徑 | pinned 真實 builder／model／ACT loss／optimizer，CPU width 32；1 train step、checkpoint reload、1 demo-only TTT step、2 inference forwards、1 candidate；接受小型路徑，無原規模或準確率宣稱 |
| 聯合候選 | 實際是 Qwen 0 + TRM 1，Qwen verifier 8 forwards；F2 使來源排序語意驗收失敗，尚缺兩分支均有真實候選的整合證據 |

## 獨立驗證及證據

- `python tools/repository_check.py --all`：PASS，213 tests，4 optional skips。
- `.irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_ml_profile.py`：PASS，
  25 tests，zero skips。包含實際 tiny ML 及 WSL 測試，但未覆蓋 F1／F2。
- `tools/verify_nvarc_m2_fsdp.py` 對既有 `fsdp-approved-003-lf` 與
  `fsdp-retrieved-003` 重新離線驗證：PASS。
- FSDP result SHA-256：
  `4624b1c4e4c4079d7daf6d0e958d74a0fd4fe5ebe1d1559a9a7faf28b5ef28ba`。
  最高 CUDA allocation 9,426.913 MiB/rank；step wall 6.324 秒。
- F1 canary probe：`[[0, 1]]`；F2 真實 tiny-model probe：上表兩種設定。

本機重現程式與新產物在 `.irisx/nvarc-acceptance-0b7002a/`：
`probes.py`、`sandbox-probe.json`、`joint-profile-probe.json`、
`joint-reproduced/result.json`、`fsdp-independent.json`、`repository.log`、
`ml.log`、`joint-probe.log`。本報告保留方法、觀察值與判定；ignored
檔案不單獨充當永久證據。原始模型、已執行 package、result 與 trial
identities 均未更動。

下一個修復範圍應先處理 F1／F2 與回歸驗證，再補齊 4B checkpoint
訓練／保存／reload／下游鏈，以及 teacher 實際產生與 sandbox replay
的整合證據。本次未啟動新的 Kaggle、teacher、外部 retrieval 或 scoring；
Decisions 0028–0030 已消耗的執行額度沒有因驗收而恢復。
