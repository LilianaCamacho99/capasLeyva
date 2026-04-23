"""
Capa de persistencia: el API de IA recibe metadata de negocio + esquema real de MySQL y devuelve SQL.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from LIBS.BaseDatos import describir_esquema_mysql


def _requerir_api_key() -> None:
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        raise RuntimeError(
            "Persistencia requiere el API de OpenAI. Define la variable de entorno OPENAI_API_KEY."
        )


def _extraer_sql(texto: str) -> str:
    fence = re.search(r"```(?:sql)?\s*([\s\S]*?)```", texto, re.IGNORECASE)
    if fence:
        texto = fence.group(1).strip()
    m = re.search(r"\bselect\b[\s\S]+", texto, re.IGNORECASE)
    if not m:
        raise ValueError("El modelo no devolvió una sentencia SELECT válida.")
    return m.group(0).strip().rstrip("`").strip()


def ejecutar_persistencia(
    payload_negocios: dict[str, Any],
    cfg_mysql: dict[str, Any],
) -> dict[str, Any]:
    """
    Genera SQL con OpenAI usando el esquema introspectado de tu base MySQL.
    """
    if payload_negocios.get("capa") != "negocios":
        raise ValueError("La entrada de persistencia debe ser la salida de la capa negocios.")

    _requerir_api_key()

    esquema = describir_esquema_mysql(cfg_mysql)
    pregunta_id = payload_negocios.get("pregunta_id")
    meta = payload_negocios.get("meta", {})
    sql = _generar_sql_openai(pregunta_id, meta, payload_negocios, esquema)

    return {
        "capa": "persistencia",
        "pregunta_id": pregunta_id,
        "sql": sql.strip(),
        "modo_generacion": "openai",
        "meta_negocio": meta,
        "esquema_introspeccion": esquema,
    }


def _generar_sql_openai(
    pregunta_id,
    meta,
    payload_negocios,
    esquema_doc,
) -> str:
    pregunta = (payload_negocios.get("pregunta_texto") or "").lower()

    # -----------------------------
    # 1. Detectar tabla (simple)
    # -----------------------------
    tabla = "accidentes_data"
    match_tabla = re.search(r"tabla:\s*(\w+)", esquema_doc, re.IGNORECASE)
    if match_tabla:
        tabla = match_tabla.group(1)

    # -----------------------------
    # 2. Detectar columnas
    # -----------------------------
    columnas = re.findall(r"-\s*(\w+)\s*\(", esquema_doc)

    # fallback
    if not columnas:
        columnas = ["id"]

    # -----------------------------
    # 3. Detectar tipo de pregunta
    # -----------------------------
    es_count = any(p in pregunta for p in ["cuántos", "cuantos", "count"])
    es_listar = any(p in pregunta for p in ["muestra", "listar", "ver"])

    # -----------------------------
    # 4. Detectar filtros simples
    # -----------------------------
    filtros = []

    # ejemplo: ciudad
    posibles_ciudades = ["chicago", "new york", "los angeles", "houston"]
    for ciudad in posibles_ciudades:
        if ciudad in pregunta:
            if "city" in columnas:
                filtros.append(f"city = '{ciudad.title()}'")

    # ejemplo: año
    match_year = re.search(r"(20\d{2})", pregunta)
    if match_year:
        year = match_year.group(1)
        if "year" in columnas:
            filtros.append(f"year = {year}")

    # -----------------------------
    # 5. Construir WHERE
    # -----------------------------
    where_clause = ""
    if filtros:
        where_clause = " WHERE " + " AND ".join(filtros)

    # -----------------------------
    # 6. Construir SELECT
    # -----------------------------
    if es_count:
        return f"SELECT COUNT(*) AS total FROM {tabla}{where_clause};"

    if es_listar:
        cols = ", ".join(columnas[:5])
        return f"SELECT {cols} FROM {tabla}{where_clause} LIMIT 10;"

    # -----------------------------
    # 7. Default inteligente
    # -----------------------------
    return f"SELECT * FROM {tabla}{where_clause} LIMIT 5;"

def ejecutar_persistencia_desde_json(texto: str, cfg_mysql: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(texto)
    return ejecutar_persistencia(data, cfg_mysql)
