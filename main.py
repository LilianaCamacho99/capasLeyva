#!/usr/bin/env python3
"""
python main.py completo
python main.py capa presentacion -o salida.json
python main.py capa negocios -i salida.json -o negocios.json
python main.py capa persistencia -i negocios.json -o sql.json
python main.py capa basedatos -i sql.json -o resultado.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from dotenv import load_dotenv

# Carga variables antes de importar capas que las lean al ejecutarse.
load_dotenv(Path(__file__).resolve().parent / ".env")

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table

from LIBS import BaseDatos, Negocios, Persistencia, Presentacion


def _leer_json(entrada: TextIO) -> Any:
    texto = entrada.read()
    if not texto.strip():
        raise SystemExit("Entrada vacía: se esperaba JSON.")
    return json.loads(texto)


def _escribir_json(salida: TextIO, data: Any) -> None:
    json.dump(data, salida, ensure_ascii=False, indent=2)
    salida.write("\n")


def _abrir_entrada(ruta: str | None) -> TextIO:
    if ruta is None or ruta == "-":
        return sys.stdin
    path = Path(ruta)
    if not path.is_file():
        raise SystemExit(
            f"No existe el archivo de entrada: {path.resolve()}\n\n"
            "Cada capa (excepto presentación) lee el JSON que generó la anterior. "
            "Guarda ese JSON con -o en el paso previo.\n\n"
            "Ejemplo encadenado:\n"
            "  python main.py capa presentacion -o salida.json\n"
            "  python main.py capa negocios -i salida.json -o negocios.json\n"
            "  python main.py capa persistencia -i negocios.json -o sql.json\n"
            "  python main.py capa basedatos -i sql.json -o resultado.json"
        )
    return path.open(encoding="utf-8")


def _abrir_salida(ruta: str | None) -> TextIO:
    if ruta is None or ruta == "-":
        return sys.stdout
    path = Path(ruta)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("w", encoding="utf-8")


def _cfg_mysql() -> dict[str, Any]:
    return BaseDatos.leer_config_mysql()


def _eco_capa_en_terminal(capa: str, data: dict[str, Any]) -> None:
    """Si la salida fue a archivo, repite un resumen legible en la terminal."""
    cons = Console()
    cons.print()
    cons.print(Rule(f"[bold green]Salida de capa «{capa}» (vista en terminal)[/bold green]"))
    if capa == "basedatos":
        _mostrar_resultado_tabla(cons, data)
        return
    if capa == "persistencia":
        sql = data.get("sql") or ""
        if sql.strip():
            cons.print(
                Panel(
                    Syntax(sql, "sql", theme="monokai", word_wrap=True),
                    title="SQL generado",
                    border_style="blue",
                )
            )
        vista = {k: v for k, v in data.items() if k != "esquema_introspeccion"}
        if "esquema_introspeccion" in data:
            vista["_nota"] = (
                "El texto largo `esquema_introspeccion` solo está en el archivo JSON (-o)."
            )
        cons.print(
            Panel(
                json.dumps(vista, ensure_ascii=False, indent=2),
                title="Resto del JSON",
                border_style="cyan",
            )
        )
        return
    cons.print(
        Panel(
            json.dumps(data, ensure_ascii=False, indent=2),
            title="JSON de esta capa",
            border_style="cyan",
        )
    )


def _mostrar_resultado_tabla(console: Console, resultado: dict[str, Any]) -> None:
    columnas = resultado.get("columnas") or []
    filas = resultado.get("filas") or []
    tabla = Table(
        title="Resultado",
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
    )
    for c in columnas:
        tabla.add_column(str(c))
    for fila in filas:
        tabla.add_row(*[str(x) for x in fila])
    console.print(Panel(tabla, border_style="green", title="Base de datos"))


def _trace_pipeline(console: Console, quiet: bool, titulo: str, detalle: Any = None) -> None:
    if quiet:
        return
    console.print(Rule(f"[bold cyan]{titulo}[/bold cyan]"))
    if detalle is not None:
        console.print(detalle)
    console.print()


def cmd_completo(args: argparse.Namespace) -> None:
    cfg = _cfg_mysql()
    console = Console()
    q = getattr(args, "quiet", False)

    _trace_pipeline(
        console,
        q,
        "0 - Configuración",
        f"[dim]MySQL {cfg['user']}@{cfg['host']}:{cfg['port']} - base `{cfg['database']}`[/dim]",
    )

    p = Presentacion.ejecutar_presentacion(console=console)
    _trace_pipeline(
        console,
        q,
        "1 - Presentación (entrada del usuario)",
        f"  pregunta_id: [bold]{p.get('pregunta_id')}[/bold]\n"
        f"  texto: {p.get('pregunta_texto', '')}",
    )

    n = Negocios.ejecutar_negocios(p)
    meta_txt = json.dumps(n.get("meta", {}), ensure_ascii=False, indent=2)
    _trace_pipeline(
        console,
        q,
        "2 - Negocios (cómo se procesará la información)",
        Panel(meta_txt, border_style="yellow", title="metadata -> persistencia"),
    )

    per = Persistencia.ejecutar_persistencia(n, cfg)
    sql = per.get("sql") or ""
    sql_syntax = Syntax(sql, "sql", theme="monokai", word_wrap=True, line_numbers=False)
    _trace_pipeline(
        console,
        q,
        "3 - Persistencia (SQL vía API; copiable para corroborar en MySQL)",
        Panel(sql_syntax, border_style="blue", title="SELECT generado"),
    )

    b = BaseDatos.ejecutar_consulta(per, cfg)
    n_filas = len(b.get("filas") or [])
    n_cols = len(b.get("columnas") or [])
    _trace_pipeline(
        console,
        q,
        "4 - Base de datos (ejecución y devolución al usuario)",
        f"[green]Consulta ejecutada correctamente[/green] - {n_filas} filas x {n_cols} columnas\n"
        f"[dim]Para verificar a mano, pega el SQL del paso 3 en tu cliente MySQL; el resultado debe coincidir.[/dim]",
    )

    _mostrar_resultado_tabla(console, b)
    if args.dump_json:
        with _abrir_salida(args.dump_json) as fh:
            _escribir_json(
                fh,
                {
                    "presentacion": p,
                    "negocios": n,
                    "persistencia": per,
                    "basedatos": b,
                },
            )


def cmd_capa(args: argparse.Namespace) -> None:
    capa = args.capa
    cfg = None
    if capa in ("persistencia", "basedatos"):
        cfg = _cfg_mysql()

    entrada = _abrir_entrada(args.entrada)
    salida = _abrir_salida(args.salida)
    guarda_en_archivo = args.salida not in (None, "-")

    try:
        if capa == "presentacion":
            cons = Console()
            data = Presentacion.ejecutar_presentacion(
                console=cons,
                opcion=getattr(args, "opcion", None),
                pregunta_id=getattr(args, "pregunta_id", None),
            )
        elif capa == "negocios":
            data = Negocios.ejecutar_negocios(_leer_json(entrada))
        elif capa == "persistencia":
            assert cfg is not None
            data = Persistencia.ejecutar_persistencia(_leer_json(entrada), cfg)
        elif capa == "basedatos":
            assert cfg is not None
            data = BaseDatos.ejecutar_consulta(_leer_json(entrada), cfg)
        else:
            raise SystemExit(f"Capa desconocida: {capa}")
    finally:
        if entrada is not sys.stdin:
            entrada.close()

    try:
        _escribir_json(salida, data)
    finally:
        if salida is not sys.stdout:
            salida.close()

    if guarda_en_archivo:
        _eco_capa_en_terminal(capa, data)


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Análisis de accidentes por capas (presentación → negocios → persistencia → MySQL). "
            "Usa tu base existente; no crea bases ni tablas."
        )
    )

    sub = parser.add_subparsers(dest="comando", required=True)

    p_full = sub.add_parser(
        "completo",
        help="Ejecuta todas las capas en secuencia (CLI interactiva).",
    )
    p_full.add_argument(
        "--dump-json",
        metavar="ARCHIVO",
        help="Opcional: guarda el payload de todas las capas en un JSON.",
    )
    p_full.add_argument(
        "--quiet",
        action="store_true",
        help="Oculta el detalle del pipeline (solo menú + tabla final).",
    )
    p_full.set_defaults(func=cmd_completo)

    p_capa = sub.add_parser("capa", help="Ejecuta una sola capa (entrada/salida JSON).")
    p_capa.add_argument(
        "capa",
        choices=["presentacion", "negocios", "persistencia", "basedatos"],
        help="Nombre de la capa.",
    )
    p_capa.add_argument(
        "-i",
        "--entrada",
        default=None,
        help=(
            "JSON de la capa anterior (archivo o '-' para stdin). "
            "Negocios←presentación, persistencia←negocios, basedatos←persistencia."
        ),
    )
    p_capa.add_argument(
        "-o",
        "--salida",
        default="-",
        help=(
            "Archivo JSON de salida (recomendado al encadenar capas; default: stdout). "
            "Si es un archivo, también se imprime un resumen en la terminal."
        ),
    )
    pre = p_capa.add_mutually_exclusive_group()
    pre.add_argument(
        "--opcion",
        type=int,
        choices=[1, 2, 3, 4],
        metavar="N",
        help="Solo presentación: 1-4 sin menú interactivo.",
    )
    pre.add_argument(
        "--pregunta-id",
        metavar="ID",
        help=(
            "Solo presentación: por_estado | dia_vs_noche | por_hora | por_dia_semana "
            "(sin menú)."
        ),
    )
    p_capa.set_defaults(func=cmd_capa)

    return parser


def main() -> None:
    parser = construir_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
