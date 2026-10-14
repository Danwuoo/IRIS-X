# Stage 1 離線支援：獨立審查

日期：2026-10-14 UTC。結論：**本輪有限離線實作通過獨立驗收；完整 repository aggregate 仍失敗，Stage 1 真實 A/B/C 實驗仍未完成。**
本文件保存這次審查證據；持續狀態只維護於[開發進度管理](DEVELOPMENT-PROGRESS.zh-TW.md)。

## 範圍與版本

- 比較起點：`66e54c90febd4d7f1a1e08f1f8b0e8d6c7c671ca`，以 detached local worktree 實跑 baseline。
- 文件整併檢查點：`ec9237fc607d592ac262b9881e276d23bb06de22`。本次新增程式以文末逐檔 SHA-256 綁定；本審查不冒稱尚未核對的遠端程式 commit 或 CI。
- 審查[新工具](../../tools/arc2_abc_continuation_20261014/README.md)、原 producer／actor／runtime／modern consumer、既有 AF3 bridge 與原 Stage 0 I/O。
- 原 run008、math、actor、runtime、budget、scorer、既有 bridge/vendor 與 Stage 0 程式均未修改；20 個 source pins 的實際 bytes 同時符合 manifest 與起點 Git bytes。
- 保留 SFT256 A、32 固定 training parents、最多四個互斥 64-slot B batches、全 B wall 配對 C、no-TTT、PUBLIC120 tasks／167 queries。無新方法、抽樣、分母、OPSM／entropy／async 變更。
- 未執行模型、LoRA、GPU、原 scorer、Kaggle/provider、網路或本地 executor；沒有安裝模型／訓練 dependencies，亦沒有 commit 或 push。

## 已處理的審查發現

1. 原 `ledger.py` 的 `event_id` 是非負整數，UUID 是另外的 `op_id`。最初新 adapter 誤要求字串 backward event ID；已修正為 strict int，synthetic fixture 及回歸同步修正，沒有放寬成任意字串／整數二選一。
2. Numeric nonadmission 必須保留未 dispatch optimizer、同 policy／adapter；不能把已更新或矛盾宣告當成原 numeric no-update。原 `.20/.05`、unclipped=1、30 秒、72/80 GiB、600 秒數值／時間／記憶體宣告與 derived failures 已逐項核對。這不驗證真實物理執行。
3. Saved logp 必須可由原 float32 精確表示，禁止靜默量化成另一組值。原 reward、tokens／prefix／DFA、64-slot order、版本、replay 身分、原 `log_mu` 與 recorded scalar 保留獨立檢查。
4. 每條 upstream metric 有限不保證累加有限；已加 merged-state／final guards 與 overflow regression。逐條 loss 保留完整 batch divisor，並保留 full-batch padding width，避免單條 reduction width 造成 float32 metric 差異。
5. CLI 的 exit0 只代表 report 寫出。Happy-path 測試現在要求 `CONFORMANT_SAVED_REPLAY`、完整64 replay 與 loss match；另測 exit0 寫出明確 `REJECTED`／missing report，避免錯把輸出成功當成 conformance。
6. 文件依賴聲明改為 Stage 0 仍僅標準函式庫，新 audit-loss 是獨立 opt-in dependencies；唯一進度文件保留原 no OPSM／entropy／async 與各真實模型缺項。

## 實測結果

使用既有 CPU proof venv，分別依各 package 的 documented discovery 在 fresh interpreter 執行；沒有修改 dependencies。

| Package | normal | `-O` | 結果 |
| --- | ---: | ---: | --- |
| Stage 0 | 148 | 148 | 全通過，無 skip |
| 原 AF3 bridge | 25 | 25 | 全通過，無 skip |
| 本輪 Stage 1 offline package | 60 | 60 | 全通過，無 skip |
| 合計 | 233 | 233 | 六次命令均 exit0 |

Stage 1 的60項包含25 audit、21 streaming、14 real-process CLI tests。最終 focused 驗收前後比較10個非文件 package 檔案 SHA，沒有任何變動。

命令形狀：

```sh
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 CPU_PYTHON -B -m unittest discover -s tools/PACKAGE/tests -v
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 CPU_PYTHON -B -O -m unittest discover -s tools/PACKAGE/tests -v
```

`CPU_PYTHON`／`PACKAGE` 是接收端須替換的佔位文字。實際三個 package 為 `arc2_sft_rl_continuation_20261014`、`arc2_agent_factory3_bridge_20261014`、`arc2_abc_continuation_20261014`。
測試保留 inherited environment，另加同一 workspace-backed `TMPDIR`、`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1`、`HF_DATASETS_OFFLINE=1` 與空 `CUDA_VISIBLE_DEVICES`。

額外獨立驗證：

