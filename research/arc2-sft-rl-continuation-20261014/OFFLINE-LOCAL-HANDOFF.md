# 離線續接工具與本地實驗循環交接

日期：2026-10-15 UTC。研究基準固定為
`cc14bd1a79aac1fe6135017c9e09d4834300675d`；工作分支為
`feat/arc2-sft-rl-continuation-20261014`。
目的環境 portability 修復另由 `fix/arc2-abc-portable-publication-20261015`
交付；各次精確版本與驗收狀態只見下列進度入口。

工具版本、開發任務、驗收證據與下一步統一見
[開發進度管理](DEVELOPMENT-PROGRESS.zh-TW.md)。本頁只維護使用方式與限制；
取得來源時須確認精確 commit 包含所需模組，不能以 Stage 0 的 SHA 指稱後續整合。

## 交付範圍

此 companion 提供既有 SFT256 → RL／等成本額外 SFT 比較的離線準備與結果解讀。
它不執行訓練、不提交或監看 Kaggle、不重跑 scorer，也不重建原始私人 admission。
本地執行端的執行／提交責任與登入分開；沒有 credentials、帳號設定、
原始 evaluator 答案或私有執行封包隨此工具移轉。

CPU 元件、保存的 log-probability 與宣告性 metadata 不能代替真實模型 replay、LoRA
梯度、儲存／重載、整段成本或 GPU 實證。工具使用不改寫 run008 的凍結比較。

第6節是「研究開發端交付 → 本地執行端驗收／提交／監看／有界修復 → 真實結果回交」
的預設不執行程序。協調者負責交付精確版本、確認當次任務範圍與接收結果；本地端是
該次 Kaggle 工作的唯一 publisher。研究開發端不登入 Kaggle、不呼叫 provider、不啟動
模型或訓練。文件、Git 發布與 CPU 通過都不建立執行授權；沒有當次有效授權及全部原
admission 時停在準備階段。本文不記錄個人機器、帳號或私人任務狀態。

## 取得與核對

Stage 0 的 prepare／analyze 用法保留在下文。Stage 1 對原始 training audit 的 opt-in
CLI、context schema、逐軌跡介面與16MiB輸入限制統一見
[Stage 1 使用說明](../../tools/arc2_abc_continuation_20261014/README.md)，不在本頁複製另一套命令。
新CLI的exit0只表示報告已寫出；報告可能明列unknown／incomplete／rejected，不能據此啟動更新。

使用此分支中經遠端核對的 commit，保存完整 SHA；不要以日後移動的分支名稱
替代執行來源身分。一般公開 Git checkout 即包含必要來源，無須取得 Drive
封包或帳號設定。保留 run008、main 與工程重整線，不混入它們的新變更。

Stage 0 的 `prepare`／`analyze` 只需 Python 標準函式庫及支援 descriptor-relative、
`O_NOFOLLOW`／`O_DIRECTORY` 的 POSIX API。Windows 等不支援環境會明確拒絕
檔案操作，應交給支援的本地 POSIX 環境；不要停用安全檢查。Python版本與
檔案系統仍須在接收端測試，此機器的實際路徑不能直接照搬。

獨立 opt-in 的 audit-loss 入口另需 AF3 bridge、Pydantic 與 PyTorch；不得由 Stage 0
命令暗中載入。依賴與 CPU proof 環境見 [AF3 使用說明](../../tools/arc2_agent_factory3_bridge_20261014/README.md)。
各入口的可用版本與驗收狀態以[開發進度管理](DEVELOPMENT-PROGRESS.zh-TW.md)為準。

### 固定來源交付身分

2026-10-14原交接所檢查的 checkout 是 `e17b6857ee6e874b2b5ed28a766f35e0b8028ea2`，tree
`408182146a41cfbba7dbb9ead040b54e4790587a`。程式驗收版本是
`8b9ca9cf915969e15339d99bc090762f349f1572`，tree
`cedac0a7486685c641506335930d7f6ab429b514`；兩者只有進度文件差異，執行碼相同。
這些是歷史Stage1來源 anchors，**不是目的環境修復或本文最終文件 commit**。協調者會在發布核對後
另行交付最終完整 SHA／tree／變動清單，本頁不預填或自指尚不存在的 commit。
接收端先核對那份精確交付及工作區差異；不能只 checkout 移動中的分支便執行。

