"""Tablas objetos e historial.

La base escribe sola el historial de los hechos (registro, entrega, reclamaciones, recuperación y devolución) y pone
el estado del objeto según lo que pasó. Aquí solo se anotan a mano las acciones que no nacen de otra tabla:
cambio de estado bajo custodia, ubicación, foto y descripción pública.
Las listas nunca leen la columna foto: solo si el objeto tiene una (tiene_foto).
"""
from .conexion import AHORA, consultar, ejecutar

SQL_OBJETOS = 'SELECT {} FROM objetos o LEFT JOIN usuarios p ON p.id = o.reportado_por'
COLUMNAS_PERSONAL = ('o.id, o.titulo, o.descripcion, o.descripcion_publica, o.categoria, o.lugar_encontrado, o.ubicacion, '
                     'o.fecha, o.hora, o.estado, o.registrado_por, o.reportado_por, o.foto_publica, o.foto IS NOT NULL AS tiene_foto, '
                     'p.nombre AS reportado_nombre, p.rol AS reportado_tipo, p.cif AS reportado_cif, '
                     'p.telefono AS reportado_telefono, p.correo AS reportado_correo')
# Lo único que ve un estudiante: sin lugar del hallazgo, fecha exacta, hora, descripción interna ni quién lo trajo.
COLUMNAS_PUBLICAS = ('o.id, o.titulo, o.categoria, o.estado, o.descripcion_publica, substr(o.fecha, 1, 7) AS periodo, '
                     'o.ubicacion, o.foto IS NOT NULL AND o.foto_publica = 1 AS tiene_foto')
COLUMNAS_EDITABLES = ('estado', 'descripcion_publica', 'ubicacion', 'foto', 'foto_publica')
COLUMNAS_CONTABLES = ('estado', 'categoria', 'ubicacion')
COLUMNAS_NUEVO = ('titulo', 'descripcion', 'descripcion_publica', 'categoria', 'lugar_encontrado', 'ubicacion', 'fecha', 'hora',
                  'estado', 'registrado_por', 'reportado_por', 'foto', 'foto_publica')


def listar(categoria=None, ubicacion=None, publicos=False):
    return consultar(SQL_OBJETOS.format(COLUMNAS_PUBLICAS if publicos else COLUMNAS_PERSONAL) +
                     ' WHERE (? IS NULL OR o.categoria = ?) AND (? IS NULL OR o.ubicacion = ?) ORDER BY o.id DESC',
                     (categoria, categoria, ubicacion, ubicacion))


def buscar(id, publico=False, con=None):
    return consultar(SQL_OBJETOS.format(COLUMNAS_PUBLICAS if publico else COLUMNAS_PERSONAL) + ' WHERE o.id = ?',
                     (id,), True, con)


def contar_por(columna):
    """{valor: total} agrupando por 'estado', 'categoria' o 'ubicacion' (lista cerrada: nunca un texto del usuario)."""
    if columna not in COLUMNAS_CONTABLES:
        raise ValueError(f'Columna no permitida: {columna}')
    return dict(consultar(f'SELECT {columna}, COUNT(*) FROM objetos GROUP BY {columna}'))


def insertar(con, datos):
    """El trigger trg_historial_registro anota el «Registro» en el historial."""
    if set(datos) - set(COLUMNAS_NUEVO):
        raise ValueError('Columnas no permitidas al registrar un objeto.')
    columnas = ', '.join(datos)
    return ejecutar(f'INSERT INTO objetos ({columnas}) VALUES ({", ".join(":" + c for c in datos)})', datos, con)


def actualizar(con, id, columna, valor):
    if columna not in COLUMNAS_EDITABLES:
        raise ValueError(f'Columna no editable: {columna}')
    ejecutar(f'UPDATE objetos SET {columna} = ? WHERE id = ?', (valor, id), con)


def buscar_foto(id):
    return consultar('SELECT foto, foto_publica FROM objetos WHERE id = ? AND foto IS NOT NULL', (id,), True)


def uso_fotos():
    return consultar('SELECT COUNT(foto) AS total, COALESCE(SUM(length(foto)), 0) AS peso FROM objetos', uno=True)


# ---------- Historial (estado_nuevo = cómo quedó el objeto, solo si la acción lo cambia) ----------

def anotar(con, objeto_id, accion, usuario_id, estado_nuevo=None):
    ejecutar(f'INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora) VALUES (?, ?, ?, ?, {AHORA})',
             (objeto_id, usuario_id, accion, estado_nuevo), con)


def listar_historial(objeto_id=None, limite=-1):
    return consultar('''SELECT h.id, h.objeto_id, h.usuario_id, h.accion, h.estado_nuevo, h.fecha_hora,
                               o.titulo, o.categoria, u.nombre AS usuario_nombre
                        FROM historial h JOIN objetos o ON o.id = h.objeto_id JOIN usuarios u ON u.id = h.usuario_id
                        WHERE ? IS NULL OR h.objeto_id = ? ORDER BY h.id DESC LIMIT ?''', (objeto_id, objeto_id, limite))


# ---------- Para relacionar con reportes de visitantes ----------

def para_relacionar(categoria):
    """Objetos que el personal puede relacionar con un reporte: primero los de la misma categoría y bajo custodia."""
    return consultar('''SELECT id, titulo, categoria, fecha, estado, ubicacion, descripcion_publica FROM objetos
                        ORDER BY categoria = ? DESC, estado IN ('Activo', 'En resguardo', 'En bodega') DESC, fecha DESC, id DESC
                        LIMIT 300''', (categoria,))


def candidatos(categoria, fecha_perdida):
    """Posibles coincidencias: misma categoría, bajo custodia y encontrados desde el día en que se perdió."""
    return consultar('''SELECT id, titulo, descripcion, descripcion_publica, categoria, lugar_encontrado, fecha, estado, ubicacion
                        FROM objetos WHERE categoria = ? AND fecha >= ? AND estado IN ('Activo', 'En resguardo', 'En bodega')
                        ORDER BY fecha, id''', (categoria, fecha_perdida))
