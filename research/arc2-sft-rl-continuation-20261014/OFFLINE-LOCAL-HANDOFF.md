# ARC-AGI-2 本地執行與結果回交

先讀[研究問題與凍結 A/B/C](README.md)，再讀[當前進度](DEVELOPMENT-PROGRESS.zh-TW.md)。
本頁只有一條接手流程：固定來源與材料 → 本地驗收 → 唯一 publisher 提交與監看 → 真實結果回交。
命令與 schema 以各工具 README 為準；舊版本的特殊恢復步驟只保留固定歷史連結。

## 交付範圍

使用者已授權沿既有 run007／run008 notebook 模式，持續「開發 → Kaggle 執行 → terminal／結果分析 →
依證據決定下一輪」的研究循環；在這個範圍內的例行續接不逐輪重新詢問。研究開發端先交付經測試、
獨立審查的精確來源、變更與缺件；本地端仍須逐次通過原材料與全部 admission。文件、Git 保存或
CPU 通過本身不代替這些必要條件。新增費用、資源、權限或超出研究範圍的變更仍需另行確認。
本地端是當次 Kaggle mutation 的唯一 publisher；研究開發端不代登入、不持有 credentials。

Stage 0／Stage 1 companion 只做離線準備與已存在結果的條件式解讀，不訓練、不收集 provider
結果、不重跑 scorer，也不製造原始私人 admission。原 audit 尚未產生時，由通過原 admission
的原 A/B/C 產生；不以「先要有 audit」阻擋首次比較。真正 AF3 模型 hook 是另一個需審查的 successor。

## 取得與核對

1. 接收協調者核對過的完整 commit／tree、變動清單、review 與驗收範圍，確認本地 bytes；
   移動分支名稱與歷史測試數字不能替代來源身分。原 frozen runtime 基準為
   `cc14bd1a79aac1fe6135017c9e09d4834300675d`，目前交付與未發布修復以進度頁區分。
2. 保留舊 checkout 原址與其 descriptors、candidate、STATE、clock、claim／journal、失敗及 raw receipts；
   新來源用明確獨立位置，不在原 f5 等已綁定 checkout 原址改檔，也不回寫 frozen runtime。
3. 核對接收環境、真正材料及獨立 review。公開 checkout 不是完整可執行封包；
   缺件就回報種類與來源，不能用 fixtures、compact report 或猜測版本補造。

### 固定來源交付身分

