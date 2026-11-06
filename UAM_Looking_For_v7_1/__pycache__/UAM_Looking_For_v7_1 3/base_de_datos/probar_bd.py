"""Prueba el modelo v8.5 desde cero: esquema, datos, pruebas positivas, pruebas negativas, índices y diagrama.
Uso: python probar_bd.py   (solo usa la biblioteca estándar de Python)."""
import html
import os
import re
import sqlite3
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import reglas_python as rp  # noqa: E402
# schema.sql es el mismo que usa la app: si no está en esta carpeta, se toma el de la carpeta del proyecto
buscar = lambda nombre: next(r for r in (os.path.join(AQUI, nombre), os.path.join(AQUI, '..', nombre)) if os.path.exists(r))
leer = lambda nombre: open(buscar(nombre), encoding='utf-8').read()
TABLAS = ('usuarios', 'objetos', 'entregas', 'reclamaciones', 'devoluciones', 'historial', 'reportes_visitantes')
resultados = []


def ok(nombre, condicion, extra=''):
    resultados.append(bool(condicion))
    print(('PASA ' if condicion else 'FALLA'), nombre, '' if condicion else f'→ {extra}')


con = sqlite3.connect(':memory:', isolation_level=None)
con.row_factory = sqlite3.Row
con.execute('PRAGMA foreign_keys = ON')
con.executescript(leer('schema.sql'))
con.executescript(leer('schema.sql'))   # se puede ejecutar dos veces
objetos_bd = dict(con.execute("SELECT type, COUNT(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' GROUP BY type").fetchall())
print(f'SQLite {sqlite3.sqlite_version} · {objetos_bd}')
con.executescript(leer('datos_prueba.sql'))
uno = lambda sql, p=(): con.execute(sql, p).fetchone()[0]


def en_prueba(pasos):
    """Ejecuta pasos dentro de una transacción que se deshace; devuelve el error o None."""
    con.execute('SAVEPOINT p')
    try:
        for paso in pasos:
            con.execute(paso) if isinstance(paso, str) else paso()
        return None
    except sqlite3.Error as error:
        return str(error)
    finally:
        con.execute('ROLLBACK TO p')
        con.execute('RELEASE p')


print('\n--- Pruebas positivas (deben funcionar) ---')
ok('El esquema crea 7 tablas, 1 vista, 12 índices y 25 triggers, y se puede ejecutar dos veces',
   objetos_bd == {'table': 7, 'view': 1, 'index': 12, 'trigger': 25}, objetos_bd)
ok('Los datos de prueba cargan sin errores', uno('SELECT COUNT(*) FROM usuarios') == 10 and uno('SELECT COUNT(*) FROM devoluciones') == 1)
ok('integrity_check y foreign_key_check sin errores', uno('PRAGMA integrity_check') == 'ok' and not con.execute('PRAGMA foreign_key_check').fetchall())
vida = [tuple(f) for f in con.execute("SELECT accion, usuario_id, estado_nuevo FROM historial WHERE objeto_id = 1 ORDER BY id")]
ok('El historial de la calculadora lo escribieron los triggers, con el autor correcto de cada hecho', vida == [
    ('Registro', 2, 'En resguardo'), ('Entrega', 2, 'Entregado'), ('Reclamación', 4, None), ('Reclamación', 5, None),
    ('Reclamación', 6, None), ('Reclamación cancelada', 6, None), ('Reclamación rechazada', 2, None),
    ('Reclamación aceptada', 2, 'Por recuperar'), ('Recuperación', 3, 'Recuperado'), ('Devolución', 2, 'Devuelto')], vida)
lag = [tuple(f) for f in con.execute('''SELECT LAG(estado_nuevo) OVER (ORDER BY id), estado_nuevo FROM historial
                                        WHERE objeto_id = 1 AND estado_nuevo IS NOT NULL ORDER BY id''')]
ok('El estado anterior se reconstruye con LAG (no se guarda)', lag == [(None, 'En resguardo'), ('En resguardo', 'Entregado'),
   ('Entregado', 'Por recuperar'), ('Por recuperar', 'Recuperado'), ('Recuperado', 'Devuelto')], lag)
v = con.execute('SELECT * FROM vista_devoluciones').fetchone()
ok('La devolución llega al objeto, a la entrega original y al dueño solo por llaves (vista)',
   (v['objeto_id'], v['entrega_id'], v['dueno_id'], v['lo_tenia_id'], v['estado_objeto']) == (1, 1, 4, 7, 'Devuelto'))
