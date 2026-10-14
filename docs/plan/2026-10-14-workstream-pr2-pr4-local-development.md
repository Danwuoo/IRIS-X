# IRIS-X：PR 2–4 本地開發與統一管理計畫

日期：2026-10-14。計畫 ID：WSF-20261014。範圍：獨立分支上的離線工程。
實作者：使用者指定的本地 Codex task（6.1 sol ultra）。獨立驗證：交回本對話，按實際提交與證據審查。
本文件是開發規格，不是實作完成、測試通過、合併或 GPU 執行證明。
啟動文字見 [Codex kickoff](2026-10-14-workstream-codex-kickoff.md)。

## 1. 固定起點與最新要求

| 身分 | 固定參考 | 用途 |
| --- | --- | --- |
| main | `baaf47d4f449c534ddd4646ab9b3175bbaf1ef89` | 比較基準；不提交、不合併、不推送到 main |
| 第一個整理 PR | GitHub PR #5；`chore/workstream-foundation-20261014` | 保留 Draft；不啟用 auto-merge，不刪除分支 |
| 第一個整理實作 | `76809c05c9d51de4a9d19e99c09e1dbd70edc9f9` | 導覽與治理基礎；後續本計畫文件提交是其後裔 |
| run008 | `feat/run008-native-research-20261013`；`cc14bd1a79aac1fe6135017c9e09d4834300675d` | 獨立保全，不整支匯入重整線 |

PR 2、3、4 是本計畫的階段代號，不是預先指定的 GitHub PR 編號。
啟動時讀取包含本計畫的 foundation 分支 HEAD，記錄完整 SHA；確認它包含 `76809c05`。
已存在的 PR #5 即使仍以 main 為比較 base，也只是 Draft 審閱入口，不構成合併授權。
本文件取代舊導覽中「共用改動直接進 main」的整合安排；不取代產品契約、資料隔離或歷史證據。

### 已讀取的驗證事實

PR #5 原 head 的 navigation workflow `38503686348` 四個 jobs 成功。
原 offline-validation `38503686421` 已結束：四個環境的 repository check 成功；
Ubuntu / Python 3.14 job `115656185090` 的完整 unittest 記錄 **1,588 tests、5 failures、96 errors、110 skips**，
其餘三個 jobs 最終為 cancelled，不能當作完成的跨平台測試結果。
CI 實際 checkout 的是測試合併提交 `b5d7e10d90bda1e80a3b0971f64ee7f688befafa`，不是 main 已被合併。
這些是既有遠端紀錄，不是本計畫的新測試或配對 baseline。

已觀察到的失敗來源包括：未建立 `.irisx` scratch、未於 interpreter 啟動前設定 `PYTHONHASHSEED=0`、
缺少 packaging / numpy / IPython、歷史封包或 review 缺失，以及缺少測試模組／研究檔案。
仍有 assertion failure；不得未經配對重現便全部歸因為環境或「既有錯誤」。
run008 的 focused CPU 修復證據、部分 Drive 交付、無新 GPU / PUBLIC120 結果維持原本分類；不查詢 Kaggle 來啟動本工作。

## 2. 交付目標與不包含項目

完成後應有：可正式安裝的巢狀套件、通用 CLI 不依賴 ARC 執行現場、明確且可核查的測試分流、
第二線的合成工程閉環、ARC 可變入口的漸進隔離，以及統一的文件／任務／驗證／交接管理。
第二線真實領域尚未指定：只建立 `line-b` 的 synthetic engineering fixture，不自行改名為 ARC-AGI-3、
不宣稱真實領域能力、不為此修改既有 public contract 或 admission 語義。

禁止 merge / rebase / force-push / reset main；禁止合併任何 PR、auto-merge、刪 branch 或移 tag。
保留 run006/007/008、archive、原始 notebook/scorer/manifest/review/inventory 與重建身分。
不下載 Drive ZIP、Git bundle、模型、evaluator inputs 或可重建的實驗封包；不繞過 Drive 安全標記。
不讀取 credentials、私有 owner/readback 文件或 evaluator 答案；不操作 Kaggle／訓練／配額／競賽提交。
正常取得本 repository 的程式／Git objects、推送本任務的獨立 branch 與建立 Draft PR 可以使用既有 GitHub 連線；
不變更登入、權限、TLS／proxy 或全域 Git／Codex 設定。
依賴優先使用既有 interpreter / cache；不能取得所需工具時明列 blocker，不擅自大量下載 ML 套件。

