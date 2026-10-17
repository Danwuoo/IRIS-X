# ARC-AGI-2 本地執行與結果回交

先讀[研究問題與凍結 A/B/C](README.md)，再讀[當前進度](DEVELOPMENT-PROGRESS.zh-TW.md)。
本頁只有一條接手流程：固定來源與材料 → 本地驗收 → 唯一 publisher 依當次授權提交及讀回。
目前以最新條件式持續授權及本輪真owner scope為準；觀察、接受、監看與結果不可互相冒充。
命令與 schema 以各工具 README 為準；舊版本的特殊恢復步驟只保留固定歷史連結。

## 當前 source003：保留真 final，修歷史觀察邊界（2026-10-16）

已公開 `500502f174608c5eb42085f05e9efd2480b31b6f` 完成 capture／owner scope 接線。
本地五讀官方capture已觀察code24／v47 ERROR，source／settings前後相同，新native clean-close。
source003三份真review及外層review已完成，但validate-publication在Provider前拒絕歷史code24
缺active receipt。本次修復的normal／-O各95項focused測試通過，真history驗收尚待本地。
尚無新code／inactive／RUN／epoch。不要重跑capture或重建科學封包。

1. 保留真final manifest
   `7c86896b297b7094b3131c0715820bee263bf3d43e32941a1b34f506d1f39c30`、原proposal／reviews與sealed
   observation `a3202c931e019c54bd43a1d53454938bbd603c10f00e292b0b8512335ae0e1fe`。
   原source003260件、canonical `42062ef934a7c5495f8d22b6a68faa715301b47b9875eef829f0988056877c75`，
   archive15,820,672bytes／`a425250bb0541981a04b9814f6edf00695b9c574ccb207035c6fd4a61980f78e`不變。
2. 本次修復是外部operator的固定觀察式disposition，僅處理原code24／v47：舊manifest、
   claim／journal／wire／finalization、新final及已有raw觀察皆須逐hash成立。
   只在active receipt與saved同時缺失、save_intent／save_calls1原件未變時使用；
   code／inactive／retention與native／refresh仍照舊fail-closed。
3. 固定新的完整commit／operator22及dependency pins後，更新真外層operator/config/action/source
   reviews，明確核准外部依賴重綁。保留private final原bytes，不重新assembly、三份科學review或
   改其archived review-only helper。不宣稱舊private final整棵樹與新operator相同。
   只跑受影響測試與該真history proof驗收；未變native／SDK／模型不重建。
4. guard會以新final內的sealed observation核對六份raw、terminal、完整metadata與settings、sourcehash，
   只建立「目前前置版本已觀察為終態」邊界，不補原Save接受或normalized_source_exact。
   observed source與原wire只差四個cell id與nbformat_minor，原兩個strictnormalizer不變。
   原7,050件STATE、缺receipt、UNKNOWN、save_calls與v47epoch1792136130全部保留。
5. 目前使用者重新授權：正常登入與操作的條件成立時，Astra依既有研究持續開發／監看。
   保留既有final內已綁定的真owner mode；新action reviews須如實綁同一scope。continuous需stop=false、
   single_post_submit_readback_authorized=false、monitor/retrieval=true；once模式則消耗後仍STOP。
   不事後修改已封存scope或claim解鎖；任何403／UNKNOWN／不確定寫入仍停止、不盲重送。
6. 真history窄驗收與更新外層reviews成立後，接現有final沿原流程：code發布／逐檔回讀→真mount
   →inactive／讀回→動態前置review→prepare-active／JIT→真active-wire獨立review→一次activate。
   最後review／dispatch仍須在原60秒freshness內；activate內已做初次來源／設定／狀態讀回。
   正常接受與讀回後，才依本輪真continuous scope啟watch／既有結果取回；once不得再verify-run。
7. 所有新mutation前仍要即時核對dataset及精確前置source／terminal。封存觀察不是遠端保留名額；
   若版本、來源、設定或狀態變動就停。後續輪由相鄰已審查manifest重驗同一code24邊界，
   不回寫舊history，也不接受其他未審查的缺receipt情況。
