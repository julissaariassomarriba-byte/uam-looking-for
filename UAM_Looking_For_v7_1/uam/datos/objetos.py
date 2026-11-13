"""Tablas objetos e historial.

La base escribe sola el historial de los hechos (registro, entrega, reclamaciones, recuperación y devolución) y pone
el estado del objeto según lo que pasó. Aquí solo se anotan a mano las acciones que no nacen de otra tabla:
cambio de estado bajo custodia, ubicación, foto y descripción pública.
Las listas nunca leen la columna foto: solo si el objeto tiene una (tiene_foto).
"""
from .conexion import AHORA, consultar, ejecutar

# ---------- Plazo de permanencia en el catálogo ----------
# Un objeto que ya salió de custodia (Entregado o Devuelto) sigue visible unos días y después se oculta del
# catálogo. No se guarda en ninguna columna: se calcula con la fecha del hecho (entrega o devolución), así nunca
# queda desactualizado. Mientras tenga una reclamación pendiente no se oculta.
DIAS_MINIMO, DIAS_MAXIMO, DIAS_DEFECTO = 3, 7, 5
_plazo = {'dias': DIAS_DEFECTO}


def configurar_plazo(dias):
    """Días que un objeto entregado sigue en el catálogo (entre 3 y 7). Lo fija crear_app() con DIAS_OCULTAR del .env."""
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        dias = DIAS_DEFECTO
    _plazo['dias'] = max(DIAS_MINIMO, min(DIAS_MAXIMO, dias))


def dias_plazo():
    return _plazo['dias']


FECHA_SALIDA = """(CASE o.estado
    WHEN 'Entregado' THEN (SELECT e.fecha_entrega FROM entregas e WHERE e.objeto_id = o.id)
    WHEN 'Devuelto' THEN (SELECT d.fecha_devolucion FROM devoluciones d JOIN reclamaciones r ON r.id = d.reclamacion_id
                          JOIN entregas e ON e.id = r.entrega_id WHERE e.objeto_id = o.id AND d.fecha_devolucion IS NOT NULL)
    END)"""
FECHA_OCULTA = f"datetime({FECHA_SALIDA}, '+' || :dias || ' days')"   # cuándo deja (o dejó) de verse en el catálogo
OCULTO = f"""(o.estado IN ('Entregado', 'Devuelto') AND {FECHA_OCULTA} <= {AHORA}
              AND NOT EXISTS (SELECT 1 FROM reclamaciones r JOIN entregas e ON e.id = r.entrega_id
                              WHERE e.objeto_id = o.id AND r.estado = 'Pendiente'))"""

SQL_OBJETOS = 'SELECT {} FROM objetos o LEFT JOIN usuarios p ON p.id = o.reportado_por'
COLUMNAS_PERSONAL = ('o.id, o.titulo, o.descripcion, o.descripcion_publica, o.categoria, o.lugar_encontrado, o.ubicacion, '
                     'o.fecha, o.hora, o.estado, o.registrado_por, o.reportado_por, o.foto_publica, o.foto IS NOT NULL AS tiene_foto, '
                     'p.nombre AS reportado_nombre, p.rol AS reportado_tipo, p.cif AS reportado_cif, '
                     'p.telefono AS reportado_telefono, p.correo AS reportado_correo, '
                     f'{OCULTO} AS oculto, {FECHA_OCULTA} AS fecha_oculta, {FECHA_OCULTA} <= {AHORA} AS plazo_cumplido')
# Lo único que ve un estudiante: sin lugar del hallazgo, fecha exacta, hora, descripción interna ni quién lo trajo.
COLUMNAS_PUBLICAS = ('o.id, o.titulo, o.categoria, o.estado, o.descripcion_publica, substr(o.fecha, 1, 7) AS periodo, '
                     f'o.ubicacion, o.foto IS NOT NULL AND o.foto_publica = 1 AS tiene_foto, {OCULTO} AS oculto')
