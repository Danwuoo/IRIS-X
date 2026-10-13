# 可直接貼給下一個開發環境的交接 prompt

請接手 IRIS-X 的本地開發移轉。先讀這份 prompt、封包中的 README、CURRENT-STATE.json、TEST-RESULTS.json 與 repo 的 AGENTS.md、Decision0074、run007 v39 transfer 說明。先驗證及還原程式，整理下一輪本地修復方案；此交接不授權新 Dataset／notebook save／RUN，也不授權持續監看。後續發布執行須由我另行明確要求。

你會拿到以下三包、SHA256SUMS 與本文件：

1. `IRIS-X-run007-program-transfer-20261014.zip`：完整 Git tracked 程式、離線 Git bundle（含 main、run006／run007 分支與失敗封存 tag）、code20 的精確 runtime/code ZIP、原救援包與操作說明。
2. `IRIS-X-run007-authentic-inputs-EVALUATOR-ONLY-20261014.zip`：真實 candidate005／006／007、selected13-file state005／006、review／sealed inputs／source proposal、run007 原發布 state、v37 診斷。歷史 evidence ZIP 含評分材料，只能 evaluator-only 保存及雜湊檢核。
3. `IRIS-X-run007-v39-results-EVALUATOR-ONLY-20261014.zip`：已抓回的 exact v39 evidence ZIP、完整選定日誌／內外 closure／ledger／provider snapshot／download receipts／独立診斷及 wrapper 驗證。不要再下載或輪詢這次 run。

把實際新目錄記為 `<TRANSFER_ROOT>`，新的 repo 記為 `<REPO_ROOT>`。先從 SHA256SUMS 核對每包；使用程式包附帶的 `verify_transfer.py --archive <絕對 ZIP 路徑> --sha256 <該包真實 SHA256> --output-root <全新絕對目錄>` 安全還原，或先 `--verify-only`。不要用不受控 unzip 覆寫舊工作區。從程式包的 `history/IRIS-X-run007.git.bundle` clone 新 repo；其 scoped bundle 包含還原 frozen snapshot 所需 Git objects。還原後查 git status／branch／log，再 fetch（有網路時），保留所有未知修改，不 force push／reset／合併 main／移动 tag。公開化、轉帳戶或新資源也未授權。

目前分支 `feat/run007-local-repair-20261013`。實際發布來源 commit 是 `08aaf2f26caeff0c9e80bd1caefc4c1f6e01e077`，原最終提交交付 commit 是 `3f47494bae41aa2457bac95925b1196aa48b8389`；本次移轉 commit 見 CURRENT-STATE.json／bundle HEAD，新增的是移轉工具／文件，沒有修改 reviewed runtime。採用遠端 main 基底 `baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`；local main 仍為失敗 snapshot e951，bundle 另保留 fetched refs/remotes/origin/main，不要混淆或移動 frozen local ref。失敗封存 snapshot `e951604b829497e81bc6e18b32662ff050bd54db`、tag `irisx-code18-run005-snapshot-20261013`，執行來源 `dbf21033b41aff9327cf4f91159df0133529f176`；全都保持不變，不能稱成功基準。

Kaggle 真實狀態：private Dataset `danielwuu/iris-x-learning-agent-code-20261011` ID12504696，最新已核對版本20；notebook `danielwuu/iris-x-learning-agent-20261011` ID138123872，38 是 inactive save，RUN39 在2026-10-14 00:42:14.611118 Taipei 已核對 **ERROR**。Saved source SHA256 `a3076380789de383c1df7c710023d8ca9e9a64a37405547bcebf0e066405d4b9`，與原發布相同；submitted source SHA256 `b70668018453a1bc14a996c54b7e0ea1f470405e492488a4c66dbb7c919da879`。原 epoch1791908053／deadline1791951253（00:14:13–12:14:13 Taipei）與已消耗 claims／時鐘／成本不能因移轉或重建重新使用。

**已證實的內層錯誤**：phase `verify-mapped-wheel-bytes`，ValueError `mapped cuDNN backend differs from exact pinned wheel member`。程序實際載入 `/usr/lib/x86_64-linux-gnu/libcudnn_graph.so.9.8.0`，3,134,416 bytes／SHA256 `8adf356b5509ee8b5f28846a81387ebca6de12ea6b19858f9b2f43c0f0e3fe2b`；固定 wheel 中 `nvidia/cudnn/lib/libcudnn_graph.so.9` 為4,439,912 bytes／SHA256 `787c955dce49091ead850e4536666594095ea9f92a8a08879d8ddad466674657`。安裝後 wheel hashes 完整，但載入不同 system backend；Torch 與 owned API 實測皆90800。run007 沒有解決此選庫問題。為何 loader 選到系統庫仍待查，不要宣稱猜測的原因已證實，也不要放寬 exact wheel／ABI／kernel dev/inode／foreign-backend 拒絕門檻。

下一輪本地開發先查 subprocess 的 loader order、已載入 SONAME／backend 及 owned library 的實際选择，再建一個 system9.8 與 installed9.10.2 混載的代表 CPU ELF fixture。任何重要修復使用 subagent 實作及另一個独立審查；先列有限必要工作清單、平行處理獨立項目，完成受影響 normal／Python-O、CPU 整合、失敗／超時／清理及封包回讀。先建新分支（例如 `feat/run008-local-loader-repair-20261014`，若已存在先查不覆寫）。舊 receipt 只支持原 hash；修改後需新測試／新審查，不能挪用原收據。這些是下一地本地工作，尚無新的 GPU 修復有效證據或提交權限。

