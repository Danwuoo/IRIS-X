# IRIS X 下一條 ARC AGI 2 技術線的架構與可驗證實驗

研究日期：2026 年 10 月 8 日。現有程式與歷史證據基準：IRIS-X commit `7ac9cca0795e8d8f98f1e2cdb7bcb546fbe30b67`。這份文件區分已實作的 CPU 原型、建議的人工執行實驗，以及尚未取得的 GPU／ARC 品質證據。

## 結論

值得優先驗證的不是把幾套 agent 框架全部接起來，而是保留 8–9B 模型的完整程式與文字能力，讓它提出可執行假設，以 demonstrations 的實際執行差異修正假設，再用預先固定的選擇規則產生兩個答案。第一個 notebook 應同時包含 direct-grid、open-loop program、feedback-repair 三個等額上限實驗臂。

本次已建立可在 CPU 檢查的最小系統：`tools/arc_next_agent.py` 與 `tests/test_arc_next_agent.py`。它使用手寫 AST interpreter，不會對模型文字呼叫 Python `eval`、`exec` 或 `compile`。程式可使用迴圈、條件、索引、helper functions 與純 grid 工具，避免沿用 E20 固定宏組合的狹窄表達空間。但這仍然是有偏好的受限語言，不是任意 Python，也不是已證明能解完整 ARC 的系統。

現在沒有足以預測「8–9B + agent 就能達到官方 >85」的證據。架構可能提高候選品質、修復率與每秒有效搜尋，也可能因上下文與修復成本而輸給單純多採樣。必須由同模型、同資料、同預算的結果决定。

## 一 名稱與實際角色

| 使用者指定名稱 | 精確對應 | 值得採用的部分 | 第一版不應混入的假設 |
| --- | --- | --- | --- |
| NeMo | NVIDIA NeMo 是產品家族；訓練應具體指 NeMo RL／其 training backend，agent 觀測則是 NeMo Agent Toolkit | 訓練 artifact 契約、packing／LoRA 後端選項，以及 call／token／latency profiling | 安裝 NeMo 不會自動帶來 ARC 推理提升；NeMo RL 與 NAT 不是同一個演算法 |
| nvidia avo | Agentic Variation Operators | 保留候選 lineage、執行回饋、遇到停滯時換假設 | 大型模型的 ARC-AGI-3 公開集結果不可直接外推到 ARC-AGI-2 或 8B |
| duck harness | Tufa Labs 的 `Tufalabs/duck-harness` | 簡單工具介面、grid 狀態外置、短上下文、完整 run artifacts | 原作使用 Qwen3.6-27B FP8；不是 8–9B 成功證據 |
| Jev | TypeSafe AI 的 System One 決策模型 | 將動作選擇與生成分開、固定型別、保留不確定性 | 本次未核實可離線使用的官方 Jev 權重；不能把 hosted API 納入 offline submission |
| prime agent | `PrimeIntellect-ai/prime-agent`，不是同名 PRIME 記憶論文 | task-local state、工具化計算、可追溯的歷史與重啟 | 不要一開始加入 recursive swarm、跨題自我改寫、無界 persistent memory |

