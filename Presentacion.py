"""
Capa de presentación: CLI interactiva para elegir la consulta del usuario.
"""

from __future__ import annotations

import os
import random
import time
from typing import Any

from rich import box
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

CONSOLE_THEME = Theme(
    {
        "pregunta": "bold cyan",
        "titulo": "bold magenta",
        "ok": "green",
        "muted": "dim",
    }
)

PREGUNTAS: list[dict[str, Any]] = [
    {
        "id": "por_estado",
        "texto": "¿En qué estado ocurren más accidentes?",
    },
    {
        "id": "dia_vs_noche",
        "texto": "¿Cómo influye el día y la noche?",
    },
    {
        "id": "por_hora",
        "texto": "¿En qué horas ocurren más accidentes?",
    },
    {
        "id": "por_dia_semana",
        "texto": "¿Qué día de la semana ocurren más accidentes?",
    },
]


def _intro_cielo_estrellas(console: Console, duracion: float = 2.2) -> None:
    """
    Breve animación tipo lluvia de estrellas antes del menú (solo modo interactivo).

    Desactivar: ``export KOPEPOD_NO_ANIM=1`` (terminal lento, scripts, accesibilidad).
    """
    if os.environ.get("KOPEPOD_NO_ANIM", "").strip().lower() in ("1", "true", "yes", "on"):
        return

    ancho = min(max(console.size.width - 2, 36), 76)
    alto = 11
    paleta = ("cyan", "bright_blue", "blue", "magenta", "dim cyan")

    def un_frame() -> Text:
        t = Text()
        for _ in range(alto):
            for _ in range(ancho):
                r = random.random()
                if r < 0.065:
                    ch = random.choice("*·✧✦˚")
                    t.append(ch, style=random.choice(paleta))
                elif r < 0.11:
                    t.append(".", style="dim")
                else:
                    t.append(" ")
            t.append("\n")
        return t

    fin = time.time() + duracion
    with Live(
        un_frame(),
        refresh_per_second=10,
        console=console,
        transient=True,
        vertical_overflow="visible",
    ) as live:
        while time.time() < fin:
            live.update(un_frame())
    console.print()


def _banner(console: Console) -> None:
    subtitulo = Align.center(
        "[muted]Análisis de accidentes · capa de presentación[/muted]"
    )
    console.print()
    console.print(
        Panel.fit(
            "[titulo]KOPEPOD[/titulo]\n[muted]Consultas estadísticas sobre la base de datos[/muted]",
            box=box.DOUBLE_EDGE,
            border_style="magenta",
            padding=(1, 4),
        ),
        justify="center",
    )
    console.print(subtitulo)
    console.print()


def _tabla_menu(console: Console) -> None:
    tabla = Table(
        title="[pregunta]Elige una pregunta[/pregunta]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="bright_blue",
    )
    tabla.add_column("#", justify="right", style="cyan", no_wrap=True)
    tabla.add_column("Pregunta", style="white")
    for i, item in enumerate(PREGUNTAS, start=1):
        tabla.add_row(str(i), item["texto"])
    console.print(tabla)
    console.print()


_IDS_VALIDOS = {item["id"] for item in PREGUNTAS}


def ejecutar_presentacion(
    *,
    console: Console | None = None,
    opcion: int | None = None,
    pregunta_id: str | None = None,
) -> dict[str, Any]:
    """
    Devuelve el payload estándar de esta capa.

    Modo interactivo (default): banner, menú y prompt.
    Modo no interactivo: pasa ``opcion`` (1-4) o ``pregunta_id`` (por_estado, dia_vs_noche, …).
    """
    cons = console or Console(theme=CONSOLE_THEME)

    seleccion: dict[str, Any]
    if pregunta_id is not None:
        pid = pregunta_id.strip()
        if pid not in _IDS_VALIDOS:
            raise ValueError(
                f"pregunta_id inválido: {pid!r}. Use uno de: {', '.join(sorted(_IDS_VALIDOS))}"
            )
        seleccion = next(p for p in PREGUNTAS if p["id"] == pid)
    elif opcion is not None:
        if opcion < 1 or opcion > len(PREGUNTAS):
            raise ValueError(f"opcion debe ser 1..{len(PREGUNTAS)}, recibí: {opcion}")
        seleccion = PREGUNTAS[opcion - 1]
    else:
        _intro_cielo_estrellas(cons)
        _banner(cons)
        _tabla_menu(cons)
        elegido = IntPrompt.ask(
            "[bold green]Número de opción[/bold green]",
            choices=[str(i) for i in range(1, len(PREGUNTAS) + 1)],
            show_choices=False,
        )
        seleccion = PREGUNTAS[int(elegido) - 1]

    salida: dict[str, Any] = {
        "capa": "presentacion",
        "pregunta_id": seleccion["id"],
        "pregunta_texto": seleccion["texto"],
    }
    modo = " (sin menú: CLI)" if (opcion is not None or pregunta_id is not None) else ""
    cons.print(
        Panel(
            f"[ok]Seleccionaste:[/ok] [bold]{seleccion['texto']}[/bold]{modo}",
            border_style="green",
            box=box.HEAVY,
        )
    )
    return salida


if __name__ == "__main__":
    from rich.console import Console as _C

    import json

    print(json.dumps(ejecutar_presentacion(console=_C(theme=CONSOLE_THEME)), ensure_ascii=False, indent=2))
