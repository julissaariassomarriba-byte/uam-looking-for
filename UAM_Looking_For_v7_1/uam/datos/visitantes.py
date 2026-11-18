# Consultas de los reportes de visitantes.
from .conexion import AHORA, consultar, ejecutar

SQL_REPORTES = '''SELECT r.id, r.codigo, r.nombre, r.telefono, r.correo, r.objeto_nombre, r.categoria, r.descripcion,
                         r.lugar_perdida, r.fecha_perdida, r.estado, r.fecha_registro, r.objeto_id, r.observaciones,
                         r.actualizado_por, r.fecha_actualizacion, r.whatsapp_estado, r.whatsapp_intentos,
                         r.whatsapp_fecha, r.whatsapp_detalle, o.titulo AS objeto_titulo, o.estado AS objeto_estado,
                         o.ubicacion AS objeto_ubicacion, u.nombre AS actualizado_por_nombre
                  FROM reportes_visitantes r LEFT JOIN objetos o ON o.id = r.objeto_id
                  LEFT JOIN usuarios u ON u.id = r.actualizado_por'''


# Guarda un reporte nuevo.
def insertar(con, d):
    return ejecutar('''INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, correo, objeto_nombre, categoria,
                       descripcion, lugar_perdida, fecha_perdida, fecha_registro, foto)
                       VALUES (:codigo, :token_hash, :nombre, :telefono, :correo, :objeto_nombre, :categoria,
                       :descripcion, :lugar_perdida, :fecha_perdida, ''' + AHORA + ', :foto)', d, con)


# Lista los reportes con filtro y búsqueda.
def listar(estado=None, codigo='', palabra=''):
    from .objetos import patron
    palabra = (palabra or '').strip()
    busqueda = ("(r.codigo LIKE :codigo OR r.nombre LIKE :palabra ESCAPE '\\' OR r.telefono LIKE :palabra ESCAPE '\\' "
                "OR r.objeto_nombre LIKE :palabra ESCAPE '\\')") if palabra else 'r.codigo LIKE :codigo'
    return consultar(SQL_REPORTES + f''' WHERE (:estado IS NULL OR r.estado = :estado) AND {busqueda}
                     ORDER BY CASE r.estado WHEN 'Pendiente' THEN 0 WHEN 'En revisión' THEN 1 WHEN 'Localizado' THEN 2 ELSE 3 END,
                     r.id DESC''', {'estado': estado, 'codigo': f'%{codigo}%' if codigo or not palabra else None,
                      'palabra': patron(palabra) if palabra else None})


# Busca un reporte por id.
def buscar(id, con=None):
    return consultar(SQL_REPORTES + ' WHERE r.id = ?', (id,), True, con)


# Busca un reporte por su enlace privado.
def buscar_por_token(token_hash):
    return consultar(SQL_REPORTES + ' WHERE r.token_hash = ?', (token_hash,), True)


# Busca un reporte por su código.
def buscar_por_codigo(codigo):
    return consultar(SQL_REPORTES + ' WHERE r.codigo = ?', (codigo,), True)


# Cuenta los reportes por estado.
def contar_por_estado():
    return dict(consultar('SELECT estado, COUNT(*) FROM reportes_visitantes GROUP BY estado'))


# Foto de un reporte.
def foto(id):
    fila = consultar('SELECT foto FROM reportes_visitantes WHERE id = ?', (id,), True)
    return fila['foto'] if fila else None


# Guarda la gestión del personal sobre un reporte.
def gestionar(con, id, estado, observaciones, objeto_id, usuario_id):
    ejecutar(f'''UPDATE reportes_visitantes SET estado = ?, observaciones = ?, objeto_id = ?, actualizado_por = ?,
                fecha_actualizacion = {AHORA} WHERE id = ?''', (estado, observaciones, objeto_id, usuario_id, id), con)


# Guarda el resultado del aviso por WhatsApp.
def anotar_whatsapp(id, estado, detalle):
    ejecutar(f'''UPDATE reportes_visitantes SET whatsapp_estado = ?, whatsapp_detalle = ?,
                whatsapp_intentos = whatsapp_intentos + 1, whatsapp_fecha = {AHORA} WHERE id = ?''', (estado, detalle, id))
