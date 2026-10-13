"""Run the unchanged run007 regression cases against the new environment overlay."""
from pathlib import Path
import importlib.util, json, subprocess, sys, tempfile, unittest
HERE=Path(__file__).resolve().parents[1]
OLD=HERE.parent/'cudnn_mapping_repair'
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('run007_regressions_against_run008',OLD/'test_cudnn_mapping.py')
tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
new=importlib.util.spec_from_file_location('owned_runtime.run008_inherited_mapping',HERE/'overlays/owned_runtime/environment_v2.py')
tests.e=importlib.util.module_from_spec(new);new.loader.exec_module(tests.e)
with tempfile.TemporaryDirectory(prefix='run008-inherited-mapping-') as temporary:
    runner=Path(temporary)/'fixture_runner.py'
    text=(OLD/'fixture_runner.py').read_text()
    text=text.replace('HERE=Path(__file__).resolve().parent','HERE=Path('+repr(str(OLD))+')')
    text=text.replace("HERE/'environment_v2.py'",'Path('+repr(str(HERE/'overlays/owned_runtime/environment_v2.py'))+')')
    runner.write_text(text)
    def fixture(self,case):
        args=[sys.executable,'-B']+(['-O'] if sys.flags.optimize else [])+[str(runner),case]
        completed=subprocess.run(args,capture_output=True,text=True,timeout=50,check=True)
        row=json.loads(completed.stdout);self.assertIs(row['fixture_only'],True)
        self.assertEqual(len(row['diagnostics']),1)
        return row
    tests.RealLoaderTests.fixture=fixture
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
raise SystemExit(0 if result.wasSuccessful() else 1)
