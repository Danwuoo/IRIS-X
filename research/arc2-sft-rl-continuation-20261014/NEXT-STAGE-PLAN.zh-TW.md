# 下一階段準備：把實際上游元件接到可審查的逐軌跡續接

日期：2026-10-14 UTC。狀態：**開發計畫，尚未實作下列新 successor，也未啟動訓練**。
承接[目前進度](README.md)與[既有研究決策次序](method-landscape.zh-TW.md#七建議的實驗順序與觸發條件)，
不改選方法、不把 framework 名稱當增益證據。

## 1. 下一個有限交付

目標是讓已實際採用的 Agent Factory 3 元件具備可接續原 runtime 的**完整 batch
契約＋逐軌跡 shadow loss**接口，而不是直接把64條真實模型 graph 堆到記憶體。
新碼應使用獨立 successor 路徑與身分；原 run008、actor、math、plan、producer、
collector 與 scorer 保留原 bytes。不能 monkey-patch 原 frozen 模組或用新 identity 冒充舊版本。

目前已完成的 bridge 先驗證64個 declarations，再一次呼叫 upstream
`compute_unpacked`；它只接受 CPU replay tensors。下一階段需要解決的是這個
呼叫形狀與原模型 owner 的接點，並非再證明同一個小 tensor 公式。

來源接點：
- [原 runtime 更新流程](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/runtime.py#L396-L496)：完整 batch、逐軌跡 replay／backward、全部 admission 後才 commit。
- [原 actor identity 與 support](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/rl_session/actor.py)：原始 token、DFA、權重／cache／來源一致性。
- [目前 bridge](../../tools/arc2_agent_factory3_bridge_20261014/bridge.py)、[實際上游來源 manifest](../../tools/arc2_agent_factory3_bridge_20261014/source-manifest.json)、[CPU proof](../../tools/arc2_agent_factory3_bridge_20261014/proof.py)。

## 2. 工作順序與可驗收交付

### A. 完整 batch 的非機密接線契約

第一個真實來源接點是**已存在的 training-only audit 檔**，不是 stage0 compact report。
`TERMINAL-VALIDATION.json` 沒有原始 trajectories，不能由它反推或補造。原
[`experiment_flow/flow.py`](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/source/experiment_flow/flow.py#L220-L246)
將 `{batch, summary, update, ...}` 保存為 `experiment/audit/sweep-N.json`，其中
`update.replays[]` 保留 `log_pi`／`log_mu`／`detached_DDIS_loss`；原
[`audit_checks.py`](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer/audit_checks.py#L201-L275)
已有逐軌跡對照責任。先做明確指定檔案＋獨立來源hash的離線 audit adapter，保存原拒絕／
缺失狀態；沒有真實檔案時只交 synthetic schema 測試。

stage0 單檔上限16MiB不能直接放寬；原證據規畫的單batch audit上界約88MiB，不代表
實際檔案都如此大。先核對實際size，超限明確拒絕；若確實需要較大輸入，另審有界reader
的大小／深度／JSON／no-follow／中斷cleanup設計，不能偷偷改既有安全上限。
只使用保存的 logp 可以重算loss及 `∂loss/∂logp`，無法重建模型graph、LoRA梯度或真實replay。
這個 audit-loss companion 使用獨立 opt-in 入口；既有 stage0 prepare／analyze 保持標準
函式庫與原介面，不暗中載入 PyTorch。將來輸出僅保留不含原始tokens／grids的緊湊
batch conformance與unknown／rejection分類，對照原 recorded `detached_DDIS_loss`。
只有宣告性資料時，仍明列 provenance 未驗證；不能改名成新的 collector 成功收據。

先列出 producer 欄位→bridge 欄位→owner 核對責任的逐項映射：固定32 parents／records、
batch0–3、每批8×8完整 slots、policy identity、generation epoch、actor／cache mode、
原始 prompt/generated IDs、位置、DFA support／states、behavior logp、reward provenance。
只能以 training-owned receipt 作將來真實來源；不能從 evaluator 答案或 PUBLIC outcome
補欄位。metadata 自洽不是 provenance authentication，沒有的證據保持 missing。

交付應是獨立 adapter 契約與 fabricated 非ARC fixtures。測試覆蓋錯版本、缺／重／亂序slot、
混合 cache／prompt、fatal／stop、retokenization、source drift、未知／非法reward與 zero-signal。
不新增登入、provider 操作、檔案搜尋或秘密資料讀取功能。

### B. 使用真正 upstream loss 的逐軌跡 reduction

完整 batch 必須先通過現有結構檢查，固定 advantage 與分母 `M×8×T_i`，然後逐軌跡
計算 upstream contribution；不得對單條 trajectory 重算 group baseline／M 或當成一個新batch。
本次 upstream bytes 與 license 保留，streaming 邏輯寫在新 glue。零advantage仍保留原 replay
診斷要求，整批 M=0 則不做 replay／loss／更新。

CPU 驗收：同一64-slot synthetic batch 比較 frozen local、目前 full upstream與新streaming
scalar／原始 logits gradients／metric weighting；不同長度、mixed counts、嚴格ratio邊界、
zero groups 均需通過。normal／`-O`、失敗／timeout／cleanup、graph釋放與禁止提前commit
測試分開列出。不得以 mock 成功聲稱真實 owner rollback 或模型梯度驗證。

### C. 本地模型接線的 shadow 規格與交接

產出 source-bound、預設不執行的接線規格；在本地另行審查的 successor 上，從**同一A、
同一完整原始 training batch、相同 unchanged-policy replay**比較本地與上游的 loss／
LoRA各target梯度。不能用額外抽樣、不同tokenization或不同模型副本掩蓋差異。

shadow 計算不是免費：新增 forward／backward、hash、Python、同步、記憶體、保存及失敗
成本全部記錄。若接進正式 B，其整段額外 wall 必須由 C 匹配，且仍受原整場12h與各
operation／batch期限限制。若作另立診斷，不可把它的成本或結果移植成既有 A/B/C 的證據。

此階段目前只準備接口、非模型 CPU 測試與本地交接，不在本環境載入Qwen、執行LoRA、
建立新GPU工作、提交Kaggle或呼叫本地executor。真正模型驗收仍需接收端的來源與材料。

## 3. 從 CPU 元件到模型證據，缺的項目不能省略

| 項目 | 已有 | 本地真實接線仍須提供 |
| --- | --- | --- |
| 來源與數學 | 固定 upstream／frozen local hashes、合成loss／logit-gradient parity | successor封裝與實際執行source一致，不能沿用舊admission |
| reward／資料 | 完整slot與排除宣告檢查 | authenticated train-only lineage、原records與排除、實際reward；無PUBLIC答案流入 |
| actor與replay | 原IDs／prefix／DFA宣告／version一致性 | 同原模型與adapter、真實DFA support、teacher-forcing causal alignment與cache實證 |
| 數值 | synthetic零差、strict bounds | 原nonforced max≤.20／p95≤.05／unclipped=1，以及每個LoRA tensor finite gradient、至少一個非零；不能只看scalar loss |
| 狀態與失敗 | CPU負例與結構拒絕 | 零更新前權重不變、完整batch才commit、真實rollback、save/reload、owner終止與完整receipt |
| 資源與結果 | 小CPU fixture | 單訓練GPU的peak memory／全B wall；最終4×L4另驗；原完整A/B/C與PUBLIC120／167評分 |

以上重申既有契約，不另加與研究問題無關的管理門檻。缺一項不能改寫為0分、已驗證或放行。

## 4. 既有決策條件繼續適用

- 工程／replay失敗：先修正來源明確的問題，保留實體成本與舊證據，不當成方法失敗或換熱門方法。
- 完整batch無相對reward訊號：不補抽樣、不改parent；保留zero-signal與incomplete區別。
  若後續確需改善訊號，才按原計畫考慮train-only curriculum／verified trajectories／rejection-SFT。
- 有真實更新：先完成同session A/B/C與固定選擇。B>A但未勝同成本C，不能宣稱RL有額外價值。
- 有相對增益：依原unused-parent／family replication條件驗證；reused held32不冒稱全新確認集。
- TTT、program proposal／feedback repair、selector／多角色仍按既有獨立觸發條件，這次不混入。

## 5. 本階段準備完成的定義

文件可從根 README／research index 找到，狀態不把CPU元件與模型接線混為一談；下一次
開發可直接依 A→B→C 的有限工作項進行。實作完成後才做獨立review、normal／`-O`與
適當CPU integration，保存新SHA並逐檔readback。Git保存、CI、模型執行與method efficacy
各自報告；本計畫自身不是執行授權或成功收據。
