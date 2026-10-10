# IRIS-X N5–N14：結果與手動執行指南

## 2026-10-10 啟動修正

第一輪 N6 啟動在模型準備前遇到的 `Source N1 manifest identity differs` 是本套件的封裝錯誤：原版內嵌了衍生的 N1 return-dict-fix1 manifest，卻要求它與 runtime8 內的原始 manifest 完全相同。原先 57 個測試沿用同一份衍生 fixture，沒有跨過真實 mount 的啟動邊界，所以漏掉這個問題。

修正版 `runtime8-manifest-fix1-20261010` 使用實際 runtime8 的精確 manifest，保留全部 Dataset inventory／SHA、N1 結構、完整 manifest equality 與 challenge 驗證。沒有關閉安全檢查，也不改動題目、prompts、seeds、模型 pins 或 budgets。

十份 notebook 都會使用新的 source／output／archive 目錄；N5–N12、N14 經過修正的 runtime 邊界，N13 維持不讀 runtime 的 CPU 路徑。請在修正版完成 N6／N7，再將同一修正版的完整 evidence 傳給下游。舊版結果與 BLOCKED 收據保留為歷史，不會自動變成新版 gate 證據，也不覆寫失敗的舊 N6 目錄。

Kaggle 仍是原來十個 notebook 連結的經審查新版本，預設停用；舊版本保留。精確修正與實測範圍見 `docs/RUNTIME8-MANIFEST-HOTFIX-20261010.md`。

## 先看結論

十份 notebook 已完成程式與獨立驗證，預設 `MANUAL_START=False`。這次完成的是可手動啟動的分階段實驗，以及 N5、N13 的真實 CPU 實測；尚未跑新的 GPU 推論、SFT、TTT、RL 或競賽 submission。

**建議先跑 N6 與 N7，檢查程式是否真正能進入 demo 執行，再決定後面的 agent 實驗。** N8 可獨立檢查語法修復；N9–N12、N14 會強制檢查前置結果，沒有通過就輸出 BLOCKED。

### N4 告訴我們什麼

- 共 93 次模型呼叫：A 32、B 32、C 29；C 有 3 個 context exclusions。
- direct-grid A 解出 1/8；program B 與 repair C 都是 0/8。
- 61 份程式都符合 raw-source 格式，45 份可 Python parse，**0 份通過原 bounded language**，因此沒有測到真正的 demo-verification 效益。
- 多數程式重寫已提供的 components／copy_grid，帶入不支援的 while／list methods，也消耗 tokens。函式重定義本身並不是被拒絕的原因。
- 21 次 repair 收到的主要是泛用語法錯誤，沒有變成可執行候選。

### 這次實際跑出的 CPU 結果

- **N5**：對完全相同的 61 份 source，舊語言與 bounded-v2 各驗證一次，共 122 次隔離 CPU 呼叫。V2 有 29/61 通過 AST、23/61 完成 demo 執行，但 **0 份通過所有 demos、0 正確 query**。放寬受限語法解決了一部分介面問題，尚未解決規則推理。
- **N13**：512 個 synthetic episodes，1,024 次隔離 CPU 驗證，沒有未知 usage，累計 3,832,550 interpreter steps。資料包含 F 格式複製、G grid、P program、R repair 四種目標。**只完成資料製作與驗證，沒有訓練，也不能據此宣稱 SFT 提升。**
- 原版 57 項測試曾通過；修正版 67 項測試在實際 runtime8 mount 下通過，0 skips，另有獨立的安全、契約、notebook、tokenizer 與記帳檢查。既有整個 repository 的歷史測試問題另列於整合紀錄，不能把本次 focused pass 說成全 repo 全綠。

## 十份實驗與執行順序

每份名稱對應 `notebooks/` 中唯一的 N5–N14 檔案；已發佈的連結由 publication receipts／索引提供。

