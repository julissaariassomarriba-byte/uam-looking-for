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

# ---------- Plazos de custodia (RF-16) ----------
# Cuánto puede quedarse un objeto sin reclamar en la oficina (Activo o En resguardo) y en bodega. Tampoco se guarda:
# la fecha de vencimiento se calcula desde el hallazgo (oficina) o desde que entró a bodega, según el historial.
# Los días los fija crear_app() con PLAZO_OFICINA_DIAS y PLAZO_BODEGA_DIAS del .env.
CUSTODIA_DEFECTO = {'oficina': 30, 'bodega': 60}   # provisionales: los define la oficina en el .env
DIAS_AVISO = 3                                     # «por vencer»: faltan 3 días o menos
_custodia = dict(CUSTODIA_DEFECTO)


def configurar_custodia(oficina, bodega):
    for clave, valor in (('oficina', oficina), ('bodega', bodega)):
        try:
            _custodia[clave] = max(1, min(3650, int(valor)))
        except (TypeError, ValueError):
            _custodia[clave] = CUSTODIA_DEFECTO[clave]


def plazos_custodia():
    return dict(_custodia)


EN_CUSTODIA = "o.estado IN ('Activo', 'En resguardo', 'En bodega')"
INICIO_CUSTODIA = """(CASE WHEN o.estado = 'En bodega'
    THEN COALESCE((SELECT date(max(h.fecha_hora)) FROM historial h WHERE h.objeto_id = o.id AND h.estado_nuevo = 'En bodega'), o.fecha)
    ELSE o.fecha END)"""
FECHA_VENCE = (f"(CASE WHEN {EN_CUSTODIA} THEN date({INICIO_CUSTODIA}, '+' || "
               f"(CASE WHEN o.estado = 'En bodega' THEN :dias_bodega ELSE :dias_oficina END) || ' days') END)")
DIAS_RESTANTES = f"CAST(julianday({FECHA_VENCE}) - julianday(date({AHORA})) AS INTEGER)"


def parametros(**extra):
    """Los días de los plazos que usan todas las consultas de objetos, más los parámetros propios de cada una."""
    return {'dias': dias_plazo(), 'dias_oficina': _custodia['oficina'], 'dias_bodega': _custodia['bodega'], **extra}


def patron(texto):
    """Texto para LIKE sin comodines: % y _ se buscan como letras."""
    return '%' + texto.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


SQL_OBJETOS = 'SELECT {} FROM objetos o LEFT JOIN usuarios p ON p.id = o.reportado_por'
COLUMNAS_PERSONAL = ('o.id, o.titulo, o.descripcion, o.descripcion_publica, o.categoria, o.lugar_encontrado, o.ubicacion, '
                     'o.fecha, o.hora, o.estado, o.registrado_por, o.reportado_por, o.foto_publica, o.foto IS NOT NULL AS tiene_foto, '
                     'p.nombre AS reportado_nombre, p.rol AS reportado_tipo, p.cif AS reportado_cif, '
                     'p.telefono AS reportado_telefono, p.correo AS reportado_correo, '
                     f'{OCULTO} AS oculto, {FECHA_OCULTA} AS fecha_oculta, {FECHA_OCULTA} <= {AHORA} AS plazo_cumplido, '
                     f'{FECHA_VENCE} AS fecha_vence, {DIAS_RESTANTES} AS dias_restantes')
# Lo único que ve un estudiante: sin lugar del hallazgo, fecha exacta, hora, descripción interna ni quién lo trajo.
COLUMNAS_PUBLICAS = ('o.id, o.titulo, o.categoria, o.estado, o.descripcion_publica, substr(o.fecha, 1, 7) AS periodo, '
                     f'o.ubicacion, o.foto IS NOT NULL AND o.foto_publica = 1 AS tiene_foto, {OCULTO} AS oculto')
COLUMNAS_EDITABLES = ('estado', 'descripcion_publica', 'ubicacion', 'foto', 'foto_publica')
COLUMNAS_CONTABLES = ('estado', 'categoria', 'ubicacion')
COLUMNAS_NUEVO = ('titulo', 'descripcion', 'descripcion_publica', 'categoria', 'lugar_encontrado', 'ubicacion', 'fecha', 'hora',
                  'estado', 'registrado_por', 'reportado_por', 'foto', 'foto_publica')


