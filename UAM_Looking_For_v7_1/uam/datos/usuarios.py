# Consultas de cuentas y personas registradas.
import sqlite3

from .conexion import consultar, ejecutar, transaccion

ES_CUENTA = "(contrasena_hash IS NOT NULL OR rol = 'Administrador')"
COLUMNAS = 'id, nombre, cif, correo, telefono, carrera, rol, activo, contrasena_hash'


# Busca una persona por id.
def buscar(id, con=None):
    return consultar(f'SELECT {COLUMNAS} FROM usuarios WHERE id = ?', (id,), True, con)


# Busca una persona por CIF.
def buscar_por_cif(cif, con=None):
    return consultar(f'SELECT {COLUMNAS} FROM usuarios WHERE cif = ?', (cif,), True, con)


# Busca una persona por correo.
def buscar_por_correo(correo, con=None):
    return consultar(f'SELECT {COLUMNAS} FROM usuarios WHERE correo = ?', (correo,), True, con)


# Cuenta que puede iniciar sesión con ese CIF.
def buscar_cuenta(cif):
    return consultar(f"SELECT {COLUMNAS} FROM usuarios WHERE cif = ? AND contrasena_hash IS NOT NULL "
                     "AND rol IN ('Encargado', 'Estudiante')", (cif,), True)


# Persona sin CIF con el mismo nombre y teléfono.
def buscar_persona_sin_cif(nombre, telefono, con=None):
    return consultar(f'SELECT {COLUMNAS} FROM usuarios WHERE cif IS NULL AND lower(nombre) = lower(?) AND telefono IS ?',
                     (nombre, telefono), True, con)


# Cambia la contraseña guardada.
def cambiar_hash(id, contrasena_hash):
    ejecutar('UPDATE usuarios SET contrasena_hash = ? WHERE id = ?', (contrasena_hash, id))


# Lista las cuentas del panel, con búsqueda.
def listar_cuentas(rol=None, busqueda=''):
    filtro = '%' + busqueda.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
    return consultar(f'''SELECT id, nombre, cif, correo, carrera, rol, activo FROM usuarios
                         WHERE {ES_CUENTA} AND NOT (rol = 'Administrador' AND activo = 0) AND (? IS NULL OR rol = ?)
                           AND (nombre LIKE ? ESCAPE '\\' OR cif LIKE ? ESCAPE '\\' OR correo LIKE ? ESCAPE '\\')
                         ORDER BY CASE rol WHEN 'Administrador' THEN 0 WHEN 'Encargado' THEN 1 ELSE 2 END, nombre''',
                     (rol, rol, filtro, filtro, filtro))


# Cuenta las cuentas por rol.
def contar_cuentas_por_rol():
    filas = consultar(f'SELECT rol, COUNT(*) AS total, SUM(activo) AS activos FROM usuarios WHERE {ES_CUENTA} '
                      "AND NOT (rol = 'Administrador' AND activo = 0) GROUP BY rol")
    return {f['rol']: {'total': f['total'], 'activos': f['activos'] or 0} for f in filas}


# Crea una cuenta.
def insertar_cuenta(nombre, cif, correo, carrera, rol, contrasena_hash):
    return ejecutar('INSERT INTO usuarios (nombre, cif, correo, carrera, rol, contrasena_hash) VALUES (?, ?, ?, ?, ?, ?)',
                    (nombre, cif, correo, carrera, rol, contrasena_hash))


# Edita una cuenta.
def actualizar_cuenta(id, nombre, cif, correo, carrera, rol, contrasena_hash=None):
    ejecutar('UPDATE usuarios SET nombre = ?, cif = ?, correo = ?, carrera = ?, rol = ?, '
             'contrasena_hash = COALESCE(?, contrasena_hash) WHERE id = ?', (nombre, cif, correo, carrera, rol, contrasena_hash, id))
    return id


# Convierte a una persona de ventanilla en cuenta.
def activar_cuenta_de_persona(id, correo, carrera, rol, contrasena_hash):
    ejecutar('UPDATE usuarios SET correo = ?, carrera = ?, rol = ?, contrasena_hash = ? WHERE id = ?',
             (correo, carrera, rol, contrasena_hash, id))
    return id


# Guarda los cambios de «Mi perfil».
def actualizar_perfil(id, correo, carrera, telefono):
    ejecutar('UPDATE usuarios SET correo = ?, carrera = ?, telefono = ? WHERE id = ?', (correo, carrera, telefono, id))


# Activa o desactiva una cuenta.
def cambiar_activo(id, activo):
    ejecutar('UPDATE usuarios SET activo = ? WHERE id = ?', (int(activo), id))


# Guarda al administrador del .env.
def guardar_admin(nombre, cif, correo):
    with transaccion() as con:
        fila = buscar_por_cif(cif, con)
        if fila:
            con.execute("UPDATE usuarios SET nombre = ?, rol = 'Administrador', contrasena_hash = NULL, activo = 1 WHERE id = ?",
                        (nombre, fila['id']))
            return fila['id']
        if buscar_por_correo(correo, con):
            correo = f'{cif.lower()}@admin.local'
        return con.execute("INSERT INTO usuarios (nombre, cif, correo, carrera, rol) VALUES (?, ?, ?, 'Administración', 'Administrador')",
                           (nombre, cif, correo)).lastrowid


# Deja como administrador solo al del .env.
def quitar_admins_sobrantes(cif_actual):
    borrados = desactivados = 0
    for fila in consultar("SELECT id, activo FROM usuarios WHERE rol = 'Administrador' AND cif IS NOT ?", (cif_actual,)):
        try:
            ejecutar('DELETE FROM usuarios WHERE id = ?', (fila['id'],))
            borrados += 1
        except sqlite3.IntegrityError:   # tiene movimientos a su nombre: la base no deja borrarlo
            if fila['activo']:
                ejecutar('UPDATE usuarios SET activo = 0 WHERE id = ?', (fila['id'],))
                desactivados += 1
    return borrados, desactivados


# Registra a una persona de ventanilla.
def insertar_persona(con, nombre, rol, cif, telefono, correo):
    return ejecutar('INSERT INTO usuarios (nombre, cif, correo, telefono, rol) VALUES (?, ?, ?, ?, ?)',
                    (nombre, cif, correo, telefono, rol), con)


# Completa el teléfono o correo que faltaba.
def completar_contacto(con, id, telefono, correo, telefono_nuevo=False):
    sql_telefono = 'COALESCE(?, telefono)' if telefono_nuevo else 'COALESCE(telefono, ?)'
    ejecutar(f'UPDATE usuarios SET telefono = {sql_telefono}, correo = COALESCE(correo, ?) WHERE id = ?',
             (telefono, correo, id), con)


# Cambia el tipo de una persona sin cuenta.
def actualizar_tipo_persona(con, id, rol):
    ejecutar(f'UPDATE usuarios SET rol = ? WHERE id = ? AND NOT {ES_CUENTA}', (rol, id), con)


# Cambia el teléfono de una persona.
def actualizar_telefono(con, id, telefono):
    ejecutar('UPDATE usuarios SET telefono = ? WHERE id = ?', (telefono, id), con)
