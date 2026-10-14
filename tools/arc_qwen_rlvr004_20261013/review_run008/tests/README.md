# Independent run008 launch checks

These are independently authored offline review tests. They send no provider
request and do not create a production approval. Synthetic positive-path
receipts are temporary fixtures, never operator admission. No credential or
answer body is read. Generated files remain in ignored scratch or temporary
fixture directories and are removed by the suites.

Run each file from repository root using the existing native venv:

```sh
python_path="$(dirname "$PWD")/kaggle_setup/venv/bin/python"
for mode in '' '-O'; do
  "$python_path" -I $mode -B tools/arc_qwen_rlvr004_20261013/review_run008/tests/test_independent_transport.py
  "$python_path" -I $mode -B tools/arc_qwen_rlvr004_20261013/review_run008/tests/test_active_verifier.py
  "$python_path" -I $mode -B tools/arc_qwen_rlvr004_20261013/review_run008/tests/test_collector_transition.py
done
```

The wire suite requires the original local numeric draft-0001 retained by the
admission workflow; it creates a separate synthetic candidate and uses a fixed
old test clock. Missing authentic fixture inputs remain failures. The staged
transition suite reuses the transport suite's synthetic provider fixture while
exercising actual staged preparation, single dispatch, initial receipt and
collector binding/poll code. It verifies dispatch may differ from predispatch
without resetting the absolute deadline. It also rejects a modified deadline
in a rehashed receipt. The transport probes separately reject unreviewed RPCs,
origins, retries, source tampering and foreign cached bytecode, and verify timeout
handler restoration. These checks are CPU mechanics, not GPU/scoring evidence.
