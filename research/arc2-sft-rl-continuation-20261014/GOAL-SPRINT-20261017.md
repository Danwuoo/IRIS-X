# 2026-10-17：AF3 完整學習與評分 successor

目標是 PUBLIC120 的 micro pass@2 嚴格超過 93%，即至少 156/167。
這是持續研究目標，不是能力預測或已取得分數。新流程使用獨立 run/source 身分，
不修改原 frozen A/B/C、v43 的 0/167 觀察或 v47 ERROR 的歷史證據。

## 為何改變

過往流程反覆完成少量 SFT、數值診斷與封裝，但沒有可用的 RL 更新比較。
新授權允許重新設計方法與文件，優先把真正上游 AF3 loss 接進模型，
一次走完學習、選擇、TTT、推論與完整評分，而不是再交付 training-only 診斷。
既有 `irisx-nvarc-original-qwen3-001` 材料聲明 `full_sft_completed=false`、
`original_sft_checkpoint=false`；它是裁剪詞彙的 Qwen3-4B base，不能稱 ARC specialist。
本輪使用已有的 Qwen3-14B BF16 與單張 RTX PRO 6000 資源。

## 新方法，不冒充舊對照

1. 依既有官方 training 材料的 parent-level 800/200 partition，排除 PUBLIC ID
   與已知 D4／顏色重命名／demo shuffle 重複。重複組碰到 dev 時整組移到 dev。
   只使用 training demonstrations，原 training-file test 欄位不作學習資料。
2. A 以廣泛 LOO demonstrations、可逆幾何／顏色 augmentation 訓練 rank-16 LoRA，
   目標最多 3,072 個真實 optimizer steps；平台時間不足時完整記錄實際步數。
3. B 從 A 出發，以原始 token、temperature-one full-vocabulary sampling/replay，
   使用真正上游 `TrainingSample`、`DDISLoss`、`MeanMetricState`。
   每批 8 parents × 8 samples，最多 12 批；完整 group 後才作更新。
   reward = training-LOO exact + 0.2 × 同形 pixel accuracy，兩項分開記錄。
4. 先以全部 reward 算 group mean 與 divisor，再逐條 replay/backward，
   不同時保留 64 個模型 graph。零訊號／全遮罩沒有假更新；失敗批次 rollback。
   真正更新須有有限梯度與改變的 adapter bytes。
5. C 從 A、fresh optimizer，匹配整段 B wall-time 的額外 SFT，不用 idle padding。
   時間匹配是否成立明列，不把不同資料／學習率的比較說成純 objective 因果證明。
6. 固定 train-derived dev panel 以完整 mean NLL 選 A/B/C，平手 A→B→C。
   若選擇未完成，預先規定回退 A，不能用不等長 partial panel 或 PUBLIC 選模型。
   Adapter export/reload 必須逐 tensor 與模型 state hash 相等。
7. PUBLIC 每題先恢復同一 selected adapter，只以該題 demonstrations 作最多 8 步 TTT。
   每 query 使用兩個預定可逆視圖，inverse transform 後保留最多兩個不同合法 grid。
   不以 PUBLIC 答案修改 checkpoint、prompt、候選順位或當輪策略。

DDIS 使用上游預設雙側 (.8, 1.2) 硬遮罩與 group-balanced sequence-token mean；
不用舊 DFA-conditioned measure。Cached/full replay drift 實測記錄並反映在真正 ratio
與 clipping，不能把舊門檻拒絕改名為成功。沒有移植 GPT-OSS/Harmony/SGLang 的 4×H100
異步框架，也沒有宣稱完整 AF3 框架重現。

## 執行與評分

新來源 `tools/arc2_goal_sprint_20261017/`。使用既有離線 weights／wheels／training／PUBLIC
材料；補入 AF3 真正需要而舊 wheel lock 沒有的官方 Pydantic dependencies。
2026-10-17 真實 CPU notebook v48 已證實 Landlock 不可用（ENOSYS），mount namespace
也不被允許（EPERM）。因此本 successor 使用真正資料分離，而不是宣稱不存在的 OS sandbox：
GPU notebook 僅掛載逐 byte 驗證的 solver-only PUBLIC projection，不掛載含 evaluator 的原 Dataset；
bootstrap／worker 驗證完整掛載清單與原 Dataset 缺席。模型與 owned 子程序結束、source-side
closure 驗證及 predictions hash 封存之後，parent 才確認 provider 的精確 notebook version/source
與終態、取回並驗證 sealed outputs，於另一個 CPU 環境載入 evaluator。這不是跨機器 PID
即時驗證，也不宣稱 chmod 複本能阻擋原 mount。評分使用未修改的
`tools/arc_offline_evaluation.py` 與固定 upstream provenance。
全部 120 tasks／167 queries 皆在分母；缺失／非法預測不能被丟掉。
有效評分、solver 運作成功與目標達成分開記錄；空 pools 或失敗訓練的 0 分不是模型能力成功。

