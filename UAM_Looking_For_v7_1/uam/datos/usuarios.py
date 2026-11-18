"""Tabla usuarios: cuentas (estudiantes, encargados, administrador) y personas de ventanilla sin cuenta.

Una persona de ventanilla es alguien que trajo o retiró un objeto sin tener cuenta; su fila no tiene contraseña.
"""
import sqlite3

from .conexion import consultar, ejecutar, transaccion

ES_CUENTA = "(contrasena_hash IS NOT NULL OR rol = 'Administrador')"
COLUMNAS = 'id, nombre, cif, correo, telefono, carrera, rol, activo, contrasena_hash'


def buscar(id, con=None):
    return consultar(f'SELECT {COLUMNAS} FROM usuarios WHERE id = ?', (id,), True, con)


def buscar_por_cif(cif, con=None):
    return consultar(f'SELECT {COLUMNAS} FROM usuarios WHERE cif = ?', (cif,), True, con)


def buscar_por_correo(correo, con=None):
    return consultar(f'SELECT {COLUMNAS} FROM usuarios WHERE correo = ?', (correo,), True, con)


def buscar_cuenta(cif):
    """Cuenta que puede iniciar sesión en /login (la contraseña la verifica el servicio de cuentas)."""
    return consultar(f"SELECT {COLUMNAS} FROM usuarios WHERE cif = ? AND contrasena_hash IS NOT NULL "
                     "AND rol IN ('Encargado', 'Estudiante')", (cif,), True)


def buscar_persona_sin_cif(nombre, telefono, con=None):
    """Persona de ventanilla registrada sin CIF, con el mismo nombre y teléfono."""
    return consultar(f'SELECT {COLUMNAS} FROM usuarios WHERE cif IS NULL AND lower(nombre) = lower(?) AND telefono IS ?',
                     (nombre, telefono), True, con)


def cambiar_hash(id, contrasena_hash):
    ejecutar('UPDATE usuarios SET contrasena_hash = ? WHERE id = ?', (contrasena_hash, id))


def listar_cuentas(rol=None, busqueda=''):
    """Cuentas del panel de administración. La búsqueda escapa los comodines de LIKE (% y _)."""
    filtro = '%' + busqueda.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
    return consultar(f'''SELECT id, nombre, cif, correo, carrera, rol, activo FROM usuarios
                         WHERE {ES_CUENTA} AND NOT (rol = 'Administrador' AND activo = 0) AND (? IS NULL OR rol = ?)
                           AND (nombre LIKE ? ESCAPE '\\' OR cif LIKE ? ESCAPE '\\' OR correo LIKE ? ESCAPE '\\')
                         ORDER BY CASE rol WHEN 'Administrador' THEN 0 WHEN 'Encargado' THEN 1 ELSE 2 END, nombre''',
                     (rol, rol, filtro, filtro, filtro))


def contar_cuentas_por_rol():
    filas = consultar(f'SELECT rol, COUNT(*) AS total, SUM(activo) AS activos FROM usuarios WHERE {ES_CUENTA} '
                      "AND NOT (rol = 'Administrador' AND activo = 0) GROUP BY rol")
    return {f['rol']: {'total': f['total'], 'activos': f['activos'] or 0} for f in filas}


def insertar_cuenta(nombre, cif, correo, carrera, rol, contrasena_hash):
    return ejecutar('INSERT INTO usuarios (nombre, cif, correo, carrera, rol, contrasena_hash) VALUES (?, ?, ?, ?, ?, ?)',
                    (nombre, cif, correo, carrera, rol, contrasena_hash))


def actualizar_cuenta(id, nombre, cif, correo, carrera, rol, contrasena_hash=None):
    """Edita una cuenta. La contraseña solo cambia si llega un hash nuevo."""
    ejecutar('UPDATE usuarios SET nombre = ?, cif = ?, correo = ?, carrera = ?, rol = ?, '
             'contrasena_hash = COALESCE(?, contrasena_hash) WHERE id = ?', (nombre, cif, correo, carrera, rol, contrasena_hash, id))
    return id


def activar_cuenta_de_persona(id, correo, carrera, rol, contrasena_hash):
    """Convierte a una persona de ventanilla en cuenta. Su nombre y CIF no cambian: ya se comprobó que es ella."""
    ejecutar('UPDATE usuarios SET correo = ?, carrera = ?, rol = ?, contrasena_hash = ? WHERE id = ?',
             (correo, carrera, rol, contrasena_hash, id))
    return id


def actualizar_perfil(id, correo, carrera, telefono):
    """Lo que la persona puede corregir de su propio perfil. El nombre, el CIF y el rol solo los cambia el administrador."""
    ejecutar('UPDATE usuarios SET correo = ?, carrera = ?, telefono = ? WHERE id = ?', (correo, carrera, telefono, id))


def cambiar_activo(id, activo):
    ejecutar('UPDATE usuarios SET activo = ? WHERE id = ?', (int(activo), id))


def guardar_admin(nombre, cif, correo):
    """Registro del administrador del .env, sin hash (su clave solo vive en el .env). Devuelve su id."""
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


def quitar_admins_sobrantes(cif_actual):
    """Deja como administrador solo al del .env. Un administrador anterior (por ejemplo el de prueba que venía con
    el sistema) se borra si nunca hizo nada; si ya figura en el historial o registró algo, se desactiva: no puede
    entrar ni aparece en la lista de cuentas, pero su nombre se conserva en lo que hizo. Devuelve (borrados, desactivados)."""
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


def insertar_persona(con, nombre, rol, cif, telefono, correo):
    return ejecutar('INSERT INTO usuarios (nombre, cif, correo, telefono, rol) VALUES (?, ?, ?, ?, ?)',
                    (nombre, cif, correo, telefono, rol), con)


def completar_contacto(con, id, telefono, correo, telefono_nuevo=False):
    """Contacto de una persona ya identificada. El correo solo se completa si no lo tenía; el teléfono también,
    salvo telefono_nuevo=True (persona de ventanilla: vale el último número que dio)."""
    sql_telefono = 'COALESCE(?, telefono)' if telefono_nuevo else 'COALESCE(telefono, ?)'
    ejecutar(f'UPDATE usuarios SET telefono = {sql_telefono}, correo = COALESCE(correo, ?) WHERE id = ?',
             (telefono, correo, id), con)


def actualizar_tipo_persona(con, id, rol):
    """Solo para personas de ventanilla (sin cuenta): un visitante puede volver después como estudiante, por ejemplo."""
    ejecutar(f'UPDATE usuarios SET rol = ? WHERE id = ? AND NOT {ES_CUENTA}', (rol, id), con)


def actualizar_telefono(con, id, telefono):
    ejecutar('UPDATE usuarios SET telefono = ? WHERE id = ?', (telefono, id), con)