- 使用 reviewer 自建、原生整數 event IDs 與完整順序的 fabricated actor/replay/backward/optimizer event map。實際原 producer `summarize`、consumer `summary`、64 次 `trajectory` 與 `validate_update(require_modern=True)` 全接受；修正前新 adapter 拒絕 `BACKWARD_DECLARATION`，修正後為 `CONFORMANT_SAVED_REPLAY`。這是 source-schema interoperability，不是真實 runtime 或 physical receipt。
- 實際公開 tokenizer SHA `aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4` 的25 ASCII pieces 為10 digits、單一 newline 與14個連續多 newline。原 `NativeGridConstraint.transition` 拒絕連續 newline，故 consumer 的合法 primitive support 與本次 synthetic native-shaped fixture 相容；沒有推論真實模型 tokenization 或 replay 已驗證。
- 實際 upstream/frozen/streaming loss、raw synthetic logits derivatives 與 sample-weighted metrics 對照，涵蓋 mixed counts、各 batch index、長度1–1024、strict ratio 邊界及 zero groups。M=0 不建構 torch/loss/replay；mixed batch 中零 advantage 軌跡仍檢查 replay 診斷。
- 每條 graph 釋放的 weak-reference 測試，以及 RuntimeError／TimeoutError／KeyboardInterrupt、未 finalize 的 session cleanup 通過。API 不保留64 graphs，也沒有 optimizer API；caller 自己保留 graph 或累加 gradient 仍由 caller 負責，不能宣稱真實 owner rollback。
- CLI 實際 timeout 後 SIGTERM、等待 child exit130、未發布 staging cleanup 通過。原 safe-reader 的 link/race/JSON/覆寫/中斷 tests 亦全部重跑。
- 額外以92,274,688 bytes（88 MiB）sparse audit，在 normal 與 `-O` 並停用 site packages 下實測：均 exit2、`INPUT_REJECTED`／`input_size`，未建 report；16 MiB 舊上限保持不變，未以增大上限或截斷解決。

## Paired repository aggregate：仍為 FAIL

兩次均使用 default Python、fresh interpreter、`PYTHONHASHSEED=0`、同一 workspace `TMPDIR`（開始前可用空間29 GiB）、上述三個 offline flags 與空 `CUDA_VISIBLE_DEVICES`；未使用 `env -i`。命令為 `python tools/repository_check.py --all`。

| 實跑 | Tests | Failures | Errors | Skips | 時間 |
| --- | ---: | ---: | ---: | ---: | ---: |
| exact66 baseline detached worktree | 1,583 | 2 | 35 | 74 | 143.676s |
| 本輪 final working surface | 1,583 | 2 | 35 | 74 | 149.126s |

兩次37個 failure/error IDs 的完整順序相同，74項 skip 的 reason 分組及計數亦完全相同；不是只看總數。
Root suite 不自動 discovery `tools/` 下新增 tests，故本輪233/233 focused 驗收另列，不能將其中任何一組冒充完整 suite 綠燈。

- 33個 errors 為原歷史 fixture／plan／admission `FileNotFoundError`：ABC 系列10個、E12 prefix plan 1個、native editor 1個、native export frozen review 1個、native-save-v4 20個。
- 2個 errors 為 E12 answer-evidence/runtime loader 無法 import `tests.test_nvarc_e10_paired_schedule`。
- Failure：`test_mixed_seed_parent_exports_real_tiny_cpu_evidence_in_fresh_child` 的子程序以未取得 retained native materials 的 `SkipTest` 結束；parent 將非零 exit 記為 failure。
- Failure：`test_active_repository_is_valid`。實際 placement 的原有6個 README 缺詞仍為 `Engineering Trials`、`Decision 0010`、`Decision 0012`、`Decision 0014`、`Decision 0015`、`Trial 001 status page`。
- 74 skips 為明列的 optional ML／SDK／retained source/material fixtures 缺失；未補造或移除 fixture 來造出綠燈。
- 兩次 validator self-tests 各3/3；兩次 aggregate 皆 exit1。Current diff whitespace 無新增問題；另外針對既有 exact vendor snapshot 的 no-index diff，仍重現 `metric_state.py:38: new blank line at EOF`，保留原 bytes，不與這次新差異混算。

非 acceptance 的早期嘗試亦保留：未設完整環境的初次 `--all` 以 cooperative interrupt／exit130 結束，未當 baseline；第一次把三個 package 串成 dotted-module suite，Stage 0 的 bare `test_analysis` import 造成1 error，另觀測2個新 CLI conformance failures且期間來源曾改動，原因未被完整建立。其後改用正確 discovery 與 frozen bytes，六次 fresh package runs 全通過；未將早期收據改寫成通過。

## 文件與本地 shadow 規格

原計畫的技術要求完整移入唯一進度文件，根／research／docs 與資料夾 README 僅導覽；舊 plan 與 README headings 保留相容 anchors。方法研究保留獨特科學理由，handoff/tool README 保留使用及安全限制，沒有另一份 mutable status。
最終10個變動 Markdown 檔案的144個相對連結、其中15個 heading anchors 已實測，0個問題；加入本審查後再跑實際 repository placement，仍只有上述6個既有 findings。
新工具 README 的 producer→adapter→owner mapping 與五步 local shadow 規格，要求同 A lineage、同完整 batch 與其真正 pre-update policy／owner snapshot，逐 LoRA target loss/gradient 對照、原 gates、rollback/save-reload/closure 與全 B/C 成本；明示本版 CPU-only 不是 CUDA hook，規格自身不啟動任何工作。

