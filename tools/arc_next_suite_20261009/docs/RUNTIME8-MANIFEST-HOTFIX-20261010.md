# 2026-10-10：runtime8 N1 manifest 啟動修正

## 已確認原因

使用者第一次手動啟動 N6，在模型準備前遇到 `Source N1 manifest identity differs`。這是套件的 reference 封裝錯誤，不是要求使用者更換正確的 mount。

實際下載 `danielwuu/iris-arc-next-runtime/8` 後，34 個 payload members 與 bundle manifest 的完整封閉 inventory／SHA 全部相符：

- Runtime bundle manifest：`c2e7913e8ae208deb26e06f37fcd76c79c1a87b6c49ffb3de7b2ee054fee7e67`
- Runtime 內 canonical N1 manifest：178,386 bytes，`ce7eddc85aac290eff1b67754fe3d689f02897be7f490f5dee019d4da78a631a`
- 原套件誤用的 derived FIX1 reference：178,403 bytes，`d4f6fbb693d35313f2b9be4eac50e5ac3c8340c61e6b4e77ba71de7a44ea54f8`

兩份 manifest 的差異只涉及 N1 experiment／implementation lineage，以及其衍生 core digest、256 筆 record 的 contract digest／record ID。64 題 challenge hashes、tuning 順序、136 題 confirmation 清單、seed／limits、model／adapter／solutions bindings 全部相同。完整欄位比對在 `evidence/RUNTIME8-MANIFEST-COMPARISON.json`。

## 為何原測試漏掉

原 57 個測試把同一份 derived reference 複製成 Fixture.original，並 patch 讀取、從 run_records 以下開始驗證。它們真實驗證了受限程式與記帳，但沒有實際跨過 mounted runtime 的 launch 邊界。

這次原 57 個測試在未改碼時再次通過；同時，使用原已發佈 runner 加上真正的 runtime8，精確重現了同一個 ValueError。這兩個結果一起確認了測試覆蓋缺口。沒有把既有 CPU 測試誤稱為完整部署測試。

## 修正範圍

修正版為 `runtime8-manifest-fix1-20261010`。

1. 以 bundle inventory 確認的 canonical N1 manifest **完整原始 bytes** 取代錯誤 reference。舊 FIX1 fixture 保留為歷史／負向測試。
2. 共用 `load_runtime_inputs` 保留全 runtime inventory／SHA、原 N1 verifier、完整 manifest equality 與 challenge verification；只新增清楚的錯誤診斷，沒有投影部分欄位、刪掉 gate 或重新猜造 canonical manifest。
3. 新的 experiment／source／output／archive namespace 不覆寫舊 N6 失敗目錄。Source lock 更改後，舊 successful／partial／BLOCKED receipts 都不會自動變成新 gate 證據。
4. 重新內嵌全部十份 notebook。N5–N12、N14 經過此 runtime 邊界；N13 維持不依賴 runtime、模型與 CUDA 的 CPU 路徑。

Policy、bounded interpreters、program verifier、IR compiler、curriculum、frozen design、N4 replay payload、token audit 的 bytes 完全不變。沒有修改題目、prompts、tokenizer、seeds、budgets、admission 門檻或模型 pins。

- 新 runner：`f1f8dfde826fa6c0dbf4ef4e88b1ae60df8964215af8ff02d197b7c49a1e2570`
- 新 source lock：`29172a035efc7704cd3f60e663a714a7570c18f636fdca32304be94d02689d50`

## 實測與界線

新增 regression 使用實際捕獲、與 bundle SHA 綁定的 canonical fixture；完整 runtime mount 測試會真正驗證 closed inventory、原 N1 manifest 與 challenges。九個 launch route 的下游 gate／模型工作只在測試中截停，避免安裝或載入模型；沒有 mock 實際 runtime verifier 或 manifest。N13 bypass 測試使用乾淨子程序，保留 production 的 stale-module 拒絕保護。

- 原發佈 N6 failure：使用真正 runtime8、原始 runner 重現，未到 installer／model。
- 修正版九個 runtime launch routes：都跨過真實 asset boundary；modified manifest／額外 mount file／舊 reference 仍被拒絕。
- 修正版 N5 完整 CPU launch：122 次驗證，v2 29 AST admitted、23 demo executions、0 all-demo-fit，1,529,608 charged steps；停止與 seal 後才進行 evaluator scoring。
- 修正版 N13 完整 CPU launch：512 episodes／1,024 verifier responses、0 unknown；payload SHA 仍為 `6c52d04171d84d57dcaa7e77d46e38b0c8b6e57c7c1e29582eec48411aa95fb4`。
- 原有 token audit 可重用，因為 policy、tokenizer contract 與全部 visible challenges 完全相同；已知 object-view exclusions 不變。

完整測試與獨立 release 收據位於 `evidence/runtime8-repair/`。第一次新測試 aggregate 曾因其他 test module 的普通 compiler import 觸發正確的 stale-module guard；只修正測試隔離，未弱化 production guard，並保留該次失敗紀錄。

本次没有新的 GPU generation、training、TTT、RL 或 competition submission。CPU／asset-boundary pass 不等於已完成 N6–N12／N14 的 GPU 實驗。

## 使用修正版

重新開啟已驗證的最新 N6 notebook 版本，保留新版 BASE 和固定 Dataset pins；確認硬體後才改 `MANUAL_START=True`。不要只更改 hash、略過 equality，或刪掉旧版失敗目錄。

新 N6 預設輸出：

```text
/kaggle/working/iris-nextphase-n6-runtime8-manifest-fix1-20261010/runs/iris-x-n6-runtime8-manifest-fix1-20261010/
/kaggle/working/iris-nextphase-n6-runtime8-manifest-fix1-20261010/runs/iris-x-n6-runtime8-manifest-fix1-20261010-evidence.zip
```

下游 `PRIOR_RESULTS` 指向同一修正版產生的完整 evidence ZIP／目錄。原版證據保留為歷史，不能直接混用。

十個既有 Kaggle notebook 的舊版本保留，修正版仍 private／inactive、GPU／TPU／Internet off、manual False。N6 既有 ARC-AGI-3 association 僅按使用者授權保留 metadata；本實驗不讀取或使用該 competition data，也不 submission。其餘九份 association 為空，五個 experiment Dataset pins 不變。
