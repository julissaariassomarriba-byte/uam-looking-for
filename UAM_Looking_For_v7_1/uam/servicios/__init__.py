# Reglas del sistema: devuelven (True, resultado) o (False, mensaje).
import sqlite3

from ..datos.conexion import transaccion

MENSAJE_RECHAZO_BD = 'La base de datos rechazó los datos: revisa el formulario.'


# Ejecuta una operación en una transacción y traduce el error de la base.
def en_transaccion(operacion):
    try:
        with transaccion() as con:
            resultado = operacion(con)
            if resultado[0] is False:
                con.rollback()   # una validación falló a mitad de camino: no queda nada a medias
            return resultado
    except sqlite3.IntegrityError as error:
        motivo = str(error)
        return False, (MENSAJE_RECHAZO_BD if 'constraint failed' in motivo else motivo)
