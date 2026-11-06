"""Acceso a SQLite: conexión y consultas. Las reglas del sistema están en logica.py.

En v7.1 la base escribe sola el historial de los hechos (registro, entrega, reclamaciones, recuperación y
devolución) y pone el estado del objeto según lo que pasó. Aquí solo se anotan a mano las acciones que no
nacen de otra tabla: cambio de estado bajo custodia, ubicación, foto y descripción pública.
"""
import sqlite3

RUTA_BD, RUTA_ESQUEMA = 'database.db', 'schema.sql'
AHORA = "datetime('now', 'localtime')"
CUENTA = "(contrasena_hash IS NOT NULL OR rol = 'Administrador')"   # filas que son cuentas (las demás son personas de ventanilla)

# Objeto con quién lo trajo. Nunca se lee la columna foto aquí: solo si tiene una (tiene_foto).
SQL_OBJETOS = 'SELECT {} FROM objetos o LEFT JOIN usuarios p ON p.id = o.reportado_por'
COLUMNAS_PERSONAL = ('o.id, o.titulo, o.descripcion, o.descripcion_publica, o.categoria, o.lugar_encontrado, o.ubicacion, '
                     'o.fecha, o.hora, o.estado, o.registrado_por, o.reportado_por, o.foto_publica, o.foto IS NOT NULL AS tiene_foto, '
                     'p.nombre AS reportado_nombre, p.rol AS reportado_tipo, p.cif AS reportado_cif, '
                     'p.telefono AS reportado_telefono, p.correo AS reportado_correo')
# Lo único que ve un estudiante: sin lugar del hallazgo, fecha exacta, hora, descripción interna ni quién lo trajo.
COLUMNAS_PUBLICAS = ('o.id, o.titulo, o.categoria, o.estado, o.descripcion_publica, substr(o.fecha, 1, 7) AS periodo, '
                     'o.ubicacion, o.foto IS NOT NULL AND o.foto_publica = 1 AS tiene_foto')


# Conexión. Usada con «with», guarda todo al final o deshace todo si hay un error (transacción).
def conectar():
    con = sqlite3.connect(RUTA_BD)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')  # SQLite no revisa las llaves foráneas si no se activa
    return con


# SELECT: una fila (uno=True) o la lista. Con con= trabaja dentro de una transacción abierta.
def consultar(sql, parametros=(), uno=False, con=None):
    cursor = (con or conectar()).execute(sql, parametros)
    return cursor.fetchone() if uno else cursor.fetchall()


# INSERT/UPDATE: devuelve el id insertado.
def ejecutar(sql, parametros=(), con=None):
    if con:
        return con.execute(sql, parametros).lastrowid
    with conectar() as con:
        return con.execute(sql, parametros).lastrowid


def crear_tablas():
    with open(RUTA_ESQUEMA, encoding='utf-8') as archivo:
        conectar().executescript(archivo.read())


def ahora():
    return consultar(f'SELECT {AHORA}', uno=True)[0]


# Texto aleatorio generado por SQLite (token de los formularios y clave de sesión de respaldo).
def token():
    return consultar('SELECT lower(hex(randomblob(24)))', uno=True)[0]


# Usuarios: cuentas y personas de ventanilla

def buscar_usuario(id, con=None):
    return consultar('SELECT * FROM usuarios WHERE id = ?', (id,), True, con)


def buscar_por_cif(cif, con=None):
    return consultar('SELECT * FROM usuarios WHERE cif = ?', (cif,), True, con)


# Cuenta que puede iniciar sesión en /login (la contraseña la verifica logica.py con el hash).
def buscar_cuenta(cif):
    return consultar("SELECT * FROM usuarios WHERE cif = ? AND contrasena_hash IS NOT NULL AND rol IN ('Encargado', 'Estudiante')",
                     (cif,), True)


def cambiar_hash(id, contrasena_hash):
    ejecutar('UPDATE usuarios SET contrasena_hash = ? WHERE id = ?', (contrasena_hash, id))


def listar_usuarios(rol=None, busqueda=''):
    filtro = f'%{busqueda}%'
    return consultar(f'''SELECT id, nombre, cif, correo, carrera, rol, activo FROM usuarios
                         WHERE {CUENTA} AND (? IS NULL OR rol = ?) AND (nombre LIKE ? OR cif LIKE ? OR correo LIKE ?)
                         ORDER BY CASE rol WHEN 'Administrador' THEN 0 WHEN 'Encargado' THEN 1 ELSE 2 END, nombre''',
                     (rol, rol, filtro, filtro, filtro))