ok('devoluciones no repite objeto, entrega ni dueño', not {'objeto_id', 'entrega_id', 'usuario_id', 'dueno_id'}
   & {c[1] for c in con.execute('PRAGMA table_info(devoluciones)')})
ok('Columna renombrada: devoluciones.devuelto_por (y ya no entregado_por)',
   [c[1] for c in con.execute('PRAGMA table_info(devoluciones)')].count('devuelto_por') == 1
   and 'entregado_por' not in [c[1] for c in con.execute('PRAGMA table_info(devoluciones)')])


def flujo_completo():
    con.execute("INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 9, 3, 'Llavero rojo', '2026-11-03 10:00:00')")
    con.execute("INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Mi llavero de la selección', '2026-11-03 11:00:00')")
    con.execute("UPDATE reclamaciones SET descripcion = 'Llavero de la selección con 3 llaves' WHERE id = 10")   # el dueño corrige mientras está pendiente
    con.execute("UPDATE reclamaciones SET estado = 'Aceptada', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 1 WHERE id = 10")
    fases.append(uno('SELECT estado FROM objetos WHERE id = 2'))
    con.execute("INSERT INTO devoluciones (id, reclamacion_id, recibido_por, fecha_recepcion) VALUES (2, 10, 3, '2026-11-03 15:00:00')")
    fases.append(uno('SELECT estado FROM objetos WHERE id = 2'))
    con.execute("UPDATE devoluciones SET devuelto_por = 3, fecha_devolucion = '2026-11-04 08:00:00', observaciones = 'Retiró con carné' WHERE id = 2")
    fases.append(uno('SELECT estado FROM objetos WHERE id = 2'))
    fases.append(uno("SELECT COUNT(*) FROM historial WHERE objeto_id = 2"))


fases = []
error = en_prueba([flujo_completo])
ok('Flujo completo del llavero: el estado lo ponen los triggers (Por recuperar → Recuperado → Devuelto)',
   error is None and fases == ['Por recuperar', 'Recuperado', 'Devuelto', 6], error or fases)
error = en_prueba(["UPDATE objetos SET estado = 'En bodega' WHERE id = 2",
                   "INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora) VALUES (2, 3, 'Cambio de estado', 'En bodega', '2026-11-03 10:00:00')"])
ok('El personal cambia a mano un estado bajo custodia y lo anota', error is None, error)
ok('Se corrige quién trajo el objeto', en_prueba(['UPDATE objetos SET reportado_por = 9 WHERE id = 2']) is None)
fases = []
error = en_prueba(["INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES (2, 2, 9, 3, 'x', '2026-11-03 10:00:00')",
                   "INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, fecha_solicitud) VALUES (10, 2, 5, 'Mías', '2026-11-03 11:00:00')",
                   "UPDATE reclamaciones SET estado = 'Rechazada', respuesta = 'No coincide', fecha_resolucion = '2026-11-03 12:00:00', resuelto_por = 3 WHERE id = 10",
                   lambda: fases.append(uno('SELECT estado FROM objetos WHERE id = 2'))])
ok('Rechazar una reclamación deja el objeto «Entregado»', error is None and fases == ['Entregado'], error or fases)
argon = '$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHRzYWx0$aGFzaGhhc2hoYXNoaGFzaGhhc2g'
ok('Se acepta un hash de otro algoritmo (argon2): el algoritmo se puede cambiar sin tocar la tabla',
   en_prueba([f"UPDATE usuarios SET contrasena_hash = '{argon}' WHERE id = 4"]) is None)
ok('Respaldo: sin el trigger de coherencia, el CHECK sigue rechazando un estado inventado',
   'CHECK constraint failed' in (en_prueba(['DROP TRIGGER trg_objeto_estado_coherente', "UPDATE objetos SET estado = 'Perdido' WHERE id = 2"]) or ''))
ok('Dos visitantes sin CIF conviven (NULL se puede repetir en UNIQUE)', uno('SELECT COUNT(*) FROM usuarios WHERE cif IS NULL') == 2)
ok('El Administrador opera sin hash en la base (su clave está en el .env)', uno('SELECT contrasena_hash IS NULL FROM usuarios WHERE id = 1') == 1)

print('\n--- Reportes de visitantes (v8.5) ---')
rv = con.execute('SELECT * FROM reportes_visitantes WHERE id = 1').fetchone()
ok('El reporte del visitante cargó con su gestión y su intento fallido de WhatsApp',
   (rv['estado'], rv['objeto_id'], rv['actualizado_por'], rv['whatsapp_estado'], rv['whatsapp_intentos']) == ('Localizado', 3, 2, 'Fallida', 1))
