# 階段 1–3 獨立驗收：9198fd4

日期：2026-09-24。範圍：owner 指定的完整來源包、上游程式接入、差分驗證。
基準：main `9198fd4`，檢視 `70385f2..9198fd4` 的三個開發提交。

結論：**主要整合與目前測試通過，來源重建工具仍有兩項可重現缺陷，
階段 1–3 暫不作無條件完成驗收。** 這不是要求提前完成後續 GPU/SFT 工作。

## 獨立重跑

- `python tools/repository_check.py --all`：PASS，208 tests，4 個既有 optional skips。
- `.irisx/nvarc-ml-venv/Scripts/python.exe tools/nvarc_ml_profile.py`：19 tests PASS，
  zero skips，包含 source differential 與 tiny 真實 Qwen3.5/PEFT。
- strict profile 的離線 source verifier：9 個 Git repositories、2 notebooks、
  9 個 bound code files 通過。實際來源樹的 tracked status 乾淨。
- 控制 task 另用臨時 Git fixture 及模擬 Kaggle response 重現下列兩項缺陷。
  沒有修改真實上游 snapshot、執行 notebook、網路取得或啟動 GPU。

本機 log/probe 位於 `.irisx/nvarc-acceptance-9198fd4/`：
`repository.log`、`ml.log`、`probe_source.py`、`source-probes.json`。
本報告保留結論與程序，ignored logs 不單獨充當永久證據。

## F1 — P2：完整來源驗證漏掉 tracked 工作樹變更

`tools/nvarc_source.py:39–59` 比對 HEAD、submodule commit、少數 notices 與
九個列名檔案；`git submodule status` 不表示各 repository 的工作樹乾淨。
HEAD 不變時，未在 code_files 中逐一列名的 tracked source 可被修改或刪除，
仍回報 `source_ready: true`。

重現：建立一個有 `bound.py`、`other.py` 的臨時 Git repository，commit 後
只將前者放進 code_files；clean verify 通過。修改 `other.py`（Git 顯示
`M other.py`）再 verify，仍通過；刪除它，再 verify 仍通過。
此案例直接呼叫交付的 `verify`，沒有 mock Git 或 verifier。

修復要求：逐一驗證 root 與 recursive submodule 的 index/worktree 相對
pinned commit 未變，或建立完整 tracked-file identity 驗證；另測 missing、
modified、staged、submodule dirty 等情境。清楚處理 untracked Python 檔案
可能影響 import 的情況，避免把執行時新增 source 當成固定 snapshot。
保留正常 cache artifacts 的明確政策，不靠修改上游 bytes 通過檢查。

## F2 — P2：已有正確 notebook cache 仍依賴 current-version API

`tools/nvarc_source.py:85–101` 每次 materialize 都重新要求 Kaggle 當前版本，
沒有先驗證並重用本機 pinned notebook。若遠端從 v10 更新到 v11，已有正確
v10 bytes 的機器也不能 materialize；clean rebuild 則沒有固定版本 fallback。
拒絕不同版本是正確的，但不代表來源已具備穩定的重建方式。

重現：fixture 內放入與 manifest SHA-256 相符的 notebook，模擬 API 回傳
current version 11、manifest 固定 10。materialize 仍發出 current request
並失敗：`fixture current version 11 differs from pinned 10`。
Git materialization 在此案例 mock 為 no-op；外部 API 亦完全模擬。

修復要求：優先 hash-check 並重用有效 cache；提供可顯式匯入且逐檔驗證的
本機 source bundle，或可取得固定歷史版本的來源。乾淨 rebuild、正確 cache
重用、遠端版本改變、下載中斷與 hash mismatch 均需有離線回歸測試。
不要以放寬 manifest 或改用最新版本解決。

## 已接受的進展與限制

已補齊七個 direct submodules 及 ConceptARC nested editor，資料/資產清單有
紀錄。上游 SDG formatter、Qwen augmentation/mask/DFS/NLL/ranking、SFT
dataset loader 與 TRM dataset builder 確實由 hash-bound 原碼執行。
TTT 所有 demonstration 回答的 mask，以及含 EOS 的 summed NLL 差異已有
測試支持的修正。來源 profile 與舊 compact pilot 的預設行為分開保留。

目前差分通過的是文件所述 common bounded domain；長序列停止條件屬本地
延伸測試，不能說所有上游 batch/cache 行為已等價。SFT/SDG/TRM 接入證據
主要在資料入口；NeMo backend、SDG sandbox/teacher、TRM 模型與 4B source
profile 的執行仍留給後續階段，沒有把未授權 GPU 工作列成本次缺陷。

TRM notebook 固定可取得的 v21，文件已揭露原 README 指向的 v18 取得失敗。
本次只接受 v21 為已保存來源，不接受 v18 推論等價或原竞賽完全重現的宣稱。

後續應由原開發 task 修復 F1/F2 並補必要回歸測試，再重跑 repository 與
strict ML profiles。沒有因本次驗收而新增外部執行額度或下一階段授權。
