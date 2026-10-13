"""Fail-closed, stdlib-only ARC demonstration adaptation artifact primitives.

No runtime, network, tokenizer, target escrow, or model dependency is imported.
Source partitioning operates on pinned identity metadata, never task contents.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha1, sha256
import json
import re
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "portfolio63/arc-adaptation-v1"
Grid = tuple[tuple[int, ...], ...]
_HEX8 = re.compile(r"[0-9a-f]{8}\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("ascii")).hexdigest()


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be a nonempty, unpadded string")
    return value


def identity_key(value: str) -> str:
    """Normalize common filename aliases; arbitrary aliases require declaration."""
    text = _text(value, "identity").lower().replace("\\", "/")
    basename = text.rsplit("/", 1)[-1]
    candidate = basename[:-5] if basename.endswith(".json") else basename
    return candidate if _HEX8.fullmatch(candidate) else text


def task_id(value: str) -> str:
    result = identity_key(value)
    if not _HEX8.fullmatch(result):
        raise ValueError("parent task IDs must be eight hexadecimal characters")
    return result


def _ids(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("IDs must be an iterable of IDs, not a string")
    return tuple(sorted(set(task_id(v) for v in values)))


def _hash(value: str, length: int, name: str) -> str:
    if type(value) is not str or not ( _HEX40 if length == 40 else _HEX64).fullmatch(value):
        raise ValueError(f"{name} must be lowercase hexadecimal with length {length}")
    return value


def _nonnegative(value: int, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def freeze_grid(value: Any) -> Grid:
    """Copy a finite rectangular ARC grid (1..30 each dimension; exact ints 0..9)."""
    if type(value) not in (list, tuple) or not 1 <= len(value) <= 30:
        raise ValueError("grid height must be 1..30")
    width = None
    result = []
    for row in value:
        if type(row) not in (list, tuple) or not 1 <= len(row) <= 30:
            raise ValueError("grid width must be 1..30")
        width = len(row) if width is None else width
        if len(row) != width:
            raise ValueError("ragged grid")
        if any(type(color) is not int or not 0 <= color <= 9 for color in row):
            raise ValueError("ARC colors must be exact integers 0..9 (bool/float forbidden)")
        result.append(tuple(row))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class Example:
    input: Grid
    output: Grid

    def __post_init__(self) -> None:
        object.__setattr__(self, "input", freeze_grid(self.input))
        object.__setattr__(self, "output", freeze_grid(self.output))


@dataclass(frozen=True, slots=True)
class SourceEntry:
    """A canonical training parent, not an augmented or synthetic task."""
    task_id: str
    path: str
    git_blob_sha1: str
    byte_count: int
    aliases: tuple[str, ...] = ()
    ancestor_ids: tuple[str, ...] = ()
    content_sha256: str | None = None

    def __post_init__(self) -> None:
        parent = task_id(self.task_id)
        object.__setattr__(self, "task_id", parent)
        if self.path != f"data/training/{parent}.json":
            raise ValueError("source must be the canonical pinned ARC training path")
        _hash(self.git_blob_sha1, 40, "Git blob SHA1")
        if _nonnegative(self.byte_count, "byte_count") == 0:
            raise ValueError("empty source file")
        if self.content_sha256 is not None:
            _hash(self.content_sha256, 64, "content SHA256")
        if isinstance(self.aliases, (str, bytes)):
            raise ValueError("aliases must be an iterable")
        object.__setattr__(self, "aliases", tuple(sorted(set(identity_key(a) for a in self.aliases))))
        object.__setattr__(self, "ancestor_ids", _ids((*self.ancestor_ids, parent)))

    @property
    def identities(self) -> frozenset[str]:
        return frozenset((self.task_id, *self.aliases, *self.ancestor_ids))


@dataclass(frozen=True, slots=True)
class SourceInventory:
    repository: str
    commit: str
    entries: tuple[SourceEntry, ...]
    expected_sha256: str
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _text(self.repository, "repository")
        _hash(self.commit, 40, "source commit")
        _hash(self.expected_sha256, 64, "expected inventory SHA256")
        entries = tuple(self.entries)
        if not entries or any(type(e) is not SourceEntry for e in entries):
            raise ValueError("inventory needs typed SourceEntry objects")
        entries = tuple(sorted(entries, key=lambda e: e.task_id))
        known: set[str] = set()
        for entry in entries:
            if known.intersection(entry.identities):
                raise ValueError("duplicate or overlapping parent/ancestor/alias identities")
            known.update(entry.identities)
        object.__setattr__(self, "entries", entries)
        actual = inventory_digest(self.repository, self.commit, entries)
        if actual != self.expected_sha256:
            raise ValueError("source inventory does not match the supplied pin")
        object.__setattr__(self, "sha256", actual)

    def to_artifact(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "artifact_type": "source-inventory", "repository": self.repository,
                "commit": self.commit, "entries": [asdict(e) for e in self.entries], "inventory_sha256": self.sha256}

    def entry(self, identity: str) -> SourceEntry:
        key = identity_key(identity)
        for entry in self.entries:
            if key in entry.identities:
                return entry
        raise ValueError(f"identity absent from pinned inventory: {identity}")


def inventory_digest(repository: str, commit: str, entries: Sequence[SourceEntry]) -> str:
    """Compute for preregistration, then independently persist/pass the resulting pin."""
    return digest({"schema": SCHEMA, "repository": repository, "commit": commit,
                   "entries": [asdict(e) for e in sorted(entries, key=lambda e: e.task_id)]})


@dataclass(frozen=True, slots=True)
class Exclusions:
    old_regression_ids: tuple[str, ...]
    old_exposed_ids: tuple[str, ...]
    public120_ids: tuple[str, ...]
    other_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("old_regression_ids", "old_exposed_ids", "public120_ids", "other_ids"):
            values = getattr(self, name)
            if isinstance(values, (str, bytes)):
                raise ValueError("exclusion groups must be iterables")
            object.__setattr__(self, name, tuple(sorted(set(identity_key(v) for v in values))))

    @property
    def identities(self) -> frozenset[str]:
        return frozenset((*self.old_regression_ids, *self.old_exposed_ids, *self.public120_ids, *self.other_ids))

    @property
    def sha256(self) -> str:
        return digest(asdict(self))


def _rank(seed: str, purpose: str, identity: str) -> str:
    return digest([SCHEMA, seed, purpose, identity])


@dataclass(frozen=True, slots=True)
class Partition:
    inventory_sha256: str
    exclusions: Exclusions
    seed: str
    optimizer_ids: tuple[str, ...]
    canary_ids: tuple[str, ...]
    holdout_ids: tuple[str, ...]
    prior_optimizer_ids: tuple[str, ...]
    eligible_order: tuple[str, ...]
    excluded_inventory_ids: tuple[str, ...]
    reserved_ids: tuple[str, ...]
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _hash(self.inventory_sha256, 64, "inventory SHA256")
        _text(self.seed, "split seed")
        if type(self.exclusions) is not Exclusions:
            raise ValueError("typed exclusion policy required")
        for name in ("optimizer_ids", "canary_ids", "holdout_ids", "prior_optimizer_ids", "eligible_order", "excluded_inventory_ids", "reserved_ids"):
            values = tuple(task_id(v) for v in getattr(self, name))
            if len(set(values)) != len(values):
                raise ValueError("duplicate IDs in partition")
            object.__setattr__(self, name, values)
        groups = [set(self.optimizer_ids), set(self.canary_ids), set(self.holdout_ids), set(self.excluded_inventory_ids), set(self.reserved_ids)]
        for index, group in enumerate(groups):
            if any(group.intersection(other) for other in groups[index + 1:]):
                raise ValueError("partition overlap")
        if not self.prior_optimizer_ids or not set(self.prior_optimizer_ids) <= groups[0]:
            raise ValueError("prior optimizer parents must remain optimizer parents")
        if (set().union(*groups[:3]) | groups[4]) & self.exclusions.identities:
            raise ValueError("partition directly contains an excluded identity")
        if set(self.eligible_order) & (set(self.prior_optimizer_ids) | groups[3]):
            raise ValueError("eligible parents overlap prior or excluded parents")
        expected_order = tuple(sorted(self.eligible_order, key=lambda p: (_rank(self.seed, "fresh-panels", p), p)))
        if self.eligible_order != expected_order:
            raise ValueError("eligible parents are not in frozen SHA order")
        boundary = len(self.canary_ids) + len(self.holdout_ids)
        if self.canary_ids != self.eligible_order[:len(self.canary_ids)] or self.holdout_ids != self.eligible_order[len(self.canary_ids):boundary]:
            raise ValueError("canary/holdout must be fixed prefixes of eligible order")
        if self.optimizer_ids != self.prior_optimizer_ids:
            raise ValueError("optimizer parents must equal exactly the frozen prior parents")
        if self.reserved_ids != self.eligible_order[boundary:]:
            raise ValueError("unselected eligible parents must remain reserved, never silently train")
        if self.prior_optimizer_ids != tuple(sorted(self.prior_optimizer_ids)) or self.excluded_inventory_ids != tuple(sorted(self.excluded_inventory_ids)):
            raise ValueError("prior/excluded parent order must be canonical")
        object.__setattr__(self, "sha256", digest(self.to_artifact()))

    def to_artifact(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "artifact_type": "partition", "inventory_sha256": self.inventory_sha256,
                "exclusions": asdict(self.exclusions), "exclusions_sha256": self.exclusions.sha256,
                "seed": self.seed, "optimizer_ids": list(self.optimizer_ids), "canary_ids": list(self.canary_ids),
                "holdout_ids": list(self.holdout_ids), "prior_optimizer_ids": list(self.prior_optimizer_ids),
                "eligible_order": list(self.eligible_order), "excluded_inventory_ids": list(self.excluded_inventory_ids),
                "reserved_ids": list(self.reserved_ids),
                "selection_policy": "SHA256 metadata-only rank; prior-only optimizer; canary prefix, holdout next; reserve remainder; no substitutions"}


def partition_parents(inventory: SourceInventory, prior_optimizer_ids: Iterable[str], exclusions: Exclusions,
                      *, canary_count: int, holdout_count: int, seed: str) -> Partition:
    """Freeze before reading contents. Only prior parents train; unused eligible parents remain reserved."""
    if type(inventory) is not SourceInventory or type(exclusions) is not Exclusions:
        raise ValueError("typed inventory and exclusions required")
    _nonnegative(canary_count, "canary_count")
    _nonnegative(holdout_count, "holdout_count")
    _text(seed, "split seed")
    prior = tuple(sorted(set(inventory.entry(v).task_id for v in prior_optimizer_ids)))
    if not prior:
        raise ValueError("existing optimizer parents must be specified")
    excluded = tuple(e.task_id for e in inventory.entries if e.identities & exclusions.identities)
    if set(prior).intersection(excluded):
        raise ValueError("prior optimizer parent conflicts with exclusion policy")
    eligible = tuple(sorted((e.task_id for e in inventory.entries if e.task_id not in (*prior, *excluded)),
                            key=lambda p: (_rank(seed, "fresh-panels", p), p)))
    total = canary_count + holdout_count
    if len(eligible) < total:
        raise ValueError("insufficient unexposed parents; never substitute old panels or inspect outcomes")
    canary, holdout = eligible[:canary_count], eligible[canary_count:total]
    return Partition(inventory.sha256, exclusions, seed, prior, canary, holdout, prior, eligible, excluded, eligible[total:])


def validate_partition(partition: Partition, inventory: SourceInventory) -> None:
    """Re-derive a loaded partition against its pinned inventory, including alias exclusions."""
    if type(partition) is not Partition or type(inventory) is not SourceInventory:
        raise ValueError("typed partition and source inventory required")
    expected = partition_parents(inventory, partition.prior_optimizer_ids, partition.exclusions,
                                 canary_count=len(partition.canary_ids), holdout_count=len(partition.holdout_ids),
                                 seed=partition.seed)
    if partition != expected:
        raise ValueError("partition does not match its complete pinned inventory and exclusions")


def assert_sprint_contract(partition: Partition, *, inventory: SourceInventory, archived_optimizer_ids: Iterable[str],
                           archived_regression_ids: Iterable[str], archived_exposed_ids: Iterable[str],
                           public120_exclusion_sha256: str) -> None:
    """Project-specific launch gate; PUBLIC120 digest must be independently pinned by caller.

    PUBLIC120 may contain multiple cases per parent; do not fabricate 120 unique IDs.
    Its exact ID-set digest, rather than its name or presumed cardinality, is the gate.
    """
    validate_partition(partition, inventory)
    prior, regression, exposed = _ids(archived_optimizer_ids), _ids(archived_regression_ids), _ids(archived_exposed_ids)
    if (len(prior), len(regression), len(exposed)) != (32, 24, 4):
        raise ValueError("archived panel identity counts must be 32/24/4")
    if set(prior) != set(partition.prior_optimizer_ids):
        raise ValueError("archived 32 optimizer parents were changed")
    if not set(regression) <= set(partition.exclusions.old_regression_ids):
        raise ValueError("old 24 regression exclusions missing")
    if not set(exposed) <= set(partition.exclusions.old_exposed_ids):
        raise ValueError("old 4 exposed exclusions missing")
    _hash(public120_exclusion_sha256, 64, "PUBLIC120 exclusions pin")
    if not partition.exclusions.public120_ids or digest(partition.exclusions.public120_ids) != public120_exclusion_sha256:
        raise ValueError("PUBLIC120 identity exclusions absent or unpinned")


@dataclass(frozen=True, slots=True)
class Lineage:
    repository: str
    commit: str
    inventory_sha256: str
    parent_id: str
    ancestor_ids: tuple[str, ...]
    source_path: str
    source_git_blob_sha1: str
    projection_sha256: str
    origin_projection_sha256: str
    visible_demo_indices: tuple[int, ...]
    excluded_demo_indices: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        _text(self.repository, "repository")
        _hash(self.commit, 40, "commit")
        _hash(self.inventory_sha256, 64, "inventory SHA256")
        _hash(self.projection_sha256, 64, "projection SHA256")
        _hash(self.origin_projection_sha256, 64, "origin projection SHA256")
        for name in ("visible_demo_indices", "excluded_demo_indices"):
            values = tuple(getattr(self, name))
            if any(type(i) is not int or i < 0 for i in values) or values != tuple(sorted(set(values))):
                raise ValueError("source demo indices must be canonical nonnegative integers")
            object.__setattr__(self, name, values)
        if not self.visible_demo_indices or set(self.visible_demo_indices) & set(self.excluded_demo_indices):
            raise ValueError("visible and excluded source demonstrations must be disjoint")
        all_indices = tuple(sorted((*self.visible_demo_indices, *self.excluded_demo_indices)))
        if all_indices != tuple(range(len(all_indices))):
            raise ValueError("source demo index inventory must be complete and contiguous")
        if not self.excluded_demo_indices and self.origin_projection_sha256 != self.projection_sha256:
            raise ValueError("root projection hashes must agree")
        _hash(self.source_git_blob_sha1, 40, "source Git blob SHA1")
        parent = task_id(self.parent_id)
        object.__setattr__(self, "parent_id", parent)
        object.__setattr__(self, "ancestor_ids", _ids((*self.ancestor_ids, parent)))
        if self.source_path != f"data/training/{parent}.json":
            raise ValueError("lineage source must be a training parent")


@dataclass(frozen=True, slots=True)
class DemonstrationTask:
    lineage: Lineage
    demos: tuple[Example, ...]

    def __post_init__(self) -> None:
        if type(self.lineage) is not Lineage:
            raise ValueError("typed lineage required")
        demos = tuple(self.demos)
        if not demos or any(type(e) is not Example for e in demos):
            raise ValueError("typed, nonempty demonstrations required")
        object.__setattr__(self, "demos", demos)
        if len(demos) != len(self.lineage.visible_demo_indices):
            raise ValueError("visible source indices must match demonstrations")
        if digest({"train": [asdict(e) for e in demos]}) != self.lineage.projection_sha256:
            raise ValueError("demonstrations do not match immutable projection digest")


def project_demonstrations(raw_task: Mapping[str, Any], inventory: SourceInventory, identity: str) -> DemonstrationTask:
    """Closed train-only projection. Root test/query/target fields are never read or retained.

    This semantic boundary does not verify raw source bytes; use the bytes entrypoint
    when original pinned source files are available. Archived sanitized data may use
    this entrypoint only after separately verifying its sanitized receipt.
    """
    if type(inventory) is not SourceInventory or not isinstance(raw_task, Mapping):
        raise ValueError("typed inventory and task mapping required")
    source = inventory.entry(identity)
    train = raw_task.get("train")
    if type(train) not in (list, tuple) or not train:
        raise ValueError("train demonstrations are required")
    demos = []
    for pair in train:
        if not isinstance(pair, Mapping) or set(pair) != {"input", "output"}:
            raise ValueError("demonstrations accept exactly input/output; query/test targets forbidden")
        demos.append(Example(pair["input"], pair["output"]))
    projection = digest({"train": [asdict(e) for e in demos]})
    lineage = Lineage(inventory.repository, inventory.commit, inventory.sha256, source.task_id,
                      source.ancestor_ids, source.path, source.git_blob_sha1, projection,
                      projection, tuple(range(len(demos))))
    return DemonstrationTask(lineage, tuple(demos))


def project_source_bytes(blob: bytes, inventory: SourceInventory, identity: str) -> DemonstrationTask:
    if type(blob) is not bytes:
        raise ValueError("immutable source bytes required")
    entry = inventory.entry(identity)
    git_hash = sha1(f"blob {len(blob)}\0".encode("ascii") + blob).hexdigest()
    if len(blob) != entry.byte_count or git_hash != entry.git_blob_sha1:
        raise ValueError("source byte count or Git blob hash mismatch")
    if entry.content_sha256 is not None and sha256(blob).hexdigest() != entry.content_sha256:
        raise ValueError("source SHA256 mismatch")
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    raw = json.loads(blob, object_pairs_hook=no_duplicates,
                     parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"nonfinite JSON: {value}")))
    return project_demonstrations(raw, inventory, identity)


def d4_transform(grid: Grid, operation: int) -> Grid:
    """0..3 clockwise quarter turns; 4..7 those turns followed by left/right reflection."""
    result = freeze_grid(grid)
    if type(operation) is not int or not 0 <= operation < 8:
        raise ValueError("D4 operation must be exact int 0..7")
    for _ in range(operation % 4):
        result = tuple(tuple(row) for row in zip(*result[::-1]))
    if operation >= 4:
        result = tuple(row[::-1] for row in result)
    return result


def d4_inverse(operation: int) -> int:
    if type(operation) is not int or not 0 <= operation < 8:
        raise ValueError("D4 operation must be exact int 0..7")
    return (-operation) % 4 if operation < 4 else operation


def deterministic_palette(seed: str, variant: int = 0) -> tuple[int, ...]:
    _text(seed, "palette seed")
    _nonnegative(variant, "palette variant")
    colors = sorted(range(1, 10), key=lambda c: (_rank(seed, f"palette:{variant}", str(c)), c))
    return (0, *colors)


@dataclass(frozen=True, slots=True)
class Transform:
    d4: int = 0
    palette: tuple[int, ...] = tuple(range(10))

    def __post_init__(self) -> None:
        d4_inverse(self.d4)
        palette = tuple(self.palette)
        if (len(palette) != 10 or any(type(c) is not int for c in palette)
                or set(palette) != set(range(10)) or palette[0] != 0):
            raise ValueError("palette must be a bijection on 0..9 fixing background 0")
        object.__setattr__(self, "palette", palette)

    def apply(self, grid: Grid) -> Grid:
        return tuple(tuple(self.palette[c] for c in row) for row in d4_transform(grid, self.d4))

    def inverse(self) -> Transform:
        return Transform(d4_inverse(self.d4), tuple(self.palette.index(c) for c in range(10)))


@dataclass(frozen=True, slots=True)
class Prompt:
    examples: tuple[Example, ...]
    query_input: Grid

    def __post_init__(self) -> None:
        examples = tuple(self.examples)
        if any(type(e) is not Example for e in examples):
            raise ValueError("LOO prompt requires typed demonstration examples")
        object.__setattr__(self, "examples", examples)
        object.__setattr__(self, "query_input", freeze_grid(self.query_input))

    def to_artifact(self) -> dict[str, Any]:
        return {"examples": [asdict(e) for e in self.examples], "query_input": self.query_input}


@dataclass(frozen=True, slots=True)
class SupervisedRecord:
    lineage: Lineage
    prompt: Prompt
    target: Grid
    withheld_demo_index: int
    context_demo_indices: tuple[int, ...]
    demo_count: int
    transform: Transform
    purpose: str
    partition_sha256: str | None
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.lineage) is not Lineage or type(self.prompt) is not Prompt or type(self.transform) is not Transform:
            raise ValueError("typed record components required")
        object.__setattr__(self, "target", freeze_grid(self.target))
        _nonnegative(self.withheld_demo_index, "withheld_demo_index")
        _nonnegative(self.demo_count, "demo_count")
        if self.demo_count != len(self.lineage.visible_demo_indices):
            raise ValueError("record demo count must match visible source indices")
        if not self.withheld_demo_index < self.demo_count or self.demo_count < 1:
            raise ValueError("invalid withheld demonstration")
        context = tuple(self.context_demo_indices)
        if any(type(i) is not int for i in context):
            raise ValueError("context indices must be integers")
        expected = tuple(i for i in range(self.demo_count) if i != self.withheld_demo_index)
        if context != expected or len(context) != len(self.prompt.examples):
            raise ValueError("target contamination or missing/duplicate context demonstration")
        object.__setattr__(self, "context_demo_indices", context)
        if self.purpose not in ("optimizer", "ttt"):
            raise ValueError("record purpose must be optimizer or ttt")
        if self.purpose == "optimizer" and (self.partition_sha256 is None or self.demo_count < 2):
            raise ValueError("optimizer records require a frozen partition and at least two demonstrations")
        if self.partition_sha256 is not None:
            _hash(self.partition_sha256, 64, "partition SHA256")
        # Reconstruct the complete untransformed task to prove target and contexts
        # are exactly the approved demonstration projection, not a query target.
        inverse = self.transform.inverse()
        restored: list[Example | None] = [None] * self.demo_count
        for index, example in zip(context, self.prompt.examples):
            restored[index] = Example(inverse.apply(example.input), inverse.apply(example.output))
        restored[self.withheld_demo_index] = Example(inverse.apply(self.prompt.query_input), inverse.apply(self.target))
        if digest({"train": [asdict(e) for e in restored]}) != self.lineage.projection_sha256:
            raise ValueError("record does not reconstruct its demonstration-only source")
        object.__setattr__(self, "sha256", digest(self.to_artifact()))

    @property
    def prompt_json(self) -> str:
        """Only this prompt field may be rendered to model input; target stays separate."""
        return canonical_json(self.prompt.to_artifact())

    @property
    def target_json(self) -> str:
        return canonical_json(self.target)

    @property
    def cell_cost(self) -> int:
        grids = [self.prompt.query_input, self.target]
        grids.extend(g for e in self.prompt.examples for g in (e.input, e.output))
        return sum(len(g) * len(g[0]) for g in grids)

    def to_artifact(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "artifact_type": "loo-supervised-record", "lineage": asdict(self.lineage),
                "prompt": self.prompt.to_artifact(), "target": self.target,
                "withheld_demo_index": self.withheld_demo_index, "context_demo_indices": self.context_demo_indices,
                "demo_count": self.demo_count, "transform": asdict(self.transform), "purpose": self.purpose,
                "partition_sha256": self.partition_sha256}


def loo_records(task: DemonstrationTask, *, transforms: Sequence[Transform] = (Transform(),),
                purpose: str, partition: Partition | None = None) -> tuple[SupervisedRecord, ...]:
    """TTT accepts demonstrations only, never an original test/query target argument."""
    if type(task) is not DemonstrationTask:
        raise ValueError("LOO/TTT accepts only a closed DemonstrationTask")
    if purpose not in ("optimizer", "ttt"):
        raise ValueError("unknown purpose")
    if partition is not None and (type(partition) is not Partition or partition.inventory_sha256 != task.lineage.inventory_sha256):
        raise ValueError("partition and task inventory mismatch")
    if purpose == "optimizer" and (partition is None or task.lineage.parent_id not in partition.optimizer_ids):
        raise ValueError("optimizer task must belong to the frozen optimizer partition")
    if purpose == "optimizer" and task.lineage.excluded_demo_indices:
        raise ValueError("optimizer records cannot use an outer-TTT subset projection")
    if purpose == "optimizer" and len(task.demos) < 2:
        raise ValueError("optimizer leave-one-out needs at least two demonstrations; no task substitution")
    transforms = tuple(transforms)
    if not transforms or any(type(t) is not Transform for t in transforms) or len(set(transforms)) != len(transforms):
        raise ValueError("transforms must be nonempty, typed, and unique")
    records = []
    for transform in transforms:
        transformed = tuple(Example(transform.apply(e.input), transform.apply(e.output)) for e in task.demos)
        for withheld, target_example in enumerate(transformed):
            indices = tuple(i for i in range(len(transformed)) if i != withheld)
            prompt = Prompt(tuple(transformed[i] for i in indices), target_example.input)
            records.append(SupervisedRecord(task.lineage, prompt, target_example.output, withheld, indices,
                                             len(transformed), transform, purpose, partition.sha256 if partition else None))
    return tuple(records)


def validate_record(record: SupervisedRecord, source_task: DemonstrationTask, *,
                    expected_excluded_demo_indices: Sequence[int] = ()) -> None:
    """Bind replay to verified ORIGINAL task and explicit expected outer-exclusion scope.

    Default expects no outer exclusion (optimizer or original-query TTT). For an
    outer fold, the caller must supply its independently known withheld indices.
    """
    if type(record) is not SupervisedRecord or type(source_task) is not DemonstrationTask:
        raise ValueError("typed record and original source task required")
    if source_task.lineage.excluded_demo_indices:
        raise ValueError("validation requires original, unsubselected source demonstrations")
    visible = record.lineage.visible_demo_indices
    expected_scope = tuple(expected_excluded_demo_indices)
    if (any(type(i) is not int or i < 0 for i in expected_scope)
            or expected_scope != tuple(sorted(set(expected_scope)))
            or record.lineage.excluded_demo_indices != expected_scope):
        raise ValueError("record exclusion scope differs from intended outer fold")
    if set((*visible, *record.lineage.excluded_demo_indices)) != set(range(len(source_task.demos))):
        raise ValueError("record does not cover the complete original source demo inventory")
    if any(i >= len(source_task.demos) for i in (*visible, *record.lineage.excluded_demo_indices)):
        raise ValueError("record source demo index outside original task")
    expected_demos = tuple(source_task.demos[i] for i in visible)
    expected_lineage = replace(source_task.lineage,
        projection_sha256=digest({"train": [asdict(e) for e in expected_demos]}),
        visible_demo_indices=visible, excluded_demo_indices=record.lineage.excluded_demo_indices)
    if record.lineage != expected_lineage:
        raise ValueError("record lineage does not match original source task")
    target = expected_demos[record.withheld_demo_index]
    transform = record.transform
    expected_prompt = Prompt(tuple(Example(transform.apply(expected_demos[i].input), transform.apply(expected_demos[i].output))
                                   for i in record.context_demo_indices), transform.apply(target.input))
    if record.prompt != expected_prompt or record.target != transform.apply(target.output) or record.sha256 != digest(record.to_artifact()):
        raise ValueError("record content or digest differs from verified source projection")


def outer_ttt_records(task: DemonstrationTask, *, outer_withheld_demo_index: int,
                      transforms: Sequence[Transform] = (Transform(),),
                      partition: Partition | None = None) -> tuple[SupervisedRecord, ...]:
    """Adapt for an outer LOO pseudo-query without ever training on its withheld pair.

    The index is local to this task's visible demonstrations. The returned lineage
    maps every remaining local index back to its original source index. One
    remaining pair produces a zero-context input-to-output supervised record.
    With no pairs remaining, raise instead of leaking or substituting tasks.
    """
    if type(task) is not DemonstrationTask:
        raise ValueError("outer TTT requires a closed DemonstrationTask")
    _nonnegative(outer_withheld_demo_index, "outer_withheld_demo_index")
    if outer_withheld_demo_index >= len(task.demos):
        raise ValueError("outer withheld demo index out of range")
    demos = tuple(e for i, e in enumerate(task.demos) if i != outer_withheld_demo_index)
    if not demos:
        raise ValueError("outer TTT has no remaining demonstrations; skip adaptation, no substitution")
    visible = tuple(i for j, i in enumerate(task.lineage.visible_demo_indices) if j != outer_withheld_demo_index)
    excluded = tuple(sorted((*task.lineage.excluded_demo_indices,
                             task.lineage.visible_demo_indices[outer_withheld_demo_index])))
    lineage = replace(task.lineage, projection_sha256=digest({"train": [asdict(e) for e in demos]}),
                      visible_demo_indices=visible, excluded_demo_indices=excluded)
    return loo_records(DemonstrationTask(lineage, demos), transforms=transforms, purpose="ttt", partition=partition)


@dataclass(frozen=True, slots=True)
class Schedule:
    record_sha256s: tuple[str, ...]
    parent_ids: tuple[str, ...]
    seed: str
    max_records: int
    max_cells: int | None
    cells_used: int
    stop_reason: str
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        hashes = tuple(_hash(value, 64, "record SHA256") for value in self.record_sha256s)
        parents = tuple(task_id(value) for value in self.parent_ids)
        _text(self.seed, "schedule seed")
        _nonnegative(self.max_records, "max_records")
        _nonnegative(self.cells_used, "cells_used")
        if self.max_cells is not None:
            _nonnegative(self.max_cells, "max_cells")
            if self.cells_used > self.max_cells:
                raise ValueError("schedule exceeds cell budget")
        if len(hashes) != len(parents) or len(hashes) > self.max_records:
            raise ValueError("schedule shape or record budget mismatch")
        if self.stop_reason not in ("max_records", "next_record_exceeds_cell_budget"):
            raise ValueError("unknown schedule stop reason")
        object.__setattr__(self, "record_sha256s", hashes)
        object.__setattr__(self, "parent_ids", parents)
        object.__setattr__(self, "sha256", digest(self.to_artifact()))

    def to_artifact(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "artifact_type": "balanced-schedule", "seed": self.seed,
                "record_sha256s": self.record_sha256s, "parent_ids": self.parent_ids,
                "max_records": self.max_records, "max_cells": self.max_cells, "cells_used": self.cells_used,
                "stop_reason": self.stop_reason, "policy": "fixed parent round-robin; SHA-ranked per-parent records; cycle on exhaustion; stop without skipping"}


def budgeted_schedule(records: Sequence[SupervisedRecord], *, max_records: int, seed: str,
                      max_cells: int | None = None) -> Schedule:
    """Every prefix has parent visit counts differing by <=1, including unseen parents.

    Cells bound data volume, NOT tokens, FLOPs or wall-clock/GPU time. A blocked next
    record ends the prefix; shorter examples/parents are never substituted.
    """
    _nonnegative(max_records, "max_records")
    _text(seed, "schedule seed")
    if max_cells is not None:
        _nonnegative(max_cells, "max_cells")
    records = tuple(records)
    if not records or any(type(record) is not SupervisedRecord for record in records):
        raise ValueError("nonempty typed record pool required")
    if len({r.sha256 for r in records}) != len(records):
        raise ValueError("duplicate records")
    if len({(r.purpose, r.partition_sha256, r.lineage.inventory_sha256) for r in records}) != 1:
        raise ValueError("cannot mix purposes, partitions, or inventories in one schedule")
    if records[0].purpose == "ttt" and len({(r.lineage.parent_id, r.lineage.projection_sha256,
                                              r.lineage.excluded_demo_indices) for r in records}) != 1:
        raise ValueError("TTT schedule must have one parent and one outer-withheld scope; reset state between schedules")
    grouped: dict[str, list[SupervisedRecord]] = defaultdict(list)
    for record in records:
        grouped[record.lineage.parent_id].append(record)
    parents = sorted(grouped, key=lambda p: (_rank(seed, "parent-order", p), p))
    for parent in parents:
        grouped[parent].sort(key=lambda r: (_rank(seed, "record-order", r.sha256), r.sha256))
    selected, selected_parents = [], []
    cells, stop = 0, "max_records"
    for step in range(max_records):
        parent = parents[step % len(parents)]
        visit = step // len(parents)
        record = grouped[parent][visit % len(grouped[parent])]
        if max_cells is not None and cells + record.cell_cost > max_cells:
            stop = "next_record_exceeds_cell_budget"
            break
        selected.append(record.sha256)
        selected_parents.append(parent)
        cells += record.cell_cost
    counts = Counter(selected_parents)
    if max((counts[p] for p in parents), default=0) - min((counts[p] for p in parents), default=0) > 1:
        raise AssertionError("parent visitation invariant violated")
    return Schedule(tuple(selected), tuple(selected_parents), seed, max_records, max_cells, cells, stop)