def contar_usuarios_por_rol():
    filas = consultar(f'SELECT rol, COUNT(*) AS total, SUM(activo) AS activos FROM usuarios WHERE {CUENTA} GROUP BY rol')
    return {f['rol']: {'total': f['total'], 'activos': f['activos'] or 0} for f in filas}


# Crea una cuenta (id=None) o edita una. Al editar, la contraseña solo cambia si se envía un hash nuevo.
def guardar_usuario(nombre, cif, correo, carrera, rol, contrasena_hash, id=None):
    if id is None:
        return ejecutar('INSERT INTO usuarios (nombre, cif, correo, carrera, rol, contrasena_hash) VALUES (?, ?, ?, ?, ?, ?)',
                        (nombre, cif, correo, carrera, rol, contrasena_hash))
    ejecutar('UPDATE usuarios SET nombre = ?, cif = ?, correo = ?, carrera = ?, rol = ?, '
             'contrasena_hash = COALESCE(?, contrasena_hash) WHERE id = ?', (nombre, cif, correo, carrera, rol, contrasena_hash, id))
    return id


def cambiar_activo(id, activo):
    ejecutar('UPDATE usuarios SET activo = ? WHERE id = ?', (int(activo), id))


# Registro del administrador del .env, sin hash (su clave solo está en el .env). Devuelve su id.
def guardar_admin(nombre, cif, correo):
    with conectar() as con:
        fila = buscar_por_cif(cif, con)
        if fila:
            ejecutar("UPDATE usuarios SET nombre = ?, rol = 'Administrador', contrasena_hash = NULL, activo = 1 WHERE id = ?",
                     (nombre, fila['id']), con)
            return fila['id']
        if consultar('SELECT 1 FROM usuarios WHERE correo = ?', (correo,), True, con):
            correo = f'{cif.lower()}@admin.local'
        return ejecutar("INSERT INTO usuarios (nombre, cif, correo, carrera, rol) VALUES (?, ?, ?, 'Administración', 'Administrador')",
                        (nombre, cif, correo), con)


# Persona que trae o retira un objeto. Si ya existe (por CIF o, sin CIF, por nombre y teléfono) se reutiliza la
# misma fila: así nadie queda guardado dos veces. A una cuenta solo se le completa el teléfono si no lo tenía.
def guardar_persona(con, nombre, rol, cif, telefono, correo):
    fila = (buscar_por_cif(cif, con) if cif else
            consultar('SELECT * FROM usuarios WHERE cif IS NULL AND lower(nombre) = lower(?) AND telefono IS ?', (nombre, telefono), True, con))
    if correo and consultar('SELECT 1 FROM usuarios WHERE correo = ? AND id IS NOT ?', (correo, fila and fila['id']), True, con):
        correo = None   # el correo ya es de otra persona
    if not fila:
        return ejecutar('INSERT INTO usuarios (nombre, cif, correo, telefono, rol) VALUES (?, ?, ?, ?, ?)',
                        (nombre, cif, correo, telefono, rol), con)
    if fila['contrasena_hash'] or fila['rol'] == 'Administrador':
        ejecutar('UPDATE usuarios SET telefono = COALESCE(telefono, ?) WHERE id = ?', (telefono, fila['id']), con)
    else:
        ejecutar('UPDATE usuarios SET nombre = ?, rol = COALESCE(?, rol), telefono = COALESCE(?, telefono), '
                 'correo = COALESCE(?, correo) WHERE id = ?', (nombre, rol, telefono, correo, fila['id']), con)
    return fila['id']


def actualizar_telefono(con, id, telefono):
    ejecutar('UPDATE usuarios SET telefono = ? WHERE id = ?', (telefono, id), con)


# Objetos

def listar_objetos(categoria=None, ubicacion=None, publicos=False):
    return consultar(SQL_OBJETOS.format(COLUMNAS_PUBLICAS if publicos else COLUMNAS_PERSONAL) +
                     ' WHERE (? IS NULL OR o.categoria = ?) AND (? IS NULL OR o.ubicacion = ?) ORDER BY o.id DESC',
                     (categoria, categoria, ubicacion, ubicacion))