ok('El visitante no es un usuario: reportar no crea filas en usuarios', uno('SELECT COUNT(*) FROM usuarios') == 10)
nuevo_reporte = ("INSERT INTO reportes_visitantes (codigo, token_hash, nombre, telefono, objeto_nombre, categoria, descripcion, lugar_perdida, "
                 "fecha_perdida, fecha_registro, foto) VALUES ('UAM-AB12-CD34', '" + 'b' * 64 + "', 'Ana', '8888 1111', 'Celular', 'Electrónicos', "
                 "'Negro con funda roja', 'Cafetería', '2026-11-01', '2026-11-01 10:00:00', X'52494646240000005745425056503820')")
ok('Un visitante registra un reporte con foto WebP y nace Pendiente, sin intentos de WhatsApp',
   en_prueba([nuevo_reporte, lambda: fases.append(con.execute("SELECT estado, whatsapp_estado FROM reportes_visitantes WHERE codigo = 'UAM-AB12-CD34'").fetchone()[:])])
   is None and fases[-1] == ('Pendiente', 'Pendiente'), fases)
ok('El sistema anota un reintento de WhatsApp sin ser personal (solo cambian las columnas whatsapp_*)',
   en_prueba(["UPDATE reportes_visitantes SET whatsapp_estado = 'Enviada', whatsapp_intentos = 2, whatsapp_fecha = '2026-11-01 10:00:00', "
              "whatsapp_detalle = 'wamid.HBgM' WHERE id = 1"]) is None)
ok('Sin WhatsApp configurado queda «No configurada» y cuenta el intento',
   en_prueba([nuevo_reporte, "UPDATE reportes_visitantes SET whatsapp_estado = 'No configurada', whatsapp_intentos = 1, "
              "whatsapp_fecha = '2026-11-01 10:00:01', whatsapp_detalle = 'Faltan datos en el .env' WHERE codigo = 'UAM-AB12-CD34'"]) is None)
ok('El personal cierra el reporte, quita la relación y deja observaciones',
   en_prueba(["UPDATE reportes_visitantes SET estado = 'Cerrado', objeto_id = NULL, observaciones = 'No era su mochila', "
              "actualizado_por = 3, fecha_actualizacion = '2026-11-02 08:00:00' WHERE id = 1"]) is None)
ok('El permiso de gestionar reportes es del personal activo (Python)',
   rp.puede(dict(con.execute('SELECT * FROM usuarios WHERE id = 2').fetchone()), 'gestionar_reporte_visitante')
   and not rp.puede(dict(con.execute('SELECT * FROM usuarios WHERE id = 4').fetchone()), 'gestionar_reporte_visitante')
   and not rp.puede(dict(con.execute('SELECT * FROM usuarios WHERE id = 10').fetchone()), 'gestionar_reporte_visitante'))

print('\n--- Validaciones en Python (reglas_python.py) ---')
h = rp.hash_contrasena('clave123')
ok('Hash nuevo: se verifica la clave correcta y se rechaza otra', rp.verificar_contrasena('clave123', h) and not rp.verificar_contrasena('clave124', h))
ok('Los hashes de los datos de prueba corresponden a «clave123»', rp.verificar_contrasena('clave123', uno('SELECT contrasena_hash FROM usuarios WHERE id = 4')))
ok('Mismo texto, hashes distintos (sal aleatoria)', rp.hash_contrasena('clave123') != rp.hash_contrasena('clave123'))
ok('El hash generado cumple el CHECK de la base', en_prueba([lambda: con.execute('UPDATE usuarios SET contrasena_hash = ? WHERE id = 4', (h,))]) is None)
ok('Un hash con menos iteraciones pide recalcularse; uno actual no', rp.necesita_rehash(rp.hash_contrasena('x', 1000)) and not rp.necesita_rehash(h))
u = {f['id']: dict(f) for f in con.execute('SELECT * FROM usuarios')}
r1 = dict(con.execute('SELECT * FROM reclamaciones WHERE id = 1').fetchone())
ok('Permisos: la encargada registra; el estudiante y la encargada desactivada no',
   rp.puede(u[2], 'registrar_objeto') and not rp.puede(u[4], 'registrar_objeto') and not rp.puede(u[10], 'registrar_objeto'))
ok('Permisos: solo el autor cancela su reclamación; una persona sin cuenta no reclama',
   rp.puede(u[4], 'cancelar_reclamacion', r1) and not rp.puede(u[5], 'cancelar_reclamacion', r1) and not rp.puede(u[7], 'presentar_reclamacion'))