| 順序／run | 假說與對照 | 上限／前置條件 | 要怎麼判讀 |
|---|---|---|---|
| 可先看 N5 language replay | 同一批 N4 source：原語言 vs bounded-v2 | CPU；0 model calls；122 次驗證 | 區分語言 admission 與語意能力；目前仍 0 demo-fit |
| 第一輪 N6 toolbox contract | 清楚標示 host-owned API，是否減少重寫 primitives；對照完整語言說明 | 64 calls；不需要 prior model run | host arm 的 32 slots 至少 8 AST admitted、4 demo executions，才開放下游 |
| 第一輪 N7 typed program IR | typed JSON 組合計畫 vs bounded Python，是否提高可執行率及有效 coverage | 64 calls；已有 compiler／witness CPU 檢查 | IR 的 32 slots 同樣須達 8 AST、4 demo executions；高 JSON 合法率本身不夠 |
| 診斷 N8 static feedback | 精確 node／line 診斷 vs generic syntax feedback | 64 calls；無 prior gate；成對初始 prompt／seed | 看失敗到可執行的轉換，另報 token 差異；不提供 demo/query feedback |
| 第二輪 N9 object perception | 保留 raw grids，增加 deterministic object view | 64 calls；需 N6 host gate | 固定分母比較 top2 與成本；不得排除困難題後才報提升 |
| 第二輪 N10 demo feedback | 真實 demo mismatch vs redacted feedback | 64 calls；需 N6 host gate | 看語意修復與最終 query 分數；這是資訊與 trajectory 對照，非等實耗 tokens 的單步因果估計 |
| 第二輪 N11 candidate memory | best-parent repair＋有界可讀記憶 vs 四個 independent roots | 64 calls；需 N6 host gate | 比較 top2、成本、每題多樣性；這是整組 controller 對照 |
| 第二輪 N12 neural CPU search | uniform vs smoothed feature prior vs hard-pruned，使用同一批 IR proposals | 32 shared model calls；需 N7 IR gate；每題每 arm 最多 64 搜尋、30 秒 | 搜尋空間 ceiling 與效率分開報；共享模型成本會完整計入每個獨立反事實 arm |
| CPU 資料 N13 curriculum | 自寫 families 產生可驗證 F/G/P/R | 0 model calls；512 episodes／1,024 verifications | 八個 family 預先分六 train、二 validation；資料成功不代表訓練有效 |
| 最後 N14 consolidation | direct-grid vs 固定規則選出的單一 agent | 256 calls；需 N6、N7、N9、N10、N11 全部合法結果 | 在 N3 已測的另外 32 題比較；至少一個 qualifying policy 解出 1 題才啟動，否則 BLOCKED |

N14 只可從 host_toolbox、typed_ir、raw_plus_objects、true_demo、best_first_memory 選擇。先比較 engineering8 的 top2，再 top1、較少 generated tokens、policy ID；選擇在 N14 開始前固定。N12 因額外 CPU search 成本不同，不列入候選。N9–N11 若因 N6 admission 失敗，可提供可重新驗證的 admission-BLOCKED 收據；缺檔、破損或任意 BLOCKED 不能代替完整結果。

**停止規則：**N6／N7 沒有跨過 admission 門檻時，不把後面十份一次全開。保留 BLOCKED 收據；若 admission 提高但仍 0 demo-fit，下一步應研究語意能力與 program／repair training objective，不能只靠更多相同 prompt 重跑。

## 環境、固定 Dataset 與啟動

### 硬體

- N5、N13：CPU-only。N5 只需要 runtime mount；N13 不需要任何 Dataset mount。兩者不載入模型，不要求 CUDA／G4，也不掃描整份模型 weights。
- N6–N12、N14：目標是已驗證的 G4 配置，1×96GB-class RTX PRO6000 Blackwell、48 CPUs、host RAM 至少 170 GiB，原 CPython 3.12／cu128 離線環境。
- 4×L4 是後續 submission deployment 條件，本 suite 尚未實測。不要把目前的 G4 notebook 當作已通過 4×L4 部署驗證。
- Granite4.2-8B 是目前唯一已驗證的 offline model。Qwen3.5-9B、Seed-Coder8B 是後續候選，未假設其 weights／wheels 已可用。

### 不更動的五個 private pins

| 設定變數 | Dataset reference |
|---|---|
| `RUNTIME_ROOT` | `danielwuu/iris-arc-next-runtime/8` |
| `MODEL_ROOT` | `danielwuu/iris-arc-granite42-8b-offline/2` |
| `WHEELS_ROOT` | `danielwuu/iris-arc-next-cu128-cp312-wheels/1` |
| `INTERPRETER_ROOT` | `danielwuu/iris-arc-next-cpython312-offline/2` |
| `ADAPTER_ROOT` | `danielwuu/iris-arc-granite42-run003-adapter-20261009/1` |

GPU runs 會驗證五份 pins；adapter 只驗證，不載入。本次沒有建立新的 Kaggle Dataset。Notebook 已內嵌經 hash 驗證的 source 與必要小型資料。各 Dataset manifest SHA 在 notebook `PINS` 與 publication manifest 內。

### 手動步驟

1. 打開要跑的單一 notebook，先保留 `MANUAL_START=False`。Internet 保持關閉，Dataset 版本不變。
2. 所有 `*_ROOT=None` 時，会依序檢查 `/kaggle/input/datasets/danielwuu/<slug>` 與 `/kaggle/input/<slug>`；必須剛好找到一個。若 mount 在其他位置，改填實際 root 路徑，不要修改 manifest/hash 來繞過驗證。
3. 有 prior gate 的 run，先將前一輪完整 evidence ZIP 或完整解壓資料夾放到執行環境，再填 `PRIOR_RESULTS`。不要只複製 report.json，也不要刪掉 seal／final-inventory 等檔案。
4. **確定要啟動這一輪運算時**才改成 `MANUAL_START=True`。CPU run 選 CPU；GPU run 使用上述已驗證硬體。此交付未替你啟動這些 GPU sessions。
5. 觀察 `IRIS-SUITE` heartbeat 與逐筆進度。結尾有 `EXPERIMENT-FINISHED` 仍須看 `summary.status` 是否為 `complete`；`partial-or-failed` 不是成功。未達 gate 會看到 `EXPERIMENT-BLOCKED`。
6. 保存顯示的 `archive` 路徑與 evidence ZIP，再自行停止 VM／session。程式不會替你停止 VM 計費。