v39 evidence ZIP 是41,793,870 bytes，SHA256 `02d5c203747f63a69b50db47de552f3cbccf1fda19cc4d7a73862bb3a3d6be6c`。48 個 member 的 SHA／CRC 全過，僅串流雜湊，不讀答案／grids 語意、不解出進 solver。41 個可用選定檔案全部有實際 receipt；experiment/result.json 與 optional installation excerpt 是404，checkpoint 未宣告。PUBLIC score、result、checkpoint 均 null，public gold 未開啟。不要偽造缺失產品、receipt、hash、closure 或分數。

closure 必須分層如實記錄：原 source-bound helper replay 的 closure_valid=true、operational=false、terminal diagnostic、runtime tree link 正確；helper 不驗證 model closure／VM teardown／billing。內層記錄 model closed／synchronized／settled／stopped=true；外層仍 safe_closure=false／model_stopped=false，worker rc1 已退出且 session empty。不要概括成完整安全成功。原 durable charged counters 為1 load、4 training steps、12 generation calls、348 scoring forwards、434560 input tokens／24 output tokens；屬預留 physical charges，不是 provider billing 或成功科學工作，不能抹成零。

移轉後先用 POSIX／Python3.12／真實 HOME／ext4 TMPDIR，設 PYTHONHASHSEED=0、PYTHONDONTWRITEBYTECODE=1、HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1、HF_DATASETS_OFFLINE=1；依 `tools/arc_qwen_rlvr004_20261013/transfer_handoff_20261014/README.md` 執行 `rebuild_portable.py --repository-root <REPO_ROOT> --inputs-root <evaluator-only還原目錄>/authentic-inputs --output-root <REPO_ROOT>/.irisx/<全新輸出目錄>`。這只重建已消耗 run007，應逐檔比對所有 source proposal 與426-file candidate；不 import provider／讀憑證／新建 epoch／跑 model。原文件中舊機器絕對路徑只作歷史資料，不改 bytes；純 CLI input roots 才改成新位置。重建失敗保留 partial，換全新輸出後重試，不覆寫舊產物。

既有測試限制：run007 focused normal／O 各74 PASS、owned CPU payload與真正 code20 numeric mount PASS；這不代表 GPU 成功。run006 全套1583 tests 中32 fail、68 error、72 skip；本移轉沒有重跑全套。失敗比較88 inherited signatures、12 unresolved；08aaf2f 的 CI 在七個 upstream README governance terms 就 FAIL，unit steps 沒跑。新移轉 wrapper9＋restore helper8，normal／O 各17 PASS，另有獨立審查。owner 最後要求「不要再比對了，把封包和 prompt 產出來」；因此本地移址完整重建已停止、partial 保留，最後封包沒有追加回讀驗證。SHA／manifest 已產出，但不能稱完整移址重建或最後 archive readback PASS，更不能寫全專案全綠。下一地若需要再依 TEST-RESULTS.json 重驗。

保留已有 run006 診斷／owned preparation 分階段真內層例外／stdout stderr／closure、8MiB installation.log 上限、原整體 deadline、owned process 清理與真實失敗狀態。run007 核心只新增 environment_v2／consumer 同步 cuDNN 映射 policy 與相關 adapter，不要從頭改科研流程。未驗證項清楚保留，CPU 不能代替 GPU 驗證。

所有 Dataset pins／Qwen14B model／wheels／資料與已配置 NvidiaRtxPro6000、offline Internet/TPU off、private Docker、ARC3 metadata-only 掛載和每 session43200秒限制見 CURRENT-STATE.json／原 publication manifest。不要讀 ARC3 task data／官方 competition submission。Public answers evaluator-only，保留 PUBLIC120 的120題／167queries完整分母、相同 scorer、科學對照與成本紀錄；長期 public90 不承諾分数。權重／巨量 wheels／原始資料未含入 Git／此程式包，使用原 pinned assets，勿新增購買資源或查剩餘 GPU 配額。

若我之後明确要求發布下一輪，屆時此新 task 是唯一 publisher；使用官方 Kaggle CLI／SDK 在新機器正式登入，不複製任何舊雲端或本機憑證，不使用聊天舊 OAuth code，不改 HOME 或關驗證。先查真實遠端版本與狀態避免重送；完成新 byte review／新 code Dataset／處理完成／notebook source-pins-mount-GPU 回讀，再單次 RUN。提交後必要一次確認 exact identity/source/settings/當下真實狀態即交付停止；QUEUED 如實 QUEUED，不為等待 RUNNING 輪詢、不 watcher／自動重提。這段是將來明確授權後的規則，現在不得據此送出。

交付下一地工作的結果時，列新分支／commit、程式／部署包與雜湊、修改項、正常／O與CPU測試限制、实际 provider 狀態（若未授權新查詢就保留本次觀測時間），以及任何需要我後續提供的 GPU 輸出。不得把 run39 或任何尚未驗證版本標成成功科學基準。
