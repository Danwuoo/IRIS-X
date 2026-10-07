"""Complete exact source proof around unchanged legacy common preparation.

The legacy preparer hashes actual dependency files but retains only an inventory
digest. This wrapper preserves that receipt and supplies the exact inventory
needed by strict native qualification. No provider/model operation is added.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical, digest, require, write
from tools.nvarc_public_eval_parent import prepare as legacy_prepare


def prepare_verified(root, plan, dependency, *, prepare=legacy_prepare):
    root, dependency = Path(root), Path(dependency)
    inventory_path = root/'source-inventory.json'
    require(not inventory_path.is_symlink() and inventory_path.is_file(),
            'regular exact source inventory required before preparation')
    before = inventory_path.read_bytes(); inventory = parse_json(before)
    require(digest(inventory) == plan['source_inventory_digest'],
            'admitted exact source inventory differs before preparation')
    result = prepare(root, plan, dependency)  # actual byte checks precede receipt
    require(inventory_path.read_bytes() == before,
            'source inventory changed during actual common preparation')
    receipt_path = root/'source-verification.json'
    require(not receipt_path.is_symlink(), 'regular prepare-produced source receipt required')
    previous = receipt_path.read_bytes(); observed = parse_json(previous)
    require(set(observed) == {'inventory_digest', 'dependency_root'} and
            observed['inventory_digest'] == digest(inventory) and observed['dependency_root'] == str(dependency),
            'actual prepare-produced source receipt does not bind exact inventory/root')
    retained = root/'source-verification-prepare.json'
    require(not retained.exists() and not retained.is_symlink(),
            'new exact preparation source receipt required')
    with retained.open('xb') as stream:
        stream.write(previous); stream.flush()
        import os
        os.fsync(stream.fileno())
    write(receipt_path, {'inventory': inventory, 'inventory_digest': digest(inventory),
        'dependency_root': str(dependency), 'prepare_receipt_sha256': hashlib.sha256(previous).hexdigest(),
        'source_inventory_file_sha256': hashlib.sha256(before).hexdigest(),
        'proof': 'unchanged preparer verified actual dependency bytes; exact input bracket retained'})
    return result
