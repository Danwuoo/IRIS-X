# ARC-AGI-2 當前開發與實驗進度

更新：2026-10-16 UTC。本頁只維護目前狀態、阻礙與下一步；研究問題與固定設計見
[研究主頁](README.md)，歷史 E0–E52、來源指紋及更新時間線見[工程歷史](archive/engineering-history.zh-TW.md)。

**使用者提供的 v47 evidence ZIP 已獨立驗證：A完成SFT256，首批B因沿用完整A/B/C時間預留而未獲准，沒有新的replay／shadow數值結果。診斷專用預算窄修已發布為 016b430；source003／run003 身份重綁已發布為 dc9eb08。使用者現授權單次 RUN＋一次必要讀回後停止；本地在 provider 前發現舊 capture／監看 scope 硬鎖，正在窄修，尚未提交。**
官方 numeric47 讀取仍曾回 HTTP403，唯一 activate 的接受狀態未 reconcile；使用者提供的封存
來源與原 code24／source002 相符，不替代官方 Save 接受收據。原 claim／epoch 保留，沒有重送。
最後完成數值 replay／shadow 的仍是 v45：原數值 gate 拒絕，RL commit 為0。
v43 的原 A/B/C 輸出與 PUBLIC 原 scorer 0/167 保留；v45 沒有重跑評分。
正式 consumer admission 尚未成立；來源評分不是官方或獨立重評結果。原研究優先事項仍是
unchanged-policy 數值落差與已定位的證據契約，研究方法與門檻不變；本輪提交範圍以最新「單次 RUN，必要讀回後停止」為準，不授權 watch／持續 polling／結果下載。
使用者先前授權依既有 run007／run008 離線 notebook 模式持續開發、Kaggle 執行、分析 terminal／結果，
再按既有研究條件進入下一輪；這項歷史授權不解除本次 HTTP403 後的停止條件。
本地端維持唯一 publisher，code 與 weights／wheels／資料 Dataset 分離鎖版；UNKNOWN 與各次 admission 不因此豁免。

## source003 單次提交接線修復（2026-10-16）

- source003 身份準備以已公開 `016b43013d652a2102c867a29dace41f5aecb28a` 為基底，僅重綁既有組裝器、
  mount／wrapper、transport／active-wire 及其完整 operator pins；修好的 flow.py 和其餘科學 runtime 不變。
- 新 namespace 固定 `numeric-diagnostic-20261016-run003`／`source003`／`environment003`。
  仍是260件 source；canonical source
  `42062ef934a7c5495f8d22b6a68faa715301b47b9875eef829f0988056877c75`，
  source.zip 15,820,672 bytes／`a425250bb0541981a04b9814f6edf00695b9c574ccb207035c6fd4a61980f78e`。
- 沿用 A SFT256、首批64條原 DDIS replay、固定兩座標各四個 shadow forward，總上限8／120秒；
  原 max0.20／p95 0.05／coverage1.0、零 RL commit、12小時硬限不變。
  其餘192／C／dev／held／PUBLIC 未請求，沒有新科學結果。
- 這是 source-only 離線包，不是完成私人 proposal／final／publication manifest。
  code／inactive／active 數字版本、predispatch epoch 均為 null，未產生 provider claim。
  舊 v47／run002 來源、失敗、UNKNOWN、claim 和原 epoch 不回寫。
- 最新單次 RUN／初次讀回授權已取得；官方 v47 曾回 HTTP403，新 predecessor 的實際來源／設定
  仍待本地一次新 capture 核實。若再次拒絕或版本／設定不合就停，不能靠候選 manifest 宣稱
  遠端接受。私人材料及完整 publication review 仍須實際成立；具體接手見既有交接頁。
- 身份重綁已公開為 `dc9eb083ac9016691d86f48d30bf48a06d7b2f1b`。原 016b430 的25項 normal／-O測試與獨立審查保留；
  該身份重綁的組裝26項＋mount／collector路徑／operator pin整合65項，normal與`-O`各91項通過、無skip；
  不重驗不變 native／SDK／模型。獨立review完成後以交付收據列其精確範圍。

### 本地尚未 provider 的兩個實際整合阻礙

本地已核對 source003260件／archive15,820,672 bytes，沒有 query、write、version claim 或新 epoch。
既有 capture 寫死 code23／v45；assembler、transport與active-wire要求監看／下載=true，
與最新單次提交後停止授權不符。不得用假 true 經過 gate。

本次窄修以 dc9eb08 為基底，沿原程式：capture 由獨立review的 expected_predecessor 綁定同config的code／active版本，
原manifest／material／config與完整operator來源、五讀bracket、全部settings、fresh output、flock、
native clean-close照舊。只保存當次實際source bytes／hash與terminal，不聲稱舊Save已接受。
單次模式明確保存 stop_after_submit_readback=true、single_post_submit_readback_authorized=true、
continuous_monitoring_authorized=false、result_retrieval_authorized=false；原監看模式仍需原真授權。
唯一active讀回在首次遠端讀前持久消耗，失敗／重入也不得自動輪詢，停止判斷在原publisher鎖內重驗。
原static consumer／source／mount review仍保留，不因不監看而省略。

本次不改source003科學runtime、預算、數值門檻、namespace或260-member archive；
只修capture與publication授權接線。原v47 claim／epoch／UNKNOWN與失敗原件不改。
舊WSL caller context失效，接收端須用真實當前runtime／路徑產生新的review-bound config，
不能重用舊WSL證明、假造環境或重建未變native／SDK。此修復尚未公開，Kaggle實作仍未執行。
本次capture15、授權11、packaging26、operator整合33項，normal／`-O`各85項全過；
另multiround為9/10，剩餘full-wire fixture缺training-purpose的錯誤已在本次基底重播，
不算新回歸或全綠。獨立review另驗單次讀回消耗、鎖內重驗及原continuous模式。

## 一、文件責任與更新規則

- 研究主頁說明問題與假設；[方法總覽](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)保存唯一實驗順序。
- 本頁記當前事實；[交接](OFFLINE-LOCAL-HANDOFF.md)記單一路徑；固定驗證與歷史審查不回寫成新結果。
- 每次只寫實際驗證的 source／scope／結果；本地回報、CPU、native、Git、CI、模型與分數分開。
  舊失敗、UNKNOWN、來源與時鐘保留；尚未取得的結果不補 0 或 PASS。

## 二、目前基線與證據索引