print('\n--- Pruebas negativas (deben ser rechazadas) ---')
antes = [con.execute(f'SELECT * FROM {t}').fetchall() for t in TABLAS]
negativas = 0
for bloque in leer('pruebas_negativas.sql').split('-- PRUEBA: ')[1:]:
    encabezado, cuerpo = bloque.split('\n', 1)
    nombre, espera = (p.strip() for p in encabezado.split('| espera:'))
    preparar, falla = cuerpo.split('-- FALLA', 1)
    falla = '\n'.join(l for l in falla.splitlines() if l.strip() and not l.startswith('--'))
    pasos = [s for s in preparar.split(';') if s.strip() and not all(l.strip().startswith('--') for l in s.strip().splitlines())]
    con.execute('SAVEPOINT n')
    try:
        for paso in pasos:
            con.execute(paso)
        try:
            con.execute(falla)
            resultado, bien = 'NO FALLÓ', False
        except sqlite3.Error as error:
            resultado, bien = str(error), espera in str(error)
    except sqlite3.Error as error:
        resultado, bien = f'falló la preparación: {error}', False
    con.execute('ROLLBACK TO n')
    con.execute('RELEASE n')
    negativas += 1
    ok(nombre, bien, resultado)
ok('La base queda idéntica después de las pruebas negativas', antes == [con.execute(f'SELECT * FROM {t}').fetchall() for t in TABLAS])

print('\n--- Índices ---')
indices = {}
for t in TABLAS:
    for i in con.execute(f'PRAGMA index_list({t})'):
        indices[i[1]] = (t, tuple(c[2] for c in con.execute(f'PRAGMA index_info({i[1]})')), bool(i[4]))
completos = [(t, cols) for t, cols, parcial in indices.values() if not parcial]
ok('Ningún índice repite a otro (mismas columnas)', len(completos) == len(set(completos)), completos)
ok('Ningún índice es el comienzo de otro (sería redundante)',
   not [a for a in completos for b in completos if a != b and a[0] == b[0] and b[1][:len(a[1])] == a[1]])

print('\n--- Diagrama vs SQL ---')
ruta = os.path.join(AQUI, 'UAM_Looking_For_BD_v8_5.drawio')
if os.path.exists(ruta):
    esperado = {}
    for t in TABLAS:
        uq = {c[2] for i in con.execute(f'PRAGMA index_list({t})') if i[2] and not i[4] and i[3] != 'pk'
              for c in con.execute(f'PRAGMA index_info({i[1]})')}
        nn = {c[1]: c[3] for c in con.execute(f'PRAGMA table_info({t})')}
        for f in con.execute(f'PRAGMA foreign_key_list({t})'):
            esperado[(f[2], t, f[3])] = ('ERmandOne' if nn[f[3]] else 'ERzeroToOne', 'ERzeroToOne' if f[3] in uq else 'ERzeroToMany')
    x = leer('UAM_Looking_For_BD_v8_5.drawio')
    dibujado = {}
    for m in re.finditer(r'value="([^"]*)" style="[^"]*startArrow=(\w+);[^"]*endArrow=(\w+);[^"]*" edge="1" parent="1" source="t_(\w+)" target="t_(\w+)"', x):
        col = re.search(r'<b>(\w+)</b>', html.unescape(m.group(1))).group(1)
        dibujado[(m.group(4), m.group(5), col)] = (m.group(2), m.group(3))
    ok(f'Las {len(esperado)} relaciones del diagrama tienen la misma cardinalidad que el SQL', esperado == dibujado,
       set(esperado.items()) ^ set(dibujado.items()))
    for padre, hijo, col, lectura in (('objetos', 'entregas', 'objeto_id', '1 : 0..1'), ('entregas', 'reclamaciones', 'entrega_id', '1 : 0..N'),
                                      ('reclamaciones', 'devoluciones', 'reclamacion_id', '1 : 0..1')):
        ok(f'{padre} → {hijo} es {lectura} en el SQL y en el diagrama',
           esperado[(padre, hijo, col)] == dibujado.get((padre, hijo, col)) == ('ERmandOne', 'ERzeroToOne' if '0..1' in lectura else 'ERzeroToMany'))

    ok('objetos → reportes_visitantes es 0..1 : 0..N (un reporte se relaciona como máximo con un objeto)',
       esperado[('objetos', 'reportes_visitantes', 'objeto_id')] == dibujado.get(('objetos', 'reportes_visitantes', 'objeto_id')) == ('ERzeroToOne', 'ERzeroToMany'))

print(f'\n{sum(resultados)}/{len(resultados)} pruebas pasaron ({negativas} negativas)')
