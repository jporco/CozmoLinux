"""Resolve Client vs Connection nos handlers PyCozmo (child dispatch)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pycozmo


def vincular_cliente(conn: Any, cli: "pycozmo.Client") -> None:
    """Backref: pacotes UDP chegam com Connection como 1º arg nos handlers."""
    conn._cozmo_client = cli  # type: ignore[attr-defined]


def resolver_cliente(src: Any) -> "pycozmo.Client":
    """Connection (dispatch filho) ou Client (eventos internos)."""
    import pycozmo
    from pycozmo.conn import Connection

    if isinstance(src, pycozmo.client.Client):
        return src
    od = getattr(src, "__dict__", None)
    if isinstance(od, dict) and "_cozmo_client" in od:
        bound = od["_cozmo_client"]
        if bound is not None:
            return bound
    if isinstance(src, Connection):
        return src  # type: ignore[return-value]
    return src  # type: ignore[return-value]
