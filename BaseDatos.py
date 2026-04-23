"""
Capa de base de datos: ejecuta SELECT contra MySQL y describe el esquema real (introspección).
No crea bases ni tablas: se conecta a la base que ya tengas.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pymysql


def leer_config_mysql() -> dict[str, Any]:
    """
    Credenciales y base desde variables de entorno (no van en el código).
    """
    host = (os.environ.get("MYSQL_HOST") or "127.0.0.1").strip()
    port = int(os.environ.get("MYSQL_PORT") or "3306")
    user = (os.environ.get("MYSQL_USER") or "").strip()
    password = os.environ.get("MYSQL_PASSWORD")
    if password is None:
        password = ""
    database = (os.environ.get("MYSQL_DATABASE") or "").strip()
    if not user or not database:
        raise RuntimeError(
            "Define MYSQL_USER y MYSQL_DATABASE (por ejemplo accidentes). "
            "Opcional: MYSQL_HOST, MYSQL_PORT, MYSQL_PASSWORD."
        )
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


def _conectar(cfg: dict[str, Any]) -> pymysql.connections.Connection:
    return pymysql.connect(
        host=cfg["host"],
        port=int(cfg["port"]),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
    )


def describir_esquema_mysql(cfg: dict[str, Any]) -> str:
    """
    Arma un texto para el modelo de IA con tablas y columnas reales de la base conectada.
    """
    sql = """
        SELECT c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE,
               c.COLUMN_KEY, c.COLUMN_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS c
        INNER JOIN INFORMATION_SCHEMA.TABLES t
          ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
        WHERE c.TABLE_SCHEMA = %s AND t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION
    """
    con = _conectar(cfg)
    try:
        with con.cursor() as cur:
            cur.execute(sql, (cfg["database"],))
            filas = cur.fetchall()
        if not filas:
            raise ValueError(
                f"No se encontraron tablas en la base `{cfg['database']}`. "
                "Verifica MYSQL_DATABASE."
            )

        lineas = [
            f"Motor: MySQL. Base (schema): `{cfg['database']}`",
            "Esquema obtenido por introspección (INFORMATION_SCHEMA):",
            "",
        ]
        actual: str | None = None
        for tabla, col, dtype, nullable, col_key, col_type in filas:
            if tabla != actual:
                if actual is not None:
                    lineas.append("")
                lineas.append(f"Tabla `{tabla}`")
                actual = tabla
            flags: list[str] = []
            if col_key == "PRI":
                flags.append("PRIMARY KEY")
            if nullable == "NO":
                flags.append("NOT NULL")
            sufijo = f" ({', '.join(flags)})" if flags else ""
            tipo = col_type or dtype or ""
            lineas.append(f"  - `{col}`: {tipo}{sufijo}")
        lineas.append("")
        lineas.append(
            "Genera únicamente SELECT válido para MySQL usando exactamente estos nombres "
            "de tablas y columnas (respeta mayúsculas/minúsculas si aplica)."
        )
        return "\n".join(lineas)
    finally:
        con.close()


def _asegurar_solo_lectura(sql: str) -> None:
    limpio = sql.strip()
    if not limpio.lower().startswith("select"):
        raise ValueError("Solo se permiten consultas SELECT.")
    nucleo = limpio.rstrip().rstrip(";").strip()
    if ";" in nucleo:
        raise ValueError("No se permiten múltiples sentencias SQL.")


def ejecutar_consulta(
    payload_persistencia: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """
    Ejecuta la sentencia generada en la capa de persistencia contra MySQL.
    """
    if payload_persistencia.get("capa") != "persistencia":
        raise ValueError("La entrada de base de datos debe ser la salida de la capa persistencia.")

    sql = payload_persistencia.get("sql") or ""
    _asegurar_solo_lectura(sql)

    con = _conectar(cfg)
    try:
        with con.cursor() as cur:
            cur.execute(sql)
            columnas = [d[0] for d in (cur.description or [])]
            raw = cur.fetchall()
        filas: list[list[Any]] = []
        for row in raw:
            filas.append([_serializar_celda(v) for v in row])
    finally:
        con.close()

    return {
        "capa": "basedatos",
        "motor": "mysql",
        "mysql_database": cfg["database"],
        "mysql_host": cfg["host"],
        "columnas": columnas,
        "filas": filas,
        "sql_ejecutado": sql.strip(),
    }


def _serializar_celda(val: Any) -> Any:
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    return val


def ejecutar_consulta_desde_json(texto: str, cfg: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(texto)
    return ejecutar_consulta(data, cfg)
