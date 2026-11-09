"""Conexión a SQLite y ayudas para consultar. Todas las consultas del proyecto usan parámetros (?), nunca texto pegado.

configurar() lo llama crear_app() con la ruta de la base; las pruebas lo usan para trabajar en una base temporal.
"""
import sqlite3

AHORA = "datetime('now', 'localtime')"
_rutas = {'bd': 'database.db', 'esquema': 'schema.sql'}


def configurar(ruta_bd, ruta_esquema=None):
    _rutas['bd'] = ruta_bd
    if ruta_esquema:
        _rutas['esquema'] = ruta_esquema


def ruta_bd():
    return _rutas['bd']


def conectar():
    """Conexión nueva. Usada con «with», guarda todo al final o deshace todo si hay un error (transacción)."""
    con = sqlite3.connect(_rutas['bd'])
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')   # SQLite no revisa las llaves foráneas si no se activa
    return con


def consultar(sql, parametros=(), uno=False, con=None):
    """SELECT: una fila (uno=True) o la lista. Con con= trabaja dentro de una transacción abierta."""
    propia = con is None
    con = con or conectar()
    try:
        cursor = con.execute(sql, parametros)
        return cursor.fetchone() if uno else cursor.fetchall()
    finally:
        if propia:
            con.close()


def ejecutar(sql, parametros=(), con=None):
    """INSERT/UPDATE: devuelve el id insertado. Sin con=, abre su propia transacción y la cierra."""
    if con is not None:
        return con.execute(sql, parametros).lastrowid
    with transaccion() as propia:
        return propia.execute(sql, parametros).lastrowid


class transaccion:
    """with transaccion() as con: ... -> confirma si todo salió bien, deshace si hubo error, y siempre cierra."""

    def __enter__(self):
        self.con = conectar()
        return self.con

    def __exit__(self, tipo, valor, traza):
        try:
            if tipo is None:
                self.con.commit()
            else:
                self.con.rollback()
        finally:
            self.con.close()
        return False


def crear_tablas():
    """Ejecuta schema.sql. Todo usa IF NOT EXISTS: en una base con datos solo agrega lo que falte."""
    with open(_rutas['esquema'], encoding='utf-8') as archivo:
        script = archivo.read()
    con = conectar()
    try:
        con.executescript(script)
    finally:
        con.close()


def ahora():
    return consultar(f'SELECT {AHORA}', uno=True)[0]


def hoy():
    return ahora()[:10]
