# 研究來源查核與限制

查核日期：2026-10-14 UTC。來源碼基準：`cc14bd1a79aac1fe6135017c9e09d4834300675d`。

## 結論

**三份研究文件通過下列範圍的來源與數學查核，可作為研究規劃材料。這不代表執行程式、GPU 訓練、部署或新分數通過驗證。** 文件區分現行已實作路徑、歷史原型、外部研究與新提案；沒有將文獻結果冒充 IRIS-X 實驗結果。

## 已查核重點

- 現行政策確為同 session SFT256、最多四個互斥64-slot批次、最多四次 RL commit，以及從 A 出發的整段額外 wall-matched SFT。固定 dev 選擇、no-TTT、完整120-task／167-query分母、held32重用與不同學習率的因果限制都有保留。依據為 `MEASURED-POLICY.json`、`rl_session/plan.py` 與實際 runtime。
- 歷史 TTT 的5→10/172與6.119倍耗時、uncapped的41個候選與1/6結果，均與保存的研究摘要吻合；文件沒有改稱目前 canonical PUBLIC120 的新結果。
- 舊 controller 的 auto trigger、demo-fit 後執行 query、repair 停止條件、program-tier／八視圖 NLL／direct floor，與實際來源碼相符；沒有聲稱這些功能已在 run008 啟用。
- DDIS 全名、雙側硬遮罩與 rollout denominator 可追溯至 [GLM-5 §4.1.2](https://arxiv.org/html/2602.15763v1)。固定 [upstream loss](https://github.com/ycchen-tw/agent-factory-3/blob/a1836decb836cd52cf2b27f5022f6838cee75df3/src/agent_factory_3/trainer/losses/ddis_loss.py) 已核對至 blob `28afd41a146e1bc2c178f50c0b68eb5d2fa7fdfb`，確有 detached ratio 與 strict bounds。本地 group mean、長度與 mixed-group 分母則另外核對本地數學及 runtime，沒有將完整上游框架算成本地能力。
- 完整G=8的RLOO advantage為group-centered advantage的8/7倍；參數更新不必在Adam下等比例。DDIS與未截斷PPO的梯度等價已明確限制為相同advantage、normalizer、ratio與適用bounds，並保留對稱ε=.2可能在ratio>1.2時截斷的例外。這些是公式推導，非GPU觀測。[RLOO原文](https://arxiv.org/html/2402.14740v1)、[PPO原文](https://arxiv.org/abs/1707.06347)
- 原始2019／ICML2020自監督TTT與2024／2025 ARC few-shot TTT已分開；不能由前者推定ARC實證。[Sun等人](https://proceedings.mlr.press/v119/sun20b.html)、[Akyürek等人](https://arxiv.org/html/2411.07279v2)
- SOAR的ARC1資料、14B與五模型集成、搜尋預算、多模型多輪資料池及TTT條件已保留；NVARC的公開榜與private final已分開。[SOAR](https://arxiv.org/html/2507.14172v2)、[NVIDIA報告](https://developer.nvidia.com/blog/nvidia-kaggle-grandmasters-win-artificial-general-intelligence-competition/)、[主辦方final](https://arcprize.org/competitions/2025)
- AVO、Duck與Prime的主要結果均限制於ARC3及其原始metric／public範圍；Arcgentica則是ARC2 frontier API系統結果，未歸因為單獨multi-agent效果。[AVO](https://developer.nvidia.com/blog/nvidia-avo-reaches-100-on-arc-agi-3-demonstrating-a-frontier-level-general-purpose-architecture-for-long-horizon-autonomous-agents/)、[Duck](https://tufalabs.ai/research/duck-harness/)、[Prime](https://arxiv.org/html/2608.23552v1)、[Arcgentica](https://www.symbolica.ai/blog/arcgentica)
- Enigmata的ARC2結果及其RFT／VC-PPO背景有原文支持；文件保留四次評估平均、模型與成本不可比，以及正文370／附錄425步的來源差異，沒有自行消除矛盾。[Enigmata](https://arxiv.org/html/2505.19914v2)

## 修正已納入

1. SOAR的14B結果補上 pooled multi-model training data 與後續TTT。
2. PPO條件式等價補上標準對稱ε=.2例外，摘要表格也保留條件；接受門檻不再寫成已取得測量。
3. NVARC的24.0%標為private final。
4. B=A只適用整個B從未有效commit；後續零訊號batch保留先前完整已commit的B。

## 查核邊界

- 這是對主要結論、來源定位、數學及實作身分的有限查核，不是所有外部專案的逐行審計、完整文獻回顧或獨立重現。較低優先的新方法及部署方案仍是有條件建議。
- 主文及RL附錄共20個固定commit的repo檔案連結已確認在該Git object內存在；此項只驗證來源定位。動態官方網站的狀態僅代表查核日。
- 文件採摘要與本地分析，沒有長篇逐字引用；不以外部行銷說法作成本或成功保證。
- 未執行模型、訓練、scorer、provider查詢、外部安裝或Git發布，也未讀取evaluator答案本體。現有未完成adapter的輸出路徑race與最終integration review仍需另處理；本查核沒有核准該程式作操作性release。

## 本次查核文件指紋

- `method-landscape.zh-TW.md`：SHA-256 `1dd4cba4f122f9907326ed052b0fa5071667c082fe2886cbdbf035d9db94c121`
- `agent-architectures.zh-TW.md`：SHA-256 `a1b6aa01383a73dcd06e2e9b54a89ad4979143658fad20157a43c9d31d5b7c1a`
- `rl-methods.zh-TW.md`：SHA-256 `3c5c5f19a793769da2894bc3711219848fc48274c74f1471558abf24bf660c01`