# Dónde busca la palabra clave. Un estudiante solo en lo público; el personal también en lo interno, en quién lo
# trajo y en quién lo retiró (nombre, CIF o carrera), y por código (#12 o 12).
BUSQUEDA_PUBLICA = "(o.titulo LIKE :q ESCAPE '\\' OR o.descripcion_publica LIKE :q ESCAPE '\\' OR o.categoria LIKE :q ESCAPE '\\')"
BUSQUEDA_PERSONAL = ("(o.id = :q_id OR o.titulo LIKE :q ESCAPE '\\' OR o.descripcion_publica LIKE :q ESCAPE '\\' "
                     "OR o.descripcion LIKE :q ESCAPE '\\' OR o.categoria LIKE :q ESCAPE '\\' OR o.lugar_encontrado LIKE :q ESCAPE '\\' "
                     "OR p.nombre LIKE :q ESCAPE '\\' OR p.cif LIKE :q ESCAPE '\\' OR p.carrera LIKE :q ESCAPE '\\' "
                     "OR EXISTS (SELECT 1 FROM entregas e JOIN usuarios r ON r.id = e.retirado_por WHERE e.objeto_id = o.id "
                     "AND (r.nombre LIKE :q ESCAPE '\\' OR r.cif LIKE :q ESCAPE '\\' OR r.carrera LIKE :q ESCAPE '\\')))")


def listar(categoria=None, ubicacion=None, publicos=False, ocultos=False, q=None, mes=None, desde=None, hasta=None,
           estado=None, por_vencer=False):
    """Catálogo: por defecto solo los objetos visibles; ocultos=True lista los que ya cumplieron su plazo
    y ocultos=None lista todos (historial y PDF). por_vencer=True: bajo custodia con 3 días o menos (o vencidos).
    q busca una palabra (o un código, para el personal); mes (AAAA-MM), desde y hasta filtran por fecha del hallazgo."""
    q = (q or '').strip()
    codigo = q.lstrip('#')
    filtros = [
        '(:categoria IS NULL OR o.categoria = :categoria)', '(:ubicacion IS NULL OR o.ubicacion = :ubicacion)',
        f'(:ocultos IS NULL OR {OCULTO} = :ocultos)', '(:estado IS NULL OR o.estado = :estado)',
        '(:mes IS NULL OR substr(o.fecha, 1, 7) = :mes)', '(:desde IS NULL OR o.fecha >= :desde)', '(:hasta IS NULL OR o.fecha <= :hasta)',
    ]
    if q:
        filtros.append(BUSQUEDA_PUBLICA if publicos else BUSQUEDA_PERSONAL)
    if por_vencer and not publicos:
        filtros.append(f'{DIAS_RESTANTES} <= {DIAS_AVISO}')
    orden = f'{DIAS_RESTANTES}, o.id' if por_vencer and not publicos else 'o.id DESC'
    return consultar(SQL_OBJETOS.format(COLUMNAS_PUBLICAS if publicos else COLUMNAS_PERSONAL) +
                     ' WHERE ' + ' AND '.join(filtros) + f' ORDER BY {orden}',
                     parametros(categoria=categoria, ubicacion=ubicacion, estado=estado, mes=mes, desde=desde, hasta=hasta,
                                ocultos=None if ocultos is None else int(ocultos), q=patron(q) if q else None,
                                q_id=int(codigo) if codigo.isdigit() else None))


def meses_con_objetos():
    """Meses (AAAA-MM) con objetos visibles en el catálogo, del más reciente al más antiguo: el filtro del estudiante."""
    return [f[0] for f in consultar(f'SELECT DISTINCT substr(o.fecha, 1, 7) FROM objetos o WHERE NOT {OCULTO} ORDER BY 1 DESC',
                                    parametros())]


def plazos_por_vencer(limite=6):
    """Objetos bajo custodia que vencen en 3 días o menos (o ya vencieron), primero los más urgentes."""
    return listar(por_vencer=True)[:limite]


def contar_plazos():
    fila = consultar(f"""SELECT COALESCE(SUM({DIAS_RESTANTES} < 0), 0), COALESCE(SUM({DIAS_RESTANTES} BETWEEN 0 AND {DIAS_AVISO}), 0)
                         FROM objetos o WHERE {EN_CUSTODIA}""", parametros(), True)
    return {'vencidos': fila[0], 'por_vencer': fila[1]}


def buscar(id, publico=False, con=None):
    return consultar(SQL_OBJETOS.format(COLUMNAS_PUBLICAS if publico else COLUMNAS_PERSONAL) + ' WHERE o.id = :id',
                     parametros(id=id), True, con)


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
