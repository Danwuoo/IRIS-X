"""Immutable, outcome-independent planning and explicit source closure."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib, json, math, sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Complete bytes are checked before any write; never truncate evidence.
    body=canonical(value)+b'\n'
    from owned_runtime.evidence import admit_write
    admit_write(path,len(body))
    with path.open('xb') as handle:
        handle.write(body)
        handle.flush()
        __import__('os').fsync(handle.fileno())
    return {'path': str(path.resolve()), 'file_sha256': file_sha(path)}


def finite_nonnegative(value, label):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'finite nonnegative ' + label)


@dataclass(frozen=True)
class SourceFreeze:
    root: str
    files: tuple[tuple[str, str], ...]

    @classmethod
    def capture(cls, root, directories=('baseline', 'rl_session', 'reviewed', 'experiment_flow', 'owned_runtime', 'validation', 'owned_tests')):
        root = Path(root).resolve()
        paths = sorted({p for name in directories for p in (root / name).rglob('*.py')
                        if '__pycache__' not in p.parts})
        # These non-executable design artifacts govern the implementation and
        # therefore belong to the same explicit freeze when present.
        paths += [root / name for name in ('design/LEAD-EXPERIMENT-DECISIONS.json',
                  'independent-protocol-review/PROVISIONAL-DEFAULTS.json',
                  'independent-protocol-review/PROTOCOL-REVIEW.md', 'design/MEASURED-POLICY.json', 'design/COST-EVIDENCE.json') if (root / name).is_file()]
        paths = sorted(set(paths))
        require(paths, 'nonempty source inventory')
        return cls(str(root), tuple((str(p.relative_to(root)), file_sha(p)) for p in paths))

    @property
    def sha256(self):
        return digest(self.files)

    def verify(self):
        # Explicit inventory means a later unrelated file does not invalidate the
        # source. Execution of an unlisted local import is still rejected below.
        for name, expected in self.files:
            require(file_sha(Path(self.root) / name) == expected, 'frozen source drift: ' + name)

    def close_imports(self, execution_guard=None):
        self.verify()
        inventory = dict(self.files)
        imports = {}
        for name, module in tuple(sys.modules.items()):
            filename = getattr(module, '__file__', None)
            if not filename:
                continue
            path = Path(filename).resolve()
            try:
                relative = str(path.relative_to(self.root))
            except ValueError:
                continue
            if path.suffix != '.py' or not path.is_file():
                continue
            require(relative in inventory, 'executed unlisted source import: ' + relative)
            imports[name] = {'file': relative, 'sha256': inventory[relative]}
        return {'source_sha256': self.sha256, 'inventory': dict(self.files),
                'observed_loaded_local_imports': imports,
                'execution_history_closure_verified': execution_guard is not None,
                'execution_guard': execution_guard.receipt() if execution_guard else None,
                'external_packages': 'runtime environment provenance is a separate release requirement'}


class SourceExecutionGuard:
    """Audit actual local file execution while the owned flow is active.

    Synthetic/nonexistent runtime origins are not mistaken for local files.
    External package identity remains a separate release requirement.
    """
    def __init__(self, freeze):
        self.freeze = freeze
        self.inventory = dict(freeze.files)
        self.observed = {}
        self.active = True
        self.rejected = []
        sys.addaudithook(self._audit)

    def _audit(self, event, args):
        if not self.active or event != 'exec':
            return
        filename = getattr(args[0], 'co_filename', None)
        if not filename or filename.startswith('<'):
            return
        path = Path(filename).resolve()
        if not path.is_file():
            return
        try:
            relative = str(path.relative_to(self.freeze.root))
        except ValueError:
            return
        actual = file_sha(path)
        if self.inventory.get(relative) != actual:
            self.rejected.append(relative)
            raise ValueError('unlisted or changed local source execution: ' + relative)
        self.observed[relative] = actual

    def receipt(self):
        require(not self.rejected, 'unlisted local source execution was rejected')
        return {'mechanism': 'Python exec audit events plus initial/current loaded-module inventory',
                'observed_file_executions': dict(self.observed), 'rejected': list(self.rejected),
                'scope': 'real local filesystem source during owned flow; excludes synthetic and external origins'}

    def stop(self):
        self.active = False


@dataclass(frozen=True)
class FixtureShape:
    """Explicitly reduced engineering fixture, never a production workload."""
    anchor_updates: int = 1
    parents: int = 1
    group_size: int = 2
    dev_cases: int = 1
    holdout_cases: int = 1
    max_sweeps: int = 1
    max_control_updates: int = 8
    batch_parents: int = 0

    def __post_init__(self):
        require(all(type(v) is int and (v >= 0 if k == 'batch_parents' else v > 0) for k, v in asdict(self).items()), 'positive fixture counts')
        require(self.anchor_updates <= 256 and self.parents <= 32 and self.group_size <= 8 and
                self.dev_cases <= 16 and self.holdout_cases <= 32 and self.max_sweeps <= 4 and
                self.max_control_updates <= 8192, 'fixture cannot expand production bounds')
        require(self.batch_parents == 0 or self.batch_parents <= self.parents and self.batch_parents * self.max_sweeps == self.parents, 'disjoint batch partition required')


@dataclass(frozen=True)
class Forecast:
    """Source-bound measurements/estimates, never inferred from task outcomes."""
    evidence_sha256: str
    evidence_kind: str
    setup_seconds: float
    sweep_seconds: float
    control_step_seconds: float
    persist_reload_seconds: float
    evaluation_seconds: float
    public_seconds: float
    failure_margin_seconds: float
    closure_seconds: float

    def __post_init__(self):
        require(len(self.evidence_sha256) == 64 and all(c in '0123456789abcdef' for c in self.evidence_sha256), 'forecast source digest')
        require(self.evidence_kind in ('controlled-fixture', 'v25-source-bound-pending-review'), 'forecast source type')
        for key, value in asdict(self).items():
            if key.endswith('_seconds'):
                finite_nonnegative(value, key)
        require(self.sweep_seconds > 0 and self.control_step_seconds > 0 and self.persist_reload_seconds > 0, 'positive indivisible costs')

    @classmethod
    def from_json(cls, path, expected_sha256):
        require(file_sha(path) == expected_sha256, 'forecast evidence bytes differ')
        value = json.loads(Path(path).read_text())
        require(set(value) == {f for f in cls.__dataclass_fields__ if f != 'evidence_sha256'}, 'closed forecast fields')
        return cls(evidence_sha256=expected_sha256, **value)

    @property
    def protected(self):
        return self.evaluation_seconds + self.public_seconds + self.failure_margin_seconds + self.closure_seconds


@dataclass(frozen=True)
class ExperimentPlan:
    sources: SourceFreeze
    forecast: Forecast
    global_started: float
    numerical_gate_json: bytes
    shape: FixtureShape = FixtureShape()
    output_cap: int = 32
    seed: int = 1917
    transforms: tuple[int, int] = (0, 1)
    inner_seconds: float = 42000.
    outer_seconds: float = 42180.
    provider_seconds: float = 42300.
    global_seconds: float = 43200.
    arm_cap_seconds: float = 7200.
    policy_sha256: str | None = None

    def __post_init__(self):
        require(type(self.global_started) in (int, float) and math.isfinite(self.global_started), 'finite monotonic global origin')
        require(type(self.sources) is SourceFreeze and type(self.forecast) is Forecast and type(self.shape) is FixtureShape, 'typed source plan')
        require((self.inner_seconds, self.outer_seconds, self.provider_seconds, self.global_seconds) == (42000., 42180., 42300., 43200.), 'original clock chain unchanged')
        require(self.arm_cap_seconds == 7200. and self.transforms == (0, 1) and self.seed == 1917, 'fixed phase/inference policy')
        require(type(self.output_cap) is int and 1 <= self.output_cap <= 1024, 'bounded output cap')
        require(type(self.numerical_gate_json) is bytes, 'immutable numerical gate before sampling')
        gate = json.loads(self.numerical_gate_json)
        require(canonical(gate) == self.numerical_gate_json and isinstance(gate, dict), 'canonical numerical gate')
        if self.policy_sha256 is not None:
            from owned_runtime.policy import POLICY_SHA256, load_policy
            require(self.policy_sha256 == POLICY_SHA256, 'exact measured policy required')
            load_policy()
            require(self.shape.anchor_updates == 256 and self.shape.parents == 32 and self.shape.group_size == 8 and self.shape.batch_parents == 8 and self.shape.max_sweeps == 4 and self.shape.dev_cases == 16 and self.shape.holdout_cases == 32, 'measured production shape')
        self.sources.verify()

    @property
    def deadline(self):
        return self.global_started + self.inner_seconds

    @property
    def sha256(self):
        return digest(self.receipt())

    def receipt(self):
        return {'format': 'local-intervention-plan-v1', 'source_sha256': self.sources.sha256,
                'forecast': asdict(self.forecast), 'global_started': self.global_started,
                'clock_chain': [self.inner_seconds, self.outer_seconds, self.provider_seconds, self.global_seconds],
                'arm_cap_seconds': self.arm_cap_seconds, 'shape': asdict(self.shape),
                'measured_policy_sha256': self.policy_sha256,
                'batch_semantics': 'disjoint-fixed-prefix' if self.shape.batch_parents else 'explicit-reduced-fixture',
                'numeric_gate': json.loads(self.numerical_gate_json), 'inference': self.inference,
                'anchor_lr': 2e-4, 'B_lr': 1e-6, 'C_lr': 2e-4,
                'anchor_schedule': {'base_lr': 2e-4, 'warmup': 4, 'cosine_steps': 256, 'min_lr_ratio': .1},
                'historical_v25_tensor_equivalence_claim': False,
                'continuation_schedule': 'fresh-constant', 'comparison': 'intervention-package',
                'selection': 'dev-exact-fixed-tie-A-B-C', 'production_admitted': False}

    @property
    def inference(self):
        return {'transforms': list(self.transforms), 'seed': self.seed, 'max_new_tokens': self.output_cap,
                'TTT': False, 'packing': 'frozen-native-whole-demo', 'maximum_answers': 2,
                'precision': 'bf16-base-fp32-lora', 'decoder': 'unchanged-native-grid-DFA'}


def tolerance(b_seconds):
    finite_nonnegative(b_seconds, 'B wall time')
    return min(120., max(5., .05 * b_seconds))


class RecoverableWorkError(Exception):
    """Adapter proves settled device state and exposes the actual partial batch."""
    def __init__(self, message, *, batch=None, update_report=None):
        super().__init__(message)
        self.batch = batch
        self.update_report = update_report


class FatalStateError(Exception):
    pass