離線 loader 是本 successor 的新設計，並非聲稱遵守舊 loader 的 symlink-overlay 禁令：
保留原 material contract 的 provider weight/index 與官方 HF tokenizer/config byte pins，
在 ephemeral runtime 建立 pinned shards/index symlink view 配合 pinned overlay。
CPython 3.12 與全部 wheels 以固定 hash、無網路、隔離 site-packages 安裝並 pip check；
實際模型仍須通過有限值、真實 optimizer delta、rollback 與 adapter save/reload 檢查。
venv 與 model view 不留在 provider 採集的 working outputs，以免無謂輸出數十 GB。

PUBLIC 已用於本專案開發。即使達標，結果也只是這個公開開發集的觀察，不是 hidden
generalization、官方 competition 分數或尚未驗證的模型曝光保證。
實際 session 仍有平台 12 小時限制，分階段保留推論／評分時間；這不是總 GPU 配額門檻。
未達目標時依真實終態、輸出、成本與學習訊號繼續下一輪；不因預估剩餘時數自行停工。

## 驗證狀態

- 歷史 v47 ERROR 保留；新 notebook 138123872／v48 是 CPU-only isolation preflight，
  已 COMPLETE，沒有模型載入、GPU 使用或新分數。Provider source SHA-256：
  `dcc9fa0cc81bb2b058c2ee36828750d4a5bde7ca1c9c4616d05624f6e0a7dd9e`。
- 專用 AF3 adapter CPU 測試 11 項：10 PASS，CUDA 專用 1 SKIP。
  Tiny Qwen 真正 autograd／SFT／upstream DDIS／control／selection／reload／TTT
  整合、failure rollback 與真實 device admission 測試 23 項皆 PASS；獨立審查找出的 optimizer-step OOM
  partial mutation 已修復，還原 adapter 並重設 optimizer。
- 正確固定 PYTHONHASHSEED/TMPDIR 後的全 repository 檢查：invariants/self-tests/whitespace
  PASS；1,654 tests 中仍有 2 failures、37 errors、22 skips，主要是未隨 clone 提供的
  舊私有 fixture／native materials，以及舊 distributed CPU collective timeout。
  這不是全 CI 綠燈；不刪除或弱化舊檢查來製造成功。
- 新流程 focused suite 在 normal 與 `python -O` 各 67 tests：65 PASS、2 SKIP
  （CPU 環境沒有 CUDA 與 Landlock）。封裝／hash 驗證不可因 optimized Python 移除。
  Opaque source package 已完成本機 roundtrip／import；pinned offline CPU READY 後續已於 v49 驗證，詳見下節。
  所有 CPU 結果都不能冒充真實 GPU throughput、學習收益或 PUBLIC 分數。

私有 solver-only Dataset `danielwuu/irisx-goal-public-inputs-20261017/1` 已 ready，
四個公開 solver 檔案下載後逐 byte 與原 manifest 相符，沒有 evaluator。Provider 會移除
每個 directory ZIP 的外層路徑，因此 source 使用 notebook-pinned opaque payload transport，
不可直接把各 source directory 交給 `--dir-mode zip`。GPU dispatch 另以明確 accelerator
參數要求現有 RTX PRO 6000，並在 14B 載入前記錄實際 GPU／memory，拒絕小記憶體 fallback。


## 已確認的 source 與 run 身分（2026-10-17 UTC）

- Source Git commit `b2e93b2f225f8ef929f321cbe7ab02dc7919fa8d`，tree
  `d412cbbfe63c3874bd31a487c999c6f8a773fd4f`；private Dataset
  `danielwuu/irisx-goal-af3-source-20261017-001/1` 的 opaque payload 與 manifest
  下載後逐 byte 核對。Source manifest SHA-256
  `6cdeb729db777f1d11c510a4d6fb4f72b8ebf41db8dc3ee1e3716e5a54e8c869`。
- Notebook 138123872／v49 是 CPU-only 完整離線材料準備，已於 03:14 UTC 前後雙向確認
  COMPLETE 與精確 source cells。CPython 3.12.15、torch 2.8.0+cu128、transformers
  5.8.1、peft 0.21.0、pydantic 2.11.7 的 hash-pinned 安裝、pip check、實際 imports、
  1,003 個 training manifest 檔案、59 個 source 檔案、solver-only projection 與 model
  material contract 均通過。實際 model load／training／inference／GPU execution 仍為 false。
  Provider source SHA-256：
  `16130404413c173a0877b07b93bc2f79d2f23715c66321237fcca9af4651d85a`。
- 首次 GPU push 因實際兩個 batch GPU slots 已佔用而被拒，回傳 body 明列拒絕，
  SDK 確認仍是 v49，沒有建立新 RUN。既有 NTL inference 被 provider 確認 COMPLETE 後，
  使用新 dispatch clock 重試；v50 於 03:21 UTC 被 SDK 確認 RUNNING、private、offline、
  source cells 完全相符，要求 NvidiaRtxPro6000。Provider source SHA-256：
  `f4adf8a483dbdab319650e3e683beebd7084d57aab045ffb487fe3fe2e077a8d`。
  Run ID 為 `irisx-goal-af3-20261017-001`。此觀察不是實際硬體、optimizer update 或分數證據。
  原 dispatch 時鐘的 12 小時 deadline 為 2026-10-17 15:19:06 UTC；不因稍後觀察而重置。
