# Conexión a SQLite y transacciones.
import sqlite3

AHORA = "datetime('now', 'localtime')"
_rutas = {'bd': 'database.db', 'esquema': 'schema.sql'}


# Guarda la ruta de la base y del esquema.
def configurar(ruta_bd, ruta_esquema=None):
    _rutas['bd'] = ruta_bd
    if ruta_esquema:
        _rutas['esquema'] = ruta_esquema


# Ruta del archivo de la base.
def ruta_bd():
    return _rutas['bd']


# Abre una conexión nueva con llaves foráneas activas.
def conectar():
    con = sqlite3.connect(_rutas['bd'])
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')   # SQLite no revisa las llaves foráneas si no se activa
    return con


# Ejecuta un SELECT: una fila o la lista.
def consultar(sql, parametros=(), uno=False, con=None):
    propia = con is None
    con = con or conectar()
    try:
        cursor = con.execute(sql, parametros)
        return cursor.fetchone() if uno else cursor.fetchall()
    finally:
        if propia:
            con.close()


# Ejecuta un INSERT o UPDATE y devuelve el id insertado.
def ejecutar(sql, parametros=(), con=None):
    if con is not None:
        return con.execute(sql, parametros).lastrowid
    with transaccion() as propia:
        return propia.execute(sql, parametros).lastrowid


# Transacción: guarda todo si sale bien, deshace todo si hay un error.
class transaccion:
    # Abre la transacción.
    def __enter__(self):
        self.con = conectar()
        return self.con

    # Guarda todo si salió bien; si hubo error, deshace todo.
    def __exit__(self, tipo, valor, traza):
        try:
            if tipo is None:
                self.con.commit()
            else:
                self.con.rollback()
        finally:
            self.con.close()
        return False


# Crea o completa las tablas con schema.sql, sin borrar datos.
def crear_tablas():
    with open(_rutas['esquema'], encoding='utf-8') as archivo:
        script = archivo.read()
    con = conectar()
    try:
        con.executescript(script)
    finally:
        con.close()


# Fecha y hora actual en texto.
def ahora():
    return consultar(f'SELECT {AHORA}', uno=True)[0]


# Fecha de hoy en texto.
def hoy():
    return ahora()[:10]
