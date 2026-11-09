"""Reglas del sistema (capa de servicios).

Las funciones que cambian datos devuelven (True, resultado) o (False, mensaje para el usuario). No conocen Flask:
reciben datos simples, así se pueden probar sin servidor. Python revisa lo que depende de quién está conectado y da
mensajes claros; la base (schema.sql) vuelve a revisar cada regla con CHECK y triggers.
"""
import sqlite3

from ..datos.conexion import transaccion

MENSAJE_RECHAZO_BD = 'La base de datos rechazó los datos: revisa el formulario.'


def en_transaccion(operacion):
    """Ejecuta operacion(con) en una transacción. Si la base la rechaza, se deshace todo y se devuelve el motivo:
    los triggers ya traen el mensaje en español; un CHECK o un UNIQUE solo dicen qué columna falló."""
    try:
        with transaccion() as con:
            resultado = operacion(con)
            if resultado[0] is False:
                con.rollback()   # una validación falló a mitad de camino: no queda nada a medias
            return resultado
    except sqlite3.IntegrityError as error:
        motivo = str(error)
        return False, (MENSAJE_RECHAZO_BD if 'constraint failed' in motivo else motivo)