各次已公開指紋見[歷史來源收據](archive/engineering-history.zh-TW.md#原-stage-1-與-transport-交付指紋)。
它們識別歷史程式，不是新版本 admission；本次精確來源與狀態只見[當前進度](DEVELOPMENT-PROGRESS.zh-TW.md)。

## 1. 產生不會啟動工作的計畫

使用 [Stage 0 介面](../../tools/arc2_sft_rl_continuation_20261014/README.md#interfaces)的
`cli.py prepare`；命令旗標以該固定版本 `--help` 為準。
只需 Python 標準函式庫與支援 descriptor-relative no-follow API 的 POSIX 環境。
計畫的 `not_inspected` 不可改稱材料已存在；不在不支援的 Windows 檔案操作上停用 gate。

## 2. 解讀已經存在的本地 collector 報告

使用同一 [Stage 0 介面](../../tools/arc2_sft_rl_continuation_20261014/README.md#interfaces)的
`cli.py analyze`，明確指定原 `TERMINAL-VALIDATION.json` 及獨立保存的 SHA256。
如有原 checkpoint／retrieval receipt，成對提供檔案與各自 SHA；不沿 JSON 內路徑搜尋或下載。
舊 SFT64／full-sweep schema 不能靜默套用。

原始 training audit 的獨立 opt-in CLI、context schema 與依賴見
[Stage 1 輸入](../../tools/arc2_abc_continuation_20261014/README.md#inputs-original-audit-bytes-not-a-compact-terminal-report)及
[CLI](../../tools/arc2_abc_continuation_20261014/README.md#cli)。每檔上限 16MiB；
超限明確拒絕，不能切 batch、截短、漏 slots 或放寬原 reader。compact report 無原始 trajectories，不能代替 audit。

## 3. 正確閱讀結果

- exit0／`OFFLINE_OUTPUT_WRITTEN` 只表示寫出檔案；仍須檢查 consistency、issues、unknown／rejection。
- 缺 scoring 保留 null。PUBLIC 分母固定 167 queries、預期 120 tasks；compact report 無法證明 task inventory。
- saved log-probability 可比 loss／logp gradient，不能重建真實模型 graph／LoRA gradient；宣告 hash 也不驗證 provenance。
- dev count／tie 自洽不證明 selection seal；配對 gain/loss 只在真正相同案例成立。
- 完整 zero-signal、incomplete、先前已 commit 而後續失敗分開；只有整個 B 從未更新才檢查 B=A。
- CPU、native、provider、runtime closure、comparison、cost match、scorer、方法收益與 CI 分欄，不互相代替。

## 4. 檔案安全與中斷後續接

[Stage 0 安全契約](../../tools/arc2_sft_rl_continuation_20261014/README.md#interpretation-and-safety)
保留明確常規檔、16MiB、exact hash、no-follow、嚴格 JSON、exclusive output 與 descriptor-relative cleanup。
不覆寫既有輸出，不掃描／刪除任意暫存。錯誤或中斷後完整輸出可能已存在，先在可信目錄核對，
保留原檔再選新檔名；拒絕不等於「什麼都沒發生」。未知 provider 寫入更不能當未發生後重送。

## 5. 測試與證據範圍

具體命令與固定證據見 [Stage 0 審查](offline-continuation-review.md)、[Stage 1 審查](stage1-independent-review.md)、
[AF3 驗證](agent-factory3/validation.md)與 [bridge 驗證收據](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/VALIDATION.json)。
normal／`-O`、失敗／timeout／cleanup、來源不變與獨立 review 均依最終來源驗收。
完整 suite／CI 的既有失敗與缺 fixtures 保留；沒有重跑的範圍明列未重跑。
歷史 native PASS 不自動適用變更過的 supervisor／worker；新版本必須有自己的適用性證據。

## 6. 本地執行與研究回交程序（預設不執行）

### 6.1 接收順序與確切缺件

只核對明確指定的原件，不搜尋秘密、不複製 credentials、不讀 evaluator 答案補欄位：

- **原材料：** genuine reconstruction、完整 source／candidate／proposal 與 reports，來源與指紋依
  [transfer README](../../tools/arc_qwen_rlvr004_20261013/transfer_run008/README.md)。歷史 283／426／311 是原重建身分；目前 canonical successor 以自己的 inventory 為準，components 子集不能代替。
- **原 admission：** owner direction、六件官方 bracket readbacks、proposal／final admission、
  destination action／material／monitor reviews。入口見 [admission README](../../tools/arc_qwen_rlvr004_20261013/admission_run008/README.md)。歷史 observation 可作組裝來源，不能冒充 fresh readback。
- **模型／資料：** pinned offline weights、完整 wheelhouse、獨立 code Dataset、train-only lineage、
  原 owner／checkpoint／consumer／scorer。loader 的 pinned-wheel inventory、API／ABI、kernel mapping 與 bytes 必須成立，CPU／ELF 檢查不能代替 GPU。
- **目的端：** 精確 interpreter、官方 Kaggle2.2.4／SDK0.1.37、來源 closure、config 與 native acceptance。
  WSL 持有 persistent ext4 state／owner；Windows 官方 library 在原 profile 使用既有登入。
  不改 HOME、TLS、proxy、ACL 或權限，不抽取 token、不另建 WSL OAuth 迴避原邊界。

### 6.2 先驗收原路徑，再考慮 changed trainer

原 A/B/C 保留 frozen runtime 與原 model-owner gates。AF3 CPU companion 不是 CUDA model hook；
把模型 tensors 複製到 CPU 也不構成正式接線。未來 changed trainer 必須另立來源與審查，
重新綁定受影響的 assembler／runtime／consumer／active wire，不把 AF3 模組塞進只准 loader overlays 的原封包。

真正模型接線要求同 A、同完整 training batch、同 pre-update unchanged policy，逐軌跡比對 loss
與每個 LoRA target 梯度，保留原 token／prefix／DFA／cache、replay 門檻、完整 batch 才 commit、
rollback／save-reload／closure 與全成本。詳見 [AF3 模型驗收](agent-factory3/integration.zh-TW.md#本地模型證據的驗收契約)及
[shadow 規格](../../tools/arc2_abc_continuation_20261014/README.md#local-shadow-wiring-specification)。

### 6.3 唯一 publisher 的有限提交與監看路徑

在上述已授權研究循環內，全部 admission 成立才續接；目前 blocker 見進度頁。以下是固定順序，
不是未知寫入的自動重送授權。沿用 run007／run008 的離線 notebook，code 與 weights／wheels／資料 Dataset
分開管理並鎖定精確版本，不另建偏離研究問題的 notebook 模式。
實際 action flags／config schema 見 [Windows／WSL bridge](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/README.md#sourceconfig-interfaces)。

1. **固定來源、材料與純預檢。** 完成一次 reviewed canonical candidate、真實獨立 release review 與完整相依 pins；
   同一 actual owner 核對 config、STATE 與原歷史。以完整 manifest／material／review／config 及 SHA 執行
   `publish validate`、`publish validate-publication`；後者需要真實 monitor review 與 consumer root。
   純 PASS 不代表發布；精確 no-auth／目前 runtime 驗收及未解除 UNKNOWN 仍是獨立條件。
2. **Fresh readiness、一次 code 發布與驗收。** 正式 readiness 重查 exact numeric identities、source、
   privacy／settings 與無 active conflict。通過後依 `update-code` 的 retention gates 及 claim 發布；
   `verify-code`／`verify-code-files` 核對完整 bytes／inventory，再做真正 numeric mount acceptance。
   weights／wheels／資料與 code 分版本，原七個 non-code pins 不變；只上傳 reviewed code payload。
3. **Inactive 與動態審查。** `save-inactive` → `verify-inactive`，核對 numeric source／settings／Dataset，
   GPU／TPU／Internet OFF；取得 persisted-readback audit 及真正 stage2／monitor／static-pin reviews。
   不把靜態來源審查當成尚未存在的 readback 證據。
4. **JIT 與一次 RUN。** `prepare-active` 建立 immutable epoch 與原四件組：active-finalized notebook、
   original-request、operator、parent-private-scorer；獨立 active-wire review 後才 `activate`。
   60 秒 dispatch-age 不變；過期保留並停下，不能自動重抽 clock。accepted／uncertain send 後
   只以 `verify-run` readback／reconcile，不因讀取中斷重發 RUN。
5. **監看到真正終態與回收。** 對同一 admitted numeric run 持續 `collect watch` 或已審查等價流程；
   QUEUED／RUNNING／暫無輸出不是完成。terminal 後繼續到可取得 outputs 完成 indexing、下載及
   原 owner／closure／seals／consumer／scorer 驗證，或有需回交的實際 blocker。原 collector 有界收集，
   缺／截斷 logs 明列，不能用 provider COMPLETE 或 collector exit0 代替研究結果。

整場 43,200 秒與原 inner42000／outer42180／provider42300 offsets 不變；所有已耗時鐘與 physical
charges 保留。worker lease 與實驗 clock 分開，clean read-only 輪替不能重置研究時鐘或解除未知寫入。
使用原單張 NvidiaRtxPro6000 資源；4×L4 是另待驗證的最終推論環境。實際 GPU-unavailable／
zero-hours 回報即停 dispatch，不查 quota、不增資源或付費。保留 Internet-off 與既有 ARC3 metadata
association，不讀 ARC3 task data、不做官方 competition submission。

### 6.3.1 沿用既有Windows登入的本地橋接驗收

入口見 [bridge README](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/README.md)。
精確來源、venv／base executable／pyvenv.cfg 與當次 source/config review 依實際版本驗收。
同一 release 的驗證只做一次；來源／設定／runtime 不變時重用原收據。native 十案例、
WSL caller-death、正式 pre-auth 只針對受影響的邊界重驗，不能把舊來源收據直接標成新來源 PASS。正常認證與 refresh 留 Windows 官方 library，
保留 WSL intent／completion 兩次 durable ACK；不確定即停止。原安裝細節見
[e491 固定說明](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#631-沿用既有windows登入的本地橋接驗收)，不因新修復重建已符合的 venv。

### 6.3.2 原failed-open的獨立恢復邊界

**此舊路徑只對應 E41 原 29 檔事件。** 原一次性人工 Restart／read-only reconciliation 已有 E47 結果。
原文見 [e491 固定恢復說明](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#632-原failed-open的獨立恢復邊界)；
不能拿來自動重跑或解決新的 ddd UNKNOWN。新事件只依其實際來源、證據與已審查 disposition 處理；
原 UNKNOWN／closure false／claim／journal 不修改、不刪鎖、不換 namespace。

### 6.3.3 已完成恢復後的同boot context續接

[原 context 說明](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#633-已完成恢復後的同boot-context續接)保存 f5→a724 的歷史邊界。
舊 checkout 原址、sealed history 與實際 WSL owner 不得以示範值替代；新 source／config 要依目前
release 的真實 review，不把歷史 runtime 驗證冒充目前 runtime 已驗收，也不重播已消耗 capability。
歷史恢復只驗證原封存來源、同 host／boot、相同 STATE／scratch 與精確 pending；目前候選／
來源／設定由當前 release 的原 gates 驗收，不再要求它們等於舊模板或另造 migration review。

### 6.3.4 Collector-only canonical material續接與完整發布預檢

[工具介面](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/README.md#one-release-admission-and-a-stable-collector-bootstrap)
說明穩定 collector bootstrap 與 publication view；
[e491 canonical 程序](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#634-collector-only-canonical-material續接與完整發布預檢)
保留原 assembler 與歷史收據。當前路徑只做一次完整 release admission，`material_lineage.py`
不再是必要續接 gate，不再為每次交接重做兩份 candidate 或要求 collector-only migration review。

collector 或 deployment bytes 有實質變更時，仍須以固定新來源，沿用原 assembler 正規生成
proposal→真實 runtime/material review→final candidate，並通過原 `validate-publication`。
不得手改已批准 candidate 的 hash。之後只有 transport/common 修復時，collector 不再為嵌入
兩個 literal pins 而改 bytes；明確傳入的 review hash、來源 descriptors 與全部原契約仍逐一核對。
accepted RUN 後不得換 review 來重新解釋該次結果。

14:20 的 ddd failed-open 可由 `preworker_disposition.py` 唯讀檢查固定 f5 native/source、
exact claim/open request、四個原始 events 與完整 diagnostics；只有實際資料全匹配才得到
SDK worker／JobProcess 未啟動的 disposition。supervisor/proxy 本身曾執行；這不是 Job-zero。
原 90 檔與 UNKNOWN／closure false 保持原 bytes，只讓歷史 validator 的 view 排除精確該 pair。
缺少或矛盾的資料、其他 UNKNOWN／pending refresh 仍阻擋，不補造 raw receipt、不自動重啟。

本地最短接續：固定 release 與一次受影響 no-auth 驗收 → 原 assembler 與單次完整材料驗收 →
既有 owner/lock 下檢查真實 90 檔與當前 context → fresh readiness → 第 6.3 節原發布及監看。
這些靜態／CPU 檢查不等於本地 disposition 通過、provider 接受或完整 A/B/C。

### v41 啟動修復的本次差分

1. 保留 v41 的五份 numeric outputs、原 clocks、v21／v40／v41 readbacks 及所有原 STATE。
   fixed source 修改兩個 deployment caller、collector nullable schema，及一個 runtime policy 的
   6 個固定 offline-guard 環境值（加上 derived release self-pin）；Windows
   supervisor／worker／protocol／auth／SDK bytes 未改，同一已驗證 runtime 的 native 收據可重用。
2. 使用本次 [admission assembler](../../tools/arc_qwen_rlvr004_20261013/admission_run008/README.md)
   沿既有 proposal → 真實 review → final 流程一次重建。原 source proposal 仍唯讀；assembler
   驗證 consumed v41 caller hashes 後覆蓋兩個新 caller；runtime 的其餘 257／259 與科學 bytes 不變，
   source／archive／normalized self-pin 正規重算並核對固定新值。
   新 deployment inventory、assembler／collector SHA 由原 review／manifest／consumer 契約傳遞；
   不手改舊 approved candidate，也不加入 material-lineage 或第二份 candidate 門檻。
3. 只核對本次變動與完整當次 pins，fresh readiness 確認目前 dataset／notebook／active status，
   再循第 6.3 節原提交與監看。最後已知是 v21／v41 ERROR，下一組數字必須由實際觀察推導。
4. collector 的 null 欄位只修相容性；對原 v41 五份已下載 bytes 可做明確離線回歸，不能把
   合成測試當真正 terminal receipt。新 run 若仍失敗保存實際診斷；缺 log／inventory 明列未知。
   官方 exact-version listing/log 支援另行完成，沒有可讀版本 echo 時不宣稱 server attribution。

### 6.4 本地修復邊界與研究決策

當次明確授權內的有限工程修復，先保存失敗 source／receipts／logs／clock／成本，再測試、獨立審查
與另立 successor；不覆寫歷史、不盲目重送、不放寬 exact-byte、數值、isolation 或 closure。
敏感材料或存取遭拒即停止，不換途徑規避。變更研究方法、parent／sampling、分母、budget、資源、
資料、權限／認證或法律承諾需回交，不以工程修復代替授權。
科學順序只見[方法決策表](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)，不在交接另立新計畫。

### 6.5 終態回交內容與完成標準

回交一份去敏摘要與實際 artifact hashes，更新唯一進度頁：

- source commit／tree、runtime／archive／manifest／code hashes、exact Dataset／notebook／run versions、
  UTC 時間、原 epoch／deadline、當次測試與獨立 review 範圍。
- provider terminal、safe runtime closure、comparison complete、B/C cost match、完整 scorer、method efficacy
  各欄的 passed／failed／unknown／not-run。CPU、native、GPU、4×L4、Git 與 CI 分開；缺 scoring 保留 null。
- planned256、dispatched、eligible、infrastructure／context excluded、not reached；完整 all-zero／all-one／mixed、
  pass@8、nonforced replay p95／max／coverage、committed updates、rollback／save-reload 與 lineage。
- A/B/C 全 wall、B/C 完整 model-phase wall、tokens／forward work／memory、失敗及 shadow 成本；
  dev selection provenance、相同案例 gain/loss、PUBLIC120／167 與 held32 重用限制。未知成本不猜值。
- 真正 blocker、已做的有限修復與仍缺前提，以及支持哪個研究判斷；不自行 promotion 或成功標籤。

原有限收據為 `TERMINAL-VALIDATION.json`、`TERMINAL-CHECKPOINT.json`、`RETRIEVAL-RECEIPT.json`；
失敗可能只有 `TERMINAL-DIAGNOSTIC.json`、`TERMINAL-BLOCKER.json` 或 `WATCH-BLOCKER.json`。
只列實際存在者，不補造成功三件組。原 logs、training audits／context、模型、完整 receipts、
evaluator 與 archives 留原私有邊界；去敏摘要不能冒充原收據，不公開 case IDs／grids 或 credentials。

單輪完成條件是 terminal＋可取得 outputs 驗證＋分類回交；接著依既有 ARC-AGI-2 決策條件，
在已授權範圍內開發並驗收下一輪，不以 ERROR 當方法成功，也不為了換輪次任意換方法。
若有真正權限／安全／材料／provider blocker，回交 exact action／target／blocker 並保留待決。
accepted RUN、來源發布或 CPU PASS 都不是完成。
