"""Offline, unpacked token/mask reference. Not a trainer or a MaxText adapter."""

from .contract import build_row, token_ledger

__all__ = ["build_row", "token_ledger"]