研究分支只有 `feat/arc2-sft-rl-continuation-20261014`。啟動修復已發布為
[`0af57780d61cc72c759fa9b67330bb655abcb761`](https://github.com/Danwuoo/IRIS-X/commit/0af57780d61cc72c759fa9b67330bb655abcb761)，已整合到本地 a5c3 successor；歷史 Kaggle v41 使用 84a5。
多輪發布修復已發布為 `0d3524caba46a4d3944d2f1686dd388f0833dc61`。歷史／即時
context 修復已發布為 `a5c3da425aeeb31cb8b45d20684aec558fd0db84`，本地已驗收並提交 v43。
native 檔案身分修復已發布為 `9fdc96325fd3f425b54fa99508d3181230f77f3e`，本地真實重取成功。
wrapper／header 窄修已發布為 `4309b890d5c19dddd29b1fb87a26fa916df22cf1`；真實 wrapper replay 通過，header 首次失敗。
header 去敏 stage／code 修復已發布為 `65543cbb4c3547fe038c3e0f42bb73ea770d3e92`；真實續接停於
`checkpoint_before`／`unexpected_error`，當次未呼叫 checkpoint output。後續診斷來源
`a3e9c8d99bf70c52afb8b6323ef03fe2ffdbbc23` 的單次真實觀察已成功取得 HTTP header，前兩次原因仍未知。
training-only successor 已發布為 `03022f2a9e716d953f22f5245b56ffa688060862`，20 檔逐檔遠端回讀一致；
該版初次本地 preflight 在 provider 前被原 edd 未閉合 session 拒絕。完整 operator 的
launcher／transport／collector source pins 已在 `1da916d39ad3e84be9f66c4beed9a97c7aebc50d` 的完整
operator 一併整合，19 檔逐 bytes／Git blob 遠端回讀一致，不能只替換三個 publication overlays。
本頁與下一次窄修同一 commit 保存，交付 SHA 由接收時 HEAD／遠端 readback 核對。歷史 fix refs、
f5／a724／e491 checkout 與原 UNKNOWN 保留；[前輪進度](https://github.com/Danwuoo/IRIS-X/blob/84a5a1f870c42899f3bea79996d1b9360c4bfee9/research/arc2-sft-rl-continuation-20261014/DEVELOPMENT-PROGRESS.zh-TW.md)
保存 lease 失敗與修復前的精確證據，不在本頁重複累積。

| 項目 | 最後已確認的事實 | 證據範圍與限制 |
| --- | --- | --- |
| Stage 0／Stage 1 | 離線計畫、report analysis、training audit adapter 與 upstream 逐軌跡 loss 已交付 | [Stage 0](offline-continuation-review.md)、[Stage 1](stage1-independent-review.md)；無模型 hook 或 ARC 分數 |
| AF3 真正元件 | `TrainingSample`、`DDISLoss`、`MeanMetricState` 實際 CPU 呼叫及合成 loss／gradient parity 成立 | [整合與 proof](agent-factory3/integration.zh-TW.md)；真實 Qwen／LoRA／GPU 效益仍未知 |
| 84a5 本地與發布 | 本地 native10、WSL caller-death、pre-auth、真實 90 檔 disposition、canonical admission 通過；code Dataset v21 的 269 檔／15,849,580 bytes numeric readback 相符 | inactive40 → active41 真正提交；所有 9 個 native sessions closed，原 995／ddd UNKNOWN 原件不變 |
| v43 封存實證 | code22／inactive42 真收據與 manifest 相符；10-15 19:33:50.121 UTC 接受 active43，23:27:59.209 首次 COMPLETE；後續新取檔收據與來源／設定一致 | 26 必要＋5 選用檔案共 130,955,581 bytes；另 5 選用 404。新 Job0 成立，原 3,511 件 STATE 不變、舊 native closure 未證 |
| v41 真實終態 | 2026-10-15 15:58:28 UTC 首次觀察 ERROR；Internet OFF、RTX Pro 6000、private | [原 notebook](https://www.kaggle.com/code/danielwuu/iris-x-learning-agent-20261011)，kernel ID 138123872 不是 scriptVersionId；native closure 不證明遠端 VM teardown |
| 啟動原因 | notebook 的 ambient interpreter 在離線環境建立前查固定 cuDNN，distribution 存在但 version 不等 9.10.2.21；停於 parent-environment-policy | ambient 實際版本與 backend 是否載入未知；prepare caller 同排序風險尚未執行。`preparation_failure:null` 另使 collector 拒絕 schema |
| 已取回證據 | 五份 numeric41 outputs 各有 HTTP200、bytes／SHA receipt：startup diagnostic、preparation request、original request、operator、outer notebook | 五份不是全 inventory；outer notebook 無 execution outputs，不能當官方 execution log。模型／audit／score／cost 其他檔存在性未知 |
| 已發布的啟動修復 | 兩個 deployment-only callers 改用無模型準備環境；真正 installed parent／worker exact-byte gates 保留。collector 只多接受原 schema 加 null 欄位 | [修復範圍與 CPU 測試](../../tools/arc_qwen_rlvr004_20261013/preparation_environment_repair/README.md)；新增 runtime policy 一檔及衍生 self-pin 一檔，其餘 257／259 與 A/B/C 不變；v43 已實際越過啟動邊界 |
| 多輪續接 | 0d3524 已隔離每輪 publication／collector 目錄，native STATE 與全域鎖共用；本地18:03 fresh no-auth 停於舊f5永久 same-boot 字串 gate | 原1,686檔完全不變，未新建 native claim／canonical／run、未 provider。CIM boot值變1.802125秒，host／Windows／source／runtime相同；符合校時漂移但未證明 same boot，不拿猜測當PASS |
| 歷史／即時 context 修復 | 原封存Restart＋reconciliation在原completion time重驗；fresh host／source／runtime／closure另核對，封存events及live STATE前後綁定 | 只支援現有f5原件的12.629秒歷史間隔，保留原120秒限制；later UNKNOWN／refresh／publication變更仍阻擋，不加BootID框架、容差或重啟 |
| Repository／CI | dc9eb08 精確 CI 仍失敗：同 6 項既有 README invariants 缺詞，unit／packaging skipped | focused 驗證只支持其實際範圍。額外誤啟的 repository aggregate 未成為驗收：一筆中止，已結束者 1,621 tests／6 failures／41 errors／74 skips；不以此修無關元件或宣稱全綠 |
| 真實研究結果 | A SFT256；B 64/256 attempts、reward15/64、RL commit0；C 額外 SFT203。固定 dev 平手規則選 A；PUBLIC 原 scorer 完整 120 tasks／167 queries 為 0/167 | 以下是取回封存輸出的觀察，正式 consumer 尚拒絕；不代表 RL 更新有效或無效，也不是官方／獨立重評分數 |

### v43 模型與評分觀察

| 項目 | 真實封存結果 | 判讀界線 |
| --- | --- | --- |
| A／B／C | dev 分別 1/16、1/16、0/16；已重用 held 分別 4/32、4/32、3/32 | dev 固定選 A；held 不是全新確認集。C 相對 A 的 held gain1／loss2 不足以推論一般化效果 |
| B 數值 admission | 64 條、9,365 非強制 tokens；6 條 max gap >0.20、另 6 條 p95 gap >0.05；3 條 coverage 不足包含在前者，聯集 12 條 | 最大 gap 0.2495684624；0.0907034695 是各 trajectory p95 的最大值，不能稱 pooled p95。192 slots 未執行，原 thresholds 不放寬 |
| B 訊號與成本 | 6 個 all-zero、1 個 all-one、1 個 mixed group；8 次實際 DDIS backward、0 optimizer commit，A/B adapter SHA 相同 | 有相對 reward 訊號但未形成可提交的更新；失敗工作仍計入 physical ledger 與 model-phase wall，帳單未驗證。replay/backward 53.687 秒未碰 600 秒 gate，已記錄阻礙是 ratio-gap |
| B/C 等成本 | B 整階段 553.034100082 秒、C 553.877390225 秒，差 0.843290143 秒，原容差 27.651705004 秒；無 idle padding | 包含 setup、抽樣、reward、replay、失敗／rollback、save／reload。不是 GPU active time 或帳單時間 |
| PUBLIC 完整性 | 334/334 views 與 dispatch 全部 complete／EOS／valid；獨立嚴格解析全通過，tokens 12–930 未碰 1024 cap；167 queries 均有候選 | pool 大小 0/1/2 為 0/33/134；單候選由兩個有效 inverse 輸出去重。pass1／pass2／pool-oracle 皆 0/167，不能用 selector 修正既有 pool miss |
| 來源與模型限制 | 封存 source 報告真實 14B、BF16 base／FP32 LoRA、RTX PRO 6000；所有 PUBLIC views 宣告載入 A adapter | 尚未下載 checkpoint tensor bodies 或獨立驗證 tensor load；來源評分的 production_admitted／publishable 都是 false，official score 是 null |

evidence archive 為 128,988,781 bytes，SHA256
`367b401d09ef554f378b8b45a6b73244a86d2c8cbb79a8ef7c4e0dce76e0e3d7`，870 members 通過原 CRC／SHA／terminal-container
檢查。原 epoch `1792092816`、execution `1792134816`、outer `1792134996`、global `1792136016` 不變。
實際 native finalize、容器驗證、來源觀察和正式 consumer admission 分開記錄。

既有 calibration 的離線差分另驗證了 4 個 length × base／updated／restored 共 12 panels、48 個 grid
steps。各 panel step0 的 selected1／support10 差均為零；後續每 panel 3 步的 greedy parity／reference
repeat 全通過，但原 full-head allclose 全未通過。封存同 support logits 用穩定 FP64 log-sum-exp
重算後，selected conditional-logprob gap 最大 0.0931341710、全 support 最大 0.2211952136，forced
support 為 0。這是封存 FP32 值的離線差分，不能稱 GPU softmax 重播、A256 gate 或特定 kernel 根因。
canonical calibration SHA256 `e0f5ec6a0b247884ffc6302a07454279f95a4d9c047195d0ebf911b36d6ac62a`；
本地差分 report SHA256 `8fdf4da15f8d7c72305f3f0c076836dab4db757119eb6130b47d159206f88452`。

v41 startup diagnostic SHA256：`0ba5efaf361da5336338a0ff170728ea7cf96aa1af447d74d5f770e0ff0de069`。
CPU 另以真正 pinned offline guard 重現子程序增加 6 個固定環境鍵、與舊 loader 全等檢查不相容；
新 policy 在 exec 前綁定同樣固定值，保留全等與所有 byte/map 檢查。這是下一邊界的 CPU 發現，並非 v41 已執行到此。
原 epoch `1792079687`、global deadline `1792122887` 保留，不重設；去敏投影不能替代原件。
現有 competition metadata association 沿用較早版本；材料仍是固定 training/1 與 PUBLIC120/1，
沒有把研究改成 ARC-AGI-3，也不為這項既有掛載新增修改。

### v47 使用者封存：時間 admission 拒絕與離線窄修

使用者自行提供完整 evidence ZIP，48,758,797 bytes／SHA256
`d2fb6ba090e5c08e08163a5dd3e3a78987e67c4579c63f93503b6ca9b176c3cb`。
離線核對79/79 member集合、長度、SHA及CRC，與使用者提供的launcher result一致；
內嵌source archive的260件亦逐檔符合 `048e9d3ee8b588cbb2075ae785b3f09fa10e3846a3269001e0c7a5f102865fda`。
沒有執行封存程式；dev／held evaluator targets僅作member hash核對，未解析、輸出或使用內容。
hash核對不等於獨立模型／tensor驗證。

- `experiment/result.json`為427,120 bytes／SHA256
  `a23cc21ccfdece15c5671b22939a216e2e390207302d5d09b3d9e82dfbe7bc8b`；
  `worker.stderr.log`為5,626 bytes／SHA256
  `9dd750153dec8c107f63a057ff234543145fb9ad61c8f5bcb4e092606401861c`。
  兩者一致指向 `training-only numeric diagnostic incomplete: not-admitted`，不是外層Papermill字串所能單獨定位的原因。
- 原epoch為07:35:30 UTC；runtime clock觀察為11:42:09.283667 UTC，原時計已經過14,799.283667秒。
  A整階段696.622902817秒，physical events包含256次anchor forward/backward與256次anchor optimizer commit；
  B整階段7.502033304秒只有進入／保存等工作，rollout、replay、RL backward及shadow均未開始。
  B模型ledger的physical attempted batches與RL updates為0，A/B adapter摘要相同。未下載tensor bodies，沒有新數值或效能結論。
- 唯一首批admission：disk PASS，但時間需求30,039.967711秒大於剩餘26,148.326455秒。
  原training-only函數仍保留paired ABC 4,200秒、PUBLIC 18,000秒、persistence margin2,400秒、closure600秒，
  並額外預留C 2,480.709305秒。C配對半窗另把B剩餘窗壓到412.501699秒，小於單批加保存2,359.258406秒；
  兩個時間條件均拒絕。planned-B7,080秒、arm7,200秒與disk條件通過。
- `diagnostic_complete=false`，C／dev／held／PUBLIC未請求、分數為null。內層報告closed/model_stopped，
  但worker以1退出使原outer `safe_closure`／`model_stopped`仍為false；保留兩層語義，不能升格正式consumer admission。
  原outer process wrapper的非強制退出與diagnostic archive完成也不證明VM teardown或帳單終止。
- 另確認報表缺陷：三個 `not-requested-by-diagnostic` placeholder被舊summarizer誤計成
  `physical_attempted_batches=3`，但完整256個row的actual dispatch全為0。原封存不改寫；這不是時間拒絕主因。

修復只限training-only controller的預算投影：保留2,400秒保守餘裕、600秒closure、300秒保存，
另明列既有shadow最多120秒；不為未請求的C／paired ABC／PUBLIC預留時間。
B deadline、required與work deadline使用同一投影，保留原42,000／42,180／42,300／43,200秒時計鏈、
7,080／7,200秒限制、disk與全部數值／記憶體／操作期限。v47標量重放的新需求為5,479.258406秒，
這只表示預算可容納，不保證真實完成。原A/B/C函數的29,624 bytes與共用audit原件保持完全相同。
placeholder修正只投影診斷結果的attempted計數，不改256分母、未請求狀態、partial attempts或optimizer計數。

受影響25項distinct CPU測試在normal／`-O`均通過、零skip；optimized作者log因重列一項ABC不變性
測例共執行26次，仍只計25項。測試涵蓋v47標量窗口、同原時計延後啟動、預算不足、過期、非有限輸入、
shadow120秒計費、三處deadline、原ABC bytes、診斷不評分／不commit、placeholder與真正partial attempts。
實際production admission→disk→break→collect的來源片段以合成storage/backend另驗五組time/disk及disk例外，
任何拒絕／例外均未collect；獨立reviewer對此最後增量normal／`-O`各1項通過，靜態審查無阻擋問題。
這些是CPU控制流程證據，未執行GPU。未變tensor/replay implementation未重驗；初次整module檢查因本環境
沒有torch而有4項skip，不能將後來focused零skip說成完整tensor suite通過。既有全repo CI狀態不變。

本輪只作離線code/test/progress修改；不沿用run002組裝新提交，也不改其epoch、claim或任何失敗證據。
後續公開發布需要這次精確檔案範圍的新授權；新source/run namespace、完整組裝與真正predispatch起點
須另在獲准的successor準備中固定，不能以這份離線預算測試授權provider操作或重送v47。

### code24／inactive46：原 training-tail 的提交阻礙

本地固定 `b0d3e0b562034ab00643323c6924b73861032edf`，研究程式 tracked clean。
新 code24 的270檔／15,902,600 bytes逐檔回讀相符；真 owned mount、prelaunch audit與
actual-wire審查已通過，inactive46已接受並驗證。唯一一次預期 active47 的 activate 嘗試於
2026-10-16 07:35:41.811844 UTC 回傳 `PROVIDER_ERROR`；後續原 `verify-run`
因 `saved_version_changed` 拒絕。截至該次官方查詢，該路徑沒有取得accepted-RUN、watch、training-tail runtime或新terminal證據。

07:43:40.418113 UTC 的官方 kernel／status／kernel前後回讀均為v46／COMPLETE，
GPU／TPU／Internet關閉；saved source為21,314 bytes／SHA256
`5a7b4e0615add4bd6da6d6f7f6d06a437b50c4cc26076c9c2aaa93f4202a214a`，與已保存inactive一致。
只讀診斷3,712 bytes／SHA256 `d10d708a7b7f5fb03900ac339b8dce7d3d3100ab0ed7105ad3d0fea7c76f69bd`；
本地獨立實測review 9,245 bytes／SHA256
`03ca6cfc6743bd58644e65fc7c2806c398cc02c439ad11f91322cc3d04eb515a`。
提交與該次只讀診斷的native sessions有有效closure；這不證明遠端GPU未執行、沒有成本或
原save已被server確定拒絕。最新可見版本仍為46也不能單獨解除一次不確定寫入。

原epoch為07:35:30 UTC；execution／outer／provider／global deadlines為
19:15:30／19:18:30／19:20:30／19:35:30 UTC。Journal保留 `save_intent`／`save_calls=1`；
原activate要求 `wire_prepared`／`save_calls=0`及≤60秒freshness已不符合，不重新prepare或重送。
既有 `safe_semantic` 已去除任意provider錯誤文字，現在不能推斷配額、權限或其他根因。
既有原件的離線投影確認：save sequence7已到 `operation_accepted`，close sequence8正常
accepted→closed，該nonce沒有UNKNOWN事件。固定來源據此可區分為typed Save response帶非空
error的路徑，而非本次HTTP／SDK例外造成的mutating UNKNOWN；仍沒有保存HTTP status，不能
推定HTTP200或RUN接受。Failure原件180 bytes／SHA256
`510da79500e9234e3170c96404e54fb24a80732bb53c26b82b3c780e46a7f718`；
closed journal473 bytes／SHA256
`bcaef90987758feb81c86d3571d14b10aa5dae88adb8ba8f27fc663ddc87a379`。
原Save DTO與raw supervisor receipt bytes皆未持久化；前者的原錯誤字串及回傳version等欄位
不可恢復，後者僅有當時驗證後留下的closed journal，不以重建收據代替。
固定numeric47的單次唯讀probe於08:47:33.642277–08:47:33.860966 UTC執行，
在bootstrap以 `unexpected_error`／`guard_error`、exit2結束。未建立output directory或
launch／worker／supervisor／DTO收據；固定流程尚未到worker／GetKernel，沒有新Job0或遠端觀察。
原CAPTURE為1,924 bytes／SHA256
`24fe63f9e0a0fe7d3ba0df321c9c3d7571950539f9c1b189c5eb61e223422730`。
WSL新測試正常／-O各32項通過；Windows原測試29項通過、1 failure、2 errors完整保留，
不能以WSL結果代稱native通過。7,050檔／69,958,140 bytes的STATE前後map完全相同。
該次bootstrap失敗後，當時先安排釐清Windows測試失敗、窄修與獨立審查，沒有直接重發probe。
當時方案僅在正向saved source／可見settings觀察後才交原verify-run；此方案已由下述
09:17的HTTP403停止條件取代。負向／fallback或讀取失敗一向不授權重送或改寫原claim／時鐘。

後續既有CAPTURE確認source參數為 `.ipynb`；原pinned native reader的副檔名集合不含它，
在任何native API前會拒絕，而helper安全診斷漏列 `windows_source_extension_invalid`。
此路徑已用原來源純CPU重現；原catch沒有保存例外，故不是恢復出的實測trace。
三個Windows測試原trace亦已確認：drive-less fixture的absolute path不一致、未模擬平台的
非Windows測試，以及需要symlink權限的fixture。窄修保留原native reader／SDK不變，
使用原notebook bytes／SHA的全新 `.json` 暫存副本，補固定bootstrap stage／安全錯誤碼，
並修正三個可攜測試；原失敗、`.ipynb`原件、STATE與所有時鐘保留。
修正版受影響CPU測試正常／-O各39項、零skip；獨立審查通過，最後23個固定診斷碼的增量
另做正常／-O驗證，其餘production AST相同。其後原Windows真測試正常／-O也各39項通過、
零skip，純bootstrap PASS，原source bytes／SHA的 `.json` 副本核對相符。

修復後唯一numeric47 GetKernel於09:17:37.586909–09:17:39.710747 UTC執行，實際HTTP403，
`get_kernel_calls=1`、`failure_stage=get_kernel`／`error_code=http_error`、exit2／INCONCLUSIVE。
新Job的active processes=0、atomic assignment／kill-on-close=true、breakaway=false；
nonce／request／worker／helper／clock綁定相符。Supervisor收據1,683 bytes／SHA256
`1b5ed5a16033a9f0e9bd5d8ab32f49e6327767bdc62414afdfe132bd17860cdd`；
CAPTURE為1,968 bytes／SHA256
`5a311b83451f5771d824ce1385e54d75940e0b4c855a75177ccf4109dc3054b9`。
沒有returned DTO或實際遠端version／source觀察；47及submitted SHA只是請求／本地綁定，
403不證明版本不存在、save確定拒絕或GPU未執行，也不能推斷配額、OAuth或帳號問題。
7,050檔STATE前後map完全相同；舊helper／tests／ZIP／收據31檔已按原bytes保留。
Owner2 idle／next32；原epoch／global deadline與UNKNOWN均未改寫。

當時阻礙為該次讀取的存取拒絕。已停止provider查詢、save、refresh、verify-run與新的epoch，
不改瀏覽器／endpoint／帳號繞過403。後續只待使用者在自己原已登入的Kaggle介面確認此notebook
是否可見、目前版本及實際存取／保存錯誤；不要求按Save／Run或提供憑證。現有數值候選與
原code24封包保留，不再重跑未變測試或新增診斷框架。修復僅私有交付，尚未公開推送。

本地既有owner續接保留原offline-final seq17 UNKNOWN；新owner未授予舊closure。
上述HTTP403階段尚無模型／audit輸出；後續使用者提供封存ZIP後的離線核對另見v47節。
它不恢復遺失的Save DTO，也不消除官方讀取／接受狀態的限制。

### v45：第一輪 training-only 診斷結果

本地已沿原 run007／run008 路徑完成 code23、inactive44、唯一 active45 與 selected retrieval。
0a346 的新版 mount 真收據為1,712 bytes／SHA256
`e7d6001bb1476f087e8332eeab9a96f17d24df6b530665211b0e810b46f5f3f3`；code23 完整270檔回讀、
source normalization 與真實 dynamic review 通過。原 epoch `1792125027`（04:30:27 UTC），
dispatch 為 `1792125040.0939875`，global deadline 為16:30:27 UTC；首次 COMPLETE 05:01:21，
取檔後05:02:54仍 COMPLETE。原 JIT／watch exit0，六個新 native sessions closed；
原3,511件歷史 STATE、196件 edd events 與4件 refresh metadata bytes 不變，舊 edd closure 未改寫。

| 項目 | 真實取回的來源觀察 | 判讀界線 |
| --- | --- | --- |
| A／首批 B | SFT256；64/64有效 attempts、reward15/64、64 replay、8 backward；optimizer 未 dispatch／commit，rollback restored | 來源 A/B adapter SHA 相同；未下載或獨立檢查 tensor bodies，不能當 RL 成效 |
| 原數值 gate | 9,365 nonforced pairs；max0.24956846237182617，最大 trajectory p95 0.09070346951484677；12條 ratio-gap 拒絕 | pooled p95 為0.022115129232406536，不能用較小 pooled 值取代原逐 trajectory gate；門檻未變 |
| 六點 shadow | 8個 forward，8.888657824秒，state preserved；train→eval及同 logits 多列／單列2D reduction 差均0 | 只限預先固定六點，非全批／full-logits／gradient 等價；尚未比較 actor [V] 與 shadow [1,V] reduction |
| 其餘六點差 | teacher→prefix 最大絕對差0.0007356181740760803；prefix→actor 最大0.008906558156013489 | 六點未覆蓋真正最大 gap；teacher／prefix 合併 hidden 與 head-row shape，不據此指定 kernel 根因 |
| 成本與終態 | A整階段700.955374268秒，B診斷561.248857801秒；replay/backward53.849507873秒，含 shadow／restore 整批64.020976263秒 | source-recorded synchronized wall，不是 kernel time、帳單或 C 等成本比較；C／dev／held／PUBLIC 未請求 |

31個 selected outputs 共55,712,870 bytes，皆 numeric45／HTTP200；另5個 optional404。
evidence ZIP 為54,393,720 bytes、82 members，SHA256
`73152f063573353a5a5d2abf936f455371b30f4def1705f255428069c6fbb3e4`。
terminal checkpoint SHA256 `65fd59442df9d10fe10566e44c05e2b5f61feee476a6cfe81341ddbf46facc93`；
本地完整安全摘要34,428 bytes／SHA256
`99806b0ba2e293a930091f4a7bd93ca25048cfad0f31f22d71a9bb8a6383922f`，六段回傳重組後 bytes／SHA 相符。
工程分類為 `NUMERIC_DIAGNOSTIC_COMPLETE`；source-bound safe closure 與外層 process closure 有證據，
原 terminal exporter 的 `model_closed:false` 保留。獨立 model-owner MAC、完整 provider inventory、
正式 consumer、GPU stop／帳單與方法成效仍未驗證，不將工程完成升格為科學 admission。

### v47 已封存的固定 training-tail 診斷設計

只修改既有 [numeric shadow](../../tools/arc_qwen_rlvr004_20261013/numeric_replay_diagnostic_20261016/runtime/rl_session/numeric_shadow.py)
與其確切封包／收集綁定，不改原 actor、replay、DDIS、精度、cache、門檻或 optimizer 流程。
用途維持 `training-only-numeric-diagnostic-v1`，新的 shadow schema 與 namespace 區分 v45；
原 v45 程式、收據、時鐘與輸出保留；本輪 code24／inactive46 已完成，active47 的一次 activate 嘗試結果見上節。

- A256＋原首批8 parents×8 samples、reward、64 replay／8 backward與零 RL optimizer commit不變。
  max0.20／p95 0.05／unclipped1.0、30秒逐條／600秒整批、72／80 GiB門檻照舊，gate PASS／FAIL
  都保留全部64條，不用挑出的兩點代替正式檢查。
- 依已存在 v45 training audit 預先固定 `(parent ordinal, slot, offset)` 為 `(6,2,66)`、`(0,7,77)`。
  前者是 v45 全批最大 gap 點 −0.24956846237182617；後者是最大 trajectory p95 那條的最差點
  −0.12339496612548828。這是歷史 training 結果選出的診斷座標，不是獨立 qualification，
  不宣稱在下一輪仍最差。缺件／forced 明列 incomplete，不換點、不補抽樣。
- 每點最多4次原 forward：完整 teacher input／全部 generated head rows、同完整 input／目標單列、
  目標單列完全重複、該點完整 prefix／單列。額外用同一 logits 比較多列2D、單列2D與actor式1D
  masked reduction，不新增 forward。總計最多8次、120秒，保留原更早 batch／phase／global deadline。
- 記錄 train→eval、同 input head-row-selection、input縮短、1D／2D reduction與prefix→actor差，
  重複差非零也如實保存。沒有 hidden capture、persistent hook、額外 head projection或精度切換；
  [固定上游 forward](https://github.com/huggingface/transformers/blob/v5.8.1/src/transformers/models/qwen3/modeling_qwen3.py#L450-L462)
  只支持 `logits_to_keep` 在 backbone 後選 row 的來源語義，不證明觀察到 hidden／CUDA kernel 因果。
- state／RNG／train-mode與原 replay前快照 rollback、全成本計量照舊；後192 slots、C／dev／held／PUBLIC
  維持未請求，score為null。成功工程狀態與 incomplete誠實區分，不替代原 A/B/C consumer。

選點來源為原 `experiment/audit/sweep-0.json`，4,969,665 bytes／SHA256
`12280cab41ec53be1b735bffd94ebc45e5f1ed427c5d15486b42b746b5b0f9ce`；私有 token、prompt、
parent IDs與答案不公開。v45的runtime source/archive仍為 `69bf39dd…`／`085a64b4…`。
該輪固定 namespace 為 run002／source002／environment002；260 members中只改 numeric_shadow body及
衍生 release／environment身份，原 consumed259與其餘六份runtime overlays不變。
新 source SHA256 `048e9d3ee8b588cbb2075ae785b3f09fa10e3846a3269001e0c7a5f102865fda`；
archive `23281295453c2d31bf125afd26f84851e2a11ff9373f711961c21082b7e37e84`（15,818,615 bytes）；
normalized `26bdc9e717c6bda46e2891159afb7365886dccd94e90e5bff9dd6aa7188a904f`；
environment `1491a329410d5aec3b81bb8849f1167295cca27527a76f05e8e82393f129fe47`。

獨立 runtime 審查找到原 teacher shape只檢查第0列的繼承缺口：CPU合成 `[2,N,V]` 原可通過；
窄修先檢查完整 `[1,N,V]` 後才索引。精確 red→green與原失敗保留，不倒推為v45實際模型故障。
最終 runtime SHA256 `71a5bcd7998e7184962620c431a700cbe764fe8bc29a5fd50e09137fabea4265`；
作者31項及獨立31＋15項normal／`-O`均通過，來源前後不變。獨立report SHA256
`185251e360e5f191f3fd4b8b10090edc5c74a6a74be386e0fc84d6bcd0f425e7`。
Collector另外核對固定座標、原 replay scalar、原batch實際parent/slot/trajectory、完整steps長度、
shape及差值算術；1e-12只用於已記錄scalar相減的一致性，不是改原模型數值gate。
原schema六點報告不能冒充v2完成；repeat非零可誠實完成診斷，不因此允許更新。
獨立 collector 審查另找到重綁所有外層 hashes 後仍可漏驗的 raw parent 座標／順序與截短 steps；
已窄修原 batch parent order、選定 parent／trajectory 及 generated／steps 長度的關聯檢查。
三個反例先 red 後 green，失敗記錄保留。最終 collector SHA256
`df7f54f9f09709a423f68b01c40b3b8b79aae16e8c98639ecf03e76b864ede54`；作者32項、獨立32＋17項，
以及真 CPU tensor report→collector roundtrip，在 normal／`-O` 均通過。獨立 report SHA256
`25ac03a60dcf9c2b0910db025aa8062df18207313d5bcfd0c1489529fcf6db09`。
完整22件 operator、23條來源相依 pins 與 v45 predecessor capture 一起重綁；沒有只換三件 overlays。
最終 packaging26／capture12／mount27／operator6 共71項，以及獨立4項相依來源反例，
在 normal／`-O` 各75項通過；49件 code／dependency 來源在測試前後相同。獨立 report SHA256
`7b8db57335d51c96903e0aa40d20deb68fad2e92e4b416961d2878aa58bc5929`。
捕捉既有 v45 的 config 不接受未來版本配置；錯 manifest、同長度改弱 transport guard，及重算 runtime
後仍沿用 stale wire pin 的反例均拒絕。完整22件 operator inventory SHA256
`e82048f41d7d259cf89d5d6c2d3b72f03fac428c200f85351431421eb3f4bb5e`。
本次固定程式／測試與既有三份文件同一 commit 交付；精確 commit／tree 及逐檔 Git 回讀由交付收據記錄。
上述為發布前 source／CPU 驗證；其後本地已完成新 candidate 與 code24／inactive46，active47 尚無接受證據，見上節。

header before bracket 的來源檢查未發現可支持的相容性修復；header mode 並未改寫 kernel／status 路由。
新的最小診斷以 provider wrapper 標記前後各三次呼叫與返回驗證、固定 exception category，
保留原 observer bytes、原 RPC 次數與成功收據；不輸出原 exception 文字或任意 class name。
這是下一次失敗定位能力，不能倒推前兩次原因；前兩次 HTTP／長度仍未知。
作者與獨立 reviewer 各161 normal／161 `-O` 通過（header63／retrieve69／observer29）；
獨立對照65543的7種成功與非 header failure 路徑，兩模式逐 bytes 相同。作者原 stdout 未落盤，
差分 JSON 另已保存；這些測試與差分均為 CPU 合成驗證。其後本地 a3e9 單次真觀察在
2026-10-16 01:30:57.303／01:31:00.250 UTC 取得 v43／code22 的 COMPLETE／COMPLETE bracket，
HTTP200、Content-Length 1,546,535,710、新 Job0 與完整 nonce／request／worker 鏈成立；
body consumed0／未 materialize。新 result 3,647 bytes／SHA256
`90d0f0b3f636b634fb9912effea26eeb0f975826cf6cc590e1812d4f54acefd9`。
這補齊 header 觀察，不證明 tensor bytes、舊 edd closure 或正式 consumer admission。

本地只讀已確認原兩份 closed assembly inventory、259-member source proposal 與原 solver descriptor
完整；不缺料、不讀 evaluator bodies。其後本地已產生 numeric final，真實 manifest／ZIP／producer
source 均為260件；當時尚未發布新 code／inactive／JIT／RUN。原外層
`admission_run008/accept_numeric_mount.py` 的 `check_helper` 仍要求259，正常／`-O` 皆對本輪
count 子條件拒絕 `exact complete source259 acceptance`。本地 receipt 8,493 bytes／SHA256
`c5977e739a9ffaf548bb30ca2786307401e2cdd6653399cc315ab4838d92ff33` 只證明 CPU count gate
不相容，不是完整 production numeric mount／CLI 失敗，也不是 provider readback。
後續本地兩次真正原 no-model helper 與 owned closure 都 PASS，原外層 `check_helper` 在兩種
Python mode 仍拒絕；summary 2,605 bytes／SHA256
`909ca3564e8aae2f578b446e3b3b92ef979f594d5e93bb4b6a1e61d37461cc3f`。這些當時的 CPU 證據不代替後來真正的
code publication／numeric download。fresh predecessor 的五讀／零mutation、code22／v43 COMPLETE
與新 native clean close 已通過，proposal／三份真 reviews／final／config 亦完成；sealed observation
SHA256 `374b55a6fafcf7ce7294ece465a24827481802ebee5c8972ea4221f67aec626b`，final manifest SHA256
`15f340149a8eff74e6c1d56f3cd34b8836d349dfa6818ef14bd142dcb600161a`。該次檢查時外層執行批准未簽署，
尚無新 epoch／GPU／RUN；capture 後共3,530件 STATE 在該次檢查中未變。
原 receipt、259 runner 與 final bytes 保留；修復限額外固定 numeric260 外層入口，不重生
candidate／manifest、科學 source／archive 或已完成的 predecessor capture。
已發布 `59d04f8c89f6a7436c00d2905a3065fb05b4f34f` 的入口為5,074 bytes／SHA256
`e473ae0e2772432b5b04b726153415df84b89b664a02bff18e8d521895f374fc`，精確載入未改的原259
runner（`d84e2aa27edc5cef4fe557a9c327a5b4bffebbadf638d80948927677f1bd70b9`），保留原流程與
七參數，只增加固定 purpose／source／archive 檢查及260 count，另在 receipt 自身來源讀取時
重驗兩件 runner bytes。作者25項與獨立25＋9項 adverse tests，各 normal／`-O` 均通過；
測試綁 frozen sources，384件既有 RLVR files 未改。獨立 final report SHA256
`9e1c82e60766be53b24ac464e34819e716ae38112dd24e80a68f7ccd8d966ba0`。
此為當時 CPU 工程驗證；後來真實 numeric mount／v45 結果另列於上，不回寫成這份測試的證據。

本地後續重現了該新入口 `source_bytes` 的有限讀取缺口：第一讀為 `first\n`，第二個 `os.fstat`
前同 inode 寫入同長度 `other\n`，真 OS 回傳的全部比較 metadata 仍相同，單次 reader 未拒絕。
測例只在 fstat 前插入真寫入，不偽造 stat 或設定 timestamps；在 WSL home 普通檔重現，
檔案系統型別未量測，不能稱已驗 ext4。normal／`-O` 補驗各兩次均重現，並非 `-O` 特有。
本地 report 10,353 bytes／SHA256
`2540f0e3b16448f0e0e78773bee0a5258460290fb97bb4f4067a8f26c4a6f78b`。
這不是完整 mount 誤 admission 證據；編譯的 BASE bytes 仍先通過固定 SHA，原前後 source rechecks
與 receipt attribution 亦保留。修補只在這個新增 reader 以同 FD 的 bounded `os.pread` 再取一次
bytes、要求兩次相等並再核 metadata；不靠 buffered seek 或放寬 gate，也不保證任意未來／ABA寫入。
新入口5,240 bytes／SHA256 `0337a772a9275cb5714367d781650fa5d8a2e38dffd766641783c43227e27a96`；
固定260、原259 runner、helper、candidate／operator／runtime 全未改。新增回歸以合成相同 stat
值搭配真內容變動，明確區分於本地原 OS 證據；作者與獨立 reviewer 各26項 focused normal／`-O`
通過，另5項獨立 adverse tests 每模式通過。獨立 review SHA256
`dda72a64c68af79a873c1f3bb09ce3e221787f3c97377a04990a7cd21dbc5ede`，逆向最小 entry 差分精確
回到59d04的 `e473ae…`；未重驗未變元件。該修復於0a346公開後，已在本地越過 reader／真260 mount並完成v45。

### 原唯讀 session 的獨立續接依據

03022 的本地 preflight 在 provider 前拒絕 `recovery_later_session_unknown`；原 edd session 的
seq97 `kernel` 已 accepted、mutation false、closure false，匿名 pipes 已無可重連端點。
較早兩次 WSL selector mismatch 仍為各自當次事實；01:41:20 UTC 已只讀確認目前 selector 回到
原 reviewed hash，不能再將 mismatch 當成持續阻礙，也不能據此宣稱舊程序已閉合。

第一筆 presence 查詢在 SID／CIM 前初始化失敗，保留 INCONCLUSIVE；後續一次修正只明確載入
已存在的官方 PowerShell modules。2026-10-16 02:04:08.1116572–02:04:09.2319704 UTC，
兩個原 executable 的 `python.exe` basename 都在同一完整 CIM enumeration 範圍；candidate0、
所有缺欄／未知 SID／不完整計數0。原 controller 在同一 publisher flock 內同步完成前快照、查詢、
後快照；3,511 個原 STATE bytes、196 個 edd events 與 refresh metadata 全未變。
RESULT 2,759 bytes／SHA256 `419b60845f9e6778b0c9495c65b19f98e2def2ff84162b169856a326554e1e23`。
query 全文獨立重組後為 15,232 bytes／`d07f3cce2e3e4338e5ae3f676088ae48d3082f36b2706fc015d1005b8a8bba7b`；
controller 為私人路徑去敏後的語義審查，原 bytes/hash 由本地核對。原 JIT／owner 的單一同步流程
與 seq14／OWNER-START 亦已核對；這是來源與既有 launch 證據，不是所有 WSL 程序的 census。

這個已發生的 cut 只用於證明原 edd worker 無法再執行舊 pipe 的 provider 請求；它不是 Job0，
不覆寫 closure=false、UNKNOWN、原時計或 f5 的覆蓋範圍。原 claim／journal、全部196事件、
refresh 與新 runtime 的實際鎖持有仍需在續接時檢查；任何後來新增的不確定狀態照常拒絕。
歷史檢查與目前 host／source／runtime admission 各自保留，不新增永久 same-boot 條件。

本次 frozen context／bridge／common 已完成獨立審查：27 項 focused 加6項獨立 adverse cases，
normal／`-O` 均通過，測試前後來源 hashes 相同；review SHA256
`76590f9c0950f5d938dff03aed0f9115b955ed8f739b501945f803c1fdd76097`。
完整 operator 仍22件、8件既有 body 更新；23條 dependency pins、numeric overlays 與 launcher
已整合。作者63項 focused（packaging25、source closure6、collector bootstrap21、capture11）
每模式通過；獨立 reviewer 另驗 capture13項及實際 source closure6項，每模式通過。
最終 source-closure receipt SHA256
`0837d0892106b0e3bb76797216ac70e32a324b3f728bd451d481e73bdda63240`。
固定 v43 capture helper SHA256
`305bcb645e183b017fe6588044fb49e4ec0fdbb22af07929928371a5c69df223`，在真實新 close 後才產生
observation；它不進入22件 operator 集合或 runtime archive。科學 source `69bf39dd…`／archive
`085a64b4…`、native7 與 SDK 未改，未重跑未變範圍；以上是離線工程驗證。之後本地已另完成真實
M／caller、action／monitor reviews、fresh predecessor與v45 admission，不把兩種證據混為一份。

## 三、任務、依賴與下一步

| 工作 | 目前狀態 | 下一個完成條件 |
| --- | --- | --- |
| 兩 caller／guard 契約／collector schema 修復 | 0af 已發布；作者與獨立 reviewer 各 613 normal／613 `-O` 通過（46 準備、9 組裝、558 bridge） | 科學 runtime／archive 與 native 七件來源在本次 bookkeeping 修復中沿用，不重做未變驗收 |
| 多輪 publication／collector 續接 | 0d3524 的作者／獨立review每模式599項PASS維持歷史證據；本次最終bridge每模式600項、獨立context每模式70項PASS，精確hash見VALIDATION | 本地真實 history／fresh readback 已通過並接受 v43；保留原件，已驗證且未變元件不重做 |
| 原 A/B/C v43 取證 | 9fdc 真實取檔完成；4309 wrapper v2 原檔 replay PASS，22／6 observations、差集2，完整 subset 仍 false；a3e9 header 真實 HTTP200／長度驗證與新 Job0 通過 | 保留原拒絕、兩次 failed header receipts，不回填其原因。tensor bodies、原 collector context 與整體 admission 仍未成立 |
| v41 官方 log／inventory | 現有 bridge 尚未支援；SDK 0.1.37 可送 numeric version_label，但 response 無 version/source echo | 另作最小唯讀支援，不阻擋已確定的啟動修復；完整分頁與 numeric bodies／log attribution 分開，不能靠 latest CLI 補稱 exact41 |
| 數值診斷與下一輪 | v47 ZIP核對通過；A256完成、首批B被完整ABC預算拒絕，沒有新tail結果。診斷預算／placeholder窄修與25項focused normal／`-O`、獨立review完成 | 僅離線patch，尚未發布或run-ready；新發布和successor準備另需明確授權。原數值方法與門檻不變 |

研究設計仍為 SFT256 A、固定互斥 64-slot RL batches B、匹配完整 B model-phase wall 的 extra-SFT C；
no-TTT、dev 選擇與 PUBLIC120／167 不變。AF3 companion 在原 audit 產生後分析；
真正 AF3 模型 hook 仍需另立受審查 successor，不能偷換 frozen trainer 或阻擋首次原 A/B/C。

## 四、技術設計與原始來源

完整 batch／逐軌跡 loss 的設計已集中至 [AF3 Stage 1 整合](agent-factory3/integration.zh-TW.md#7-stage-1完整-batch與逐軌跡續接)，不在進度頁重複維護。

## 五、離線實作與驗收契約

見 [AF3 的 audit／reduction／shadow 契約](agent-factory3/integration.zh-TW.md#離線實作與驗收契約)與 [Stage 1 工具介面](../../tools/arc2_abc_continuation_20261014/README.md)。

## 六、本地模型證據的驗收契約

見 [AF3 模型驗收表](agent-factory3/integration.zh-TW.md#本地模型證據的驗收契約)；來源宣告與 CPU 梯度不能替代真實模型證據。

## 七、既有決策條件

只見[方法總覽第 7 節](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)。本頁不另立方法計畫。

## 八、離線交付與後續更新驗收

只在來源、測試、獨立審查與精確發布結果可核對後更新對應狀態；本次新文件與未發布程式不自稱已通過舊審查。

## 九、開發與本地執行循環

依[單一交接流程](OFFLINE-LOCAL-HANDOFF.md)取得實際結果，更新本頁；完成事件移入固定歷史，保留失敗與成本。

### 更新紀錄

舊時間線完整移至[工程歷史](archive/engineering-history.zh-TW.md#原更新紀錄)；不再於此累積第二份歷史表。

### 2026-10-15 v43 獨立唯讀入口驗證

[observer](../../tools/arc_qwen_rlvr004_20261013/readonly_observer_20261015/observe.py) 的
29 項 focused CPU 測試在 normal／`-O` 各 PASS；獨立 source review PASS。測試先找出並修復
混合 CLI option spelling 重複值，以及 URL params／空 userinfo 的不精確比對；最後僅允許
兩個 read RPC 的四個精確 HTTPS URL。output 拒絕 `state*` ancestry／native source／既有目錄。
helper SHA256 `696cbfc6336fa208526352c4479bf3a32eb5a835d8fa75aca01a87ffa7346655`；
test SHA256 `dce7d59ea01c99d180658e3e0a01a6ac135b031d01d55d9254d9d71dff3ba6ef`。
原 native 七來源及 SDK lock 不變，不重跑其歷史 suite。本地已真正取得20:45:36.341 UTC RUNNING bracket與新Job0，原3,511件 STATE不變，舊session closure仍未證；不代表遠端終態、GPU、成本或科學結果。

### v43 selected retrieval 的窄驗證

另增 `retrieve.py`，status observer與已接受run不變。新增57項CPU測試，合併固定observer29項，
作者與獨立review各86 normal／86 `-O` PASS；另有5項獨立mocked supervisor負例／finalization驗證。
retrieval helper SHA256 `68a2291e1ebb174471baec9067babe6f71a6305f4ab3641921f18461e188e8be`；
test SHA256 `b4661450c8cfcd338829914c42dad08ce9cc4479b5dbdf9f94f99411c537111e`。
只允許原selected白名單的單一numeric43檔案；terminal前不下載，完整來源／設定bracket、原clock、
no-refresh／mutex／Job、exactcap／diskreserve、prior-terminal完整receipt鏈與Job0後hash／finalize
皆保留。首次 native／provider terminal JSON 下載已完成 worker 與新Job0，但 parent finalization 失敗；
跨筆aggregate／ZIP／owner／wrapper／科學驗收不由新helper授予。

### v43 native 檔案身分修復

首次 partial 的119,652 bytes／SHA256 `a95c964a8e29d5b27e067ac1a6ee66af7efe345cd55684f88ab11a0cf32092a7`
與 worker 相符；本地 Python3.12.10 Windows 的 Path.stat ctime 是 birthtime，fstat ctime 是
ChangeTime。兩個 API 各自前後穩定，只有跨 API ctime 不等；normal／`-O` 獨立重現
`download_file_changed`，不是原 catch 的例外 trace。[CPython 對應問題](https://github.com/python/cpython/issues/157671)
也記錄這項語義差異。修復只在 Windows 跨 API 比較共同身分欄位，兩路各自的六欄前後檢查
（含 ctime）仍完整保留；POSIX 不放寬。post-close 失敗以固定 stage／allowlisted code 回報，
不外洩任意例外文字，不再只留下 `worker_exit`。原 failed receipt／partial 保留；9fdc 已以新 output 真實重取 terminal／archive 成功。

本次 retrieval suite 69 normal／69 `-O` PASS；獨立 focused identity／supervisor 20 normal／20 `-O`，
另以獨立19-case身分矩陣驗證。helper SHA256
`1bdadfd56c68f53528babf64390295bb53965884bb9eacaff5f20a207e53d615`；test SHA256
`29d4ffe0ccf04ff393ac68267b605df8bd817a9dcc9d002d261a5bef0b68ff44`。
未重跑不變 native／SDK／科學 suite。真實 terminal native receipt SHA256
`c7aed6c2ea053b4dde32fdb280b36e6694f9da282b9db872abde53185082c697`，archive receipt SHA256
`d3f5eae93987fd60dee2251ef47d8e679ea4bea1793c8323e88cc52040e5596e`；兩者各有新 Job0 與成功 finalize。

### v43 checkpoint header-only 窄驗證

`retrieve.py` 增加明確 `--checkpoint-header`；固定 checkpoint 路徑不加入原 body 白名單。
40 項新 header 測試，加上原 retrieval69／observer29，作者與獨立 reviewer 各 138 normal／138 `-O`
PASS。helper SHA256 `62c2fddd50525af7d37e20368412a5d424f8aa19281932eb6ef897b761741f92`；
新 test SHA256 `f8cd4e76cef5176774f4da2889ddfc2591fda65a0affff9d1e6483d8680db55b`。
原 observer、native 七來源及 SDK lock 不變。獨立 review 找出 SDK JSON response 可能先讀 body 的路徑，
已在原 SDK 前強制 stream 並拒絕 JSON-body URL redirects，只保留 Location redirects；未修改 SDK。

入口驗證固定 9fdc 真 terminal receipt 全鏈，要求實際 HTTP200／identity encoding／Content-Length
與 1,546,535,710-byte 來源宣告一致，再以新 Job0 後的獨立 header receipt 保存。沒有 body、遠端 SHA
或 collector admission 宣稱。4309 的首次本地實測沒有完成：`selected_retrieval_failed`、
header null、HTTP status 未知、Content-Length 未驗；新 Job0 成立且 body consumed0／materializedfalse。
原失敗收據 1,891 bytes／SHA256 `d1dc741cbb075135e1ed971a4ca22b8e7f9380452d799629f4916a11286c35ce`
保留；不能從來源宣告或 body0 推斷已取得實際 HTTP header。

本次只增加固定 allowlist 的 `worker_failure_stage`／`worker_error_code`，經原 nonce／hash／format
驗證後寫入失敗 parent receipt；不傳 raw exception、URL、headers 或私人路徑。成功 worker bytes／
parent receipt 的 baseline 差分相等，請求、no-refresh／mutex／Job0 與讀取／重試行為不變。
helper 43,162 bytes／SHA256 `793e3e1d10e6f0d0dd2a0ec43ca9d78ce8f3a81336fba60332de4441901fcda0`；
test 46,888 bytes／SHA256 `1d1c30b8aa3527685770473755203d67e80b40bc0dfe3c0e59519cfce9062804`。
作者與獨立 reviewer 各 154 normal／154 `-O` PASS（header56＋retrieval69＋observer29）；
另有獨立 43 種 parent envelope 與 18 種 worker exception 負例。獨立 review SHA256
`fb5091eb81671e60a6b7d3dc960e176e7c7bf56844ccdbf0d73ac17da4cffaf4`。此版本後續真實重試仍失敗，
再後的 a3e9 單次 header 觀察成功，精確結果見本頁目前證據；不改寫這兩次失敗。

### v43 nested-wrapper observation 契約修復

原 guard 分別記錄各階段觀察到的子程序，不是完整生命週期 census；真實 CPU counterexample 證明
兩個 clean nested scopes 不保證完整 inventory subset。v43 的兩個額外內層 triple 也在該內層原
supervisor receipt 中，且三個必要 anchor 均在外層；此為本地原件只讀觀察，不補造個別 exit 時間。
獨立 [successor](../../tools/arc_qwen_rlvr004_20261013/wrapper_observation_repair/verify_parent_wrappers.py)
保留原各階段驗證、source／JIT／interval／runtime／terminal checks，以雙 clean closure、原收據
雙 witness 與 exact anchors 處理此窄差集；共同 incarnation 的 session 衝突仍拒絕。

原 v43 verifier 為 24,468 bytes／SHA256
`4dd228f6559ccad58d421d9b1e90f6aea9339b32c15e4df4f32855731a77d3f8`；其與模板的 `verify_stage`
原 bytes 相同（4,881 bytes／`6d2f1da36f8e17ef1c87a608c2c1d5af8624ff7959c8797c1db700daf7e344bf`）。
successor SHA256 `c3aa3b40cfba89a969dd171e758e3d9c4875686b259cfcabf80dec1da486d6bb`；
test SHA256 `8d2e3f29e8f5eae3b12a4eb0c95f4c99a09dd0277a4c011f199c91411214dd20`。
作者與獨立 reviewer 各 29 normal／29 `-O` PASS，另有獨立六種 rebound runtime identity 負例。
審查發現並補上原先缺少的 incarnation.pid／worker_pid 一致與嚴格 int 檢查；所有原 checks 仍保留。
真正 CPU counterexample 有兩筆缺內層 supervisor witness，因此 successor 仍拒絕；未修改它換取 PASS。
原 source、manifest、wrapper 拒絕與 native UNKNOWN 不改。4309 本地原檔完整 successor replay 已 PASS：
closure_valid／operational／runtime_tree_link true，prep22／inner6／diff2；完整 subset false、
model_closure_verified_by_this_helper false 如實保留。新結果 9,522 bytes／SHA256
`e72b7c8363746cfd01903b37103899b44428a9e216e209d35ea4b7d599c27101`。
這沒有補齊舊 native closure、trusted collector context 或正式科學 admission。
