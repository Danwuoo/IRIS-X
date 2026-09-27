# Combined 003 本地修復交付

日期：2026-09-27
狀態：本地修復、離線驗證及 inert 套件完成；repository check PASS。
開發基底：main `7f74c8b7159fad034dacaf2bf91d6ebeabd35591`。

Owner 要求新的 `gpt-6-sol / xhigh` task 實作修復。
[設計與差異](../../docs/plan/2026-09-27-nvarc-combined-local-repair.md)已具體實作；
本次未取得外部執行權限。combined 001/002 的 submission、Editor 觀察與
背景版本仍是不同 evidence；背景 combined 002 保持未查詢。

## 已修內容與證據

**M2**：新增固定大小 root logits／grammar／cumulative-score／token-limit
診斷，在每次 generation 完成時寫入 call ledger，並區分沒回傳候選、缺 EOS、
grid parse failure。非 16-symbol logits 不再被 compact DFS 接受。
新候選的 semantic counters 顯示 `missing-candidate`，不將 runtime complete
當成可用答案。原 source representation、token IDs、0.2 門檻、DFS 順序、
TTT／生成／ranking budgets 都不變，沒有遮罩後機率重正規化。

原 ZIP／所有 extracted member hash、M2 semantic verifier／terminal envelope
與 M3 dependent partial ledgers 重播均一致。M2 四次只展開 root，64-token cap
未達且零候選；配合原始綁定 DFS，可推論所有合法起始 digit 都未越過 0.2。
仍缺 root logits，不能宣稱已找到特定最高機率 symbol 或證明模型品質改善。
source differential 核對 role/newline/EOS／native ID、adaptation masks 與
DFS traversal/pruning，沒有找到這些路徑的新增 representation 錯配。

**M3**：`qwen-direct-permutation-v2` 是新的方法／prompt 候選。
同一 summary call 用相同 JSON schema 描述兩個 public parents，再用短 mix
spec 定義 3×3 的九個唯一 row-major source indices。下游兩個 code stages
使用同一 parsed spec。這縮小了原 free-form puzzle 設計空間；mix 明確指定
boundary-pair swap 後接 180-degree rotation，不能當作原提示 parity。

EOS／thinking-marker／完整 AST／sandbox／SDG acceptance gate 與原四階段
token ceiling 均保留。原始 length reply 在舊、新 profile 都仍因缺 EOS 拒絕；
即便做反事實 EOS 標記，舊回覆也不符合新 JSON schema。七格、重複 index、
boolean index、重複 JSON key、未知欄位、未閉合 JSON 均有拒絕回歸。
四階段成功 replay 使用明確標示的人工 fixture，沒有新的 teacher reply 或
accepted SDG pair；無法據此聲稱新 profile 會在 Qwen3.5-4B 上完成。

**Combined**：保留兩個獨立 L4 worker、shared setup、UUID binding、分支隔離、
原 wall/cleanup budgets。錯誤摘要具體顯示 branch、phase、stage、原因與
M2 ranked-candidate 數，保留正確 partial outcome 和已完成分支證據。
新 profile 禁止套用已消耗的 standalone Decision 0033/0034 identity，
並有在 ML import 前拒絕的回歸。

## 最終待審查材料

套件目錄：
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-candidate-003-reviewed/`

單檔 notebook：該目錄的 `kernel/kaggle-notebook.ipynb`。
完整 ZIP：
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-candidate-003-reviewed.zip`。
ZIP 已逐 member 核對，含 16 個檔案；stage inventory 綁定 15 個 member 加 summary。
metadata、source bundle、runtime wheel、prompt、seed、model/dependency manifests
均包含在套件；既有 7.8 GB export 與 full-vocabulary model 保持 reference／mount。

[候選 plan](configs/m2-m3-combined-candidate-003.json) 使用新 identity
`nvarc-m2-m3-combined-003`，`approved=false`、`owner_decision=null`，所有 external
allowances 都是零。notebook 無條件在 shared setup 前拒絕；packaged parent／worker
亦拒絕原 plan 及冒用 Decision 0036 的變體。不可直接 push 或 Editor rerun，
未提交、未監控、未 retrieve、未更新 Dataset，USD 0，零新增真實 4B generations。

Plan canonical digest：
`sha256:907dee6ecf5cfe043be5953ba90afb7524e5ee5ad5074b6d3d24e94170741cb8`。