8. 新session epoch只在原JIT、真dispatch前量取，保留42000／42180／42300／43200秒邊界。
   A256＋首批64＋固定兩座標最多8個shadow／120秒，零RLcommit；其餘192／C／dev／held／PUBLIC未請求。
   CPU、native、官方接受、GPU與科學結果分開回報，維持唯一publisher與答案隔離。

## 交付範圍

使用者已授權沿既有 run007／run008 notebook 模式，持續「開發 → Kaggle 執行 → terminal／結果分析 →
依證據決定下一輪」的研究循環；本次執行以頁首最新條件式指示及真owner scope為準。研究開發端先交付經測試、
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

## 6. 本地執行與研究回交程序（依已授權循環驗收後執行）

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

### 6.3.3 已完成恢復後的歷史與即時context續接

[原 context 說明](https://github.com/Danwuoo/IRIS-X/blob/e491ba4be3562d48d78f4f615a1dd155bcdc0cfc/research/arc2-sft-rl-continuation-20261014/OFFLINE-LOCAL-HANDOFF.md#633-已完成恢復後的同boot-context續接)保存 f5→a724 的歷史邊界。
舊 checkout 原址、sealed history 與實際 WSL owner 不得以示範值替代；新 source／config 要依目前
release 的真實 review，不把歷史 runtime 驗證冒充目前 runtime 已驗收，也不重播已消耗 capability。
歷史恢復以原 after-Restart observation 與原 completion time 交給未修改的 f5 validator 重驗，
只處置原995 UNKNOWN。這份真實原件間隔12.629秒；其他 history 若超出原120秒 freshness
仍拒絕，不改時間或加容差。這是已完成的程序終止邊界，後來校時或再開機不會使舊程序復活。
即時另做 fresh no-auth observation、同 host／Windows／source／runtime 與原 observation closure
驗證；不宣稱已證明 same boot，也不宣稱全系統程序不存在。相同 STATE／scratch、精確 pending、
封存 event bytes、當前 publication 與 pending-refresh gates 保留；後來 UNKNOWN 不借舊 coverage。
目前候選／來源／設定由當前 release 的原 gates 驗收，不要求等於舊模板或另造 migration review。
續接先唯讀核對原1,686檔與封存鏈，再由現有 actual owner 做一次 fresh observation／remote bracket；
只有 transport/context 與衍生 pins 改變，不重建 SDK、不重驗未變 native 七來源、不重新 Restart。

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

### 多輪發布使用同一 native history

每輪仍只做一次 canonical admission。新的 WSL config 可選用 `publication`，其唯一欄位
`history` 是既有輪次的 `{root, manifest:{path,bytes,sha256}}` 清單；具體 schema 見
[bridge 介面](../../tools/arc_qwen_rlvr004_20261013/publication_windows_bridge_20261015/README.md#multi-round-publication-selection)。
沒有該欄位的舊 config 維持原 flat layout，不能拿新 manifest 解析舊 accepted RUN。

- `state_root`／`scratch_root`、native／refresh／recovery records、共用 events、publisher.lock 與 gpu-stop 不換根。
  新 publication 檔固定選 `state_root/publications/code-vN`；collector outputs／cache 選
  `evidence_root/code-vN`。N 取當次真實 allocation，不由 manifest hash 另開重試 namespace。
- 首次續接把真正 v41 manifest descriptor 與原 flat state_root 列為歷史輪次；舊 config、
  19 件 publication 檔、4 件 retention、269 件 payload 及其他歷史 bytes 原址保留。
  之後把已完成輪次及它自己的 manifest 加入同一清單。未決 publication mutation 要先原路 reconcile，
  新目錄不能繞過；舊 995／ddd UNKNOWN 仍只由原精確 disposition 處理。
- `validate`／`validate-publication` 回傳本輪 publication／evidence 路徑。numeric mount 的
  `--code-root`／`--code-receipt-path`、persisted audit、static pins 與 active-wire review 使用本輪
  真正原件；static pins 的 state_root 仍表示共用 native STATE，不把舊 receipt 搬過來。
- update-code 沿用原 numeric retention listing，先比對歷史 inventory，再把本輪新觀察寫入本輪目錄。
  原 captured20 不改成21；下一個 newly exposed numeric version 由真正 provider listing 取得。
  metadata inventory 仍不是 payload byte verification。
- 固定新來源後，本地對真實舊 manifest／STATE 做一次純 projection 與 normal／`-O` 回歸，
  確認全部歷史 bytes 不變、consumer／wire／mount 選路一致，再沿第 6.3 節 fresh readiness →
  code／inactive／RUN／terminal 走完。Windows native／SDK／科學 runtime 未變的既有證據重用。

### 已接受 v43 的獨立唯讀監看續接

v43／code22 已接受；原監看程序與匿名 pipes 中斷，最後保存的是 readonly kernel
operation accepted，沒有舊 Job-zero／closure 證據。原 STATE、已接受 RUN、source 與
clock 全部保留。新 [status observer](../../tools/arc_qwen_rlvr004_20261013/readonly_observer_20261015/observe.py)
是一個另外審查的唯讀能力，不重用、關閉或宣告解決舊 native session。

本版只做一次 `get_kernel → get_kernel_session_status → get_kernel`，固定 v43、kernel
138123872 與接受的 source／完整 metadata。不得把 provider terminal 當作模型安全收束、
GPU 用量、帳單或科學成功。numeric output retrieval 尚未在本版開放。

本地先獨立核對 helper 的固定 commit bytes／SHA、原 native config（ec328670…）、
原 923-byte metadata DTO（0a22a919…），再由原 native Windows venv 執行 supervisor entry：

```text
<original-python.exe> -I -B <observe.py> --helper-sha <reviewed-helper-sha256> --bridge-root <unchanged-native-source-directory> --config <original-native-config> --config-sha ec32867044bd6de4f8cead0cc6d9f73a45419c1a091dbe3cdbdfadaf669fe0f9 --accepted-metadata <byte-identical-local-metadata-copy> --accepted-metadata-sha 0a22a9193407c049cbbceeb01f8ea9c5385d2a1855d0f97a6371adfa8a364106 --output <fresh-observation-directory>
```

metadata 原樣複製至 Windows staging，不重新序列化；source body 不需要搬入新參數。
output 的父目錄須存在且為 ordinary no-reparse 路徑，新目錄不得已存在、位於 native source
內或任何 `state*` ancestry。只執行 supervisor entry，不直接使用內部 `--worker`。
每次會獨立保存 launch、worker-result、supervisor-result；只接受 matching nonce／request hash
及新 worker 的真實 closure，舊 closure 永遠維持未證。未完成或缺 receipt 仍是未完成。

原 SID-scoped `publication-worker-v1` mutex 不換名稱、不接管 existing/abandoned object；
若仍存在即拒絕。沿用原 native Job containment、真實 parent process handle、完整 SDK source
lock 與 profile／SID／venv／TLS 綁定。新私有 hold-open pipe 不是外部 caller EOF 證據；
最多 300 秒的原始 monotonic lease 與真實 parent watch 才是本次生命週期界線。
只允許兩個 official read RPC；在開啟 writable credential handle 前拒絕 refresh，另於 refresh
exchange／HTTP 出口再次拒絕。需要更新 token 時回報既有 AUTH_REFRESH_UNKNOWN 與
pre-network refusal，不自動 refresh、登入、另換 store 或重試。此限制不解除其他 auth pending。

保留 epoch1792092816、execution1792134816、outer1792134996、global1792136016；
每筆 observer 只縮短自己的期限，不重設 run deadline。這個 helper 不改 accepted notebook，
不開新的 RUN／Restart／quota 查詢，也不取用舊 Job handle 或 pipe。

### v43 終態後的 selected numeric outputs

status observer 保持 ae960a2 的固定 bytes。另用同目錄的 `retrieve.py`，旁邊的
`observe.py` 必須仍是 SHA256 `696cbfc6336fa208526352c4479bf3a32eb5a835d8fa75aca01a87ffa7346655`。
每筆只取一個原 collector `output_paths` 白名單中的檔案，不含 checkpoint body、全 inventory
或額外 failure-path fallback。只在 fresh v43 source/settings bracket 真正為 terminal 後送
`DownloadKernelOutput(version_number=43)`，完成後再核對相同 terminal status 的完整 bracket。

同一原 Windows runtime／config／metadata 參數不變，另外提供原 134,508-byte manifest
副本與 SHA256 `619dc66bb9b4c1697c0753475ab3e68123d77edbc1d9b0737ba3cbd238db7442`。
第一筆選 `irisx-qwen14b-rlvr-20261013-run008.evidence.zip.terminal.json`，cap 16 MiB；
輸出仍在 fresh、非 STATE 的獨立目錄。原 source／config／manifest 不重新組裝。

```text
<original-python.exe> -I -B <retrieve.py> --helper-sha <reviewed-retrieve-sha256> --bridge-root <unchanged-native-source-directory> --config <original-native-config> --config-sha ec32867044bd6de4f8cead0cc6d9f73a45419c1a091dbe3cdbdfadaf669fe0f9 --accepted-metadata <byte-identical-metadata-copy> --accepted-metadata-sha 0a22a9193407c049cbbceeb01f8ea9c5385d2a1855d0f97a6371adfa8a364106 --manifest <byte-identical-manifest-copy> --manifest-sha 619dc66bb9b4c1697c0753475ab3e68123d77edbc1d9b0737ba3cbd238db7442 --name <exact-selected-provider-path> --output <fresh-retrieval-directory>
```

成功才會有 finalized `payload.bin`；`retrieval-result.json` 將其 bytes／SHA 綁到 numeric43、
provider path、兩側 source/status brackets、原 clocks、request／worker hashes 及新 Job-zero。
原 native session 未閉合的證據保持不動。失敗只留下真實 partial／failed receipts，不能改名當成功。

首次 native terminal JSON 的 worker／Job-zero 通過，但 parent 在跨 API ctime 比較時拒絕；
原 `payload.part` 與 failed receipt 必須保留。使用本次修復的固定 helper，在另一個 fresh 目錄
重新取相同 numeric43 terminal JSON 的步驟已由 9fdc 真收據完成，archive 及 selected outputs 也已取回；
不得手動改名舊 partial 或修改舊 receipt，不因後續 header 能力新增而重取已驗檔案。Windows 的
Path.stat 與 fstat 分開保留完整前後身分（含 ctime）檢查，跨 API 比較共同的 dev／inode／size／
mtime／nlink；POSIX 仍比較全部欄位。post-close 失敗另記固定 `failure_stage`／`error_code`，
並保留 `supervisor_reason`；不傳遞任意 exception text。只有新實際成功 receipt 才能作 archive 輸入。

每筆最多300秒且不越過原global期限；輸入／串流／後驗 hash 皆受限，沿原 no-refresh／mutex／
containment。下載前及每chunk檢查4 GiB free reserve，拒絕壓縮 Content-Encoding、長度不符。

取 `.evidence.zip` 時再加 `--terminal-receipt <prior-retrieval-result.json>` 與
`--terminal-receipt-sha <actual-receipt-sha256>`。必須是本helper真正完成的前一筆 terminal JSON
下載，完整 launch／worker／Job-zero／檔案 hash 鏈相符，且 terminal 格式、output root、完整archive
宣告成立；不能手造收據或只傳一份自行填寫的 terminal JSON。archive 必須符合其宣告 bytes／SHA
以及原 manifest 的 5 GiB＋16 MiB cap。raw archive／private evaluator材料只留本地私有證據區。

這是 selected-observation-only transport，不是原 collector 的驗收。跨筆按 numeric version＋
provider path 去重；保留partial的實際磁碟用量，不能把重複下載當不同證據。cross-invocation
aggregate 尚未驗證；原 evidence cap＋256 MiB aggregate、ZIP 安全、owner／wrapper／inventory、
checkpoint／scorer 與科學 admission 仍須由原 offline contracts 獨立成立。404 只代表該 selected
output pending或missing；terminal、hash成功或新Job-zero都不證明遠端模型收束或科學成功。

### v43 checkpoint 的單次 header-only 觀察

此項已由 a3e9 單次真實觀察完成；下列保留原取證契約，不是再次執行指令。沿同一 `retrieve.py` 的明確
`--checkpoint-header` 模式；checkpoint body 不加入 selected 白名單。同一原 runtime、config、
metadata、manifest、clock 與 observer bytes 不變。以上 supervisor 命令的 `--name` 改為
`irisx-qwen14b-rlvr-20261013-run008/checkpoints.zip`，另加：

```text
--checkpoint-header --terminal-receipt <9fdc-terminal-0001/retrieval-result.json> --terminal-receipt-sha c7aed6c2ea053b4dde32fdb280b36e6694f9da282b9db872abde53185082c697
```

`--helper-sha` 使用新來源經審查的精確 SHA，`--output` 必須是另一個 fresh 非 STATE 目錄。
入口完整重驗原 9fdc terminal launch／worker／新 Job0／119,652-byte payload 鏈，並只接受固定
predecessor helper 與上述實際 receipt；不是任意舊 helper 的通用放行。

checkpoint 的來源宣告為 1,546,535,710 bytes；只有實際 HTTP200、identity encoding、嚴格
Content-Length 全等且未超原 4 GiB cap 才成立。原 SDK 保留，請求強制 stream；只允許
Location redirect，可能預先讀 body 的 JSON-body URL redirect 誠實拒絕。不讀 `.content`、chunks
或 tensor bodies，不把來源宣告 SHA 稱為獨立取得的遠端 SHA。

成功後是獨立 `checkpoint-header-result.json` 的 `header_observation_finalized:true`，包含兩側
相同 terminal／source／metadata、新 nonce／request／worker 與 Job0，`body_consumed_bytes:0`、
`body_materialized:false`、`independently_sha256_verified:false`。它不是 `download_finalized`，
不能用作 prior-terminal receipt 或原 collector admission。no-refresh／原 mutex／300 秒與原 global
期限不變；遇到 token、mutex、HTTP 或來源阻礙即保存實際失敗，不登入、接管或重新 RUN。

4309 首筆與65543第二筆 header 都已失敗並保留，不能當 header observation。65543 helper SHA256
`793e3e1d10e6f0d0dd2a0ec43ca9d78ce8f3a81336fba60332de4441901fcda0` 的真實回報為
`worker_failure_stage:checkpoint_before`／`worker_error_code:unexpected_error`，尚未呼叫 checkpoint
output；header null、finalized false、新 Job0、body consumed0、未 materialize，原3,511件 STATE 不變。
本次 result SHA256 `b9dae444cf7ee6ca61654d910c5f98782333a9b5d07044b7970cdf582f7fdca1`。
來源檢查未定位可支持的相容性修復；前兩次原因仍未知，不推斷 auth／HTTP 或回填4309原因。
其餘 header 契約與原 deadline 保留。

後續已使用新 helper SHA256
`d42102d5754845bb15cc9ff591cc4d4773e0037a68984bad5445167fcbfe60c2`，在另一個 fresh output
沿同一命令和所有原件執行一次；不重取 terminal／archive。新增固定 `checkpoint_before_*`／
`checkpoint_after_*` 呼叫／返回驗證 stage、`worker_exception_category` 與兩個既有 metadata cap codes。
任何未知例外仍只輸出 `unknown`／`unexpected_error`，不帶原 message、任意 class name、URL 或 headers。
原 `observe.py`、非 header 路徑與 RPC 次數不變；相同合成 request bindings 下，成功 worker／parent
收據 schema／content 逐 bytes 相同，真實新 helper／request hashes 自然不同。failure 欄位經原 nonce／
request／worker hash、format 及固定 enum 綁定後傳遞，另保留實際 closure；failure 診斷本身不要求
或證明 Job closure 成立。

a3e9 的本地真實單次觀察已成功：2026-10-16 01:30:57.303／01:31:00.250 UTC 兩側均為
v43／code22 COMPLETE，HTTP200、Content-Length 1,546,535,710 bytes，新 Job0、atomic／kill-on-close
true、breakaway false，body consumed0／未 materialize。result 3,647 bytes／SHA256
`90d0f0b3f636b634fb9912effea26eeb0f975826cf6cc590e1812d4f54acefd9`；nonce／request／worker 鏈通過。
不必重取已驗 header、terminal 或 archive；tensor bodies、舊 edd closure、trusted collector context
及正式 consumer admission 仍未成立。

### v43 nested-wrapper 的唯讀 successor 驗證

使用獨立 [successor verifier](../../tools/arc_qwen_rlvr004_20261013/wrapper_observation_repair/verify_parent_wrappers.py)
的 `verify_wrappers`，沿原已驗證下載檔、同四件 JIT bytes、notebook release、reviewed environment 及三份
runtime raw documents 呼叫；介面不變，輸出是新 `irisx/rlvr-parent-wrapper-verification-v2`。
原 manifest 指向的 verifier（24,468 bytes／SHA256
`4dd228f6559ccad58d421d9b1e90f6aea9339b32c15e4df4f32855731a77d3f8`）、原完整 subset 拒絕、
raw receipts 及 source／clock 全部保留。新結果寫到 fresh 分析輸出，不換掉原 descriptor 或 consumer pins。

guard 的 `owned_identities` 是各階段實際觀察集合，不能假定每個短命子程序都同時被外層取樣。
successor 保留原 `verify_stage` 全部 bytes、各階段原 supervisor union、來源／JIT／時鐘／terminal
檢查，只以保守條件取代跨階段完整 subset：共同 pid/birth 的 session 不能衝突，內層 supervisor、
worker、runtime worker 必須有外層相同 triple；內層額外觀察須在其已綁 bytes/SHA 的 supervisor
原收據中，且兩階段均有原 clean closure。另嚴格驗證 runtime incarnation 的 int 欄位與 PID 一致。

本地原檔完整 4309 successor replay 已 PASS；新結果 SHA256
`e72b7c8363746cfd01903b37103899b44428a9e216e209d35ea4b7d599c27101`。不必重跑已通過的相同來源。
保留 prep22／inner6 的兩套原 inventory 與差集2，完整 subset false、helper model closure false；不合併或
補造程序 exit/reaped/closure。新 wrapper 結果不證明舊 Windows native session 已閉合，也不賦予
正式 collector `CollectionContext`、tensor 驗證、scorer 或整體科學 admission。

### 固定 training-only numeric successor 的提交準備

v45／code23 已完成並取回。原final／capture／收據與時鐘保留，不重提該 run；下一輪只依
[進度頁](DEVELOPMENT-PROGRESS.zh-TW.md#下一輪固定-training-tail-數值診斷)的兩個既有training-tail座標，
更新受影響的 shadow／封包身份與完整operator pins。原259 consumed proposal/base、native7／SDK、
M與caller證據不重建；以真正accepted code23／v45作新的固定fresh predecessor。新來源尚未交付前，
不拿本段歷史命令或舊v43 capture來提交。

本輪只跑原 A256 與第一64 training batch 的原 replay／DDIS backward，加最多8個 bounded shadow
forward 後強制無 RL commit；不執行其餘192／C／dev／held／PUBLIC。原方法與門檻、資料隔離、
現有資源與43,200秒上限不變。完整研究解讀與 shadow 因素限制見[進度](DEVELOPMENT-PROGRESS.zh-TW.md#下一輪固定-training-tail-數值診斷)。

1. 取得本次固定 commit 與逐檔 readback；數值 source 在
   `tools/arc_qwen_rlvr004_20261013/numeric_replay_diagnostic_20261016/`，完整 operator 仍在既有
   `publication_windows_bridge_20261015/` 路徑，不能只搬三個 overlays 或沿用舊 launcher pins。
   本地已核對的原件不重建：
   source proposal inventory `fc32f98bef4188761fd51275bb05dd26c6fbd237afb8b8403b492f61442055cd`、
   base inventory `de519816720ceb3bf07e0bf015c888b7e4bd9fdb344c2dbe355281230920ee88`，以及 base 根目錄的
   父目錄下 `source-rebuild/review-only/solver-descriptor.json`；後者需與 base material review 的
   `dataset_file_sha256` 相等。這是實際父目錄，不是名為 `parent` 的子目錄。不要讀 evaluator escrow bodies。
2. 先以本次 `assembly/observe_predecessor.py --review <new-readonly-review> --review-sha <sha256>`
   取得真正當下 predecessor。它只觀察固定 code23／v45，先驗本次完整22件 operator 與已接受
   v45 manifest／material／新當前路徑 config，然後在同一 publisher lock 內執行原五次唯讀呼叫
   dataset→kernel→status→kernel→dataset、保存六件 DTO／source，並等待這個新 native session
   真正 clean close。它不呼叫不適用於舊 manifest 的 numeric `load_contract`，也不授予 mutation。
   新 observation review 的 `observer` 僅含 `purpose`（`fixed-code23-v45-predecessor-capture-v1`）、
   `script`、`output_root`、`manifest`、`material`、`local_config`；除 purpose／output_root 外為
   標準 path／bytes／sha256 descriptor。allowed_actions 僅 `reconcile-read-only`，且需真實
   non-synthetic provider admission；不能改寫舊 review 或用 self-written PASS 代替審查。
   `output_root` 是 configured scratch 下的新目錄，與 STATE／candidate 分離。
   此次及後續 action／monitor reviews 另帶 `readonly_frontier`，指向原 2,759-byte RESULT
   `419b60845f9e6778b0c9495c65b19f98e2def2ff84162b169856a326554e1e23`；`readonly_caller`
   含 jit／owner／seq14／owner_start 四個原件 descriptor。實際路徑由既有私有材料取得，
   不另做 presence 查詢或改造歷史 closure。已驗 native7／SDK 不重建。
   再由既有 `admission_run008/seal_inputs.py` 封裝這次六件真 bytes，格式改為 assembler 已接受的
   current-predecessor observation；此步不做 provider 呼叫，不更新時間或來源。保留原 numeric
   版本／source／settings／terminal／Dataset DTO bytes；建立與已授權 training-only 範圍相符的
   owner direction，格式和欄位以
   [owner_inputs](../../tools/arc_qwen_rlvr004_20261013/numeric_replay_diagnostic_20261016/assemble.py)為準。
   原 broad owner receipt 不代替較窄 purpose；request_id／instruction 來自真實授權，不使用測試fixture。
   固定 capture 綁 v45 manifest 135,137 bytes／SHA256
   `15f340149a8eff74e6c1d56f3cd34b8836d349dfa6818ef14bd142dcb600161a`，以及 active45 saved source
   22,913 bytes／SHA256 `5f884856484087033f6569335f5c65f752c4868c823276efaffed3c3e96eaeff`。
   capture config 的已接受 versions 為 code predecessor22／code23／inactive predecessor43／inactive44／active45，
   不能先換成未提交 successor 的 allocation。helper bytes/hash 以本次固定 commit 的逐檔交付收據為準。
   sealer 以 `--repository-root <repo> --observation-root <fresh-capture-root>`、
   `--observation-sha <raw-OBSERVATION-sha256> --output-root <fresh-sealed-root>` 呼叫；輸出必須
   位於 `<repo>/.irisx/run008-admission/`，不是下一步 numeric proposal 的目錄。
   sealer 仍為 SHA256 `4f8507e8c1b549a5bc558fbfea652850a349de02025b792cfc2bf42d7f4ef7a0`；
   下一步 `--observation-sha` 使用 sealed `OBSERVATION.json` 的真 hash，不沿用 raw hash。
3. 新 assembler `--mode proposal`，明確提供 `--repository-root`、`--source-proposal-root`、`--base-root`、
   `--observation-root`／`--observation-sha`、`--owner-direction-path`／`--owner-direction-sha`、
   `--collector-path`／`--collector-sha`、`--output-root`。輸出必須在該 repo 的
   `.irisx/numeric-diagnostic-20261016/` 下的新目錄。collector 指向本次新 `publication/rl_collect.py`，
   不是原 ABC collector。proposal 尚未授予 provider mutation，也不分配 epoch。
4. 用真正 reviewer 核對此份 `ADMISSION-PROPOSAL.json`、兩個 solver path substitutions／reverse byte
   equality、source/archive／namespace／purpose／實際來源與 helper bindings；再提供 assembler 所列
   `--proposal-*`、`--solver-review-*`、`--runtime-review-*`、`--material-review-*`，以 `--mode final`
   寫另一個新目錄。既有雲端 CPU review 可作已驗範圍依據，不能直接冒充這份本地 proposal 的收據。
5. 使用本次完整 source closure：context→bridge→common→numeric transport，以及 recovery entry、
   launcher 和 collector／wire 的全部衍生 pins；action／monitor reviews 都綁實際22件 operator。
   assembler 僅允許 reviewed numeric transport 的單一 common dependency pin 變更，其餘 body
   與 active wire 全 bytes 固定，且同目錄 operator 必須等於 numeric overlays。原 native7、SDK、
   config／recovery contracts 沿用，不重建或重測未變元件。
   collector bootstrap 仍需要同目錄、經 action review 綁定的原 `operator_common.py`／transport。
   原 `state-run008`／`evidence-run008` 是 wire family 名稱，實際每輪用原 per-code publication isolation；
   config 的 publication history 另納入已完成 code-v23 及它原本的 manifest descriptor，舊輪次原址保留。
   所有歷史 STATE、UNKNOWN、claim／journal 保留。真正 gate 阻礙回報，不套舊 closure 或重送。
   新 run/source/environment namespace 為 run002／source002／environment002，舊 run001不改名或覆寫。
6. 只有 final source、local review、numeric code readback／mount、inactive readback／獨立 active-wire 與
   JIT freshness 均成立後，由原唯一 publisher 接受一個 RUN，沿既有模式監看到終態並取 exact outputs。
   版本取當下真回讀，不在此預填 code／active version；fresh epoch 只屬這個尚未接受的 successor。

   numeric mount 使用本輪 `numeric_replay_diagnostic_20261016/assembly/accept_numeric_mount.py`，
   原 `admission_run008/accept_numeric_mount.py` 固定259的入口保留供原來源，不直接用於260件
   successor。新入口沿用七個 required flags：`--candidate-root`、`--code-root`、
   `--code-receipt-path`、`--code-receipt-sha`、`--output-root`、`--manifest-sha`、`--inventory-sha`。
   它只接受固定 training-only purpose／source／archive 與260件來源，原 helper／guard、真實
   numeric receipt、完整下載閉集／ZIP bytes、source-only import 和 unforced owned closure 都保留。
   輸出仍為 repo `.irisx/` 下的新目錄；先前 CPU count-gate 證據不是可傳入的 numeric receipt。
   外層 runner 不進入 candidate／payload；它單獨改動不改 candidate，但本輪 shadow runtime 已變，
   必須依步驟3–4正規產生新的 proposal／reviews／final，不能沿用 v45 final。發布前 runner／source
   review 綁本輪入口真 hash。code publication／numeric readback 後才執行真 mount，後續
   persisted-readback／static review 再綁真正完成的新 `MOUNT-RECEIPT.json`，不能套用原259的
   runner pin，也不能在發布前要求或補造尚未存在的 mount receipt。
   本輪新入口只隨新 source/archive 重綁；固定260與0a346的 bounded byte-consistency reader保持。
   精確 entry hash 見本次交付收據；原259 runner仍為
   `d84e2aa27edc5cef4fe557a9c327a5b4bffebbadf638d80948927677f1bd70b9`。
   59d04 的同長度／timestamp collision失敗保留。只核本輪受影響的 shadow／collector／封包pins，
   不重驗未變 reader、native7或SDK；本輪自己的真fresh capture、proposal/final與numeric mount仍需成立。

新工程完成須有 `owned-numeric-diagnostic-complete-no-update`、原64 replay、shadow／rollback、
實際閉合 capability／raw closure 與完整 diagnostic archive。collector 寫 `NUMERIC_DIAGNOSTIC_COMPLETE`
或誠實的 `NUMERIC_DIAGNOSTIC_INCOMPLETE`；`consumer_admitted`、comparison／PUBLIC／goal 全 false，
public score null。terminal 的 process-termination authority 與 `model_closed:false` 保留，不用其
代替 live closed-model capability。預先選定點的 scalar gap、dtype／shape、原 gate 與全實際成本
供下一步定位；私人 tokens、logits、parents、audit／archives 都不公開。

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
