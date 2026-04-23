"""
Capa de negocios: interpreta la selección del usuario y define cómo se procesará la información.
"""

from __future__ import annotations

import json
from typing import Any


def _meta_por_estado(payload_presentacion: dict[str, Any]) -> dict[str, Any]:
    return {
        "intencion": "ranking_por_dimension",
        "dimension_principal": "estado",
        "metrica": "conteo_accidentes",
        "agregaciones": ["COUNT(*) AS total_accidentes"],
        "agrupar_por": ["estado"],
        "ordenar": "total_accidentes DESC",
        "limite_sugerido": 15,
        "notas_procesamiento": "Se busca comparar estados por volumen de accidentes.",
    }


def _meta_dia_vs_noche(payload_presentacion: dict[str, Any]) -> dict[str, Any]:
    return {
        "intencion": "comparacion_categorica",
        "dimension_principal": "periodo",
        "metrica": "conteo_accidentes",
        "agregaciones": ["COUNT(*) AS total_accidentes"],
        "agrupar_por": ["periodo"],
        "ordenar": "total_accidentes DESC",
        "limite_sugerido": None,
        "notas_procesamiento": "Comparar accidentes en Día frente a Noche según la columna periodo.",
    }


def _meta_por_hora(payload_presentacion: dict[str, Any]) -> dict[str, Any]:
    return {
        "intencion": "distribucion_temporal",
        "dimension_principal": "hora",
        "metrica": "conteo_accidentes",
        "agregaciones": ["COUNT(*) AS total_accidentes"],
        "agrupar_por": ["hora"],
        "ordenar": "total_accidentes DESC",
        "limite_sugerido": 24,
        "notas_procesamiento": "Identificar horas punta (0-23).",
    }


def _meta_por_dia_semana(payload_presentacion: dict[str, Any]) -> dict[str, Any]:
    return {
        "intencion": "distribucion_semanal",
        "dimension_principal": "dia_semana",
        "metrica": "conteo_accidentes",
        "agregaciones": ["COUNT(*) AS total_accidentes"],
        "agrupar_por": ["dia_semana"],
        "ordenar": "total_accidentes DESC",
        "limite_sugerido": 7,
        "notas_procesamiento": "Ordenar resultados por total descendente; la tabla usa nombres en español.",
    }


_HANDLERS = {
    "por_estado": _meta_por_estado,
    "dia_vs_noche": _meta_dia_vs_noche,
    "por_hora": _meta_por_hora,
    "por_dia_semana": _meta_por_dia_semana,
}


def ejecutar_negocios(payload_presentacion: dict[str, Any]) -> dict[str, Any]:
    """
    Recibe la salida de Presentación y devuelve metadata de negocio para Persistencia.
    """
    if payload_presentacion.get("capa") != "presentacion":
        raise ValueError("La entrada de negocios debe ser la salida de la capa presentacion.")
    pregunta_id = payload_presentacion.get("pregunta_id")
    if pregunta_id not in _HANDLERS:
        raise ValueError(f"pregunta_id desconocido: {pregunta_id!r}")

    meta = _HANDLERS[pregunta_id](payload_presentacion)
    return {
        "capa": "negocios",
        "pregunta_id": pregunta_id,
        "pregunta_texto": payload_presentacion.get("pregunta_texto"),
        "meta": meta,
        "contexto_presentacion": {
            k: v for k, v in payload_presentacion.items() if k != "capa"
        },
    }


def ejecutar_negocios_desde_json(texto: str) -> dict[str, Any]:
    data = json.loads(texto)
    return ejecutar_negocios(data)