def buscar_objeto(id, publico=False, con=None):
    return consultar(SQL_OBJETOS.format(COLUMNAS_PUBLICAS if publico else COLUMNAS_PERSONAL) + ' WHERE o.id = ?',
                     (id,), True, con)


# Cuenta los objetos por 'estado', 'categoria' o 'ubicacion': {valor: total}.
def contar_objetos_por(columna):
    assert columna in ('estado', 'categoria', 'ubicacion')
    return dict(consultar(f'SELECT {columna}, COUNT(*) FROM objetos GROUP BY {columna}'))


# El trigger trg_historial_registro anota el «Registro» en el historial.
def insertar_objeto(con, d):
    columnas = ', '.join(d)
    return ejecutar(f'INSERT INTO objetos ({columnas}) VALUES ({", ".join(":" + c for c in d)})', d, con)


# Cambia una columna editable de un objeto.
def actualizar_objeto(con, id, columna, valor):
    assert columna in ('estado', 'descripcion_publica', 'ubicacion', 'foto', 'foto_publica')
    ejecutar(f'UPDATE objetos SET {columna} = ? WHERE id = ?', (valor, id), con)


def buscar_foto(id):
    return consultar('SELECT foto, foto_publica FROM objetos WHERE id = ? AND foto IS NOT NULL', (id,), True)


def uso_fotos():
    return consultar('SELECT COUNT(foto) AS total, COALESCE(SUM(length(foto)), 0) AS peso FROM objetos', uno=True)


# Historial. estado_nuevo = cómo quedó el objeto (solo si la acción lo cambia).

def anotar(con, objeto_id, accion, usuario_id, estado_nuevo=None):
    ejecutar(f'INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora) VALUES (?, ?, ?, ?, {AHORA})',
             (objeto_id, usuario_id, accion, estado_nuevo), con)


def listar_historial(objeto_id=None, limite=-1):
    return consultar('''SELECT h.*, o.titulo, o.categoria, u.nombre AS usuario_nombre FROM historial h
                        JOIN objetos o ON o.id = h.objeto_id JOIN usuarios u ON u.id = h.usuario_id
                        WHERE ? IS NULL OR h.objeto_id = ? ORDER BY h.id DESC LIMIT ?''', (objeto_id, objeto_id, limite))


# Entrega inicial (una sola por objeto) con los datos de quien lo retiró.

def buscar_entrega(objeto_id, con=None):
    return consultar('''SELECT e.*, r.nombre, r.cif, r.telefono, r.rol AS tipo, p.nombre AS entregado_por_nombre
                        FROM entregas e JOIN usuarios r ON r.id = e.retirado_por JOIN usuarios p ON p.id = e.entregado_por
                        WHERE e.objeto_id = ?''', (objeto_id,), True, con)


# El trigger trg_entrega_hecha pasa el objeto a «Entregado» y lo anota.
def insertar_entrega(con, objeto_id, retirado_por, senas, entregado_por):
    return ejecutar(f'INSERT INTO entregas (objeto_id, retirado_por, senas, entregado_por, fecha_entrega) VALUES (?, ?, ?, ?, {AHORA})',
                    (objeto_id, retirado_por, senas, entregado_por), con)


# Reclamaciones con su objeto, quién retiró el objeto (para recuperarlo) y su devolución, si ya existe.

SQL_RECLAMACIONES = '''SELECT r.*, e.objeto_id, o.titulo, o.categoria, o.estado AS objeto_estado, o.ubicacion,
                              u.nombre AS usuario_nombre, u.cif AS usuario_cif, u.correo AS usuario_correo, u.telefono AS usuario_telefono,
                              q.nombre AS retiro_nombre, q.cif AS retiro_cif, q.telefono AS retiro_telefono,
                              a.nombre AS resuelto_por_nombre,
                              d.id AS devolucion_id, d.fecha_recepcion, d.fecha_devolucion, d.observaciones,
                              rb.nombre AS recibido_por_nombre, dv.nombre AS devuelto_por_nombre,
                              d.fecha_devolucion IS NOT NULL AS entregado_a_mi
                       FROM reclamaciones r JOIN entregas e ON e.id = r.entrega_id JOIN usuarios q ON q.id = e.retirado_por
                       JOIN objetos o ON o.id = e.objeto_id
                       JOIN usuarios u ON u.id = r.usuario_id LEFT JOIN usuarios a ON a.id = r.resuelto_por
                       LEFT JOIN devoluciones d ON d.reclamacion_id = r.id
                       LEFT JOIN usuarios rb ON rb.id = d.recibido_por LEFT JOIN usuarios dv ON dv.id = d.devuelto_por'''


