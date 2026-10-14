# 本地 Codex 啟動 prompt：IRIS-X PR 2–4

先在本地 task 介面選擇使用者指定的 **6.1 sol ultra**，把 task 指向 IRIS-X checkout，再貼上以下文字。
模型／模式要用介面或本機版本實際支援的設定；本 prompt 不會替你切換模型，也不提供猜測的 CLI flags。
如果 task 無法看見 effective model / mode，在交接中記錄「不確定」，不偽稱已驗證配置。
完整計畫：[PR 2–4 開發與統一管理計畫](2026-10-14-workstream-pr2-pr4-local-development.md)。

---

你是 IRIS-X 的本地實作 task。請直接完成下述已授權的離線工程，不要只交另一份計畫。
主要任務是依序實作計畫中的 PR 2、PR 3、PR 4，建立統一文件與開發管理系統，然後留下可交回 ChatGPT 獨立驗證的提交與報告。

## 必讀與起點

先讀目前 task 的根 AGENTS.md、實際修改路徑內更窄的 AGENTS，再依序讀：

1. `docs/plan/2026-10-14-workstream-pr2-pr4-local-development.md`（完整規格與 A2/A3/A4 驗收）。
2. `docs/workstreams/README.md`、`docs/workstreams/core/STATUS.md`、`docs/workstreams/line-b/STATUS.md`。
3. `tests/README.md`、`tools/irisx_build_backend.py`、`src/irisx/cli.py`，以及計畫指定的相關模組。
4. `docs/workstreams/arc-agi-2/RESEARCH.md`，並按本階段範圍閱讀其中 R1–R5 的固定原文。既有完整研究文件是設計輸入，不可僅看 run008 工程 handoff。

研究延續補充：必須交付計畫 A2-6／A3-7／A4-7，保留研究主問題、原結果與限制、當前凍結實驗及條件式後續。不要重新選題、把架構 A/B/C 與 run008 訓練 A/B/C 混為一談，或因無新 GPU 分數把研究判成無效。`arc-next-line` 不是新 `line-b`。
跨分支原文可讀固定 GitHub 文件或本地已取得的 Git objects；不為閱讀下載模型、封包或 evaluator inputs。若 task 已啟動，先做補充計畫差異核對並記錄採用 SHA，不重置原分支或重寫 stack。

不要把歷史 AGENTS 的 Active 執行段落當成這次任務，也不必下載或恢復 run008 封包。
取得遠端 `chore/workstream-foundation-20261014` 的目前 HEAD，確認本計畫存在且 `76809c05c9d51de4a9d19e99c09e1dbd70edc9f9` 是其祖先，記錄完整起點 SHA。
先辨識目前 worktree、未提交修改、既有 branches 與 interpreter；不 reset、stash、clean 或覆寫別人的工作。
用新的獨立 worktree 開發；既有名稱撞名時先檢閱其內容，不重置 branch。

## 分支規則

main 固定參考是 `baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`，只用於比較。
run008 保留在 `feat/run008-native-research-20261013` / `cc14bd1a79aac1fe6135017c9e09d4834300675d`，不整支匯入。

依序建立：

- `refactor/workstream-pr2-packaging`，base `chore/workstream-foundation-20261014`。
- `refactor/workstream-pr3-validation`，base PR 2 最終 delivery commit（含通過自測的 code checkpoint 與交接／metadata）。
- `refactor/workstream-pr4-arc-boundary`，base PR 3 最終 delivery commit（含通過自測的 code checkpoint 與交接／metadata）。

各階段用小 commit 留可審查的差異。可以用現有 GitHub 連線推送這三條分支、建立 stacked Draft PR：
PR 2 指向 foundation，PR 3 指向 PR 2 branch，PR 4 指向 PR 3 branch，不要指向 main。
PR 2–4 是階段代號，GitHub 的實際編號由平台分配。
禁止 merge 任何 PR、auto-merge、推送 main、rebase/force-push 已發布歷史、移動 tag、刪 branch。
PR #5 保留 Draft、不合併。若權限不足，保留本地 commits 和 PR 草稿，不假稱已發布。

## 實作順序

先在未修改的 foundation worktree 建 baseline，然後按相同 OS/Python/依賴/啟動條件對每階段 head 比較。
已知原 aggregate 不綠：PR #5 的 Ubuntu / Python 3.14 job 有 1,588 tests、5 failures、96 errors、110 skips。
這不是容許照抄的預期失敗清單。先查具體 test IDs，區分 setup、缺依賴、缺歷史資料、真實 regression 與未判定問題。
建立 `.irisx` scratch；對要求固定 hash seed 的測試，在 interpreter 啟動前設 `PYTHONHASHSEED=0`。
測試輸出／venv 按工作線分開；完整 aggregate 遵守計畫的 workspace-backed TMPDIR、offline flags 與磁碟前置要求。

### PR 2 / WSF-02