## 3. 分支、執行與交接方式

```text
main @ baaf47d4                       [維持不動]
  └─ chore/workstream-foundation-20261014   [PR #5，含本計畫]
       └─ refactor/workstream-pr2-packaging
            └─ refactor/workstream-pr3-validation
                 └─ refactor/workstream-pr4-arc-boundary

feat/run008-native-research-20261013 @ cc14bd1a   [另外保全，不合併]
```

| 階段 | Draft PR 的 base | 工作 branch |
| --- | --- | --- |
| PR 2 | `chore/workstream-foundation-20261014` | `refactor/workstream-pr2-packaging` |
| PR 3 | `refactor/workstream-pr2-packaging` | `refactor/workstream-pr3-validation` |
| PR 4 | `refactor/workstream-pr3-validation` | `refactor/workstream-pr4-arc-boundary` |

每一階段各有 worktree、venv、忽略的輸出根與 task 紀錄；每個 code checkpoint 用完整 SHA 固定。
每階段先提交通過自測的 code checkpoint，再提交交接／metadata；將含兩者的最終 branch tip 記為 delivery commit。
下一階段從該 delivery commit 建立，保留上游全部交接；PR 不必合併才能疊加開發。
本地 task 可依序完成三階段，不必為例行離線修改反覆詢問，但每階段停在 `review_ready`，不能自己填獨立驗證通過。
下一階段可以在自測通過的前一階段上施工，仍屬 provisional，直到本對話對其依賴提交完成驗證。
遇到本階段新 regression、凍結來源衝突或需改產品契約時，停止該依賴鏈，提交已有的安全部分與具體 blocker；
不把 blocker 藏進後續 PR。無 GitHub 寫入能力時保留本地 branches / commits 與 PR 草稿文字，不假稱已開 PR。

並行子任務只分配互不重疊的檔案；主 task 獨占 `cli.py`、build backend、CI、共用契約與管理 schema 的整合。
實作子代理的 code review 是自我檢查，不等同本對話的獨立驗證。上游改動以新 commit 修正；
對已發布的 stacked branch 不強制改寫歷史，先報告需重新整合／複驗的下游範圍。

## 4. 第一個動作：建立可比較的本地 baseline

在獨立 worktree 檢查 branch、HEAD、Git objects、所有較窄的 AGENTS 與既有未提交修改。
不要 stash、reset、clean 或覆寫使用者現場；branch／目錄撞名時先辨認，不重置既有 worktree。

對包含本計畫的未修改 foundation checkout 留下 baseline，再對每階段 head 使用相同條件重跑。
至少記錄 OS、Python、必要工具版本、測試命令、實際 cwd、允許的測試環境設定、exit code 與缺失輸入分類。
不要 dump 全部環境變數。一般公開測試用 3.11 / 3.14 相容性；需要原始條件的測試另用實際可用的 Linux / 3.12，
不能以其他 Python 的通過宣稱 3.12 精確重建通過。

