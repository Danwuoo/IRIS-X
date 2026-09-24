# 階段 1–3 修復後獨立驗收：002f457

日期：2026-09-24。基準：main `002f45764ec2f784049ed83d4ef14a1fc6c36220`。
範圍：完整來源包、上游程式接入及差分驗證，以及前次 F1/F2 修復。

結論：**本次階段 1–3 驗收通過；F1、F2 已獨立確認修復。**
完整 NVARC 方法、真實 ARC-SFT 與後續 GPU 驗收仍未完成，且不在本次完成宣稱內。

## 獨立驗證結果

| 檢查 | 結果 |
| --- | --- |
| `python tools/repository_check.py --all` | PASS；212 tests，4 個既有 optional skips |
| `.irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_ml_profile.py` | PASS；19 tests，zero skips，包含來源差分及 tiny 真實 Qwen3.5/PEFT |
| 真實 pinned source bundle 匯入全新目錄 | PASS；9 個 Git repositories、2 notebooks、9 個 bound code files |
| 正確 cache 的 materialize | PASS；以拒絕網路的 notebook fetch stub 驗證，呼叫次數為 0 |
| 重建副本 root 的未逐檔綁定 tracked source 修改／刪除 | 正確拒絕；復原原 bytes 後通過 |
| 重建副本 TRM submodule tracked source 修改／刪除 | 正確拒絕；復原原 bytes 後通過 |

控制 task 使用既有 `.irisx/nvarc-source-bundle-9198fd4-v4`，其 bundle record
涵蓋 4,821 個 members、267,726,102 bytes，source manifest SHA-256 為
`728c7c43137abe288fcc9eddac2cb77dc927909146aa1b3b661e8bc1e73929a2`。
重新逐檔 size/hash 檢查並匯入
`.irisx/nvarc-acceptance-002f457/independent-rebuild`；設定
`GIT_NO_LAZY_FETCH=1`，不依賴隱性 Git 物件下載完成此檢查。
破壞案例僅作用在這份新副本；既有 source cache、notebooks、模型與執行證據未改動。

本機程序與 logs：`.irisx/nvarc-acceptance-002f457/check_repairs.py`、
`independent-repair-check.json`、`repository.log`、`ml.log`。
本報告保留結論與重現程序；ignored logs 不單獨充當永久證據。

## 修復判定

F1：逐 repository 檢查 pinned HEAD、index/worktree 與 recursive submodules，
另外拒絕 assume-unchanged、skip-worktree、未核准的 untracked/ignored source。
新回歸測試涵蓋 staged changes、nested submodule、被忽略的 Python 檔案及
cache policy。可保留的三種既有 bytecode cache 不作執行來源；adapter 改為
編譯 hash-checked 原始碼，TRM 的 `dataset.common` 也經相同來源檢查後載入。

F2：有效 cache 可直接重用；缺失 notebook 才走顯式取得路徑。已提供完整
本機 source bundle 的 export/import，來源可離線搬移重建；錯誤 hash、
缺失或多餘 members、版本變更、下載或檔案寫入中斷都有對應拒絕路徑與測試。
未放寬 notebook pins，亦未以最新版本替代固定版本。

## 保留限制與後續範圍

- 接受的是已固定的 Qwen v10／TRM v21 source profile。原文引用的 TRM v18
  仍未取得；沒有 v18 parity 或原競賽完全重現宣稱。
- 第一次取得來源仍受上游供應狀態影響。離線重建需要保留已驗證的 bundle；
  沒有 bundle/cache 時，不保證 Kaggle 歷史版本日後仍可下載。
- 上游差分只涵蓋已列明的資料／候選語意與 common bounded domain；原始
  batch KV、packed training、長 context 裁切等差異繼續保留於 reproduction matrix。
- 真實 ARC-SFT checkpoint、完整 SDG sandbox/teacher、TRM 模型訓練／TTT、
  4B source profile 與 Kaggle 整體執行、準確率與規模驗證屬後續工作。

本次沒有新增外部執行授權，也沒有啟動 Kaggle、teacher、付費服務或 holdout 評分。
