"""Pasa una base de UAM Looking For v6.2 al esquema v7.1 sin perder datos.

app.py lo ejecuta solo al iniciar si hace falta (también: python migrar.py).
1. Copia de respaldo de la base original.  2. Arma la base nueva en memoria.  3. Revisa integridad, llaves
foráneas y que no falte ningún registro.  4. Solo entonces reemplaza la original. Si algo no cuadra, no toca nada
y dice qué revisar: no se inventan datos que la versión anterior no guardaba.

Qué cambia respecto a v6.2:
- contraseñas en texto -> hash PBKDF2 (contrasena_hash);
- la devolución al dueño ya no es una segunda entrega: pasa a la tabla devoluciones (recuperación + devolución);
- estados nuevos «Recuperado» y «Devuelto», calculados a partir de los hechos;
- historial.estado -> historial.estado_nuevo.
Los triggers se quitan mientras se copian los datos (si no, volverían a escribir el historial) y se vuelven a crear.
"""
import sqlite3

import base_datos as bd
from logica import hash_contrasena

PASOS = [
    """INSERT INTO usuarios (id, nombre, cif, correo, telefono, carrera, rol, activo)
       SELECT id, trim(nombre), nullif(trim(cif), ''), nullif(lower(trim(correo)), ''), nullif(trim(telefono), ''),
              nullif(trim(carrera), ''), rol, activo FROM vieja.usuarios""",
    # si lo trajo quien lo registró, en v7.1 cuenta como encontrado por el personal (reportado_por vacío)
    """INSERT INTO objetos (id, titulo, descripcion, descripcion_publica, categoria, lugar_encontrado, ubicacion, fecha, hora,
                            estado, registrado_por, reportado_por, foto_publica, foto)
       SELECT id, titulo, descripcion, nullif(trim(descripcion_publica), ''), categoria, lugar_encontrado, ubicacion, fecha,
              substr(hora, 1, 5), estado, registrado_por, nullif(reportado_por, registrado_por), foto_publica, foto FROM vieja.objetos""",
    # la entrega inicial es la que no es devolución de una reclamación
    """INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega)
       SELECT id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega FROM vieja.entregas WHERE reclamacion_id IS NULL""",
    """INSERT INTO reclamaciones SELECT id, entrega_id, usuario_id, descripcion, nullif(trim(lugar_perdida), ''), fecha_perdida,
              estado, nullif(trim(respuesta), ''), fecha_solicitud, fecha_resolucion, resuelto_por FROM vieja.reclamaciones""",
    # Momento 1: la «Recuperación» anotada después de aceptar. Momento 2: la entrega al dueño (sus señas van a observaciones).
    """INSERT INTO devoluciones (reclamacion_id, recibido_por, fecha_recepcion, devuelto_por, fecha_devolucion, observaciones)
       SELECT r.id, h.usuario_id, h.fecha_hora, d.entregado_por, d.fecha_entrega, 'Señas al devolver: ' || d.senas
       FROM vieja.reclamaciones r JOIN vieja.entregas e ON e.id = r.entrega_id
       JOIN vieja.historial h ON h.id = (SELECT min(id) FROM vieja.historial WHERE objeto_id = e.objeto_id
                                          AND accion = 'Recuperación' AND fecha_hora >= r.fecha_resolucion)
       LEFT JOIN vieja.entregas d ON d.reclamacion_id = r.id
       WHERE r.estado = 'Aceptada'""",
    # La recuperación queda como «Recuperado» y la entrega al dueño (la última «Entrega» del objeto) como «Devolución».
    """INSERT INTO historial (id, objeto_id, usuario_id, accion, estado_nuevo, fecha_hora)
       SELECT h.id, h.objeto_id, h.usuario_id,
              CASE WHEN h.accion = 'Entrega' AND h.id = u.ultima AND u.devuelto THEN 'Devolución' ELSE h.accion END,
              CASE WHEN h.accion = 'Recuperación' THEN 'Recuperado'
                   WHEN h.accion = 'Entrega' AND h.id = u.ultima AND u.devuelto THEN 'Devuelto' ELSE h.estado END,
              h.fecha_hora
       FROM vieja.historial h LEFT JOIN (SELECT objeto_id, max(id) AS ultima,
                                                EXISTS (SELECT 1 FROM vieja.entregas x WHERE x.objeto_id = hh.objeto_id
                                                        AND x.reclamacion_id IS NOT NULL) AS devuelto
                                         FROM vieja.historial hh WHERE accion = 'Entrega' GROUP BY objeto_id) u ON u.objeto_id = h.objeto_id""",
    # Estado según los hechos (los objetos sin entrega conservan el suyo)
    """UPDATE objetos SET estado = (SELECT CASE WHEN d.fecha_devolucion IS NOT NULL THEN 'Devuelto' WHEN d.id IS NOT NULL THEN 'Recuperado'
                                               WHEN r.id IS NOT NULL THEN 'Por recuperar' ELSE 'Entregado' END
                                    FROM entregas e LEFT JOIN reclamaciones r ON r.entrega_id = e.id AND r.estado = 'Aceptada'
                                    LEFT JOIN devoluciones d ON d.reclamacion_id = r.id WHERE e.objeto_id = objetos.id)
       WHERE id IN (SELECT objeto_id FROM entregas)""",
]

