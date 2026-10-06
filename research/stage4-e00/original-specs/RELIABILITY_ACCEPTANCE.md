# IRIS X Stage 4 有限故障驗收矩陣

供後續E00/E01離線實作採用的研究規格，尚未執行測試。本矩陣不代表已修復官方submission56840442；根因仍未知。



E00先檢查WIP、補source/telemetry與schema；E01只變output lifecycle。24個合成案例各做兩次fake-clock replay，不跑model；對hard watchdog需加CPU-only bounded child stub，fake clock本身不能證明OS kill行為。

| 編號 | 單一主要變因／故障 | 必須觀察 |
|---|---|---|
| F01 | 合法單task單test | 全schema、bindings、正常terminal |
| F02 | 1與4 tests的unequal tasks | 60/75/50% scoring fixture，全部test保留 |
| F03 | 同IDs改test order | index/input digest跟著actual順序，不join錯位置 |
| F04 | task object次序／worker完成次序交換 | 不影響task mapping與test order |
| F05 | missing／extra task或duplicate test index | 拒絕foreign資料；未執行合法task以明確missing保留 |
| F06 | duplicate JSON keys／NaN／bool cell | strict reject，不能silent parse |
| F07 | ragged／0或31維／color -1或10 | schema reject，不污染last valid |
| F08 | test output／nested evaluator field注入 | runtime拒絕；evaluator不能被solver讀到 |
| F09 | 一／零候選與fallback巧合正確 | duplicate/fallback audit；raw與model-only不同 |
| F10 | source/model/code digest mismatch | no launch、no promotion、fatal reason明確 |
| F11 | 缺offline dependency | phase＋traceback；無模型呼叫；不稱已修hidden |
| F12 | actual count/token cost超allocation | bounded explicit rejection；不偷偷縮epoch或刪題 |
| F13 | test0 ordinary timeout、test1有效 | 完整分母；後續test獨立deadline／checkpoint |
| F14 | reserve forward前到期 | 不launch新forward；budget ledger一致 |
| F15 | forward進行中越過deadline | watchdog終止group，記overrun與未完成reservation |
| F16 | verifier只做4/8 views | partial不升格；前一verified候選保留 |
| F17 | worker exception／signal | 先前committed tests留存，receipts含exit/signal |
| F18 | OOM-like／reset mismatch | worker retire、後續reuse不發生；不偽稱GPU測過 |
| F19 | notebook reserve開始、尚未launch tasks | stop dispatch，全部unlaunched denominator仍在 |
| F20 | write temp中斷／replace之前被kill | old完整hash保留，新generation未commit |
| F21 | replace完成、audit/manifest尚未commit | 正確恢復last committed generation，不錯配sidecars |
| F22 | disk-full或permission-like write error | last durable檔可讀；無保證初次寫入可成功 |
| F23 | strict export timeout／root-copy途中失敗 | candidate checkpoints仍在；notebook/output/evidence gates分開 |
| F24 | terminal logger再失敗／stale checkpoint resume | 原始錯誤仍可辨；foreign/stale binding拒絕 |

共用acceptance：所有預期failure應被正確識別；安全/schema/source gate零誤放；已commit可恢復輸出不損壞；完整actual分母；不變更default solver；passed/failed/skipped/never-run逐項列出。對不可恢復source/dependency或初始無可寫disk，不要求偽造successful artifact。測試壞掉不能調門檻、刪owner檔或放寬證據gate使它變綠。

資源估計僅規劃：E00 CPU 0.1–1 wall-hour，E01 0.1–0.5 hour，合成資料、1–4 cores、1–8GiB RAM，零GPU／新外部服務費；不是用Modal GPU rate推算CPU成本。若full suite需要更久，保留原失敗與原因，由總控選適當延長，不取消必要驗證。有限CPU stub不啟動神經推論。


來源：固定專案 [official parent](https://github.com/Danwuoo/IRIS-X/blob/6e04ee3cfcb8ebc3a43e7cff5ac32baf808dd08f/tools/nvarc_official_parent.py)、[generic submission](https://github.com/Danwuoo/IRIS-X/blob/6e04ee3cfcb8ebc3a43e7cff5ac32baf808dd08f/tools/arc_kaggle_submission.py)、[native export](https://github.com/Danwuoo/IRIS-X/blob/6e04ee3cfcb8ebc3a43e7cff5ac32baf808dd08f/tools/nvarc_native_export.py)。存取2026-10-05 UTC。