| 檔案 | SHA-256 |
| --- | --- |
| Plan bytes | `656542eba546e9861b2687e151e65d92928a598f32b7ce30dbc2a40cf4d9963a` |
| Notebook | `d40f8bc823e7f89b138cf9fd095f2cc864bb81a5b2c736baddd55352ce90802c` |
| Metadata | `3630ab772b8400f1e0cce844fda1d811f40a61622f4cb4094269a9072145ccb2` |
| Runtime wheel | `b11744ece5b4be6233d59a4e46c01c59508fdf38d1d3e9c2a793cc88e4ff172c` |
| Prompts | `88f11658e35639803e7f38799b2f496108ccc3fe6abb7a6a6753b88231c0cc67` |
| Paired public seed | `46c5a9deddadf9cdc101145324e2e5d613d7744db1a1373e9a5cecc0465a8861` |
| Stage summary | `fa6bbe168ca390a703379e0d052abd467f1887ebfda9cf026b2933e8eaf64bd7` |
| Final preflight | `9d1a595938fa53fa552a9ef2b8a1c91e3581b3c536fb8df4e15eaef900a112bc` |
| Complete ZIP | `c413d6b4813c16b9536e29b8c91adb08e3872f67da4b9ef9d0fb3d62e85b81a1` |

相鄰 `combined-candidate-003-reviewed-preflight.json` 驗證 closed inventory、
exact template／embedded bytes、wheel 每個 module 對應最終 source、export ancestry、
cached tokenizer 與十二個 generated hardware fixtures；actual CUDA acceptance 仍 pending。
`combined-003-freeze-verification.json` 確認 96 份舊 package/draft/template/Editor
檔案沒有改動，並重新核對 001/002 push receipt 的已記錄 SHA-256。

## 離線檢查

- `python tools/repository_check.py --all`：254 項 PASS，4 項既有 optional skips；log
  `.irisx/nvarc-combined-003-repository-handoff.txt`。
- 新舊 combined strict suites：8 項 PASS，包括 tiny real Qwen 的 root logits
  與獨立 unmasked forward 相等、沒有額外 forward、package deterministic rebuild、
  actual wheel parent/worker guard、template tampering 拒絕及舊 approved/draft 相容性。
  log `.irisx/nvarc-combined-003-strict.txt`。
- 最新 standalone-profile guard 及 continuation 聚焦回歸：17 項 PASS。
  最終 wheel 的獨立 cached-package strict check一項 PASS，另留
  `.irisx/nvarc-combined-003-final-wheel-strict.txt`。
- source differential 三項 PASS：role/EOS/native IDs、source DFS traversal/pruning、
  source task-adaptation views/masks。
- digest-bound Editor replay、四階段人工 fixture 與 cached tokenizer：
  `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-003-repair-replay-final/report.json`。
  Fixture input tokens 為 321／251／155／185，皆在原 stage caps 內；這不是
  未知真實 model output 的 token／EOS 完成證據。

本地 WSL namespace 未安裝 NumPy。實際 NumPy fixture 的隔離呼叫回報
`ModuleNotFoundError: No module named 'numpy'`，因此未聲稱該生成碼在本地 sandbox
通過。獨立 authored pure-Python 語義 control 在同一 namespace 驗證三個 seed
的 shape／variation／九格 permutation，並拒絕七格程式。未替換 NumPy import、
未安裝套件、未在 host 執行 generated code，也未放寬 SDG acceptance。

## 重建命令與剩餘驗證

在 repository root，使用未存在的新 `.irisx/` output 目錄：

```powershell
.irisx/nvarc-ml-venv/Scripts/python.exe tools/stage_nvarc_combined_candidate.py --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-003-new-review
.irisx/nvarc-ml-venv/Scripts/python.exe tools/stage_nvarc_combined_candidate.py --preflight .irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-003-new-review
.irisx/nvarc-ml-venv/Scripts/python.exe tools/replay_nvarc_combined_repair.py --output .irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-003-new-replay --tokenizer
```

仍待真實 GPU 驗證：M2 root distribution 與可用候選、新 M3 summary/mix 的 EOS
完成率、真實 code stages 與 NumPy sandbox／SDG filter、兩卡完整 runtime。
這些都沒有被本地 fixture 或 submission acceptance 取代，亦沒有新的執行許可。