# Datos que v7.1 exige y v6.2 permitía dejar vacíos: se piden, no se inventan.
REVISIONES = {
    'personas sin tipo (rol)': 'SELECT id FROM vieja.usuarios WHERE rol IS NULL',
    'objetos sin ubicación de resguardo': 'SELECT id FROM vieja.objetos WHERE ubicacion IS NULL',
    'objetos entregados a otra persona después de recuperarlos (v7.1 admite una sola entrega inicial)':
        'SELECT objeto_id FROM vieja.entregas WHERE reclamacion_id IS NULL GROUP BY objeto_id HAVING count(*) > 1',
    'reclamaciones sobre una devolución': '''SELECT r.id FROM vieja.reclamaciones r JOIN vieja.entregas e ON e.id = r.entrega_id
                                             WHERE e.reclamacion_id IS NOT NULL''',
    'devoluciones sin «Recuperación» anotada': '''SELECT d.id FROM vieja.entregas d JOIN vieja.reclamaciones r ON r.id = d.reclamacion_id
        JOIN vieja.entregas e ON e.id = r.entrega_id WHERE NOT EXISTS (SELECT 1 FROM vieja.historial WHERE objeto_id = e.objeto_id
        AND accion = 'Recuperación' AND fecha_hora >= r.fecha_resolucion)''',
}


def tablas(con, base='main'):
    return {fila[0] for fila in con.execute(f"SELECT name FROM {base}.sqlite_master WHERE type = 'table'")}


# Hace falta migrar si la base tiene datos de antes (tabla entregas) y todavía no tiene devoluciones.
def necesita_migracion(ruta):
    try:
        con = sqlite3.connect(f'file:{ruta}?mode=ro', uri=True)
    except sqlite3.OperationalError:
        return False   # la base no existe: la app la crea con el esquema nuevo
    nombres = tablas(con)
    con.close()
    return 'entregas' in nombres and 'devoluciones' not in nombres


def migrar(ruta):
    original = sqlite3.connect(ruta)
    if 'reclamacion_id' not in [c[1] for c in original.execute('PRAGMA table_info(entregas)')]:
        raise RuntimeError('Esta base es de una versión anterior a la 6.2. Ábrela primero con UAM Looking For v6.2 '
                           '(la pasa a la 6.2 sin perder datos) y después con la v7.1.')
    respaldo = ruta.replace('.db', '_respaldo_') + original.execute("SELECT strftime('%Y%m%d_%H%M%S', 'now', 'localtime')").fetchone()[0] + '.db'
    original.backup(sqlite3.connect(respaldo))

    nueva = sqlite3.connect(':memory:')
    with open(bd.RUTA_ESQUEMA, encoding='utf-8') as archivo:
        esquema = archivo.read()
    nueva.executescript(esquema)
    disparadores = nueva.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'").fetchall()
    for (nombre,) in disparadores:
        nueva.execute(f'DROP TRIGGER {nombre}')
    nueva.execute('PRAGMA foreign_keys = ON')
    nueva.execute('ATTACH DATABASE ? AS vieja', (respaldo,))
    problemas = [f'{texto}: {", ".join(str(f[0]) for f in filas)}' for texto, consulta in REVISIONES.items()
                 if (filas := nueva.execute(consulta).fetchall())]
    if not problemas:
        try:
            with nueva:
                for paso in PASOS:
                    nueva.execute(paso)
                for id, clave in nueva.execute('SELECT id, contrasena FROM vieja.usuarios WHERE contrasena IS NOT NULL').fetchall():
                    nueva.execute('UPDATE usuarios SET contrasena_hash = ? WHERE id = ?', (hash_contrasena(clave), id))
            nueva.executescript(esquema)   # vuelve a crear los triggers (IF NOT EXISTS no toca lo demás)
        except sqlite3.Error as error:
            problemas.append(f'error de SQLite: {error}')
    if not problemas:
        contar = lambda sql: nueva.execute(sql).fetchone()[0]
        if contar('PRAGMA main.integrity_check') != 'ok' or nueva.execute('PRAGMA main.foreign_key_check').fetchall():
            problemas.append('integridad o llaves foráneas con errores')
        for tabla in ('usuarios', 'objetos', 'reclamaciones', 'historial'):
            antes, despues = contar(f'SELECT COUNT(*) FROM vieja.{tabla}'), contar(f'SELECT COUNT(*) FROM main.{tabla}')
            if antes != despues:
                problemas.append(f'{tabla}: {antes} registros antes y {despues} después')
        if contar('SELECT COUNT(*) FROM vieja.entregas') != contar('SELECT (SELECT COUNT(*) FROM entregas) + COUNT(fecha_devolucion) FROM devoluciones'):
            problemas.append('no cuadran las entregas con las entregas iniciales y las devoluciones')
        if contar('SELECT COUNT(foto) FROM vieja.objetos') != contar('SELECT COUNT(foto) FROM objetos'):
            problemas.append('faltan fotos')
        if contar('SELECT COUNT(*) FROM vieja.usuarios WHERE contrasena IS NOT NULL') != contar('SELECT COUNT(contrasena_hash) FROM usuarios'):
            problemas.append('faltan contraseñas')
        if contar("SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger'") != len(disparadores):
            problemas.append('faltan triggers')
    nueva.execute('DETACH DATABASE vieja')
    if problemas:
        raise RuntimeError(f'No se migró la base (la original no se tocó; respaldo en {respaldo}). Revisa en la v6.2: ' + '; '.join(problemas))
    nueva.backup(original)
    original.close()
    print(f'Base migrada a v7.1. Respaldo de la anterior: {respaldo}')


def migrar_si_hace_falta(ruta):
    if necesita_migracion(ruta):
        migrar(ruta)


if __name__ == '__main__':
    migrar(bd.RUTA_BD) if necesita_migracion(bd.RUTA_BD) else print('La base ya usa el esquema v7.1. No hay nada que migrar.')
