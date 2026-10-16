# ARC-AGI-2 當前開發與實驗進度

更新：2026-10-16 UTC。本頁只維護目前狀態、阻礙與下一步；研究問題與固定設計見
[研究主頁](README.md)，歷史 E0–E52、來源指紋及更新時間線見[工程歷史](archive/engineering-history.zh-TW.md)。

**v43 已完成並取回真實輸出；B 沒有提交 RL 更新，原 scorer 的 PUBLIC 觀察為 0/167。**
正式 consumer admission 尚未成立；來源評分不是官方或獨立重評結果。現在先釐清 unchanged-policy
數值落差並修復已定位的證據契約，研究方法與門檻不變。
使用者已授權依既有 run007／run008 離線 notebook 模式持續開發、Kaggle 執行、分析 terminal／結果，
再按既有研究條件進入下一輪；本地端維持唯一 publisher，code 與 weights／wheels／資料 Dataset 分離鎖版。
同範圍例行續接不逐輪重新詢問，但現有 UNKNOWN 與各次 admission 不因此豁免。

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
本地 preflight 在 provider 前被原 edd 未閉合 session 拒絕，尚無新 code 或 RUN。完整 operator 的
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
| v43 當前實證 | code22／inactive42 真收據與 manifest 相符；10-15 19:33:50.121 UTC 接受 active43，23:27:59.209 首次 COMPLETE；後續新取檔收據與來源／設定一致 | 26 必要＋5 選用檔案共 130,955,581 bytes；另 5 選用 404。新 Job0 成立，原 3,511 件 STATE 不變、舊 native closure 未證 |
| v41 真實終態 | 2026-10-15 15:58:28 UTC 首次觀察 ERROR；Internet OFF、RTX Pro 6000、private | [原 notebook](https://www.kaggle.com/code/danielwuu/iris-x-learning-agent-20261011)，kernel ID 138123872 不是 scriptVersionId；native closure 不證明遠端 VM teardown |
| 啟動原因 | notebook 的 ambient interpreter 在離線環境建立前查固定 cuDNN，distribution 存在但 version 不等 9.10.2.21；停於 parent-environment-policy | ambient 實際版本與 backend 是否載入未知；prepare caller 同排序風險尚未執行。`preparation_failure:null` 另使 collector 拒絕 schema |
| 已取回證據 | 五份 numeric41 outputs 各有 HTTP200、bytes／SHA receipt：startup diagnostic、preparation request、original request、operator、outer notebook | 五份不是全 inventory；outer notebook 無 execution outputs，不能當官方 execution log。模型／audit／score／cost 其他檔存在性未知 |
| 已發布的啟動修復 | 兩個 deployment-only callers 改用無模型準備環境；真正 installed parent／worker exact-byte gates 保留。collector 只多接受原 schema 加 null 欄位 | [修復範圍與 CPU 測試](../../tools/arc_qwen_rlvr004_20261013/preparation_environment_repair/README.md)；新增 runtime policy 一檔及衍生 self-pin 一檔，其餘 257／259 與 A/B/C 不變；v43 已實際越過啟動邊界 |
| 多輪續接 | 0d3524 已隔離每輪 publication／collector 目錄，native STATE 與全域鎖共用；本地18:03 fresh no-auth 停於舊f5永久 same-boot 字串 gate | 原1,686檔完全不變，未新建 native claim／canonical／run、未 provider。CIM boot值變1.802125秒，host／Windows／source／runtime相同；符合校時漂移但未證明 same boot，不拿猜測當PASS |
| 歷史／即時 context 修復 | 原封存Restart＋reconciliation在原completion time重驗；fresh host／source／runtime／closure另核對，封存events及live STATE前後綁定 | 只支援現有f5原件的12.629秒歷史間隔，保留原120秒限制；later UNKNOWN／refresh／publication變更仍阻擋，不加BootID框架、容差或重啟 |
| Repository／CI | 59d04 精確 CI 仍失敗：同 6 項既有 README invariants 缺詞，unit／packaging skipped | focused 驗證只支持其實際範圍。額外誤啟的 repository aggregate 未成為驗收：一筆中止，已結束者 1,621 tests／6 failures／41 errors／74 skips；不以此修無關元件或宣稱全綠 |
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

### 下一輪：固定 training-only 數值診斷

新增來源在 [numeric diagnostic successor](../../tools/arc_qwen_rlvr004_20261013/numeric_replay_diagnostic_20261016/assemble.py)，
用途固定為 `training-only-numeric-diagnostic-v1`；不是可開關的另一套訓練方法。

- 保留同 session A256、原首批 8 parents×8 samples、reward、64 條 replay／原 DDIS backward 與
  max0.20／p95 0.05／unclipped1.0、30 秒逐條／600 秒整批、72／80 GiB 原門檻。
  原 gate 的 PASS／FAIL 另外保留；兩種結果都不 dispatch／commit RL optimizer。
- 固定看 parent ordinal0、7 的 slot0；各 offset0、1、last 去重。缺件／forced 明列，不能換樣或
  挑本輪最差例。每條新增一次 eval／full-teacher 原多 row head 與至多三次 eval／full-prefix M1，
  總計最多8個 full-model forward；不捕捉 hidden、不新增 hook、不額外 head projection。
- 記錄 train→eval 的 mode／autograd／checkpoint 合併差、teacher→prefix 的 hidden／head-shape
  合併差、prefix→原 cached actor 差。另用同一 logits 比較多 row／單 row masked-softmax。
  不能把 teacher／prefix 差稱為已隔離 head 因果，也不能單指 attention kernel。
- 額外同步 wall 最多120秒，單 forward 有獨立25秒 soft／30秒 hard watchdog，仍受原 batch／phase／
  global 更早期限與 memory caps 限制。成功、失敗、host／同步工作及 forward input tokens 都留在
  physical ledger；不重設 peak，不宣稱帳單已驗。
- shadow 後清梯度並恢復**原 replay 前快照**，包含當時 RL optimizer／scheduler、post-sampling RNG
  與邏輯計數；A adapter 必須相等。這不是把整段 A 訓練或實際工作／generation epoch 倒帶。
  後三批192 slots 為 `not-requested-by-diagnostic`；C／dev／held／PUBLIC 全不執行，scoring 保留 null。

成功工程狀態為 `owned-numeric-diagnostic-complete-no-update`；原64 replay、完整 shadow、真實
rollback、原 deadline 與 live closed-model capability／raw safe closure 均須成立。任何缺件或原首批
無 mixed signal 而未 replay，明列 `owned-numeric-diagnostic-incomplete`，不補抽樣／評分。
仍使用原 process-termination diagnostic exporter，所以 terminal `status:diagnostic`、
`model_closed:false` 不改；獨立工程分類不能冒充原 ABC consumer、comparison 或科學 admission。
collector 核對原 container／source／JIT／closure 與4份 raw audit，後192 slots 必須確為未請求空格。

新 namespace 為 `irisx-qwen14b-numeric-diagnostic-20261016-run001`／`source001`／`environment001`；
原 publication format／角色名稱只作 wire compatibility，另綁固定 purpose 與較窄 owner direction。
per-code publication isolation、原 mutex、UNKNOWN／auth-refresh 與 exact-byte gates 沿用。
新 runtime 260 members，其中251個 consumed source members、全部200個 consumed baseline members
不變；199是更早原 baseline 的歷史計數，另1個已存在 installer repair 並未在這輪重改。
source SHA256 `69bf39ddee56278197eb4f1a46119d569dba45f51621a92588a56dd7d6f1e292`；
archive SHA256 `085a64b4dbe9c35db40d81ef0ae28dcce445eaa78f5da0e85518900bab035061`；
normalized contract `804598522bf81b54ddbfdb585ea21ee925905dc8ac87ddc9b717ea988aff4c4f`。

作者整合80 normal／80 `-O` PASS：probe21、runtime16、packaging23、collector20。
使用既有 Torch2.9 CPU、受控完整形狀 flow、真正 durable ledger 與原 ZIP／terminal helpers；
沒有安裝或執行原 Qwen／Transformers／PEFT／GPU。`--tiny-proof` 的小 fixture 不符合固定64／ordinal7，
不宣稱完整 factory proof。獨立 runtime review 的55項當時測試與8個額外對抗案例各模式均通過；
review SHA256 `3aae4cba52e0a3e9ddf9475416e7efdd1819d6b187614190bf19d87cfebd6b72`。
審查抓到新增 token 計量與 collector 後三批語義缺口，已補真 event 計量與 raw audit 負例；
publication／collector 獨立審查亦 PASS：43 項 targeted、18 個拒絕負例與1個誠實 incomplete、
9 個重新綁全套 hash 的 raw-audit 負例，各 normal／`-O` 均通過。review SHA256
`5ebdb47ec5fa09b60d351b8c90548fae7d89e51340f6acf3b838eaf2c7b437a0`。
以上只綁定來源；本地 exact proposal 的 solver／runtime／material reviews 仍須另核對，不能沿用未對應的 review。

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
source 均為260件；新 code／inactive／JIT／RUN 尚未發生。原外層
`admission_run008/accept_numeric_mount.py` 的 `check_helper` 仍要求259，正常／`-O` 皆對本輪
count 子條件拒絕 `exact complete source259 acceptance`。本地 receipt 8,493 bytes／SHA256
`c5977e739a9ffaf548bb30ca2786307401e2cdd6653399cc315ab4838d92ff33` 只證明 CPU count gate
不相容，不是完整 production numeric mount／CLI 失敗，也不是 provider readback。
後續本地兩次真正原 no-model helper 與 owned closure 都 PASS，原外層 `check_helper` 在兩種
Python mode 仍拒絕；summary 2,605 bytes／SHA256
`909ca3564e8aae2f578b446e3b3b92ef979f594d5e93bb4b6a1e61d37461cc3f`。這不取代尚未發生的
code publication／numeric download。fresh predecessor 的五讀／零mutation、code22／v43 COMPLETE
與新 native clean close 已通過，proposal／三份真 reviews／final／config 亦完成；sealed observation
SHA256 `374b55a6fafcf7ce7294ece465a24827481802ebee5c8972ea4221f67aec626b`，final manifest SHA256
`15f340149a8eff74e6c1d56f3cd34b8836d349dfa6818ef14bd142dcb600161a`。外層執行批准尚未簽署，
沒有新 epoch／GPU／RUN；capture 後共3,530件 STATE 在本次檢查中未變。
原 receipt、259 runner 與 final bytes 保留；修復限額外固定 numeric260 外層入口，不重生
candidate／manifest、科學 source／archive 或已完成的 predecessor capture。
已發布 `59d04f8c89f6a7436c00d2905a3065fb05b4f34f` 的入口為5,074 bytes／SHA256
`e473ae0e2772432b5b04b726153415df84b89b664a02bff18e8d521895f374fc`，精確載入未改的原259
runner（`d84e2aa27edc5cef4fe557a9c327a5b4bffebbadf638d80948927677f1bd70b9`），保留原流程與
七參數，只增加固定 purpose／source／archive 檢查及260 count，另在 receipt 自身來源讀取時
重驗兩件 runner bytes。作者25項與獨立25＋9項 adverse tests，各 normal／`-O` 均通過；
測試綁 frozen sources，384件既有 RLVR files 未改。獨立 final report SHA256
`9e1c82e60766be53b24ac464e34819e716ae38112dd24e80a68f7ccd8d966ba0`。
此為 CPU 工程驗證；尚無真正 numeric readback mount receipt，不將其當 GPU 或 runtime admission。

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
回到59d04的 `e473ae…`；未重驗未變元件，尚未宣稱本地新版 mount 完成。

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
`085a64b4…`、native7 與 SDK 未改，未重跑未變範圍；以上均為離線工程驗證，尚未取代本地真實
M／caller 原件核對、action／monitor reviews、fresh predecessor 或新 RUN admission。

## 三、任務、依賴與下一步

| 工作 | 目前狀態 | 下一個完成條件 |
| --- | --- | --- |
| 兩 caller／guard 契約／collector schema 修復 | 0af 已發布；作者與獨立 reviewer 各 613 normal／613 `-O` 通過（46 準備、9 組裝、558 bridge） | 科學 runtime／archive 與 native 七件來源在本次 bookkeeping 修復中沿用，不重做未變驗收 |
| 多輪 publication／collector 續接 | 0d3524 的作者／獨立review每模式599項PASS維持歷史證據；本次最終bridge每模式600項、獨立context每模式70項PASS，精確hash見VALIDATION | 本地真實 history／fresh readback 已通過並接受 v43；保留原件，已驗證且未變元件不重做 |
| 原 A/B/C v43 取證 | 9fdc 真實取檔完成；4309 wrapper v2 原檔 replay PASS，22／6 observations、差集2，完整 subset 仍 false；a3e9 header 真實 HTTP200／長度驗證與新 Job0 通過 | 保留原拒絕、兩次 failed header receipts，不回填其原因。tensor bodies、原 collector context 與整體 admission 仍未成立 |
| v41 官方 log／inventory | 現有 bridge 尚未支援；SDK 0.1.37 可送 numeric version_label，但 response 無 version/source echo | 另作最小唯讀支援，不阻擋已確定的啟動修復；完整分頁與 numeric bodies／log attribution 分開，不能靠 latest CLI 補稱 exact41 |
| 數值診斷與下一輪 | actor 為 eval／inference cached 增量解碼；replay 為 train／autograd checkpointed 全因果 teacher-forcing。相同 token／DFA 上仍有 gap | 既有 calibration 差分已完成；下一輪固定 training-only 診斷 mode／checkpoint、teacher／prefix 及 cached 路徑，teacher／prefix 仍合併 hidden 與 head shape 因素。不得猜 kernel 根因、放寬門檻或依 PUBLIC 答案改模型 |

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
