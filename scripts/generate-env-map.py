#!/usr/bin/env python3
"""Gera docs/env-vars.md a partir de os.environ.get nos fontes."""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from pathlib import Path


def coletar(root: Path) -> dict[str, list[tuple[str, str]]]:
    itens: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for path in sorted((root / "src" / "cozmo_companion").rglob("*.py")):
        try:
            arvore = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call) or not no.args:
                continue
            fn = no.func
            if not (
                isinstance(fn, ast.Attribute)
                and fn.attr == "get"
                and isinstance(fn.value, ast.Attribute)
                and fn.value.attr == "environ"
            ):
                continue
            chave = no.args[0]
            if not isinstance(chave, ast.Constant) or not isinstance(chave.value, str):
                continue
            default = ast.unparse(no.args[1]) if len(no.args) > 1 else "None"
            local = f"{path.relative_to(root)}:{getattr(no, 'lineno', 0)}"
            itens[chave.value].append((default, local))
    return dict(itens)


def markdown(itens: dict[str, list[tuple[str, str]]]) -> str:
    linhas = [
        "# Variáveis de ambiente do Cozmo Companion",
        "",
        "Arquivo gerado por `scripts/generate-env-map.py`.",
        "",
        "| Variável | Default(s) no código | Local(is) |",
        "|---|---|---|",
    ]
    for nome, usos in sorted(itens.items()):
        defaults = sorted({d.replace("|", "\\|") for d, _ in usos})
        locais = [p for _, p in usos]
        linhas.append(
            f"| `{nome}` | `{'`, `'.join(defaults)}` | "
            + "<br>".join(f"`{p}`" for p in locais)
            + " |"
        )
    linhas.extend(["", f"Total: **{len(itens)}** variáveis.", ""])
    return "\n".join(linhas)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    out = args.output or args.root / "docs" / "env-vars.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(coletar(args.root)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