COLUMNAS_EDITABLES = ('estado', 'descripcion_publica', 'ubicacion', 'foto', 'foto_publica')
COLUMNAS_CONTABLES = ('estado', 'categoria', 'ubicacion')
COLUMNAS_NUEVO = ('titulo', 'descripcion', 'descripcion_publica', 'categoria', 'lugar_encontrado', 'ubicacion', 'fecha', 'hora',
                  'estado', 'registrado_por', 'reportado_por', 'foto', 'foto_publica')


def listar(categoria=None, ubicacion=None, publicos=False, ocultos=False):
    """Catálogo: por defecto solo los objetos visibles; ocultos=True lista los que ya cumplieron su plazo
    y ocultos=None lista todos (historial y PDF)."""
    return consultar(SQL_OBJETOS.format(COLUMNAS_PUBLICAS if publicos else COLUMNAS_PERSONAL) +
                     f' WHERE (:categoria IS NULL OR o.categoria = :categoria) AND (:ubicacion IS NULL OR o.ubicacion = :ubicacion)'
                     f' AND (:ocultos IS NULL OR {OCULTO} = :ocultos) ORDER BY o.id DESC',
                     {'categoria': categoria, 'ubicacion': ubicacion, 'dias': dias_plazo(),
                      'ocultos': None if ocultos is None else int(ocultos)})


def buscar(id, publico=False, con=None):
    return consultar(SQL_OBJETOS.format(COLUMNAS_PUBLICAS if publico else COLUMNAS_PERSONAL) + ' WHERE o.id = :id',
                     {'id': id, 'dias': dias_plazo()}, True, con)


def contar_por(columna, visibles=False):
    """{valor: total} agrupando por 'estado', 'categoria' o 'ubicacion' (lista cerrada: nunca un texto del usuario).
    visibles=True cuenta solo lo que se ve en el catálogo."""
    if columna not in COLUMNAS_CONTABLES:
        raise ValueError(f'Columna no permitida: {columna}')
    filtro = f'WHERE NOT {OCULTO}' if visibles else ''
    return dict(consultar(f'SELECT o.{columna}, COUNT(*) FROM objetos o {filtro} GROUP BY o.{columna}', {'dias': dias_plazo()}))


def contar_ocultos():
    return consultar(f'SELECT COUNT(*) FROM objetos o WHERE {OCULTO}', {'dias': dias_plazo()}, True)[0]


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


# ---------- Limpieza del historial (v9.1.01; ver «limpiezas_historial» en schema.sql) ----------

def contar_historial(antes_de=None):
    """Movimientos que borraría una limpieza: todos, o los anteriores al día antes_de."""
    return consultar('SELECT COUNT(*) AS n FROM historial WHERE ? IS NULL OR fecha_hora < ?', (antes_de, antes_de), uno=True)['n']


def limpiar_historial(con, antes_de, usuario_id):
    """Abre la limpieza (la base la valida y desde ese momento deja borrar), borra y la cierra con el total.
    Todo va en la transacción de quien llama: si algo falla, no se borra nada y no queda una limpieza abierta."""
    ejecutar(f'INSERT INTO limpiezas_historial (usuario_id, antes_de, fecha_hora) VALUES (?, ?, {AHORA})', (usuario_id, antes_de), con)
    borrados = con.execute('DELETE FROM historial WHERE ? IS NULL OR fecha_hora < ?', (antes_de, antes_de)).rowcount
    ejecutar("UPDATE limpiezas_historial SET estado = 'Hecha', filas_borradas = ? WHERE estado = 'En curso'", (borrados,), con)
    return borrados


def listar_limpiezas(limite=5):
    return consultar('''SELECT l.antes_de, l.filas_borradas, l.fecha_hora, u.nombre AS usuario_nombre
                        FROM limpiezas_historial l JOIN usuarios u ON u.id = l.usuario_id
                        WHERE l.estado = 'Hecha' ORDER BY l.id DESC LIMIT ?''', (limite,))
