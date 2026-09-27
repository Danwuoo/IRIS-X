# NVARC combined notebook 本地修復

日期：2026-09-27
狀態：本地實作完成；combined-003 是 inert 候選，未授權外部執行。

## 目標與依據

Owner 指示交由新的 `gpt-6-sol / xhigh` task 完成修復、回歸驗證及可審查套件。
本次沿用 main 上的本地開發，依據
[Editor 診斷](../../trials/arc-agi-2-qwen35-nvarc/combined-002-editor-diagnosis.md)
與[既有 combined 設計](2026-09-26-nvarc-combined-two-gpu-notebook.md)。
這不是 Kaggle 執行授權；不沿用已消耗的 Decision 0036。

保留 submitted 001/002、原始 draft、receipt、runtime wheel、Editor ZIP 與證據。
不查詢背景 version 1、不更新 Dataset、不呼叫模型、不做 ARC scoring 或監控。

## 已實作的候選設計

### M2：診斷先於方法變更

維持同一 export、source representation、demonstration-only TTT、四次生成、
64 new tokens、128 DFS expansions、累積機率門檻 0.2 與原 ranking。
不對 grammar 遮罩後的機率重新正規化，不增加呼叫或訓練。

- 每次 search 留一份 16-symbol root log-probability snapshot、合法 root token、
  最高機率 token 是否被遮罩、合法／非 grid symbol 機率量、門檻通過者及 enqueue 數。
- 固定大小計數區分 grammar、累積 score、token cap；另留 suffix 深度、
  expansion/deadline stop reason、query 長度及四個 role-tail IDs。
- generation 返回後立即將診斷寫入既有 call ledger；後續呼叫失敗仍保留前次診斷。
- 區分 backend 沒有回傳候選與回傳候選缺 EOS／grid parse 失敗。
- compact DFS 對非 16-symbol logits 明確拒絕；不改合法搜尋路徑的剪枝順序。

Editor 四次 `expansions=1`，在 64-token cap 下皆無候選，與已綁定 DFS 一起
可推論所有合法 root digit 機率都未越過 0.2。缺少逐 token 證據，仍不能判定
最高機率 token、representation 的實際影響或訓練不足的程度。source differential
與 tiny Qwen 檢查只支持實作／token-ID 相容性，不證明真實 4B 品質改善。

### M3：新方法候選，保留完整性 gate

新 profile `qwen-direct-permutation-v2` 明確替代 free-form mix 設計；不是
原提示 parity，也不是已驗證的模型修復。

1. 將同一兩個 public parents 的 demo 正規化成 `train_demos` 與
   `second_train_demos`，由同一 summary call 用相同 JSON schema 分別描述。
   不增加第二次 summary，也不把原始第二組 JSON 與第一組 prose 混用。
2. summary 限定兩個 `input_shape`／簡短 `rule` 物件；保留 5×1 與 3×3 的
   已知 public demonstration shapes。
3. mix 限定 3×3 row-major permutation JSON：將第一個 puzzle 的 boundary-pair
   swap generalize 到九格，再套用第二個 puzzle 的 180-degree rotation。
   僅輸出 `shape` 與九個唯一的 `output_from_input` indices。
   此限制是明確的提示／方法設計調整，縮小自由設計空間。
4. input/output code stages 使用已解析的同一 spec；保留原 Python/numpy
   signature、完整 EOS、禁止 thinking markers、完整 Python AST 及後續隔離
   sandbox／SDG pair filter。JSON 結構通過不等於 accepted SDG pair。

四階段 greedy call、thinking disabled、無 retry、各 stage 原 input/output caps
4096/512、4096/1024、4096/3072、8192/3072，以及 28,160 reserved-token ceiling
全部不變。未用增加 token budget 取代修復。

### Notebook 與交付

新 identity `nvarc-m2-m3-combined-003`，child identities 各以 `-m2`／`-m3` 結尾。
`approved=false`、`owner_decision=null`、外部 allowances 全部為零，metadata 使用
`DRAFT-DO-NOT-PUSH` ID。notebook 在 payload/plan 核對後、shared setup 前明確拒絕，
packaged parent/worker guard 亦拒絕此 plan，沒有自行 activation 的入口。

保留 shared offline setup、兩個不同 L4 worker、UUID mapping、分支隔離、
1800 秒總上限、300 秒 setup/readiness、30 秒 terminal reserve 與 process cleanup。
候選 completion error 同時顯示每個 branch 的 phase／具體原因；M2 零候選仍標示
missing-candidate，runtime complete 不冒充可用答案。M3 partial stage ledger
保留被拒絕的 stage，不丟失 M2 已完成的證據。

## 檢查與限制

必跑 offline repository check、新增診斷/schema/guard 回歸、retained Editor replay、
source token/DFS differential、tiny real Qwen、deterministic package rebuild、
實際 wheel guard、十二個 generated hardware fixtures，以及既有 namespace control。
目前 namespace 無 NumPy；直接 NumPy fixture 被拒絕，另用獨立 authored pure-Python
語義 control 檢查 shape、seed variation 與 permutation。未安裝套件或放寬 sandbox。

新提示能否完成 EOS、新 spec 能否經真實 code generation 與 SDG acceptance、
M2 root logits／候選改善及真實兩卡 runtime 都待新的 owner-directed GPU 證據。
完成狀態、exact package bindings 與命令見
[本地修復交付紀錄](../../trials/arc-agi-2-qwen35-nvarc/combined-notebook-003-local-repair.md)。