# Filtra por estado, objeto o estudiante (los que no se envían no filtran).
def listar_reclamaciones(estado=None, objeto_id=None, usuario_id=None):
    return consultar(SQL_RECLAMACIONES + ''' WHERE (? IS NULL OR r.estado = ?) AND (? IS NULL OR e.objeto_id = ?)
                                             AND (? IS NULL OR r.usuario_id = ?)
                                             ORDER BY CASE r.estado WHEN 'Pendiente' THEN 0 ELSE 1 END, r.id DESC''',
                     (estado, estado, objeto_id, objeto_id, usuario_id, usuario_id))


def buscar_reclamacion(id, con=None):
    return consultar(SQL_RECLAMACIONES + ' WHERE r.id = ?', (id,), True, con)


# La reclamación aceptada de un objeto (como máximo una), con su devolución.
def reclamacion_aceptada(objeto_id, con=None):
    return consultar(SQL_RECLAMACIONES + " WHERE e.objeto_id = ? AND r.estado = 'Aceptada'", (objeto_id,), True, con)


def contar_reclamaciones():
    return dict(consultar('SELECT estado, COUNT(*) FROM reclamaciones GROUP BY estado'))


# Reclamaciones aceptadas cuyo objeto ya se recuperó y espera que el dueño lo retire (aviso en el menú).
def contar_por_retirar(usuario_id):
    return consultar('''SELECT COUNT(*) FROM reclamaciones r JOIN devoluciones d ON d.reclamacion_id = r.id
                        WHERE r.usuario_id = ? AND d.fecha_devolucion IS NULL''', (usuario_id,), True)[0]


# El trigger trg_historial_reclamacion anota la reclamación.
def insertar_reclamacion(con, entrega_id, usuario_id, descripcion, lugar_perdida, fecha_perdida):
    return ejecutar('INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, lugar_perdida, fecha_perdida, fecha_solicitud) '
                    f'VALUES (?, ?, ?, ?, ?, {AHORA})', (entrega_id, usuario_id, descripcion, lugar_perdida, fecha_perdida), con)


def pendientes_de_entrega(con, entrega_id):
    return [f['id'] for f in consultar("SELECT id FROM reclamaciones WHERE entrega_id = ? AND estado = 'Pendiente'",
                                         (entrega_id,), con=con)]


# Los triggers ponen el estado del objeto (si se acepta) y anotan la resolución en el historial.
def cerrar_reclamacion(con, id, estado, respuesta, usuario_id):
    ejecutar(f'UPDATE reclamaciones SET estado = ?, respuesta = ?, resuelto_por = ?, fecha_resolucion = {AHORA} WHERE id = ?',
             (estado, respuesta, usuario_id, id), con)


# Devoluciones. Momento 1: el personal recibe el objeto de quien lo tenía (-> «Recuperado»).
# Momento 2: se lo entrega a su dueño (-> «Devuelto»). Los triggers ponen el estado y lo anotan.

def insertar_devolucion(con, reclamacion_id, recibido_por, observaciones):
    return ejecutar(f'INSERT INTO devoluciones (reclamacion_id, recibido_por, fecha_recepcion, observaciones) VALUES (?, ?, {AHORA}, ?)',
                    (reclamacion_id, recibido_por, observaciones), con)


def completar_devolucion(con, id, devuelto_por, observaciones):
    # la nota nueva se suma a la del momento 1, no la reemplaza
    ejecutar(f'UPDATE devoluciones SET devuelto_por = :yo, fecha_devolucion = {AHORA}, '
             "observaciones = COALESCE(observaciones || ' · ' || :nota, observaciones, :nota) WHERE id = :id",
             {'yo': devuelto_por, 'nota': observaciones, 'id': id}, con)


# Reportes de visitantes (v8.5). Un visitante no es un usuario: sus datos viven solo en su reporte.
# Las listas nunca leen la foto; el enlace privado de seguimiento solo se guarda como hash (token_hash).