- v50 固定保留 200 dev parents，但 A/B/C selection 實際預定使用其中 SHA 排序的 24-parent
  panel，不把保留 partition 大小當成實際 selection 樣本數。
- 後續 public-clean-checkout 修復在乾淨環境得到 1,739 tests：1,606 PASS／133 SKIP，
  其中 27 是明列未執行的 retained-evidence integration。Strict `--all` 仍因真正缺少
  歷史私有材料而有 1 failure／13 errors，不宣稱完整歷史接受。GitHub run 38998183416
  的 Windows 3.11 job 又揭露 POSIX-only tests 與一個 Windows Job cleanup lifecycle
  問題；其餘 jobs 被 fail-fast 取消，不能算 PASS。Portable Windows lane 與修復另案驗證，
  不改變正在執行的 v50 source bytes。


## 未改動 v50 的下一輪實作與觀察界線

截至 2026-10-17 04:41:56 UTC，最後成功取得的 v50 provider metadata 仍為
RUNNING，source cells 與已提交版本一致。隨後同一合法讀取路徑與普通 status endpoint
都回覆 `kernels.get` permission denied；其他獨立 notebook 亦出現同樣拒絕，原因未確認。
不把 denied read 解讀成 notebook 完成、失敗、GPU slot 釋放或配額耗盡，也不重啟 run、
更改 credentials 或繞過拒絕。Provider 終態、實際硬體、optimizer update 與分數仍待恢復
存取後驗證。持續本機準備不能取代真正的終態／seal／輸出驗證。

下列選項只屬未來新 source/run identity，全部預設關閉，不回寫 v50 protocol：

- 可從經終態與 seal 確認的 pre-PUBLIC selected adapter 繼續；以獨立 model material
  contract、完整 LoRA config／tensor inventory／state digest 綁定。Optimizer 與 RNG 不續接。
  既有 run 的 PUBLIC task-specific TTT adapter 不是允許的 resume 來源。
- SFT 與 demonstration-only TTT 可用 Fast tokenizer offsets 對所有已有因果示例的 output
  tokens 訓練；第一個保留 demo、所有 inputs、跨 boundary token 都不計 loss。
  Dev NLL 仍只用最後答案，AF3 原 trajectory completion mask 不變。
- 可用固定 8／16 transformed views，逆變換與去重後，以固定 vote 或完整跨-view
  likelihood panel 排序。Likelihood panel 若未完整計算則回退 vote，不用不等算力的局部
  scores 選答案。最終仍只交 top two、全 120 tasks／167 queries，不報更大的 pass@k。
- Private full candidate pools 與選定 top two 綁定並另外 seal；只作 provenance audit，
  不可看答案後重新選候選。有限長度、nonblocking／best-effort solver log relay 只是觀察通道，不替代完整私有 log。
- Clean RE-ARC corpus 僅來自已准入的 training parents；parent-uniform sampling 後，
  有 corpus 的 parent 以 original/generated 各半，僅用於 A/C SFT。
  詳見 [CLEAN-CURRICULUM-20261017.md](CLEAN-CURRICULUM-20261017.md)。

這些實作已做 tiny-Qwen 真正 autograd、resume rollback、完整 denominator、實際 pinned
Qwen tokenizer 合成網格至 30×30 的 CPU 測試與獨立審查；仍不是 14B CUDA throughput、
ARC2 收益或接近 93% 的證據。後續 package/bootstrap 材料 pinning 整合另外驗證，完成後
才可用新 source identity 發布。新資料與更大 candidate pool 本身不保證達標。

### 下一輪 source 的本機整合驗證

2026-10-17 的目前工作樹在 normal 與 optimized Python 各執行 170 個 goal tests，
168 PASS／2 明列 SKIP；已提供 hash-pinned 真實 Qwen tokenizer 與 pinned RE-ARC
source，沒有以 mock 取代該兩項檢查。剩餘 skips 是 CUDA 與 Landlock 在目前環境不可用，
不是模型效果證據。
獨立 review 另驗證 private candidate audit 被修改時，必須在第一次 evaluator access 前
拒絕；失敗 run 的不完整 audit 與成功 run 的完整 coverage 分開記錄。

Optional materials 固定放在 source 的 `materials/adapter-resume/` 與
`materials/curriculum/`，由 `continuation-materials.json` 與外層 source manifest
雙重 byte pin。Notebook-only 建構與參數驗證只需 stdlib；安裝完成後才對照真正 runtime
API 並作 CPU tensor／lineage readback，實際 PEFT key/config/shape 載入仍在 GPU solver
內再次檢查。Model path 與 base identity 只由成功驗證的 `prepare_model` 注入，不能由
request、tuning map 或 adapter manifest 自行指定。這些本機結果沒有 dispatch 新 run。
