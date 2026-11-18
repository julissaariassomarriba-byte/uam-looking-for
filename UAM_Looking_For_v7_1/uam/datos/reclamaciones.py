"""Tablas entregas, reclamaciones y devoluciones (el recorrido de un objeto después de salir de custodia).

Los triggers de schema.sql ponen el estado del objeto y anotan cada hecho en el historial.
"""
from .conexion import AHORA, consultar, ejecutar

# ---------- Entrega inicial (una sola por objeto) ----------

def buscar_entrega(objeto_id, con=None):
    return consultar('''SELECT e.id, e.objeto_id, e.retirado_por, e.entregado_por, e.senas, e.fecha_entrega,
                               r.nombre, r.cif, r.telefono, r.correo, r.carrera, r.rol AS tipo, p.nombre AS entregado_por_nombre
                        FROM entregas e JOIN usuarios r ON r.id = e.retirado_por JOIN usuarios p ON p.id = e.entregado_por
                        WHERE e.objeto_id = ?''', (objeto_id,), True, con)


def insertar_entrega(con, objeto_id, retirado_por, senas, entregado_por):
    """El trigger trg_entrega_hecha pasa el objeto a «Entregado» y lo anota."""
    return ejecutar(f'INSERT INTO entregas (objeto_id, retirado_por, senas, entregado_por, fecha_entrega) VALUES (?, ?, ?, ?, {AHORA})',
                    (objeto_id, retirado_por, senas, entregado_por), con)


# ---------- Reclamaciones, con su objeto, quién lo retiró (para recuperarlo) y su devolución ----------

SQL_RECLAMACIONES = '''SELECT r.id, r.entrega_id, r.usuario_id, r.descripcion, r.lugar_perdida, r.fecha_perdida, r.estado,
                              r.respuesta, r.fecha_solicitud, r.fecha_resolucion, r.resuelto_por,
                              e.objeto_id, o.titulo, o.categoria, o.estado AS objeto_estado, o.ubicacion,
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


def listar(estado=None, objeto_id=None, usuario_id=None, con=None):
    """Filtra por estado, objeto o estudiante (los que no se envían no filtran). Primero las pendientes."""
    return consultar(SQL_RECLAMACIONES + ''' WHERE (? IS NULL OR r.estado = ?) AND (? IS NULL OR e.objeto_id = ?)
                                             AND (? IS NULL OR r.usuario_id = ?)
                                             ORDER BY CASE r.estado WHEN 'Pendiente' THEN 0 ELSE 1 END, r.id DESC''',
                     (estado, estado, objeto_id, objeto_id, usuario_id, usuario_id), con=con)


def buscar(id, con=None):
    return consultar(SQL_RECLAMACIONES + ' WHERE r.id = ?', (id,), True, con)


def aceptada_de_objeto(objeto_id, con=None):
    """La reclamación aceptada de un objeto (como máximo una), con su devolución."""
    return consultar(SQL_RECLAMACIONES + " WHERE e.objeto_id = ? AND r.estado = 'Aceptada'", (objeto_id,), True, con)


def contar_por_estado():
    return dict(consultar('SELECT estado, COUNT(*) FROM reclamaciones GROUP BY estado'))


def contar_por_retirar(usuario_id):
    """Reclamaciones aceptadas cuyo objeto ya se recuperó y espera que el dueño lo retire (aviso en el menú)."""
    return consultar('''SELECT COUNT(*) FROM reclamaciones r JOIN devoluciones d ON d.reclamacion_id = r.id
                        WHERE r.usuario_id = ? AND d.fecha_devolucion IS NULL''', (usuario_id,), True)[0]


def insertar(con, entrega_id, usuario_id, descripcion, lugar_perdida, fecha_perdida):
    """El trigger trg_historial_reclamacion anota la reclamación."""
    return ejecutar('INSERT INTO reclamaciones (entrega_id, usuario_id, descripcion, lugar_perdida, fecha_perdida, fecha_solicitud) '
                    f'VALUES (?, ?, ?, ?, ?, {AHORA})', (entrega_id, usuario_id, descripcion, lugar_perdida, fecha_perdida), con)


def pendientes_de_entrega(con, entrega_id):
    return [f['id'] for f in consultar("SELECT id FROM reclamaciones WHERE entrega_id = ? AND estado = 'Pendiente'",
                                         (entrega_id,), con=con)]


def resolver(con, id, estado, respuesta, encargado_id):
    """Aceptar o rechazar. Los triggers ponen el estado del objeto (si se acepta) y lo anotan en el historial."""
    ejecutar(f'UPDATE reclamaciones SET estado = ?, respuesta = ?, resuelto_por = ?, fecha_resolucion = {AHORA} WHERE id = ?',
             (estado, respuesta, encargado_id, id), con)


# ---------- Devoluciones: 1) el personal recibe el objeto de quien lo tenía (-> «Recuperado»);
#            2) se lo entrega a su dueño (-> «Devuelto»). Los triggers ponen el estado y lo anotan. ----------

def insertar_devolucion(con, reclamacion_id, recibido_por, observaciones):
    return ejecutar(f'INSERT INTO devoluciones (reclamacion_id, recibido_por, fecha_recepcion, observaciones) VALUES (?, ?, {AHORA}, ?)',
                    (reclamacion_id, recibido_por, observaciones), con)


def completar_devolucion(con, id, devuelto_por, observaciones):
    """La nota nueva se suma a la del momento 1, no la reemplaza."""
    ejecutar(f'UPDATE devoluciones SET devuelto_por = :yo, fecha_devolucion = {AHORA}, '
             "observaciones = COALESCE(observaciones || ' · ' || :nota, observaciones, :nota) WHERE id = :id",
             {'yo': devuelto_por, 'nota': observaciones, 'id': id}, con)