SQL_REPORTES = '''SELECT r.id, r.codigo, r.nombre, r.telefono, r.correo, r.objeto_nombre, r.categoria, r.descripcion,
                         r.lugar_perdida, r.fecha_perdida, r.estado, r.fecha_registro, r.objeto_id, r.observaciones,
                         r.actualizado_por, r.fecha_actualizacion, r.whatsapp_estado, r.whatsapp_intentos,
                         r.whatsapp_fecha, r.whatsapp_detalle, o.titulo AS objeto_titulo, o.estado AS objeto_estado,
                         o.ubicacion AS objeto_ubicacion, u.nombre AS actualizado_por_nombre
                  FROM reportes_visitantes r LEFT JOIN objetos o ON o.id = r.objeto_id
                  LEFT JOIN usuarios u ON u.id = r.actualizado_por'''


def insertar_reporte_visitante(con, d):
    return ejecutar('''INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, correo, objeto_nombre, categoria,
                       descripcion, lugar_perdida, fecha_perdida, fecha_registro, foto)
                       VALUES (:codigo, :token_hash, :nombre, :telefono, :correo, :objeto_nombre, :categoria,
                       :descripcion, :lugar_perdida, :fecha_perdida, ''' + AHORA + ', :foto)', d, con)


# Lista para el personal: filtra por estado y por parte del código; primero lo que falta atender.
def listar_reportes_visitantes(estado=None, codigo=''):
    return consultar(SQL_REPORTES + ''' WHERE (? IS NULL OR r.estado = ?) AND r.codigo LIKE ?
                     ORDER BY CASE r.estado WHEN 'Pendiente' THEN 0 WHEN 'En revisión' THEN 1 WHEN 'Localizado' THEN 2 ELSE 3 END,
                     r.id DESC''', (estado, estado, f'%{codigo}%'))


def buscar_reporte_visitante(id, con=None):
    return consultar(SQL_REPORTES + ' WHERE r.id = ?', (id,), True, con)


def buscar_reporte_por_token(token_hash):
    return consultar(SQL_REPORTES + ' WHERE r.token_hash = ?', (token_hash,), True)


def buscar_reporte_por_codigo(codigo):
    return consultar(SQL_REPORTES + ' WHERE r.codigo = ?', (codigo,), True)


def contar_reportes_visitantes():
    return dict(consultar('SELECT estado, COUNT(*) FROM reportes_visitantes GROUP BY estado'))


def foto_reporte_visitante(id):
    fila = consultar('SELECT foto FROM reportes_visitantes WHERE id = ?', (id,), True)
    return fila and fila['foto']


# Gestión del personal (estado, observaciones y objeto relacionado). El trigger exige personal activo.
def gestionar_reporte_visitante(con, id, estado, observaciones, objeto_id, usuario_id):
    ejecutar(f'''UPDATE reportes_visitantes SET estado = ?, observaciones = ?, objeto_id = ?, actualizado_por = ?,
                fecha_actualizacion = {AHORA} WHERE id = ?''', (estado, observaciones, objeto_id, usuario_id, id), con)


# Resultado REAL de cada intento de aviso por WhatsApp (los intentos solo aumentan).
def anotar_whatsapp(id, estado, detalle):
    ejecutar(f'''UPDATE reportes_visitantes SET whatsapp_estado = ?, whatsapp_detalle = ?,
                whatsapp_intentos = whatsapp_intentos + 1, whatsapp_fecha = {AHORA} WHERE id = ?''', (estado, detalle, id))


# Objetos que el personal puede relacionar con un reporte: primero los de la misma categoría y bajo custodia.
def objetos_para_relacionar(categoria):
    return consultar('''SELECT id, titulo, categoria, fecha, estado, ubicacion, descripcion_publica FROM objetos
                        ORDER BY categoria = ? DESC, estado IN ('Activo', 'En resguardo', 'En bodega') DESC, fecha DESC, id DESC
                        LIMIT 300''', (categoria,))


# Posibles coincidencias: misma categoría, bajo custodia y encontrados desde el día en que se perdió.
def objetos_candidatos(categoria, fecha_perdida):
    return consultar('''SELECT id, titulo, descripcion, descripcion_publica, categoria, lugar_encontrado, fecha, estado, ubicacion
                        FROM objetos WHERE categoria = ? AND fecha >= ? AND estado IN ('Activo', 'En resguardo', 'En bodega')
                        ORDER BY fecha, id''', (categoria, fecha_perdida))