建立新的 `.irisx/core/workstream-restructure/<attempt>/` 作 logs / TMPDIR；需要 `.irisx` parent 的舊測試可建立空 parent，
但這不等於補齊歷史 fixture。啟動測試 interpreter 前設定 `PYTHONHASHSEED=0`、`PYTHONDONTWRITEBYTECODE=1`、
`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`HF_DATASETS_OFFLINE=1`；完整 aggregate scratch 預留既有要求的 5 GiB 以上。
保留原始失敗與調整前後不同 attempt 的紀錄，不在同一檔覆寫。

先做 navigation、repository check、明確列出的共用測試，再做不需受限資料的 aggregate。
外部資料型測試先靜態盤點；缺失 inputs 時記錄 blocked，不下載或偽造。
完整舊 aggregate 的失敗總數只是觀察值；歸因需 test ID、exception signature 與相同環境的 base/head 比較。

## 5. 統一文件與開發管理系統

採用 **repository-native、離線可讀、Git 可審查** 的管理方式，先不建立 Web 服務、資料庫或 Notion／Projects 雙向同步。
它管理所有工作線，而不是另一套 ARC 工作日誌。Markdown 是閱讀介面，少量 JSON 是可核查的索引與任務狀態。

### 5.1 唯一來源與目錄

```text
docs/
  README.md                         # 全專案閱讀入口
  plan/                             # 計畫與啟動 prompt；不放執行 log
  development/                      # 長期工作方式與工具使用說明
  management/
    README.md                       # 管理操作方式
    documents.json                  # 活躍文件目錄，唯一 metadata 來源
    tasks/WSF-02.json                # 每階段一筆任務，可拆成少量有價值子任務
    tasks/WSF-03.json
    tasks/WSF-04.json
    BOARD.md                        # 從 task records 產生，禁止人工改狀態
  verification/
    WSF-02/                         # developer handoff 與後續 independent review 分開
    WSF-03/
    WSF-04/
  workstreams/
    registry.json                   # 保留純導覽 schema，不塞 task / authorization
    core/STATUS.md                   # 範圍與證據摘要＋任務看板連結
    arc-agi-2/STATUS.md
    line-b/STATUS.md