下列 SHA-256 在上述 checkout 重新核對。完整 Stage 1 檔案指紋及 CPU 範圍見
[獨立審查](stage1-independent-review.md#reviewed-source-fingerprints)；20個 frozen／bridge
來源的逐檔 pins 見 audit manifest。這些 hashes 只識別程式，不是生產 admission。

| 路徑（相對 repository root） | SHA-256 |
| --- | --- |
| `tools/arc2_abc_continuation_20261014/audit.py` | `fb7ede3a20f4921842f637f6cd32465a22ecfe61b0ffa7bbe9c4bb8627c825d0` |
| `tools/arc2_abc_continuation_20261014/streaming.py` | `4c7ea1d1c00f13329a7cd2491880b269e02d04cd169336aa3926751626328b81` |
| `tools/arc2_abc_continuation_20261014/cli.py` | `c41bccf7a36920a55bddd0e682798be1243aa9d7fec5633e683f930af647419d` |
| `tools/arc2_abc_continuation_20261014/audit-source-pins.json` | `015e2549da2ab445b30273fa62e106d98510b26c2f130866eae393418531b8cd` |
| `tools/arc2_agent_factory3_bridge_20261014/bridge.py` | `68e09ed7c01bc51a32a7ddf31eaceb16d928dc3f20069d3f53967a9d70ab74a3` |
| `tools/arc2_agent_factory3_bridge_20261014/source-manifest.json` | `9810243f51001318e5d08c608358092c12895e81e76dfcd82ec08f500ce439e1` |
| `tools/arc2_sft_rl_continuation_20261014/source-pins.json` | `220640c4f5a963d38153633040a0428ae2174e827b41f4dc466b119b1cf0c062` |

原 run008 的 frozen runtime identity 是
`c61025e67354272099e40941cadcd77202964846d9a4c42c51a1817f77bb661b`；source archive 是
`4d8b414bd35ca79a2eaaec7042880966879ed13bdeaf96762eaee7932ee1de4c`；loader overlay manifest
是 `1d3aabee0419acd2b42a4343d36028b0ba296f14f30341e5be8e6c83e42600f0`。
歷史候選 manifest `beda6a5647df0431ac2ac8da26db170d84776be8f59181b5fee537e87423a857`
及 inventory `bb096f6d53967523961f894c954daa1b4b1f956d54af3586d89bf544aea90cf2`
只供對照；新 numeric pins、路徑或 trainer 變更都需要新的候選與對應審查，不能沿用其放行。

原 native transport 的歷史 byte 核對如下，路徑前綴均為
`tools/arc_qwen_rlvr004_20261013/publication_run008/`。launcher 含後續既有 CA 傳遞修正，
應併讀 [TLS 審查](../native-continuation-20261014/independent-native-tls-review.json)，
不能把更早 launch review 的舊 launcher hash 當成本版。

| 檔案 | SHA-256 |
| --- | --- |
| `launch.py` | `e1794056b20dd1c143cb8ea23b1e985f579ab008260ef6b9d1f50c451301e48b` |
| `config.py` | `a4492c5a7b4d6cb42b2ee212f35b788fc70730fbd2fc13bf8b5cac03b48091fc` |
| `native_auth.py` | `b9b5aec37385f7a5de37ae92bbf0bfb3b7b664f0bc31c3fcc044532cb46a19de` |
| `sdk-lock.json` | `3d447ab7fad280fcc378fd18b57c3792c5b39798127f583679646027ab73288d` |
| `operator_common.py` | `f9b2acad7816b4af97baa877821ce4c9e3d16831fa340caf02d3e8c00b3f2805` |
| `rl_transport.py` | `a4da4850d7a2e44af2d85d4be65e55913a746ddeb66a26238500457911261bac` |
| `rl_collect.py` | `71603a1eb47b1b7656f2ca6a8f2b2eb6faa99469a27aef63d4f0446828ef3a78` |

`source-pins.json` 固定五個公開來源，總共118,615 bytes；Python原始碼只雜湊，
不import、不執行。它驗證選定來源bytes，不驗證完整checkout、Git HEAD、
私人材料、原始review或實際遠端版本。

## 1. 產生不會啟動工作的計畫

在 repository root 執行。輸出父目錄須先存在，檔名須尚未存在。

```sh
mkdir -p .irisx/offline-continuation
python3 -B tools/arc2_sft_rl_continuation_20261014/cli.py prepare \
  --repository-root . \
  --output .irisx/offline-continuation/plan.json
```

輸出包含 SFT256、32 parents×8 samples、最多四個互斥64-slot批次、完整 B wall
配對 C、固定 dev 選擇、no-TTT、PUBLIC120／167，以及接收端必須保留的原始
collector／owner／checkpoint artifact名稱。清單的 `not_inspected` 不可改稱已具備。
原始材料缺失時保留blocker，不能由此計畫製造admission或成功收據。

## 2. 解讀已經存在的本地 collector 報告

取得原 collector 產生的 `TERMINAL-VALIDATION.json`，保留原始bytes，從獨立保存的
原始收據核對 SHA-256。自行計算hash只能核對檔案身分，不能建立外部收集真實性。
下例的 `LOCAL_COLLECTOR` 與大寫 SHA 都是須替換的佔位文字。

```sh
python3 -B tools/arc2_sft_rl_continuation_20261014/cli.py analyze \
  --report LOCAL_COLLECTOR/TERMINAL-VALIDATION.json \
  --report-sha256 SHA256_OF_ORIGINAL_VALIDATION_FILE \
  --output .irisx/offline-continuation/analysis.json
```

若原始 `TERMINAL-CHECKPOINT.json` 與 `RETRIEVAL-RECEIPT.json` 也有保存，可明確加上：

```text
--checkpoint LOCAL_COLLECTOR/TERMINAL-CHECKPOINT.json
--checkpoint-sha256 SHA256_OF_ORIGINAL_CHECKPOINT_FILE
--retrieval LOCAL_COLLECTOR/RETRIEVAL-RECEIPT.json
--retrieval-sha256 SHA256_OF_ORIGINAL_RETRIEVAL_FILE
```

這只核對報告之間的bytes／hash／狀態鏈，不會沿著JSON內的路徑找檔，也不會連線
下載。retrieval必須與checkpoint一起提供；每個檔名必須有其明確hash。
支援原batched consumer的 `irisx/owned-rl-batched-offline-validation-v1`；
舊SFT64／full-sweep schema不能靜默套用。格式不明的collector診斷可保留拒絕狀態，
不因此獲得可用分數。

## 3. 正確閱讀結果

- `OFFLINE_OUTPUT_WRITTEN`／exit0只表示寫出新檔，不表示輸入真實、完整或有效。
  檢查 `analysis_structurally_consistent`、`issues`、`declared_axes` 和 nullable 指標。
- `INPUT_REJECTED`／exit2是參數、檔案、hash、JSON或安全操作拒絕。
  錯誤不輸出私人路徑、原文錯誤或JSON內容。
- 合作式SIGINT／SIGTERM回報 `INTERRUPTED`／exit130；父程序仍須有timeout並等待
  真正結束。工具不派生訓練或網路子程序。
- 缺少scoring保留 `null`。只有原scorer已評分後的缺失／非法prediction才算錯；
  不把中斷或漏收變成0分。PUBLIC固定167queries；120tasks是預期值，compact report
  沒有task inventory，`task_count_verified`仍為false。
- 正確案例ID可算條件式gain／loss，但不能證明全部case相同；不輸出case IDs或答案。
  Dev count／tie一致不證明selection seal或先後順序，相關驗證旗標仍為false。
- B/C整段同步model-phase wall包含setup、抽樣、reward、replay、失敗／rollback、
  hash／Python、save／reload／verification；不能改成只配optimizer時間。
- 全零完整稽核、未完成、之前已commit而後續失敗要分開；整個B從未commit才檢查B=A。
  不得抹除先前完整更新或退回其實體成本。

所有聚合都以不可信本地JSON為條件。此companion永遠不建立authenticated collection、
method efficacy、promotion或下一輪dispatch authority。

## 4. 檔案安全與中斷後續接

輸入為明確指定的單一常規檔，最多16MiB；拒絕symlink、hardlink、FIFO、重複JSON key、
非有限數及不符hash。目錄與檔案使用no-follow descriptors，避免祖先替換把讀寫導向
另一棵樹；安全界限不是先呼叫一次 `is_symlink()`。

輸出使用受限staging與exclusive publication。既有或競爭產生的目的檔不覆寫；
偵測namespace／identity改變即拒絕，不回報另一檔案hash。暫存清理由持有的directory
descriptors進行，不沿交換後路徑操作。

exclusive publication成功後若後續檢查、fsync或程序終止失敗，完整目的檔可能已存在。
這時是**結果不確定，先檢查檔案**，不能直接重跑或刪除。工具不以stat-then-unlink移除
已發布檔，避免刪掉競爭者替換的檔案。接收端應在可信目錄核對完整JSON與SHA，保留
原檔，再選新輸出名稱。SIGKILL、斷電、惡意同UID程序或返回後namespace變更，不在
Python cleanup可保證範圍。敵對替換的foreign staging entries會保留，不能任意刪除。

若staging mkdir成功，但首次stat/open失敗而無法確認inode，空的0700目錄也可能保留；
工具不刪除未能綁定所有權的名稱。這與已修復的祖先交換導向錯誤位置是不同情況。

本工具不掃描／刪除任意舊暫存，也不替代OS使用者隔離或權限控制。

## 5. 測試與證據範圍

參見 [最終獨立審查](offline-continuation-review.md) 的精確結果與來源指紋。
normal與`-O`都要測；涵蓋source pin、非有限數、完整分母、固定配對、不可信宣告、
symlink／祖先交換、拒絕覆寫、失敗／中斷cleanup及CPU CLI。

真正原consumer的拒絕分支可用空的合成目錄做interoperability檢查；完整成功路徑的
歷史fixtures並未隨這次公開checkout具備。完整shape的合成報告只證明schema與聚合，
不是原run結果、full14B數值驗證、scorer重播或Kaggle狀態。

測試數字、CI 與缺失證據統一見[開發進度管理](DEVELOPMENT-PROGRESS.zh-TW.md)。
原始暫停 checkpoint `0451441` 的 race 與研究文件 `d13500c` 皆按其固定版本解讀；
不得將後續修復結果回寫為舊版本已通過。

## 6. 本地執行與研究回交程序（預設不執行）

### 6.1 接收順序與確切缺件

先讀本文、唯一[進度文件](DEVELOPMENT-PROGRESS.zh-TW.md)、
[方法總覽第7節](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)，再讀
[run008 原交接](../native-continuation-20261013/RUN008-LOCAL-HANDOFF.md)、
[transfer reconstruction](../../tools/arc_qwen_rlvr004_20261013/transfer_run008/README.md)、
[admission](../../tools/arc_qwen_rlvr004_20261013/admission_run008/README.md)、
[原 native operator](../../tools/arc_qwen_rlvr004_20261013/publication_run008/README.md)與
[目的端 POSIX successor](../../tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/README.md)。
舊文件的當時 transfer-only／stop-after-submit 記錄保留為歷史，不自行移植成當次授權。

公開 checkout **不構成完整可執行封包**。接收端以明確指定的檔案逐項驗證，缺件回報其
種類及需要的來源，不搜尋秘密、不從 fixture／compact report 補造。

#### 既有 A/B/C baseline 的原必要輸入

1. **原 run007／run008 reconstruction：** genuine Git snapshot
   `e951604b829497e81bc6e18b32662ff050bd54db`，原 authentic-inputs 的已核對 archive，
   `source-rebuild`、`candidate-rebuild`、`REBUILD-REPORT.json` 及311檔 inert
   `independent-reviewed-proposal`。傳輸 README 列出原 hashes 與有界重建命令。
   308檔 portable components 子集不等於完整候選；缺少歷史 fixture 的測試不能 skip-to-green。
   evaluator archive 保留隔離，必要的 opaque hash 不等於語意讀取答案。
2. **當次官方觀察與 authority：** 真正 owner direction、最新 notebook／Dataset bracket
   及其六個原始 readbacks（source、notebook before／after／status、Dataset before／after）。
   `admission_run008/seal_inputs.py` 只封存已有 readback，自己不查 provider。
   公開資料沒有原私人 bracket、owner direction、`draft-0001` 或完整執行 approvals；
   不生成假的歷史文件通過 validator。若既有接口不能產生當前所需 bracket，先回交缺口，
   明確審查新的有限讀取路徑，不能猜造命令或解除 gate。
3. **接收環境的實際 binding：** exact interpreter／SDK source lock／launcher／既有 trust、
   private local config、manifest／material／action／monitor-consumer review 及其獨立 hashes。
   現行 transport 固定 Kaggle2.2.4／kagglesdk0.1.37 和原 wrapper bytes；目的環境不同時，
   需要狹窄 portability successor 與審查。保留已審 wrapper 的正常 isolated HOME 設定；
   不得為規避拒絕而更換 HOME、關閉 TLS、改 proxy／權限或換存取途徑，也不複製憑證。
   正常 destination binding 必須獨立審查；登入與任何新增權限依當次確認規則獨立處理。
4. **真實模型材料與 owner gates：** pinned offline weights、完整 wheelhouse、獨立 code
   Dataset、訓練資料 lineage、原 owner admission／checkpoint／consumer／scorer 材料。
   loader 必須保持 installed pinned-wheel inventory、API／ABI、kernel mapping 和 byte
   identity 檢查，不能只看 cuDNN version string 或以系統 library 代替。原
   [loader repair](../../tools/arc_qwen_rlvr004_20261013/loader_repair_run008/README.md)
   的 CPU／ELF 通過不是目的環境 cuDNN／Qwen／GPU 通過。

#### 已產出的 audit：離線分析輸入，不是 baseline 的事前 gate

**真實 training audit 與 context：** 原 producer 的完整
`experiment/audit/sweep-N.json`、獨立保留的原檔 SHA、train32 records／exclusions、
source／plan／panel／sampling-policy／pre-update policy 收據，及據此明確建立的
`irisx/abc-audit-context-v1`。來源與 schema 見
[Stage 1 inputs](../../tools/arc2_abc_continuation_20261014/README.md#inputs-original-audit-bytes-not-a-compact-terminal-report)。
第一個真實 audit 檢查只接收每檔≤16MiB；先核對實際 bytes，較大即拒絕，不能切 batch、
截短、漏 slots 或放寬 reader。若前次根本未產生 audit，companion 保留
`MISSING_ORIGINAL_ARTIFACTS`，由通過原 admission 的既有 A/B/C 產生並在回收後分析；
不以「先要有 audit」阻擋首次原 A/B/C，也不能把 CPU fixtures 當原始執行資料。
以上是缺件核對清單，不聲稱任何私人材料已存在或可讀。只有在接收端已有適合依賴的
CPU 環境時，才照 Stage 1 README 執行 audit CLI 與 normal／`-O` focused tests；不自動
安裝模型／框架。原始檔與 context 雖通過，結果仍是 saved-scalar conformance，非真實
模型 replay 或更新放行。本文不另提供依賴缺失 admission 的可直接執行 RUN 命令。

### 6.2 先驗收原路徑，再考慮 changed trainer

分清兩條路徑：

- **既有 A/B/C：** 原 run008 source／材料／owner admission 與 repair readiness 通過，
  且當次執行範圍有效，即沿原 runtime 數學、原 model-owner 數值／狀態 gates 執行。
  若已有原 audits 就先核對；尚無 audits 則由這次原 A/B/C 產生，終態回收後再用 Stage 1
  CPU companion 分析。缺少事前 audit 或 CPU-only companion 都不增加一個阻止首次原
  A/B/C 的新 gate，也不改凍結研究安排。
- **未來 AF3 model hook：** 目前 Stage 1 只接受 CPU tensors，**不是 CUDA model hook**；
  把真實 tensors 複製到 CPU 不構成正式接線。真實原 audit conformance 是這條後續接線的
  證據輸入，不能用 fixtures 代替，也不能先偷換成 AF3 trainer 來產生它。

任何 changed trainer 先由研究開發端提出獨立 source-reviewed successor，並重新綁定
受影響的 assembler／runtime／consumer／active-wire 審查；現行 run008 assembler 只准
loader overlays，不能直接塞入 AF3 模組或沿用舊 admission。接線依
[shadow specification](../../tools/arc2_abc_continuation_20261014/README.md#local-shadow-wiring-specification)：
同 A lineage、同完整 batch、同真正 pre-update unchanged policy，逐軌跡 replay／backward，
比較每個 LoRA target 的 loss／finite gradient／差異，保留原 token／prefix／DFA／cache。
nonforced p95≤0.05、max≤0.20、strict-DDIS coverage=100% 不變，至少一個 LoRA target
非零；完整 batch 通過前不 commit，實測 rollback、save/reload、owner exit／closure。
所有 shadow／失敗／rollback 成本計入；若進 B，C 配對其整段 model-phase wall。

### 6.3 唯一 publisher 的有限提交與監看路徑

下列是現有 operator action 的順序索引，不是已執行紀錄或開放式重試授權。
原 `publication_run008` 的歷史wrapper綁定不適用移轉後機器。純POSIX方案保留於
[POSIX successor介面](../../tools/arc_qwen_rlvr004_20261013/publication_portable_20261015/README.md)；
本次選擇WSL持有state、Windows官方SDK沿用原profile的
[Windows／WSL bridge介面](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/README.md)。
該方案先完成下列6.3.1本地驗收，再承接相同publish／collect action。每次都需explicit
manifest/material/review/local-config及各自SHA；目前是否已驗收只讀單一進度頁，不以此程序當完成證據。

開始前另做目的端準備：

- 在持續存在的native Linux／WSL ext4路徑重建checkout與ignored scratch，保留原失敗。
  不把`/tmp`存活或DrvFS權限／rename／FIFO行為當成已驗證的native語意。
- 先完成原`transfer_run008/rebuild_engineering.py`的283檔source、426檔candidate與311檔inert
  proposal及各自report；移轉components子集與純單元測試不能取代這些真實重建。
- 以下兩項native POSIX登入／SDK步驟只適用純POSIX方案；目前選擇Windows橋時改用6.3.1，
  不在WSL建立OAuth。純POSIX方案建立或核對明確的Python3.12 venv，固定Kaggle2.2.4及SDK0.1.37，核對完整170-source closure。
  官方`python3.12 -m venv --copies /chosen/native-venv`可避免多層interpreter symlink；不要覆寫既存venv。
  在該新venv用`python -I -B -m pip install 'kaggle==2.2.4' 'kagglesdk==0.1.37'`安裝官方pins與相依，
  再跑`python -I -B -m pip check`；以`importlib.metadata`記錄版本與來源root，不要import Kaggle當作metadata probe。
  實際interpreter bytes、patch version、sysconfig purelib、real HOME及既有CA選擇寫入本次private local config，
  供獨立review綁定；不把個人機器路徑或config內容提交公開Git。
- 若native HOME尚無官方OAuth，先停在認證建立這一關。新的官方登入固定要求`resources.admin:*`，
  並保存native HOME/.kaggle，須另外取得使用者當次同意並由使用者完成官方consent。
  精確官方命令及來源見successor README；不得複製Windows store、改HOME、抽取token或擴權代替。
- 新collector SHA須由原assembler的explicit collector參數重新綁入proposal與consumer release，
  並重做相依material／transport／monitor／Git／active-wire reviews；原259 runtime members及21 helpers不改。
  使用successor的exact-version static-pin verifier；不要將原21／40／41寫死的review重用於另一組版本。

1. **核對、觀察、review：** 先靜態核對交付 SHA／bytes、當次授權及已有材料；經授權取得
   並封存當次 fresh read-only bracket，完成新的 proposal／final admission、destination
   action review 與完整 local config。候選及 manifest/material/review 齊備後，才做不建立
   Provider 的 local `validate`，再進 `readiness` 重查 exact numeric identities、source、
   privacy、settings、mounts、status 與無衝突 active run。`validate` 需要成形契約，不能
   用來代替缺失候選的重建。保存 claims／journals；
   有未知寫入先 read-only reconcile。歷史 code20／notebook39 ERROR 及預估21／40／41
   都不能當本次現況或可用版本，plain ERROR 不等於 GPU 不可用。
2. **code 與 mount：** 只由唯一 publisher 對 reviewed `code-payload` 做一次 claimed
   `update-code`；weights／wheels／資料與 code 各自版本化，保留原七個 non-code pins。
   `verify-code` 或 exact numeric `verify-code-files` 做完整 bytes／closed inventory
   readback，再由 `admission_run008/accept_numeric_mount.py` 通過真實下載的 owned
   no-model mount acceptance。不可上傳整個 repo、候選、私人 receipts 或 evaluator archive。
3. **inactive 與靜態審查：** `save-inactive` → `verify-inactive`，核對真實 numeric source、
   settings／Dataset identity，GPU／TPU／Internet OFF。取得 persisted-readback audit、
   新 independent stage2／monitor-consumer／static-pin reviews；原21個 consumer helpers
   與 collector binding 保持 closed，不能以純 source review 代替這些動態證據。
4. **準備、獨立檢查、一次 RUN：** `prepare-active` 只建立一個新的 immutable predispatch
   epoch 與四個 JIT 文件：`active-finalized.ipynb`、`original-request.json`、`operator.json`、
   `parent-private-scorer.json`。保留 finalization、wire、prepared journal；由
   所選successor的`verify_active_wire.py`依其格式及當次真實 static pins 核對，產生對應獨立 active
   review 後才 `activate`。60秒 dispatch-age 上限不變；stale preparation 保留並停止，
   不能自動重抽時鐘。一次 accepted／uncertain send 後用 `verify-run` readback/reconcile，
   不能把讀取中斷當理由重發 RUN。provider 接受不等於已跑模型。
5. **直到終態與完整回收：** 同一 admitted numeric run 用 `collect watch` 或其等價已審查
   poll/collect 流程持續監看；QUEUED／RUNNING／暫時無輸出都不是完成。transient read
   backoff，terminal 後仍繼續到 selected outputs 完成 indexing／下載／驗證，或出現需
   回交的實際 blocker。讀回 exact source、logs 與結果，驗證原 owner、closure、seals、
   原 consumer／scorer；不因 provider COMPLETE 就停止，也不假定所有 outputs 都已盤點。
   原 collector 只收 selected outputs；log 缺失或截斷須明列，不能繞過其有界傳輸限制。

所有 setup／queue／learning／inference／scoring／closure 都在原43200秒內；保留
inner42000／outer42180／provider42300 offsets。整場已消耗時鐘及每次 physical charges
不重置或退還；新 reviewed attempt 才能有自己的明確新 identity／clock，舊結果永久保留。
實際 GPU-unavailable／zero-hours 回報即停止後續 dispatch，不查 quota、不新開資源或付費。
使用原單張 NvidiaRtxPro6000 訓練資源；4×L4 是另外的最終推論驗證，不能以單訓練卡
或 CPU 通過推定4×L4能部署。Internet-off 與既有 ARC3 metadata association 保留，
不讀 ARC3 task data、不做官方 competition submission。

### 6.3.1 沿用既有Windows登入的本地橋接驗收

這是選定的目的端實作，不另改研究方法。WSL的checkout／candidate／state／scratch保留在
persistent ext4；Windows只接收同一固定commit的公開bridge來源、獨立venv及非秘密本地設定。
原登入留在原Windows profile，由官方library使用；沒有新的WSL OAuth、credential搬移或HOME替換。

1. 核對交付commit／tree與所有source bytes。另在Windows實際native路徑放置相同bridge source；
   不以換行轉換的checkout替代Git blob。native config的七檔來源必須同時等於WSL reviewed sibling。
2. 用既有官方Python3.12建立新的Windows venv，不覆寫既有環境。以該venv執行：

   ```powershell
   & <official-python.exe> -I -B -m venv <new-native-venv>
   & <new-native-venv>\Scripts\python.exe -I -B -m pip install 'kaggle==2.2.4' 'kagglesdk==0.1.37'
   & <new-native-venv>\Scripts\python.exe -I -B -m pip check
   ```

   保存實際package版本／官方wheel來源及hash；metadata使用`importlib.metadata`，不為檢查版本
   import Kaggle。SDK lock只覆蓋170個官方Python來源，不能代稱整個venv供應鏈已鎖定。
   WSL owner只需原Python3.12與標準函式庫；不將Windows帳號設定傳入WSL。
3. 以新Windows venv `-I -B`跑`native_probe.py`，保存stdout JSON、stderr、exitcode與hash；
   必須十案例完整通過，來源四hash及venv executable／base executable／pyvenv.cfg均吻合。
   另從WSL執行同commit的`wsl_native_probe.py`，實際測caller死亡→pipe EOF→native Job全清空。
   兩者皆為合成程序；歷史global Python原8案例不能代替新版實測。
4. 由本地metadata建立ignored native config：實際token SID/profile、venv/base executable bytes、
   pyvenv.cfg、Python patch、purelib、完整七檔來源、既有network環境hash及同一版本配置。
   不修改proxy／TLS／ACL，不加權限，不讀出或填入credential值。WSL config另綁現有
   WSL_INTEROP socket selector與exact drive mapping、native config與genuine probe receipt的hash。
   若WSLENV帶入未審查跨OS環境設定，停下說明，不靜默變更系統設定。
5. 以同commit的`preauth_probe.py`測正式supervisor／worker CLI，僅send open、驗證ready後
   故意不送ready_ack並關閉input，要求nonce-bound Job-zero closure。此時官方SDK只驗source及
   store metadata，未載入credential內容／登入／RPC。失敗或無closure保留unknown，不繼續認證。
   確切CLI參數看該工具`--help`；沒有把probe結果改寫為provider PASS。
6. 新source／native實測／config皆交獨立review。全15檔operator source要已commit且remote驗證，
   原collector、proposal、consumer、material、monitor、active-wire每條相依hash重新綁定。
   接著回6.3第一步的fresh official observation與完整admission，才可走正常既有auth／readiness。
   任何官方refresh均由Windows官方library保存原store，前後要求WSL fsync ACK；中斷或未知不自動重送。

所有diagnostic／local config／原始log留ignored側；對研究端只回傳來源與非秘密結果／hash／缺件。
若閉合的來源、runtime、ACL或原credential metadata不符，停在精確失敗點交回修復，不停用gate。
跨OSworker的12h lease只約束該worker，不等於原實驗clock；只允許clean read-only輪替。

### 6.4 本地修復邊界與研究決策

本地端可在當次明確授權內診斷並修復可重現的有限工程問題，例如 packaging／path
binding／transport readback／已定位的 loader selection；先保留 failed source、錯誤、
receipts、logs、clock 與成本，測試與獨立 review 之後才準備 distinct successor。
修復使用獨立工作區／repair branch，記錄明確新 source commit、delta 與 review，交回研究
開發端審查整合；不覆寫其正在開發的工作區／分支，也不悄悄寫回 frozen run008。
不盲目重送相同候選、不抹除 claim、不因失敗放寬 exact-byte／數值／isolation／closure。
原 collector 不會 relaunch；下一次提交必須重新走上列 source／admission／readback gates。
唯一 publisher 指當次 Kaggle mutation 的單一責任者，不授予任意修改其他工作線的權限；
未知 provider 寫入先 reconcile，不能把未知當成未發生後重試。敏感材料或下載遭拒仍停止，
不改用其他下載／存取途徑繞過。

若需要改演算法、sampling／parent、分母、budget、硬體／資源、資料存取、material pins、
新的權限／認證／法律承諾，或現有介面無法安全完成必要步驟，先回交研究開發端／協調者，
不以「修復」代替授權或科學設計。不能靜默加入 AF3 runtime、OPSM、entropy、async、TTT，
不能在 all-zero 後追加抽樣。

首輪固定 A=同 session SFT256 並 save/reload；B=train32、最多4個不重疊64-slot batch、
最多256 attempts／4次更新；C=同 A＋fresh optimizer 的額外 SFT，匹配 B **整段同步
model-phase wall**（setup、sample、reward、replay、失敗／rollback、save/reload/verification），
不用 idle padding。dev16 只選一次，tie A→B→C；凍結後才 selected PUBLIC、held32
predictions、model closure、隔離 scoring。PUBLIC120始終120 tasks／167 queries，固定
兩視圖334 planned views；答案不進 solver、training、prompt、selector 或記憶。

結果回交後依[既有方法順序](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)：
- 工程／replay incomplete：先補證據或修復，不能判成0分或方法無效。
- 完整 all-zero／all-one、無相對 reward 訊號：保留 zero-signal，不補抽樣；研究端再決定
  train-only curriculum／verified trajectories／rejection-SFT 的獨立對照。
- 有真實更新：先完成 A/B/C；B>A但未勝等成本C，不支持 RL 額外價值。有淨增益才安排
  新獨立 panel／family 重複，再一次改一項；reused held32 不稱全新確認。
- 穩定可重載 baseline 及預算足夠後才獨立 TTT；program／repair 要和獨立提案同成本；
  只有 evaluator 診斷出候選池含正解但 top2 流失，才考慮 selector／多角色，不回灌答案。

### 6.5 終態回交內容與完成標準

回交的是一份去敏結果摘要加有限的來源／artifact hash 清單，供研究開發端選下一步；
不另建第二份 mutable 進度表或 handoff。協調者把結論與證據索引寫回唯一進度文件。
摘要最少包含：

1. 實際 source commit/tree、runtime／archive／manifest／code-byte hashes、精確 numeric
   Dataset/notebook/run 版本、UTC觀察時間、原 epoch/deadline、來源變更與測試／review 範圍。
2. 各欄分開：provider terminal、safe model/runtime closure、comparison complete、B/C
   compute matched、完整 scorer、method efficacy。每欄明列 passed／failed／unknown／not-run，
   缺 scoring 保留 null，沒有可用數據不能填0。CPU、GPU、4×L4 與 CI 狀態分列。
3. planned256／dispatched／eligible／infrastructure excluded／context excluded／not reached；
   完整 all-zero／all-one／mixed groups、pass@8 coverage；非法模型答案0與基礎設施null分開。
   replay p95/max／nonforced coverage、committed updates、rollback、save/reload 與 lineage 證據。
4. A/B/C wall、全B model-phase wall與C、tokens／forward work／memory、失敗及shadow成本；
   unknown physical cost／billing 不猜值。固定dev選擇 provenance、相同case gain/loss、
   PUBLIC120/167有效分數與held32重用限制；原始case IDs／grids不放公開摘要。
5. 真正阻塞點、已做的有限修復／仍缺前提，以及對第7節哪個條件有證據；不要自行 promotion、
   successful-baseline tag 或在回交前偷偷換下一個研究方法。

原 collector 的有限 evidence 檔名為 `TERMINAL-VALIDATION.json`、
`TERMINAL-CHECKPOINT.json`、`RETRIEVAL-RECEIPT.json`；失敗分支可能只有
`TERMINAL-DIAGNOSTIC.json`、`TERMINAL-BLOCKER.json` 或 `WATCH-BLOCKER.json`。
只記錄實際存在的檔案及獨立保存的 hash，不能補造成功三件組。原始 logs、完整 receipts、
training audits／context、checkpoint、模型、evaluator data 與 archives 留在其原有私有邊界；
不直接貼進 Git／handoff 或交給研究端的公共封包。去敏衍生摘要須標為摘要，不能冒充原收據。

當次程序到「terminal＋可取得 outputs 的驗證＋分類後回交」才完成；若權限、安全 gate、
材料或 provider 狀態真正阻塞，回交 exact action／target／blocker，保留待決狀態。
QUEUED、accepted RUN、CPU pass、source 發布或 collector exit0 都不能替代這個完成條件。