## 必須維持的未完成項

沒有取得或處理真實歷史 training audit，沒有 authentication、真實 Qwen/LoRA gradients、原 owner rollback、checkpoint reload、GPU memory 或全 B/C wall 實證。Saved logp leaf derivatives 不重建模型 graph；source／hash／schema 自洽不授予 admission。Stage 1 真實 A/B/C、sealed 原 scorer 的 PUBLIC120/167 與方法效益仍待接收端完成。Git 保存及後續精確 CI 結果另由唯一進度頁紀錄。

## Reviewed source fingerprints

下列為最終驗收所用 bytes；文件後續若更新狀態，不應改寫這些已驗證來源身分。

| File | SHA-256 |
| --- | --- |
| `tools/arc2_abc_continuation_20261014/__init__.py` | `425868b4af2ddae939ca523643e54eff175e222636b89d2d6f61b5e51c90dc7c` |
| `tools/arc2_abc_continuation_20261014/audit-source-pins.json` | `015e2549da2ab445b30273fa62e106d98510b26c2f130866eae393418531b8cd` |
| `tools/arc2_abc_continuation_20261014/audit.py` | `fb7ede3a20f4921842f637f6cd32465a22ecfe61b0ffa7bbe9c4bb8627c825d0` |
| `tools/arc2_abc_continuation_20261014/cli.py` | `c41bccf7a36920a55bddd0e682798be1243aa9d7fec5633e683f930af647419d` |
| `tools/arc2_abc_continuation_20261014/fixtures.py` | `f707e81c49097bcfce07c97d1898306267c6bb6cf79009ef66eb52f49c3af8a2` |
| `tools/arc2_abc_continuation_20261014/streaming.py` | `4c7ea1d1c00f13329a7cd2491880b269e02d04cd169336aa3926751626328b81` |
| `tools/arc2_abc_continuation_20261014/tests/__init__.py` | `d6711964bc9316f2766b5b7f52a73a7f0b75f2c30666a2f7bb0ca823c8e9cb60` |
| `tools/arc2_abc_continuation_20261014/tests/test_audit.py` | `02f05f0008904134b50683b9dcd07c9674935c3140a653e3f498f94fa151a828` |
| `tools/arc2_abc_continuation_20261014/tests/test_cli.py` | `0cb8a4c7c75432bb873debff2beb2b9eed8cf049361b81c56c76a72f84611bd3` |
| `tools/arc2_abc_continuation_20261014/tests/test_streaming.py` | `feb633b150407208eaeb2b4763a6014ce14d9052d7b1cf8772195be6f58328be` |
| `tools/arc2_abc_continuation_20261014/README.md` | `d90466814d6aba278ed2ebbb238376e5e1465cc1f959f4e19369345225f305ad` |

原 source pins manifest 核對20個檔案；每個原檔均與起點相同。以下 log digests 綁定本地驗證收據，不將 raw logs 或私人路徑發布到 Git：

| Validation receipt | SHA-256 |
| --- | --- |
| `baseline-all.log` | `8da04fc1443f597e7d3dd09509602099163a7424d02abe99953271179fc81efd` |
| `final-all.log` | `84949d8e0764166fed600005f402b1c6a1835d2523ef5b52e89235717711e6dd` |
| `arc2_sft_rl_continuation_20261014-normal.log` | `f02d5ae596fa347a1fdcabdb37e164a7031bae7dfc3e382401c6f78a81035f3c` |
| `arc2_sft_rl_continuation_20261014-optimized.log` | `c71a7b9096816b1f7f6957fd3b00a22d26b2ed4635cedbc3e6e3a90e93e19c43` |
| `arc2_agent_factory3_bridge_20261014-normal.log` | `73955aa647572f699f452c31cf18f31da0e2405aa037f3c7d6122728693d069e` |
| `arc2_agent_factory3_bridge_20261014-optimized.log` | `5dd0270c9316e5fd8471a133a9294d02cf3ccf2a1328b47c233e239a4eeabb63` |
| `arc2_abc_continuation_20261014-normal.log` | `34fdfba72fa0f128b732ea3d1629a2daeefade1ac3f7c54ce8d429f76e4a9658` |
| `arc2_abc_continuation_20261014-optimized.log` | `51e67e0307bbba898d59456b10fcdebcd3413262721c46c57cb1612535fc8b5d` |
| `source-interop-fixed.log` | `1c04801174b153c84f64529d16426a4dcb016650eaf19aaa133f5bd2abb7315d` |
| `88MiB-safe-rejection.json` | `ad1602e02ab1c416266e021a8a0fe2544e6c003347e4cabf3bb857a86eed055e` |
