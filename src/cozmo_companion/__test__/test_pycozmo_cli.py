"""Handlers PyCozmo recebem Connection no 1º arg."""

import unittest
from unittest.mock import MagicMock

from cozmo_companion.core.pycozmo_cli import resolver_cliente, vincular_cliente


class TestPycozmoCli(unittest.TestCase):
    def test_resolver_connection(self) -> None:
        cli = MagicMock()
        conn = MagicMock()
        vincular_cliente(conn, cli)
        self.assertIs(resolver_cliente(conn), cli)

    def test_resolver_cliente_direto(self) -> None:
        cli = MagicMock()
        self.assertIs(resolver_cliente(cli), cli)


if __name__ == "__main__":
    unittest.main()