tools/dev.py                        # repo 開發工具，不是產品 CLI 或 provider operator
```

每個事實只由一處維護：文件內容在其 canonical Markdown；文件類型／狀態在 documents.json；
任務狀態在 tasks/*.json；測試結果在具名驗證 report / CI；code identity 在 Git。
STATUS 保留工作線的範圍、科學／執行證據、限制及看板入口，不再手抄每個任務的完成百分比。
README、BOARD 與 PR 說明可以引用或產生摘要，不能成為第二套人工 task ledger。

### 5.2 最小資料契約

`documents.json` 使用版本化 format，文件包含 `id`、`path` 或 commit-pinned `url`（二擇一）、
`kind`、`workstream`、`status`、`owner_role`、`related_tasks`、`supersedes`。
kind 至少區分 guide / plan / decision / reference / evidence / prompt；
status 為 draft / active / superseded / historical。用 Git 記錄修訂，不額外人工維護每篇文件的內容版本號。
先登錄 README、AGENTS、現行 product/development 入口、workstream 入口、本計畫、新管理文件與新增驗證報告；
歷史集合用固定索引與明確 legacy scope 納管，不強迫重寫所有舊文件或補 YAML front matter。
新增／修改的活躍文件必須被登錄；凍結歷史免改動且不得因此免除既有完整性檢查。

Task 最小欄位：`format`、`id`、`title`、`workstream`、`state`、`depends_on`、`owner_role`、
`plan_ref`、`scope_paths`、`base_branch`、`head_branch`、`base_commit`、`implementation_commit`、
`acceptance`（check IDs）、`blockers`、`handoff_ref`、`verification_refs`。
未產生的 SHA／report 用 null 或空集合；禁止填虛構的執行結果。
state：planned → in_progress → review_ready → verified；blocked 可回 in_progress，
changes_requested 表示獨立審查要求修正。`verified` 代表具名工程範圍通過，不代表合併、實際領域能力或 GPU 成功。
只有有來源的獨立 review 能支持 verified；開發者先留下 review_ready。

`implementation_commit` 指向先提交的程式 checkpoint；其後才提交交接／metadata。
下一階段的 `base_commit` 是上游最終 delivery commit，不是漏掉交接檔案的較早 code checkpoint。
驗證 report 記錄 `target_commit`，必要時另外記 `tested_commit`（如 GitHub 測試合併提交）。
不能要求 report 同時填它自身所在的 commit SHA，造成自我雜湊循環。
受驗範圍的程式、測試、依賴或 CI 再改變，舊 review 保留為歷史而不覆蓋新 head；依賴階段也需複驗。

### 5.3 開發入口與必要檢查

PR 2 先交付 metadata、模板、`tools/dev.py status` / `check` / `render --check` 的最小 stdlib 實作；
PR 3 接入 suite selection 與 CI；PR 4 補完實際 code scopes、遷移索引與跨線演練。
可提供 `context --task WSF-02` 輸出必要閱讀清單，不自動載入整個歷史、不執行文件中的命令。
以下是要實作的介面，不能在實作前宣稱可用：

```sh
python tools/dev.py status
python tools/dev.py check
python tools/dev.py render --check
python tools/dev.py context --task WSF-02
python tools/dev.py verify --suite core
```

管理檢查至少拒絕：重複 ID／JSON key、非法狀態、目錄逃逸與 linked path、缺檔、未登錄活躍文件、
懸空 task/check/doc refs、依賴循環、同一批並行任務的共用可寫檔衝突、過期 generated BOARD，以及沒有 review 的 verified。
路徑權限採 explicit globs 並拒絕任意 executable command 欄位；以正反測試驗證，不只比對特定文字。
`check` 和 `render --check` 唯讀；顯式 `render` 只更新有標記的產生檔，不改歷史／證據。
驗證器只檢查結構與證據關係，不冒充人工判斷 review 內容正確；本對話仍核對其實際來源。

每個 routine task 只需要一筆記錄＋一份具體交接，不要求每次小修再建 ADR、第二份驗收表或大量重複 handoff。
只有跨工作線契約等長期決策才用既有 `docs/decisions/`；不另建競爭的 decision 系統。

## 6. PR 2：正式打包與 CLI 邊界，加上管理骨架

Task：WSF-02。範圍：`tools/irisx_build_backend.py`、`src/irisx/cli.py`、必要新 parser-only 模組、
新增 distribution / import-boundary / management tests，以及第 5 節的最小管理工具與文件。
不搬舊 ARC runtime、不改模型／scorer、不改 frozen manifests。原 full CI 先保持；可新增獨立 scoped checks。

### 實作順序

1. 建立管理骨架、三階段 task records、文件目錄與 baseline report，讓本次重整本身用同一套管理方式。
2. 修正 wheel 收檔：支援巢狀 Python packages，保留 licenses，資源檔採明確 allowlist。
   不直接 `rglob('*')` 把 caches、測試資料、`.irisx`、credentials 或外部 linked paths 打包。
   保留排序、timestamps、RECORD digest/size 與可重現規則；測試安全路徑、缺失必要檔及大小寫碰撞。
   不因搬資料夾就換 build system；若現有 backend 真有無法合理維護的限制，先記錄取捨。
3. 把 ARC implementation imports 延後到對應命令真正執行。通用 `fixture/spec/trial/package/admission` 與 root help
   不匯入 ARC／Kaggle 執行實作；parser-only registration 可以存在但不能有隱藏 side effects。
   保留 `irisx.cli:main`、既有命令名稱、選項、exit code 與錯誤語義；不要依靠吞 ImportError 靜默停用功能。
4. 加上 fresh-process tests，檢查 `sys.modules` 與 import blocker，證明通用路徑不依賴 ARC、tools、ML 或私有 fixture。
   不以所有 CLI commands 都不能匯入 ARC 為目標；選用 ARC 時才允許載入其領域實作。

### 驗收 A2

- A2-1：在兩個不同的乾淨 staging roots 建出的相同來源 wheel 雜湊一致，RECORD 全部有效；隔離 staging 的巢狀測試 package 確實入其測試 wheel；正式產品 wheel 不夾帶 tests。
- A2-2：用新 venv 安裝非 editable wheel，於 repository 外執行 CLI 和完整 synthetic reference flow；
  驗證 `irisx.__file__` 來自該 venv，不靠 cwd、PYTHONPATH、editable .pth 或 source checkout 偷渡。
- A2-3：舊 public CLI smoke / contract / reference flow 通過；所有新 import 邊界測試一般及 `-O` 通過。
- A2-4：management metadata、狀態流轉、壞路徑／重複 ID／缺 review 負測試與 generated view 一致性通過。
- A2-5：明列 base/head 對照與非範圍舊失敗；未碰的凍結區域 Git blob identity 保持，未更新 main/run008/tags。

正式安裝建議由可攜 Python 測試 harness 建立 venv 並呼叫：
`python -m pip wheel --no-index --no-deps --no-build-isolation ...` 及
`<venv-python> -m pip install --no-index --no-deps <exact-wheel>`。
解析實際 wheel 名稱而非假設版本；先確認本地 pip/venv 可用。
此處的暫存小型 wheel 是新驗收輸出，不是下載既有實驗封包。

## 7. PR 3：測試分流、可見的 CI 與第二線最小閉環

Task：WSF-03。依賴 WSF-02 的可比較 code checkpoint。

### 測試與 CI

建立 versioned test inventory，採「workstream」與「dependency class」兩軸，不把所有 ARC 測試丟進可忽略的 legacy bucket。
盤點 `tests/` 與 `tools/**/test_*.py`；對特殊命名、load_tests 和 helper-only 模組明確記錄。
每個測試檔需有主歸屬、依賴、執行命令／受控 runner 與被哪個 suite 覆蓋；未分類、重複分類或收集失敗必須報錯。
選 suite 時先讀靜態 inventory，再 import 被選檔案；不可全域 discover 私有 operational tests 後才排除。

| Suite | 執行原則 |
| --- | --- |
| management / navigation / integrity | 不依賴產品安裝、模型、雲端或私有資料 |
| core / distribution | 共用 contracts、reference flow、wheel、CLI，相同公開 checkout 可重跑 |
| arc-unit | 確認自足的 ARC CPU 測試；需要小型 Python 依賴者列出 test-only pins |
| line-b | 獨立的 synthetic engineering fixture，不匯入 ARC 私有內部 |
| arc-reconstruction / operational | 指定歷史／私有 inputs；缺失時明確 blocked，不冒充通過 |
| legacy aggregate | 保留原完整入口及結果，暴露未解決問題，不 blanket continue-on-error |

先讓每個 PR 都執行全部公開 suites；工作線穩定後才優化 path-based dispatch。
共用 build/CLI/contracts/test-runner/management/CI 改動必須覆蓋兩線。
各 job 解耦，避免 README／legacy failure 遮住 core、wheel 與 line-b 的結果；matrix 設 fail-fast false 保留完整資訊。
固定 `workstream-gate` 需驗證應跑 jobs 確實執行且成功；empty selection、unexpected skip、cancelled、timeout 或缺 report 不能算 pass。
本工作不修改 GitHub branch protection；不要聲稱新 gate 已被設為 required。

原 aggregate 可以重整成獨立 audit job，但保留完整命令、原始 exit code 與歷史對照，不能刪除、改名後不執行或把失敗轉綠。
至少維持 `python tools/repository_check.py --all` 的完整意義；新增 scoped commands 不取代它。
legacy audit 紅燈和 scoped gate 綠燈可同時存在，報告必須分別標示。
只因 missing `.irisx` 或 test-only dependency 即將一項本可自足測試移成 private，屬不合格分類。

### 第二線工程閉環

新增 `src/irisx/domains/line_b/` 與實際路徑的 AGENTS、tests/line_b、獨立輸出根。
用現有 P1 qualification profile 支援的 label / bounded-lookup 等合成案例建立具獨立 ID、workload 與 artifact refs 的測試流程。
可使用既有契約 constructor；不能只把 ARC 命令重新命名，也不要複製共用 engine/package 的實作。
若 profile 有固定約束，保持其語義，只在允許的範圍產生新 fixture；真實 domain extension 另列待定。

流程必須包括 specification/workload → baseline/candidate → evaluation/selection → package build/verify。
測試未達標與 missing evidence 的結果，不能只用所有預測都正確的 happy path。
所有輸出清楚標記 synthetic / engineering-only / non-deployable，不以此宣稱 line-b 已有科學成果。
真實領域未定義只阻擋其科學開發，不阻擋上述 scaffold 與管理基礎完成。

### 驗收 A3

- A3-1：inventory 完整覆蓋當前受管測試路徑，負測試能抓出新未登錄檔、collect error、重複歸屬與空 suite。
- A3-2：core/arc-unit/line-b 在各自 fresh process 執行；在未提供任何 ARC 私有 fixture 的新 checkout 仍可跑 core/line-b；不刪除使用者既有資料。
- A3-3：line-b 真正使用共用 contracts/engine/package，兩次 synthetic 結果具可重現語義／約定 bytes，篡改 package 被拒絕。
- A3-4：至少一次兩條線同時執行的小型 CPU 測試，證明輸出／task IDs／暫存檔不碰撞；不啟動任何 GPU。
- A3-5：CI 分別顯示公開 suites 與原 aggregate；錯誤、blocked、skipped 數字不混為成功。
- A3-6：`tools/dev.py verify --suite ...` 使用受控 inventory，產生具名報告；管理 check 與文件導覽在 CI 生效。

## 8. PR 4：ARC 漸進隔離與管理系統完整演練

Task：WSF-04。依賴 WSF-03。目的不是一次搬完所有 ARC 歷史。

先產生 migration map，逐項列出 old path、target path、可否修改、known consumers、byte/path pins、測試與 rollback。
盤點 Python imports，也查 notebook 內嵌 source、字串式 imports、`inspect.getsource`、`__file__` 相對路徑、
subprocess scripts、wheel / manifest 收檔、pickle module identity 與 monkeypatch consumers；AST 不足以證明所有相依。

優先把現行 CLI 的 ARC parser／dispatch 可變程式隔離到 `src/irisx/domains/arc_agi_2/`。
shared CLI 只做路由，不複製實作。已凍結的 legacy 模組可維持原路徑，由 ARC 邊界明確呼叫；
新資料夾不能成為第二份 solver fork。再選少量有完整測試的非凍結 helper 遷移，每組單獨 commit。

不得把被 runtime/source archive/review 綁定的原檔替換為 shim、更新原 manifest hash，或大量 search/replace 歷史路徑。
若某模組無法在缺少 authentic inputs 下證明可搬，維持原位並記錄原因；以新的可變入口隔離完成可做部分。
PR 4 至少交付一個實際可用的 ARC 邊界與 tests，不把空資料夾／文件索引稱為完成 runtime migration。
不重新建立受限實驗封包；只做 Git/source preservation 與公開 CPU/fixture 驗證，完整重建驗證另記 blocked。

管理系統完成：活躍閱讀入口接上 documents catalog、task 看板、測試指令與驗證報告；
core/ARC/line-b STATUS 使用相同結構，歷史 trial/research 文件仍可追溯。
開發者可以只從 docs/README → BOARD → task → plan → code → handoff 找到下一步，不必順讀全部 AGENTS 歷史。

### 驗收 A4

- A4-1：ARC 可變入口隔離實際可用；舊 CLI／允許保留的 imports 與錯誤語義測試通過。
- A4-2：core 不反向 import ARC／line-b；兩線不直接 import 對方，ARC facade → legacy 的例外逐項登錄。
- A4-3：migration map 覆蓋每個搬動項目，未允許的 source／notebook／manifest／review／archive bytes 與舊 Git 身分不變。
- A4-4：non-editable wheel、兩線公開 suites、navigation／management 與新增 negative tests 通過。
- A4-5：從乾淨 checkout 演練新增一項 line-b 任務、登錄文件、執行 scoped check、產生 handoff，再返回 core 任務；
  產生的看板一致、工作線不需讀 run008 私有材料。
- A4-6：交付完整但有限定的總結：哪些已隔離、哪些故意保留、哪些重建未驗證；不把部分 pass 稱為 full-green。

## 9. 驗證紀錄與本對話的審查程序

每階段交付 developer report 與機器可讀測試摘要，位置放 `docs/verification/WSF-0N/`。
raw logs / 小型 wheel / 暫存測試產物留 ignored `.irisx`，公開 report 只放必要且已去敏的內容與可核查指紋／CI 連結。
不要把整份私有 log 上傳 Git，也不要只交一個無來源的 PASS。

| 必備證據 | 內容 |
| --- | --- |
| Identity | base/head branch、base/code checkpoint SHA、report/delivery commit；PR base 明確不為 main |
| Changes | 修改路徑、public API／CLI 相容性、受保留區域差異與 migration map |
| Tests | command、OS/Python、條件、exit code、tests/failures/errors/skips/blocked、scope |
| Regression | 相同條件的 base/head test IDs／signature 對照；未配對者標明 unclassified |
| Distribution | wheel SHA、RECORD 核對、乾淨 venv 安裝與外部 cwd 的 package origin |
| Management | catalog/task/BOARD checks、依賴圖、code ownership、負測試與完整交接鏈 |
| Limits | 未跑項目、原因、缺失依賴、已知問題與下一步；獨立 review 初始 pending |

使用者把每階段的 branch / code SHA / Draft PR 與 handoff 路徑交回本對話後，
本對話先重新讀取遠端 refs、diff、workflow 和 report，再在可取得的獨立環境重跑公開測試／distribution checks，
並抽查負測試、舊失敗歸因、metadata 真實性、資料邊界與 frozen preservation。
遠端 CI 的讀取核對、自行執行的測試與僅檢閱開發者報告分開記錄；環境不可執行時不假稱已重跑。

review outcome：verified / verified_with_limits / changes_requested / blocked，必須附 target_commit 與範圍。
verified_with_limits 只用於明確不影響本階段目標的殘留限制；wheel 漏檔、資料洩漏、刪測試或偽造 evidence 不可條件放行。
後續修正提交必須重新核對受影響範圍；不自動合併任何 PR，也不在背景監看。
任務 records 的 verified 狀態若採用有限定 review，BOARD 必須顯示 limitations，不能只顯示綠色完成。

## 10. 完成定義

三條 stacked development branches 與各自清楚的差異／checkpoint 存在，main 和 run008 保持原工作線。
PR 2–4 的程式、tests、文件管理工具與報告可由本地 task 實際交付；未獨立審查前停在 review_ready。
第二線可獨立進行合成工程開發；ARC 的續接證據與凍結來源完整保存。
全專案有單一閱讀入口、任務狀態來源與可重跑驗證，不再用根 AGENTS 或多份手寫進度表取代開發管理。

## 11. 來源與實作參考

以下是本計畫形成時實際閱讀的固定來源；網路文件只作 API／工具行為參考，不凌駕本任務範圍。

- [PR #5](https://github.com/Danwuoo/IRIS-X/pull/5)、[navigation CI](https://github.com/Danwuoo/IRIS-X/actions/runs/38503686348)、[aggregate job](https://github.com/Danwuoo/IRIS-X/actions/runs/38503686421/job/115656185090)。
- [原 build backend](https://github.com/Danwuoo/IRIS-X/blob/76809c05c9d51de4a9d19e99c09e1dbd70edc9f9/tools/irisx_build_backend.py)、[原 CLI](https://github.com/Danwuoo/IRIS-X/blob/76809c05c9d51de4a9d19e99c09e1dbd70edc9f9/src/irisx/cli.py)、[P1 fixture](https://github.com/Danwuoo/IRIS-X/blob/76809c05c9d51de4a9d19e99c09e1dbd70edc9f9/src/irisx/fixture.py)。
- [run008 transfer boundary](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/transfer_run008/README.md)、[重建 helper](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/transfer_run008/rebuild_engineering.py)。
- [Codex AGENTS](https://developers.openai.com/codex/guides/agents-md/)、[設定參考](https://developers.openai.com/codex/config-reference/)。模型／模式由本地 task UI 或實際支援設定選擇；prompt 文字不能自行切換執行模型。`6.1 sol ultra` 是使用者指定的執行配置，不在 repository 硬寫未確認的 effort／CLI flags，也不修改歷史 model pins。
- [GitHub required-check 注意事項](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)：本計畫採始終啟動的公開 suite jobs，不用最外層 paths filter 跳過需要回報的 gate。
