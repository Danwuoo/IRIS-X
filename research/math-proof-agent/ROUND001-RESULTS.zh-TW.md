# R001 結果：數值通過不等於證明成立

日期：2026-10-18。研究程式為 [round001/experiment.py](round001/experiment.py)，協定為 [protocol.json](round001/protocol.json)。本輪是**自編、非盲化、刻意构造反例的 verifier pilot**；不是模型Agent消融，不是IMO／Putnam得分，不是Lean kernel檢查。

## 問題與方法

研究問題：只用有限點代入成功與一個看似達到最小值的樣本，是否足以接受「所有實數／非負實數上，多項式的最小值是a」？若改用綁定原命題的精確非負分解＋達到下界的見證，能拒絕哪些错误？

比較兩個instrument：

- **有限代入 shortcut（刻意不安全）**：在實數域用`-2,-1,0,1,2`，非負域用`0,1,2`檢查`p(x)>=a`，并檢查`p(w)=a`。它不檢查certificate，不是真實LLM或合理的通用證明基線。
- **精確證書 checker**：以Fraction精確驗證`p-a = Σ weight × multiplier × q²`；weight不得為負，multiplier為1或在非負域才可用x；最後核對見證在定義域且`p(w)=a`。原題／domain／目標皆有digest；不讀ground-truth標籤或反例。

在指定實數代數語義下，係數恆等、項非負及下界可達足以推出最小值結論。這個數學理由不代表Python程式已被形式化證明正確；信任基礎仍包括本checker和Python的有理數運算。覆蓋只有單變數低次多項式，不支持一般IMO、幾何、組合、分析或任意Python。

## 真正執行的結果

Linux／CPython 3.13.5，normal與`-O`各執行一次，決策內容及panel指紋一致。

| 類別 | 案例 | 精確證書結果 |
| --- | ---: | --- |
| 合法完整證書：二次、四次、帶非負域乘子 | 12 | 12 certificate_verified |
| 命題數學上為假：有限代入陷阱＋漏假設 | 8 | 8 rejected |
| 命題其實為真，但certificate權重／原題binding不合法 | 8 | 8 rejected；沒有說命題因此為假 |
| 命題其實為真，但只給LLM評論或有限樣本 | 4 | 4 unknown；沒有假稱證明完成 |
| **總計** | **32** | **12 verified / 16 rejected / 4 unknown，預期決策差異0** |

8個具精確反例的錯誤命題中，有限代入shortcut放行4個；精確checker放行0個。這是構造性示範，不是估計真實數學題的50%錯誤率，也不證明一般checker soundness。兩個方法擁有不同證據結構，不能將本結果當作等成本Agent表現比較。

額外12項自測在normal與`-O`均全數通過（0 failure/error/skip），其中一項用200組固定seed有理數樣本，交叉核對Horner／係數運算與獨立冪和評值。這200組是測試內部控制，不是200道數學題。raw reports及測試log見 [HANDOFF](../../docs/verification/MATH-001/HANDOFF.md)。

## 一個具體反例

取

`p(x) = x² + 1 - [x(x²-1)(x²-4)]²`。

在`x=-2,-1,0,1,2`時，平方括號為0，所以有限樣本都支持`p(x)>=1`，而`p(0)=1`。但`p(3)=10-14400=-14390<1`，因此「全實數最小值1」為假。增加對這五個點的自信或重複檢查都不能把它變成證明。精確checker因係數恆等式不成立拒絕；此反例由本輪作者公開構造，不是模型自主發現。

另一類是`x(x-a)²+2`：在非負域可由x乘平方證明至少2；改成全實數後原證書失去前提。對`x=-1`即有反例。命題的domain也是proof identity的一部分。

## 研究結論及下一步

本輪支持把**statement binding、前提檢查、完整性與unknown**列為第一級研究約束。也顯示最小值題不能只證明下界，還需要達到下界的見證。因此下一轮不能用`tool returned True`或LLM打分直接當reward。

尚未回答：真實模型有多少這類錯誤、收到回饋能否修復、相同預算下是否勝過更多獨立採樣、Lean worker可否重現證書、TPU吞吐或IMO／Putnam解題能力。所有model／training／Lean／TPU執行數均為0。下一輪才實作實際模型與Lean配對實驗，不拿本輪人工構造資料的通過率宣傳能力提升。

## 重現

```sh
python -B research/math-proof-agent/round001/experiment.py --self-test
python -O -B research/math-proof-agent/round001/experiment.py --self-test
python -B research/math-proof-agent/round001/experiment.py --output .irisx/line-b/MATH-001/r001-new.json
python -O -B research/math-proof-agent/round001/experiment.py --output .irisx/line-b/MATH-001/r001-new-O.json
```

每個output必須不存在；不覆寫舊證據。wall timing及環境可能不同；比較決策、panel/protocol/script指紋，不要求整份runtime report逐byte相同。
