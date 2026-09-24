# Qwen3.5-4B compact 小型完整流程開發

日期：2026-09-24。狀態：Decision 0026 已授權並執行一次；[終止紀錄](../../trials/arc-agi-2-qwen35-nvarc/compact-complete-001.md)顯示在模型載入前因 Dataset 清單不符而失敗。一次提交及一次取回均已消耗。

## 範圍與材料

獨立身份 `nvarc-4b-compact-complete-001`。重用私有 Dataset v2 的 pinned
Qwen/Qwen3.5-4B revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`、
base-model 與 wheel manifest。新流程按順序驗證 base 全量 inventory、選出
16 個 native tokenizer rows、保存與 reload compact artifact，再對兩個小型合成
task 作題內 LoRA 適應、真實 compact model 生成、inverse/dedupe/likelihood
ranking、checkpoint/result.zip 封裝與獨立回讀。合成 truth 只在本機 evaluator。
正式 NVARC rank 256 / 8192 token 設定仍是未驗證的另一個配置；本 pilot 的
rank、steps、tokens 和 sequence ceiling 必須另列且由 binding 驗證。

## 重用與接線

* `arc_nvarc_representation`：`verify_source_model_material`、`vocabulary_manifest`、
  `select_rows`、`convert_qwen35_checkpoint`、`verify_model_material`；修正轉換時
  不必要的整份 embedding/head clone。
* `arc_nvarc_training`：`TaskLocalAdapter`、`task_local_sequences`、`collate`、
  `load_compact_model`；補每步 loss、grad、adapter finite 檢查與 reset 證據。
* `arc_nvarc_candidates`：`solve_task`、`QwenCandidateBackend`、bounded DFS、
  full-grid EOS parse、inverse、canonical dedupe 與 likelihood rerank。
* `arc_nvarc_runtime`：同一份 checked-in config schema、binding、reservation、
  checkpoint、outbound/result verifier。單卡 pilot 以明確 `worker_count: 1`
  綁定；既有四卡 run 的 binding 不變。
* `arc_nvarc_kaggle` 與 pilot 004 staging：重用硬體與 official mount 診斷、
  私有 Internet-off metadata、離線 wheel preflight、`torchao` 相容性處理；
  不修改 pilot 004 已執行 notebook、wheel、manifest 或結果。

## 驗收

CPU：checked-in config 建 outbound 並驗證；注入 NaN/Inf loss、grad、adapter
時拒絕且 reset；tiny **真實 Qwen3.5** conversion/reload、兩 task 多 test
適應、model forward/生成、結果回讀；缺有效候選須真實記 missing。

GPU 待執行：exact base/wheel hash、official competition mount presence、L4 UUID
與顯存、dependency preflight；真實 4B compact 保存/reload；短 LoRA 每步
finite/group 記錄與跨 task reset；至少一個真實完整 grid，否則標 partial；
每 test 呼叫/sequence/DFS/verification、phase wall/peak VRAM、停止原因、
truth-free checkpoint/result.zip 均可核對。GPU 枚舉不算多卡使用。

## 外部上限與中止

開發與本機測試不觸發新 provider mutation。新執行提案固定 private、
Internet-disabled、USD 0 paid，沿用官方競賽 mount 僅驗證存在，不讀題庫；
一個 kernel version、一個 terminal output retrieval，模型失敗不重跑；
pre-version transport rejection 最多一次同 bytes、同身份重送，先檢查
auth freshness、owner kernel version 並記錄 API 結果。已接受版本不重送。
已固定的上限是：單 L4 使用、兩 task／四 test、每 task 900 秒、整體
2,400 秒（其中 300 秒留給收尾）、worker 2,100 秒；總共至多兩個 LoRA
step／128 training tokens、四次 generation、八條返回序列、64 次 DFS
forward、八個獨特候選 verification（至多 64 次 forward）。設定為
rank 2、每 task 一步、單序列至多 64 tokens、每 test 一次 call、每 call
至多兩條 sequence、每次 DFS 至多 16 expansions、輸出至多 8 tokens。
只保存私有 truth-free package、checkpoint、result 和診斷至 owner review；
新 compact model 可能約 8–9 GB，單次 retrieval 的實際體積需審核。
沒有有效候選不補 truth、不延長預算。
