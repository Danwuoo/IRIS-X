# Kaggle TPU v5e-8：工程可行性與測量計畫

日期：2026-10-18。硬體由使用者指定；本輪沒有登入 Kaggle、查配額、建立 session 或下載權重。以下區分官方規格、算術估計與本地建議。[S11-S14]

## 已核對的規格與未知項

Google TPU v5e 文件列每晶片16 GB HBM；8晶片的名目合計為128 GB。**每晶片仍是16 GB，不是一個128 GB單卡記憶體。** Kaggle staff 公告提供 v5e-8 選项；一般 docs 部分段落仍寫v3-8。本研究採較新的產品公告確認選項，但實際帳號的可用性、session限制、hostCPU/RAM及可用HBM以preflight回讀為準，不把Cloud host規格當成Kaggle保證。

粗略BF16權重下界：4B約8 GB、8B約16 GB、32B約64 GB（參數數×2 bytes，十進位GB）；不含KV cache、activations、編譯暫存、padding、runtime、optimizer或多份模型。8B完整權重已逼近單晶片名目容量，不能直接套DDP後宣稱必可用。這些是容量算術，不是速度／可訓練性實測。

## 起始模型與後端候選

先以公開 `Qwen/Qwen3-4B` 作工具與runtime校準候選 [S15]；形式化子線候選為 `Goedel-LM/Goedel-Prover-V2-8B` [S03]。兩者都未在這個TPU環境驗證，正式實驗須固定完整模型revision與tokenizer，不因本文件列出就自動下載。基準模型不是「最新最強」承諾；若formal候選無法精確轉換，先報backend不合格，不降格成模型不會證明。

Tunix公開說明提供JAX／TPU、Qwen家族及rollout整合 [S13]，可做技術候選；JAX的Mesh/Sharding描述真正的多裝置資料布局 [S14]。只有在精確checkpoint architecture、權重轉換、tokenizer、位置編碼／attention、logit parity及採樣語義核對後，才選一條stack，不同時移植三個框架。

學姊相關Pochi系統的Hopper kernels、DFlash和attention sinks不屬於這個TPU起點 [S06-S08]。不直接搬CUDA封包，不照抄8×H200的候選／上下文預算。

## 第一個真實環境任務

1. 只回報必要的jax/jaxlib/backend版本、device種類與count、每device記憶體及host可用資源；禁止dump全環境或密鑰。
2. 固定2D或1Dmesh候選并明示參數／KV布局；不得將總記憶體當成每replica可用。以短固定prompt檢查token IDs、short-prefix logits／greedy輸出對照；bitwise equality並非跨硬體必然，tolerance需在正式結果前固定且有理由。
3. 分開cold compile、warm prefill、decode、CPU Lean驗證、IO與峰值記憶體；報time-to-first-token、tokens/s、單題wall與完成率。先短context，再測8k／16k；不能從短prompt推估128k可行。
4. TPU只做模型工作；CPU做Lean／精確工具及orchestration。限制worker數，避免verifier oversubscription拖垮生成或產生重試風暴。保存可續接的候選與工具狀態，不在check失敗時無限重跑。
5. preflight通過後才鎖定M-SAMPLE／M-REPAIR的wall ceiling與小面板。在不讀答案下判斷是否可於實際session內完整交付；否則先縮小另版機制pilot，不吞掉未到達題目。

目前不給訓練時間、可達IMO／Putnam分數或成本預測。需要學習時先評估小模型LoRA／verified-trajectory SFT；教師OPD需要另外的teacher成本、API／hidden-state介面與資料授權，不因有128GB總HBM就認定可以重現大型蒸餾。