先交付統一管理骨架：`docs/management/documents.json`、`tasks/WSF-02.json` 至 WSF-04、產生的 BOARD、
`tools/dev.py status/check/render --check`、模板與有意義的正反測試。
修正正式 wheel 的巢狀 package 收檔、licenses、明確資源 allowlist、RECORD 與安全路徑。
用新 venv 安裝非 editable wheel，在 repository 外驗證 package origin、CLI 和完整 synthetic reference flow。
讓通用 CLI 不在載入／help 階段 import ARC、Kaggle 執行實作；維持既有命令與錯誤語義。
通過 A2，提交程式 checkpoint，再提交 handoff / metadata；記錄最終 delivery SHA，推送並建立 Draft PR。
下一階段由此 delivery SHA 分支，不能遺漏上游交接檔案。

### PR 3 / WSF-03

建立包含 `tests/` 與工具測試的完整 inventory，分離 core / distribution / arc-unit / line-b / management / historical / operational。
用靜態 inventory 選 suite 再 import；不得先 import 全部私有 fixture tests 再排除。
拆開 CI jobs，保留 legacy aggregate 命令與真實失敗；固定 gate 拒絕空 suite、缺 report、異常 skip 和 cancelled。
將管理驗證接到 CI，實作受控 `tools/dev.py verify --suite ...` 與必要 context 入口。
建立 `domains/line_b` 的合成工程閉環，真正使用共用 contracts/engine/package；不是 ARC 改名，不能自選真實領域。
只在新建 checkout／合成 sandbox 模擬缺資料，不刪除任何使用者既有 fixture。
測試兩線獨立執行、輸出不碰撞、負例與 package tampering。通過 A3，留下第二組 checkpoint、handoff 和 Draft PR。

### PR 4 / WSF-04

先產生 migration map，查 Python imports、動態字串、notebook 內嵌、`__file__`、manifest／wheel 與相關 consumers。
優先隔離現行 ARC CLI parser/dispatch 到 `domains/arc_agi_2`，再遷移少量已證明可變的 helper。
凍結實作可留原路徑，由 ARC facade 明確呼叫；不複製成第二份 solver，不更新歷史 pin 來遷就搬檔。
補齊依賴方向檢查、實際路徑 AGENTS、管理目錄／看板／STATUS 導覽與跨線 onboarding 演練。
通過 A4；無法在缺少 authentic inputs 時驗證的精確重建保持 blocked，不擅自下載。

## 統一管理必須成立

文件 metadata 只維護在 documents catalog；任務狀態只維護在 task JSON；BOARD 自動產生。
STATUS 放工作線範圍、領域證據與限制，不再複製逐任務進度。既有 workstream registry 保持純導覽。
檢查重複 ID/JSON key、壞路徑、缺文件、懸空依賴、依賴循環、過期 BOARD 與沒有 review 的 verified。
只納管新／活躍文件；舊歷史用固定索引保留，不批量改 front matter，不再新增一套平行 ADR 系統。
不要做 Web dashboard、雲端資料庫或外部 tracker 同步；先讓 repository 本身能完整操作。

## 驗證與獨立性

每一階段可在自測通過後接著下一階段，但狀態停 `review_ready`；下游在獨立驗證前仍是 provisional。
你與你的子代理的 review 都標為 self-review，不能代填 ChatGPT independent review 或把 task 標 verified。
每份 report 綁定先前提交的 implementation SHA，不要求填自己的 commit SHA 造成循環。
保存完整命令、版本、exit code、測試數與 missing/blocked；對未配對的舊失敗用 unclassified，不籠統說都是 inherited。
新 regression、凍結來源衝突或需要改既有 public contract 時，停止該依賴鏈，提交可用部分與具體 blocker，不刪測試硬闖。
與本次無關的舊問題不要求全修，但不得讓分流把本可自足的失敗靜默移除。

## 操作邊界

不下載 Drive 移轉 ZIP／Git bundle／模型／evaluator inputs，不讀答案、credentials 或私有 owner/readback。
不操作 Kaggle，不啟動 GPU／訓練／配額查詢／競賽，不改登入／TLS／proxy／全域設定。
不要把整份私有 log 或生成封包加入 Git；公開 report 去敏，raw logs 留 ignored `.irisx`。
正常 Git 程式讀取、既有工具和離線自測可直接進行；缺少可用依賴時記錄問題，不擅自大量安裝 ML stack。
真實 line-b 領域尚未指定不構成停止本次 scaffold 的理由；不得以合成結果宣稱產品、ARC 或 GPU 成功。

## 最後回傳

用繁體中文給一份精確交接，包含三階段各自 branch、base/code/report/delivery SHA、Draft PR URL 或未發布原因、
修改檔案摘要、A2/A3/A4 逐項結果、正式 wheel 驗證、測試與失敗差異、管理系統操作方式、
受保留區域檢查、未驗證／blocked 項目，以及 `docs/verification/WSF-0N/` 的實際檔案路徑。
明列 main 未更新、PR 未合併、run008 未動、沒有新 GPU 或 PUBLIC120 結果。
到可審查提交為止；下一步交回原 ChatGPT 對話，由另一輪實際讀取與重跑完成獨立驗證。