例：跑 N9、N10 或 N11 時，設定：

```python
PRIOR_RESULTS = {'N6': '/實際掛載位置/iris-x-n6-runtime8-manifest-fix1-20261010-evidence.zip'}
```

跑 N12 用 `N7` key。跑 N14 要提供全部五個 key：`N6`、`N7`、`N9`、`N10`、`N11`。路徑是示意，必須換成該環境實際可讀檔案；可以保留 ZIP，程式支援安全匯入，不需手動移除 metadata。若 Kaggle 使用新增 private Dataset 承接前次 outputs，先自行上傳完整、未改寫的 evidence ZIP，再在下一份 notebook 掛載；本次沒有自動發佈或假設這份傳遞 Dataset 已存在。

## 預算、輸出與封存

每個正常 task／arm 有四個預定 slots；每 call 最多 2,048 新 tokens、6,144 prompt、8,192 context。全套 gates 全過時上限 672 model calls、1,376,256 generated tokens。這是預定最大模型工作量，不是費用報價；相同上限也不等於實際 compute 相同。

每次 program verification：最多 200,000 steps、3 秒 parent wall timeout、2 CPU 秒、256 MiB。未知 work 保留完整上限 reservation，不會抹掉成本。N12 的 30 秒涵蓋子程序啟動／驗證，deadline 後完成的候選不參與選擇。

Controller：一般 9,600 秒；N14 32,400 秒；N5 CPU 600 秒；N13 CPU 1,200 秒。Generation 的 120 秒限制是 cooperative。初始化／驗證／封存／評分／輸出與清理可能額外耗時，**不是 VM 計費硬停止器**。

Kaggle 預設輸出：

```text
/kaggle/working/iris-nextphase-n6-runtime8-manifest-fix1-20261010/runs/iris-x-n6-runtime8-manifest-fix1-20261010/
/kaggle/working/iris-nextphase-n6-runtime8-manifest-fix1-20261010/runs/iris-x-n6-runtime8-manifest-fix1-20261010-evidence.zip
```

其他 run 把 n6 換成其編號。非 Kaggle 時，預設 BASE 在目前工作目錄。程式禁止覆寫既有 run identity；不要藉由刪掉未完成結果來挑選好看的重跑。

完整 model/replay evidence 有 manifest、封存 seal、report、summary、final-inventory 與逐筆 records。N13 有 run identity、curriculum 與 summary；BLOCKED 有 blocked receipt 與閉合 inventory。下載 ZIP 後可以直接附回來分析。

## 實驗邊界與研究落地

- N5–N12 是原八題已曝光工程題；N14 為 tuning[8:40]，雖與八題不同，但已被 N3 測過，仍是 exposed tuning。136 題 confirmation 完全未使用。
- N9 的 object view 在 33067df9 超出 prompt cap，固定保留四個 excluded slots；N14 若選 object policy，a096bf4d 同樣有四個 exclusions。沒有截斷 raw grids、換題或從分母移除。
- N4 重播、program/IR 都經有界 AST interpreter 和獨立 CPU 子程序執行，generated source 不送 Python exec/eval。Query 答案與錯誤不進入 repair feedback；評分在停止／封存後才讀 evaluator gold。
- AVO 對應 lineage／restart，Duck 對應精確 task views，Jev 對應 typed decisions，Prime 對應有界 task state，NeMo 對應 rollout／profile／成本記帳。這些是機制借鑑，不是宣稱那些專案提供已驗證 ARC weights，也不是遷移完整 framework。
- N12 是有限 typed candidate inventory 的 smoothed feature-prior ranking；空 proposals 時恢復 uniform，不宣稱完整復現 PCFG／HySynth。
- Program-SFT、repair-SFT、TTT、RL 與 four-L4 deployment 仍需另訂配方、可用 assets 與實測，N13 只提供後續訓練資料的準備度證據。

## 交付內容與驗證入口

Repository 目錄：`tools/arc_next_suite_20261009/`。

- `notebooks/`：十份可手動執行 notebook
- `src/`：固定 source、設計、source lock、truth-free replay 資料
- `docs/`：研究來源、exposure ledger、安全報告、N4 分析
- `evidence/`：N5／N13 摘要、focused tests、獨立 review
- `VALIDATION.md`：精確通過範圍、source hashes 與尚未跑的項目
- `publication-manifest.json`：十份 notebook 的固定身分與 hashes；其中絕對路徑是產製 provenance，新 checkout 使用本目錄的 `notebooks/` 檔案

由 repository root 執行 focused tests：

```text
python3 -m unittest discover -s tools/arc_next_suite_20261009/tests -p 'test_*.py' -v
```

原版 source-lock SHA256 為 `5483b47b573960c4dba64e2af95efdb1a92e19c2f9bdf652a8b45d9db45e290d`；修正版精確 hash 見本目錄 `publication-manifest.json` 與修正驗證報告。

技術封裝只包含程式、notebooks、文件、必要 challenge／truth-free replay 與驗證收據；不含 query gold、credentials 或 weights。出版與 Git 的最後回讀狀態，以附帶的最終 receipts／索引為準。