NeMo RL 官方提供 single-GPU SFT 路徑，以及 GRPO／DPO 等後訓練流程；支援存在不等於特定 9B checkpoint 已在這張 GPU 上驗證。NAT 的 profiler 記錄各次模型與工具呼叫、tokens、latency、瓶頸，適合當觀測介面參考，不必成為提交 notebook 的重依賴。[NeMo RL](https://github.com/NVIDIA-NeMo/RL)、[NAT profiler](https://docs.nvidia.com/nemo/agent-toolkit/latest/improve-workflows/profiler.html)

Jev 官方介面為 Choice、Score、Noul 三種輸出。型別正確只限制答案格式，不能保證判斷正確。ARC demonstrations 的 exact-match 應直接用程式計算，不應花另一個模型來猜。需要 learned router 時，也必須使用離線可部署模型，另外校準 false accept 與成本。[Jev 官方文件](https://docs.typesafe.ai/introduction)、[TypeSafe 原始介紹](https://typesafe.ai/blog/introducing-system-one-models-and-jev)

## 二 直接 ARC AGI 2 證據與不能混用的成績

| 證據 | 原始觀察 | 能支持什麼 | 限制 |
| --- | --- | --- | --- |
| Qwen3.5-4B + LLM-seeded genetic search | 公開 evaluation 前 60 題，LLM seed pool 2/60，加入 GA 後 6/60；9 個 demonstration-perfect 程式只有 6 個 test 正確 | 小模型提出起點、機器執行與搜尋改善候選，值得做受控實驗 | 非等算力比較；random-seed control 在開發中改變；不是官方 hidden score |
| Arcgentica | Opus 4.6 公開 120 題由 79.03%／$3.81 提高到 85.28%／$6.94，每題兩次嘗試 | 真實 ARC-AGI-2 的 REPL／程式代理可以有實質提升 | Frontier API 模型、花費增加；不是 L4 offline，也沒有隔離 recursive delegation 的單獨因果效應 |
| CoreThink compositional reasoner | 公開集 24.4%；ensemble selector 30.8%；同主模型 ablation 的 hints-only 20.5%，greedy baseline 15.0% | 結構化提示、不同來源候選互補值得測量 | 實作同時用 Grok-4、o4-mini、Claude；論文中的精確符號交集是理想化描述，實際有提示共識近似 |
| ARCANA | 論文自報 48M 模型 semi-private 32.5%，反思移除後公開 ablation 下降 | 可作架構構想來源 | 本次未核實可重現權重、完整執行包或官方 receipt；表中 NVARC 660M 與原始 4B 系統描述不一致，不作採用主依據 |

來源：[Qwen3.5-4B 與 GA 論文](https://arxiv.org/html/2609.27242v1)、[Arcgentica 原始報告](https://www.symbolica.ai/blog/arcgentica)、[Compositional Neuro-Symbolic Reasoning](https://arxiv.org/html/2604.02434v1)、[ARCANA](https://arxiv.org/html/2607.09059v1)。這些文獻的資料切分、metric 與計算條件不相同，不應把表中的數字當排行榜排序。

### 跨領域可借鏡但不是 ARC AGI 2 的證據

AVO 在 ARC-AGI-3 的 25 個 public environments 得到 100 RHAE，使用 Claude Opus 5。NVIDIA 也明說，30% baseline 對 100% 系統結果不是 controlled ablation；VISTA 比較同時改變 backend、observation、memory 等因素。可借鏡的是 execution feedback 與 lineage，不是把 70 個百分點視為架構加成。[NVIDIA AVO](https://developer.nvidia.com/blog/nvidia-avo-reaches-100-on-arc-agi-3-demonstrating-a-frontier-level-general-purpose-architecture-for-long-horizon-autonomous-agents/)

Duck 的 Qwen3.6-27B FP8 在 25 個 public games、每題 20 次的 mean score 是 1.6002 ± 0.4475；它把狀態放進 Python REPL，以 image 與 text 觀測並移除舊訊息。其模型能力限制與成本觀察更值得重視，不能因為「Milestone winner」就推論小模型已解決 ARC 推理。[Tufa 原始報告](https://tufalabs.ai/research/duck-harness/)、[Duck 原始程式](https://github.com/Tufalabs/duck-harness)

Prime Agent 的 ARC-AGI-3 95.5% 對 30% 使用外部官方基準作參照，作者表示自己的 native-harness rerun 未重現官方成績，不能隔離 harness 效果。另一些 fixed-budget kernel／nanoGPT 實驗沒有大幅勝出；Factorio trace 甚至把規格漏洞保留成 reusable skill。這支持受控 memory 與 verifier isolation，而非無條件 self-improvement。[Prime Agent 論文](https://arxiv.org/html/2608.23552v1)

SOAR 是較接近本案的訓練參考：在 ARC-AGI-1，Qwen2.5-Coder-7B 经多輪搜尋、樣本與修復訓練、test-time adaptation，由 14.25% 到 36.25%；不是 ARC-AGI-2。它使用單 H100 的 LoRA／QLoRA，但搜尋量與多模型資料累積不能忽略。可借用 trajectory 格式及 train-time refinement，不宜直接複製其完整成本。[SOAR 原始論文](https://arxiv.org/html/2507.14172v1)

REFLEX with Jev 是一般工具控制研究，其 held-out simulator 95% success、較少強模型呼叫不等於 ARC 規則歸納效果。多模型與外部驗證的比較存在不確定性；因此路由器優先級低於直接執行與候選覆蓋。[REFLEX](https://arxiv.org/html/2609.26532v1)

## 三 現有專案證據如何改變下一版

| 現有來源或觀察 | 已知問題 | 下一版決策 |
| --- | --- | --- |
| `research/stage4-e20/DEV_SCREEN_001.json` | 24 tasks／35 tests；0 candidate vectors，17 wall-limit，7 completed | 不把原 1,120 macros、深度 3 的列舉器直接放大；改由完整語言模型提出具條件與迴圈的程式 |
| `research/stage4-e20/README.md` | E20 closed grammar、background heuristic 與 render 規則會限制可表达假設 | 新解譯器提供像素／物件與 generic composition；工具 grammar 仍是限制，需記錄 unsupported-syntax 與工具缺口 |
| `src/irisx/arc_nvarc_representation.py` 與 Qwen3 compact 檢查 | `vocab_size=16`，只保留 grid symbols | 新 agent 必須保留原始 tokenizer、embedding、LM head；不能把 compact checkpoint 當 code proposer |
| `research/stage4-arc-agi-2-research.json` | 歷史 BASE 5/172、TTT128 10/172；來源 variant 不同於官方 120/167 | 新 split 明確來源／task／test 數；這些歷史數據只作診斷，不當新 baseline |
| 同一歷史 aggregate | 大量 empty pools，ranking miss 各只有 1 | 先提高合法輸出與 pool coverage，再研究 learned selector；避免先投資昂貴 judge |
| `src/irisx/arc_candidates_neutral.py` | 已隔離 symbolic provenance 與 native likelihood | 保留 evidence type；demo fit 絕不改名為 native eight-view verification |
| E12／E13 retained result 與 telemetry failure | completion、artifact retention 與品質是分開的問題 | 每次呼叫、預算、失敗及 artifact 都留存；log byte cap 不能讓完成的實驗無結果 |
| archive source registry | Prime Agent／NAT／Verifiers 有 local tree fingerprints，但 upstream revision 多為 Unknown | 作設計參考；要正式依賴則重新固定官方 commit／license／依賴，不宣稱歷史 snapshot 就是最新版 |

此表只把舊資料當證據，沒有恢復歷史執行授權。舊 checkpoint 的 pretraining／SFT exposure 未因此解決。

## 四 第一個 notebook 的實驗契約

### 先校準，再決定是否擴大

目前材料流程的第一階段很小：固定 upstream `f3283f727488ad98fe575ea6a5ac981e4a188e49`，先對完整 1,000 個 public-training task IDs 排序，再讀選中內容。排序 key 為 SHA-256(`irisx-arc-next-training-groups-v1` + task_id)。索引 0..799 是 training 區，800..999 是 development 區；首輪取前 32 個 training tasks 和 development 區前 4 題。

Development 的最後一個 demonstration 變成 held-out query，其 output 只寫到獨立 evaluator 檔；solver 只看其他 demonstrations 和 query input。官方 public-evaluation、先前 locked confirmation，以及 hidden truth 都不進此 notebook。這是「未參與本次訓練的 public-training task、留一個示範」校準，不是正式 ARC-AGI-2 evaluation，也不是 pretraining-clean 證明。

四題只能排除流程不通、context、記憶體、格式與明顯修復問題。不能用一兩題的勝負宣稱架構較好。若人工校準完成，下一個獨立凍結實驗可把相同 development pool 擴到 32 tasks、每臂兩個 seeds，仍不碰官方 confirmation。所有 augmentation、synthetic descendant 與同來源 task 都跟著原 task split，不能跨邊界；若加入新 generator，按 generator family 再分組。

### A B C 固定權重比較

| Arm | 模型行為 | 機器驗證 | 下一次呼叫 |
| --- | --- | --- | --- |
| A `grid` | 輸出完整 ordered test grid vector | 格式與尺寸合法性；沒有虛構 demo-fit 證據 | 重新獨立採樣 |
| B `program` | 輸出 `transform(grid)` 程式 | 對每個 demonstration fresh execution；全部 exact-fit 才執行 test inputs | 重新獨立提案，不能看到驗證回饋 |
| C `repair` | 與 B 相同程式格式與模型 | 相同 executor | 失敗時讀取 shape／mismatch／runtime error，修復；成功時重新提案以尋找不同答案 |

三臂的模型 revision、adapter、精度、chat template、sampling 設定、資料與 seed 對齊；每題輪替 arm order，避免永遠先暖機 A。模型 ID 不能在同一實驗臂中偷偷更換。

第一輪目前工作流上限：每臂 4 calls、generated tokens 合計 4,096、prompt tokens 合計 32,768、每 call 最多 1,024 new tokens、每臂 120 秒；全部 notebook 1,800 秒。這些是可比較的共同「上限」，不是實際相同 tokens 或 FLOPs。修復用更多 prefill，可能更早耗盡 prompt budget，這正是成本之一。結果同時列實際 input/output tokens、model calls、CPU interpreter gas、wall time、peak VRAM。Context 超出即拒絕或縮小剩餘 generation allowance，不截掉 demonstration。

生成前用同一 tokenizer／template 計數；返回後用實際 input IDs 與 completion IDs 核對。Parse error、無效程式及晚到答案照樣收取模型成本。若 callback exception 無法取得使用量，標記 unknown usage 並停止，不把它記為免費。所有候選與結果先凍結，再由不被 solver 匯入的 evaluator 評分。

### 選擇與真正的 LODO

第一版用 whole-task output vector 去重、同向量投票、首次 call 作 tie-break；每個 test 回傳最多兩個不同完整 grid。沒有答案時回傳空 attempts，提交格式補位由另外的 exporter 處理；補位不能計作 solver coverage。避免 cell-wise 混合不同假設後生成從未被候選程式產生的 grid。

`all_demonstrations_exact` 只代表已看到的示範全對。第一版 `lodo_status=not_run`。真正 leave-one-demo-out 必須從提示、記憶、程式選擇與回饋中移除該 output，重新產生／選擇程式，再評其預測；把看過全部 demonstrations 的程式跑回去不是 LODO。若加入 D 臂，所有 fold generation／prefill／execution 都計入同一 budget。LODO 衡量 procedure，仍不能保證 test generalization。

## 五 實作邊界與驗證

`execute_program(source, grid, limits)` 只接收單一 input，複製後執行，傳回 output 与 interpreter steps。候選不能取得整個 task、evaluator、檔案系統、network、Python host objects 或其他題的狀態。原始 task／答案文字也不傳給 transform 函式。

語言支援 integer／bool／None、list／tuple、索引與 slice、算術、比較、條件、for、list comprehension、helper functions；工具有 `copy_grid`、`new_grid`、`transpose`、`crop`、`components` 及少量 list／integer primitives。它不是固定 ARC solution library，模型可組合新程式；但 unsupported Python、物件表徵與工具選擇仍可能造成能力損失，必須當測量項而非掩蓋。

限制包含 source bytes、AST nodes、container size／depth、integer magnitude、locals、call depth 與 interpreter gas。每個 demonstration／test 用 fresh state；primitive 不暴露 host capability。禁止 imports、attributes、dict／arbitrary class、while、exceptions 與 dynamic code。gas 是保守的語言工作單位，不是硬體 instruction 數。AST filtering 本身不是 sandbox；安全邊界在於沒有執行 Python bytecode、沒有暴露任意 host object 的手寫 interpreter。

已通過的 CPU controls 涵蓋迴圈重著色、物件關係、helper／comprehension、caller isolation、遞迴／配置上限、cycle、illegal grids、host API rejection、answer-bearing task rejection、feedback routing、call／token accounting、unknown usage、model switch、Unicode malformed source、超長 JSON integer，以及 slow-tokenizer pre-dispatch／post-verification deadline。這不是形式驗證，也沒有驗證 GPU throughput 或 8B 模型實際輸出格式。

Blocking model callback 不能由這個函式硬中斷。它傳入 `deadline_monotonic` 供 generation stopping 使用，並在生成與驗證後拒絕晚到候選；外層 process supervisor 才能處理卡住的 prefill／kernel。Notebook 停止與 GPU billing 停止必須分開看。

## 六 訓練應如何接到這個系統

### 首輪只做可辨識的改變

先凍結 checkpoint 並取得 A/B/C baseline。若 notebook 同時做少量 LoRA 訓練，訓練前後都跑同一 A/B/C，分開報告 architecture delta、training delta 和兩者交互作用。單一 after-training repair 結果無法說是哪一項有效。Grid SFT 也不能被稱為 agent trajectory SFT。

單 GPU 第一階段優先 LoRA；8–9B BF16 權重約 16–18 GB 只是權重下限。傳統 full AdamW 還有 gradients、master weights、moments 與 activations，不能因 96 GB 就承諾 full fine-tuning。G4 `g4-standard-48` 官方規格為一張 96 GB RTX PRO 6000、48 vCPU、180 GiB 主記憶體。實際峰值與 optimizer 可行性必須量測。[Google 官方 GPU 規格](https://docs.cloud.google.com/compute/docs/gpus)

### 後續 trajectory SFT 的目標格式

每筆 record 至少固定：source task／family ID、split、source digest、model／tokenizer／harness revision、messages、assistant target、tool feedback、execution digest、label provenance、loss mask。資料分三類，不能只記最終答案：

1. Proposal：可見 demonstrations → JSON `{kind: program, source: ...}`。
2. Repair：可見 demonstrations + 錯誤程式 + executor mismatch → 修正後同格式程式。
3. Grid retention：相同可見 demonstrations + test input → JSON `{kind: grid, outputs: [...]}`，避免程式訓練毀掉 direct-grid baseline。

Executor 給出的 feedback 必須真的由保存的舊程式產生；assistant target 要重播核對。Tool text 不計 assistant loss。只有 train split 的可授權標籤能用來驗證 target；dev／official answers 不能變成資料篩選器。只在 demos fit 的 test-time pseudo-label 不應冒充 ground-truth；用不同 provenance 欄位並單獨做 ablation。

初期可由已知生成規則的 synthetic tasks 建立 proposal／repair pairs，再使用 training-only 模型 rollout 中可驗證的程式。不要用 held-out public eval 的成功 trace 反向訓練後繼續宣稱 holdout。外部 teacher API、資料上傳與額外 paid rollout 均不在這個 CPU原型的執行範圍。

### 何時值得 RL

至少先看到合法程式率、非零 exact-fit 與非零 held-out success；否則 reward 太稀疏，GRPO 只是高成本探索。RL reward 只能用允許的 train tasks 或 synthetic hidden queries；demo exact-fit 是可能被 exploit 的 proxy，不能當普遍正確性。Partial cell score 可作搜尋回饋，但不可取代 exact-grid 最终 metric。若試 RL，要和等數量資料／算力的 rejection-SFT 比較，記錄 reward hacking、長度膨脹與失敗率。NeMo RL、Prime Verifiers 是可替換訓練介面，不需出現在最終推論包。

## 七 四張 L4 的部署方向與停止條件

先嘗試每張 L4 各一個 full-tokenizer 8–9B replica，task-level scheduling，CPU executor 處理便宜的程式運算。四張卡的 96 GB 不是單一可任意使用的 VRAM pool；是否要量化或 model parallel 必須由最長 prompt 的實測決定。不要把 Blackwell 訓練時編譯的 kernel binary 當作 Ada L4 可用。部署 artifact 只包含 pinned base／adapter／tokenizer／必要工具和依賴，不含 optimizer、training labels、evaluator 或跨題持續記憶。

首輪可以判定：模型是否能用此語言、三臂是否完整完成、修復是否改善可執行性、候選是否互補、成本是否可接受。四題沒有統計 promotion 能力；未發現候選時先查看 tokenizer／format／grammar／context 問題，不能直接宣稱 model reasoning 不足。擴大實驗後，以 task-cluster paired bootstrap、gain/loss tasks、normalized task pass@2、test-level coverage、candidate oracle、selection gap 與 cost curves 判斷。不能只比較 tokens 上限相同的最終單點。

若 B/C oracle 不優於 A，先不要加入 router。若有 oracle gain 但兩槽選擇退步，才研究 selector。若 C 在同樣預算下輸給 B，修復過深可能應改成較多獨立提案。若語法拒絕主導且 task-specific execution 支持需要新原語，可以在 training-only evidence 上擴語言，重新凍結版本。無論哪個結果，都不能宣告已取得官方分數或達成 >85。

## 附錄 可重現交付

- CPU runtime：`tools/arc_next_agent.py`。
- CPU tests：`tests/test_arc_next_agent.py`。
- 主控整合：`tools/arc_next_workflow.py`；它的 model loader、外層 process supervisor 與 notebook 打包由整合線另外驗證。
- 本次 focused command：`PYTHONHASHSEED=0 PYTHONPATH=src CUDA_VISIBLE_DEVICES= python -m unittest tests.test_arc_next_agent tests.test_arc_next_workflow -v`。
- 2026-10-08 07:15 UTC 觀察：25 個 agent tests + 5 個 workflow tests 通過；未執行 model／GPU／Kaggle／GCP 呼叫。這不是整個 repository aggregate pass。
- 原始 source pins：NAT historical tree `e02a7c4a0c7c49a3408e1ca757d75a3e0f198466`；Prime Agent historical tree `0d2e18dcfc8f1bb1bf1c65f5b6ad00934173e98a`；Verifiers historical tree `cbe80a474790e5aa98642c754e34ded4a759bbf4`。上游 exact revisions 未由這些 local tree IDs 建立。
