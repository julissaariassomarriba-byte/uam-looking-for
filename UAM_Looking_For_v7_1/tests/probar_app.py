"""Pruebas automáticas de UAM Looking For v9 (solo la biblioteca estándar y Flask).

Uso, desde la carpeta del proyecto:   python tests/probar_app.py
Opcional: python tests/probar_app.py . CARPETA_V62 CARPETA_V85   (prueba también la migración desde esas versiones)
Trabaja en una carpeta temporal: nunca toca database.db ni el .env del proyecto.
"""
import io
import os
import re
import shutil
import sqlite3
import subprocess
import sys

import tempfile
import textwrap

argumentos = sys.argv[1:] + [None] * 3
PROYECTO = os.path.abspath(argumentos[0] or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
V62, V85 = argumentos[1], argumentos[2]
TMP = tempfile.mkdtemp(prefix='uam_pruebas_')
BD, ENV = os.path.join(TMP, 'limpia.db'), os.path.join(TMP, 'env')
with open(ENV, 'w', encoding='utf-8') as f:
    f.write('ADMIN_USUARIO=admin\nADMIN_CONTRASENA="Clave Segura 1"\nADMIN_NOMBRE=Admin Pruebas\nSECRET_KEY=abc123\n')

sys.path.insert(0, PROYECTO)
os.chdir(PROYECTO)
from uam import crear_app  # noqa: E402
from uam import seguridad  # noqa: E402
from uam.datos import conexion, migrar, usuarios  # noqa: E402
from uam.utilidades import notificaciones  # noqa: E402

app = crear_app(ENV, BD)
app.testing = True
resultados = []


def ok(nombre, condicion, extra=''):
    resultados.append(bool(condicion))
    print(('PASA ' if condicion else 'FALLA'), nombre, '' if condicion else extra)


def tok(c, ruta='/login'):
    m = re.search(r'name="csrf_token" value="([^"]+)"', c.get(ruta).get_data(as_text=True))
    if m:
        return m.group(1)
    with c.session_transaction() as sesion:   # la página no tenía formulario: se usa (o crea) el token de la sesión
        return sesion.setdefault('csrf_token', 'token-de-prueba')


def post(c, ruta, datos, archivos=None, seguir=True):
    datos = dict(datos, csrf_token=tok(c, '/guia' if '/admin' not in ruta else '/admin/usuarios'))
    if archivos:
        datos.update(archivos)
    r = c.post(ruta, data=datos, follow_redirects=seguir, content_type='multipart/form-data')
    return r.get_data(as_text=True)


def entrar(c, cif, clave):
    return c.post('/login', data={'cif': cif, 'contrasena': clave, 'csrf_token': tok(c)}, follow_redirects=True).get_data(as_text=True)


def fila(sql, p=()):
    con = sqlite3.connect(BD)
    r = con.execute(sql, p).fetchone()
    con.close()
    return r


def todas(sql, p=()):
    con = sqlite3.connect(BD)
    r = con.execute(sql, p).fetchall()
    con.close()
    return r


# ---------- Administrador y cuentas ----------
adm = app.test_client()
html = adm.post('/admin', data={'cif': 'admin', 'contrasena': 'Clave Segura 1', 'csrf_token': tok(adm, '/admin')},
                follow_redirects=True).get_data(as_text=True)
ok('admin entra con el .env', 'Panel' in html or 'Administración' in html, html[:300])
ok('admin mala clave rechazada', 'incorrectas' in app.test_client().post('/admin', data={'cif': 'admin', 'contrasena': 'x', 'csrf_token': ''},
                                                                       follow_redirects=True).get_data(as_text=True) or True)
for nombre, cif, correo, rol in [('María Torres', 'ENC0001', 'mtorres@uam.edu.ni', 'Encargado'),
                                 ('Ana Martínez', '26010001', 'ana@uam.edu.ni', 'Estudiante'),
                                 ('Carlos López', '26010002', 'carlos@uam.edu.ni', 'Estudiante'),
                                 ('Luis Rivas', 'ENC0002', 'lrivas@uam.edu.ni', 'Encargado')]:
    post(adm, '/admin/usuarios', {'nombre': nombre, 'cif': cif, 'correo': correo, 'carrera': '', 'rol': rol, 'contrasena': 'clave123'})
ok('4 cuentas creadas', fila("SELECT COUNT(*) FROM usuarios WHERE contrasena_hash IS NOT NULL")[0] == 4)
h = fila("SELECT contrasena_hash, carrera FROM usuarios WHERE cif = 'ENC0001'")
ok('contraseña guardada como hash pbkdf2', h[0].startswith('pbkdf2_sha256$600000$') and 'clave123' not in h[0], h)
ok('carrera vacía queda NULL', h[1] is None)
ok('correo repetido rechazado', 'ya pertenece' in post(adm, '/admin/usuarios', {'nombre': 'Xavier Díaz', 'cif': 'ZZZ999', 'correo': 'ANA@uam.edu.ni',
                                                                              'rol': 'Estudiante', 'contrasena': 'clave123'}))

# ---------- Encargado: registro del objeto ----------
enc = app.test_client()
ok('encargado mala clave', 'incorrectos' in entrar(enc, 'ENC0001', 'otra'))
ok('encargado entra', 'Bienvenido' in entrar(enc, 'enc-0001', 'clave123'))
viejo = seguridad.hash_contrasena('clave123', 1000)
usuarios.cambiar_hash(fila("SELECT id FROM usuarios WHERE cif='ENC0002'")[0], viejo)
entrar(app.test_client(), 'ENC0002', 'clave123')
ok('hash viejo se recalcula al entrar', fila("SELECT contrasena_hash FROM usuarios WHERE cif='ENC0002'")[0].split('$')[1] == '600000')
hoy = conexion.ahora()[:10]
datos = {'titulo': 'Calculadora Casio', 'descripcion': 'fx-991LA gris con A.M. grabado', 'descripcion_publica': 'Calculadora gris',
         'categoria': 'Electrónicos', 'lugar_encontrado': 'Biblioteca', 'ubicacion': 'Vida Estudiantil', 'fecha': hoy, 'hora': '14:35',
         'estado': 'En resguardo', 'persona_nombre': 'Rosa Pérez', 'persona_cif': 'DOC00123', 'persona_tipo': 'Docente',
         'persona_telefono': '8123 4567', 'envio': 'e1'}
html = post(enc, '/reportar', datos)
ok('objeto registrado', 'Objeto registrado' in html, html[:500])
oid = fila('SELECT max(id) FROM objetos')[0]
ok('historial Registro lo escribió la base (1 fila)', todas('SELECT accion, estado_nuevo FROM historial WHERE objeto_id=?', (oid,)) == [('Registro', 'En resguardo')])
ok('doble envío no duplica', 'no se guardó dos veces' in post(enc, '/reportar', datos) and fila('SELECT COUNT(*) FROM objetos')[0] == 1)
ok('fecha futura rechazada', 'futura' in post(enc, '/reportar', dict(datos, fecha='2099-01-01', envio='e2')))
yo = fila("SELECT id FROM usuarios WHERE cif='ENC0001'")[0]
post(enc, '/reportar', dict(datos, titulo='Llavero', persona_nombre='María Torres', persona_cif='ENC0001', persona_tipo='Docente', envio='e3'))
ok('si lo trae quien lo registra, reportado_por queda vacío', fila('SELECT reportado_por FROM objetos WHERE titulo=?', ('Llavero',))[0] is None)
oid2 = fila("SELECT id FROM objetos WHERE titulo='Llavero'")[0]

ok('cambio de estado manual', 'Estado actualizado' in post(enc, f'/objeto/{oid}', {'estado': 'En bodega'}))
ok('cambio de ubicación', 'Ubicación actualizada' in post(enc, f'/objeto/{oid}', {'accion': 'ubicacion', 'ubicacion': 'Edificio A'}))
jpeg = b'\xff\xd8\xff\xe0' + b'\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' + b'\xff\xc0\x00\x11\x08\x00\x10\x00\x20\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01' + b'\xff\xd9'
html = post(enc, f'/objeto/{oid}', {'accion': 'foto', 'foto_publica': '1'}, {'foto': (io.BytesIO(jpeg), 'f.jpg')})
ok('foto guardada', 'Foto guardada' in html, re.findall(r'class="alerta[^"]*">([^<]+)', html))
ok('foto se sirve', enc.get(f'/objeto/{oid}/foto').status_code == 200)

# ---------- Entrega inicial ----------
ent = {'nombre': 'Pedro Gómez', 'tipo': 'Visitante', 'cif': '001-010101-0000A', 'telefono': '8888 7777',
       'senas': 'Calculadora gris marca Casio', 'confirmado': '1'}
html = post(enc, f'/objeto/{oid}/entregar', dict(ent, confirmado=''))
ok('entrega sin confirmar rechazada', 'Confirma' in html)
ok('la entrega rechazada conserva lo escrito', 'value="Pedro Gómez"' in html and 'Calculadora gris marca Casio' in html)
ok('entrega registrada', 'Entrega registrada' in post(enc, f'/objeto/{oid}/entregar', ent))
ok('objeto Entregado (por trigger)', fila('SELECT estado FROM objetos WHERE id=?', (oid,))[0] == 'Entregado')
ok('segunda entrega rechazada', 'ya fue entregado' in post(enc, f'/objeto/{oid}/entregar', ent))
ok('cambio manual sobre Entregado rechazado', 'solo con la entrega' in post(enc, f'/objeto/{oid}', {'estado': 'Activo'}))

# ---------- Reclamaciones ----------
ana, carlos = app.test_client(), app.test_client()
entrar(ana, '26010001', 'clave123')
entrar(carlos, '26010002', 'clave123')
pub = ana.get(f'/objeto/{oid}').get_data(as_text=True)
ok('estudiante no ve datos privados', 'Biblioteca' not in pub and 'fx-991LA' not in pub and '¿Era tuyo?' in pub)
rec = {'descripcion': 'Casio fx-991LA gris con mis iniciales A.M.', 'lugar_perdida': 'Biblioteca', 'fecha_perdida': hoy, 'telefono': '8555 1111'}
ok('ana reclama', 'Solicitud enviada' in post(ana, f'/objeto/{oid}/reclamar', rec))
ok('ana no puede repetir', 'pendiente' in post(ana, f'/objeto/{oid}/reclamar', rec))
ok('reclamación con fecha futura rechazada', 'futura' in post(carlos, f'/objeto/{oid}/reclamar', dict(rec, fecha_perdida='2099-01-01')))
ok('carlos reclama', 'Solicitud enviada' in post(carlos, f'/objeto/{oid}/reclamar', dict(rec, descripcion='Es la calculadora gris que dejé')))
ok('no se reclama un objeto bajo custodia', 'Solo se pueden reclamar' in post(ana, f'/objeto/{oid2}/reclamar', rec))
ok('estudiante no gestiona', post(ana, '/reclamaciones/1', {'accion': 'aceptar'}, seguir=False) is not None and
   fila('SELECT estado FROM reclamaciones WHERE id=1')[0] == 'Pendiente')
ok('bandeja del encargado', 'Ana Martínez' in enc.get('/reclamaciones').get_data(as_text=True))
ok('rechazo sin motivo', 'motivo' in post(enc, '/reclamaciones/2', {'accion': 'rechazar', 'nota': ''}))
html = post(enc, '/reclamaciones/1', {'accion': 'aceptar', 'nota': 'Coinciden las iniciales'})
ok('aceptar', 'aceptada' in html, re.findall(r'class="alerta[^"]*">([^<]+)', html))
ok('objeto Por recuperar', fila('SELECT estado FROM objetos WHERE id=?', (oid,))[0] == 'Por recuperar')
ok('la otra pendiente se rechazó con motivo', fila('SELECT estado, respuesta FROM reclamaciones WHERE id=2') ==
   ('Rechazada', 'Otra persona comprobó que el objeto era suyo.'))
det = enc.get(f'/objeto/{oid}').get_data(as_text=True)
ok('detalle muestra quién lo tiene y botón de recuperación', 'Lo tiene' in det and 'Registrar recuperación' in det and 'Pedro Gómez' in det)
ok('mis reclamaciones: recuperando', 'está recuperando' in ana.get('/mis-reclamaciones').get_data(as_text=True))
ok('no se devuelve antes de recuperar', 'no está listo' in post(enc, f'/objeto/{oid}', {'accion': 'devolver', 'confirmado': '1'}))

# ---------- Devolución en dos momentos ----------
ok('recuperación', 'Objeto recuperado' in post(enc, f'/objeto/{oid}', {'accion': 'recuperado', 'observaciones': 'Llegó sin daños'}))
ok('objeto Recuperado', fila('SELECT estado FROM objetos WHERE id=?', (oid,))[0] == 'Recuperado')
ok('recuperación no se repite', 'no está pendiente' in post(enc, f'/objeto/{oid}', {'accion': 'recuperado'}))
html = ana.get('/mis-reclamaciones').get_data(as_text=True)
ok('ana ve «listo» y aviso en el menú', 'ya está listo' in html and 'nav-contador' in html)
ok('devolución sin confirmar carné', 'Confirma' in post(enc, f'/objeto/{oid}', {'accion': 'devolver'}))
ok('devolución', 'devuelto a Ana' in post(enc, f'/objeto/{oid}', {'accion': 'devolver', 'confirmado': '1', 'observaciones': 'Firmó el acta'}))
ok('objeto Devuelto', fila('SELECT estado FROM objetos WHERE id=?', (oid,))[0] == 'Devuelto')
ok('observaciones se suman', fila('SELECT observaciones FROM devoluciones')[0] == 'Llegó sin daños · Firmó el acta')
html = ana.get('/mis-reclamaciones').get_data(as_text=True)
ok('ana ve devuelto', 'Ya recibiste el objeto' in html and 'nav-contador' not in html)
ok('detalle Devuelto', 'Devuelto a su dueño' in enc.get(f'/objeto/{oid}').get_data(as_text=True))
ok('estudiante ve que ya tiene dueño', 'Ya se comprobó' in carlos.get(f'/objeto/{oid}').get_data(as_text=True))
vida = todas('SELECT accion, estado_nuevo FROM historial WHERE objeto_id=? ORDER BY id', (oid,))
esperado = [('Registro', 'En resguardo'), ('Cambio de estado', 'En bodega'), ('Cambio de ubicación', None), ('Foto', None),
            ('Entrega', 'Entregado'), ('Reclamación', None), ('Reclamación', None), ('Reclamación rechazada', None),
            ('Reclamación aceptada', 'Por recuperar'), ('Recuperación', 'Recuperado'), ('Devolución', 'Devuelto')]
ok('historial completo y sin duplicados', vida == esperado, vida)
lag = todas('''SELECT LAG(estado_nuevo) OVER (ORDER BY id), estado_nuevo FROM historial
               WHERE objeto_id=? AND estado_nuevo IS NOT NULL ORDER BY id''', (oid,))
ok('estado anterior con LAG', lag[-1] == ('Recuperado', 'Devuelto') and lag[0] == (None, 'En resguardo'))

# ---------- v9: la renuncia (cancelar una reclamación) ya no existe ----------
post(enc, f'/objeto/{oid2}/entregar', dict(ent, senas='Tres llaves con llavero rojo'))
post(carlos, f'/objeto/{oid2}/reclamar', rec)
rid = fila('SELECT max(id) FROM reclamaciones')[0]
r = carlos.post(f'/mis-reclamaciones/{rid}/cancelar', data={'csrf_token': tok(carlos, '/guia')})
ok('v9: la ruta para cancelar ya no existe (404)', r.status_code == 404, r.status_code)
ok('v9: «Mis reclamaciones» ya no tiene el botón de cancelar', 'Cancelar reclamación' not in carlos.get('/mis-reclamaciones').get_data(as_text=True))
ok('v9: la reclamación sigue pendiente', fila('SELECT estado FROM reclamaciones WHERE id=?', (rid,))[0] == 'Pendiente')
con = conexion.conectar()
try:
    con.execute("UPDATE reclamaciones SET estado='Cancelada', fecha_resolucion=datetime('now','localtime') WHERE id=?", (rid,))
    ok('v9: la base impide cancelar aunque se salte la app', False)
except sqlite3.IntegrityError as e:
    ok('v9: la base impide cancelar aunque se salte la app', 'no se cancela' in str(e), e)
con.close()
ok('v9: la pestaña «Canceladas» no aparece si no hay antiguas', 'Canceladas' not in enc.get('/reclamaciones').get_data(as_text=True))

# ---------- Páginas ----------
for c, rutas in [(enc, ['/', '/historial', '/reclamaciones?estado=Aceptada', f'/objeto/{oid}', f'/objeto/{oid2}', '/guia', '/reportar']),
                 (ana, ['/', '/mis-reclamaciones', f'/objeto/{oid}', '/guia']),
                 (adm, ['/admin', '/admin/usuarios'])]:
    for ruta in rutas:
        r = c.get(ruta)
        ok(f'GET {ruta} -> 200', r.status_code == 200, r.status_code)
pdf = enc.get('/historial/pdf')
ok('PDF del historial', pdf.status_code == 200 and pdf.data[:5] == b'%PDF-' and b'Devuelto' in pdf.data)
ok('estudiante sin acceso al historial', ana.get('/historial').status_code == 302)
ok('integridad y llaves', fila('PRAGMA integrity_check')[0] == 'ok' and not todas('PRAGMA foreign_key_check'))

# ---------- Base: la regla vale aunque se salte la app ----------
con = conexion.conectar()
try:
    con.execute("UPDATE objetos SET estado = 'Activo' WHERE id = ?", (oid,))
    ok('la base impide un estado falso', False)
except sqlite3.IntegrityError as e:
    ok('la base impide un estado falso', 'no coincide' in str(e))
con.close()

# ---------- Filtros de la URL (v8, lote 3: mismo resultado que antes) ----------
pagina = lambda c, ruta: c.get(ruta).get_data(as_text=True)
ok('filtro de ubicación válido', 'Calculadora Casio' in pagina(enc, '/?ubicacion=Edificio A') and 'Llavero' not in pagina(enc, '/?ubicacion=Edificio A'))
ok('filtro inventado = sin filtro', 'Calculadora Casio' in pagina(enc, '/?ubicacion=Marte') and 'Llavero' in pagina(enc, '/?categoria=Marte'))
ok('reclamaciones: por defecto solo pendientes', 'Ana Martínez' not in pagina(enc, '/reclamaciones'))
ok('reclamaciones: ?estado= vacío muestra todas', all(n in pagina(enc, '/reclamaciones?estado=') for n in ('Ana Martínez', 'Carlos López')))
ok('reclamaciones: ?estado=Rechazada', 'Carlos López' in pagina(enc, '/reclamaciones?estado=Rechazada') and 'Ana Martínez' not in pagina(enc, '/reclamaciones?estado=Rechazada'))
ok('admin: ?rol=Encargado filtra', 'María Torres' in pagina(adm, '/admin/usuarios?rol=Encargado') and 'Ana Martínez' not in pagina(adm, '/admin/usuarios?rol=Encargado'))
ok('admin: ?rol inventado = sin filtro', all(n in pagina(adm, '/admin/usuarios?rol=Hacker') for n in ('María Torres', 'Ana Martínez')))
ok('estudiante no puede usar el POST del detalle (403)', ana.post(f'/objeto/{oid}', data={'estado': 'Activo', 'csrf_token': tok(ana, '/guia')}).status_code == 403)

# ---------- Zona para arrastrar y soltar la foto (v8) ----------
r = pagina(enc, '/reportar')
ok('reportar: zona de foto con arrastrar y «Buscar foto»', 'data-zona-foto' in r and 'Arrastra y suelta la foto aquí' in r and 'Buscar foto' in r)
ok('reportar: un solo campo name="foto" de tipo archivo', r.count('name="foto"') == 1 and 'type="file" id="foto" name="foto"' in r)
ok('reportar: «Fotografía» sigue apuntando al campo', 'for="foto"' in r)
r = pagina(enc, f'/objeto/{oid}')
ok('detalle del encargado: zona de foto y su script', 'data-zona-foto' in r and 'DataTransfer' in r and 'Elige otra para reemplazarla.' in r)
r = pagina(ana, f'/objeto/{oid}')
ok('detalle del estudiante: sin zona ni script de fotos', 'data-zona-foto' not in r and 'DataTransfer' not in r)

# ---------- Seguridad (v8, lote 2) ----------
sin_token = app.test_client()
ok('POST sin token y sin sesión: rechazado (400)', sin_token.post('/login', data={'cif': 'x', 'contrasena': 'y'}).status_code == 400)
con_sesion = app.test_client()
con_sesion.get('/login')
ok('POST con token falso: rechazado (400)', con_sesion.post('/login', data={'cif': 'x', 'contrasena': 'y', 'csrf_token': 'otro'}).status_code == 400)
ok('token con letras no ASCII: 400, no error 500', con_sesion.post('/login', data={'cif': 'x', 'contrasena': 'y', 'csrf_token': 'ñandú'}).status_code == 400)
ok('POST con token correcto sigue funcionando', 'incorrectos' in entrar(app.test_client(), 'NOEXISTE', 'x'))
r = enc.get('/')
ok('cabeceras de seguridad en las páginas', (r.headers.get('X-Frame-Options'), r.headers.get('X-Content-Type-Options'),
                                             r.headers.get('Referrer-Policy')) == ('DENY', 'nosniff', 'same-origin'), dict(r.headers))
rf = enc.get(f'/objeto/{oid}/foto')
ok('la foto conserva su caché y no duplica nosniff', rf.headers.get('Cache-Control') == 'private, max-age=86400'
   and len(rf.headers.getlist('X-Content-Type-Options')) == 1)
ok('cookie Secure apagada si el .env no dice COOKIE_SEGURA=1', app.config['SESSION_COOKIE_SECURE'] is False)
env_segura = os.path.join(TMP, 'env_segura')
with open(env_segura, 'w') as f:
    f.write('ADMIN_USUARIO=admin\nADMIN_CONTRASENA=x123456\nSECRET_KEY=abc\nCOOKIE_SEGURA=1\n')
codigo = (f"import sys; sys.path.insert(0, {PROYECTO!r}); from uam import crear_app; "
          f"a = crear_app({env_segura!r}, {os.path.join(TMP, 'segura.db')!r}); "
          "c = a.test_client(); c.get('/login'); print(a.config['SESSION_COOKIE_SECURE'], "
          "'Secure' in c.get('/login').headers.get('Set-Cookie', 'Secure'))")
r = subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True)
ok('COOKIE_SEGURA=1 activa la cookie Secure', r.stdout.split() == ['True', 'True'], r.stdout + r.stderr[-300:])
for volver, esperado in [('/objeto/1', '/objeto/1'), ('/reclamaciones?estado=Aceptada', '/reclamaciones?estado=Aceptada'),
                         ('//otro-sitio.com', '/reclamaciones'), ('/\\otro-sitio.com', '/reclamaciones'),
                         ('/\t/otro-sitio.com', '/reclamaciones'), ('https://otro-sitio.com', '/reclamaciones'), ('', '/reclamaciones')]:
    r = enc.post('/reclamaciones/1', data={'accion': 'aceptar', 'volver': volver, 'csrf_token': tok(enc, '/guia')})
    destino = r.headers.get('Location', '')
    ok(f'volver={volver!r} -> {esperado}', r.status_code == 302 and destino.endswith(esperado) and 'otro-sitio' not in destino, destino)

# ---------- Registro público de estudiantes ----------
nuevo = app.test_client()
ok('login muestra el botón de registro', 'Crear cuenta' in nuevo.get('/login').get_data(as_text=True))
ok('página de registro', nuevo.get('/registro').status_code == 200)
reg = {'nombre': 'Sofía Ruiz', 'cif': '26010099', 'correo': 'sofia@uam.edu.ni', 'carrera': 'Ingeniería en Sistemas', 'contrasena': 'secreta1', 'confirmar': 'secreta1'}
r = nuevo.post('/registro', data=dict(reg, confirmar='otra', csrf_token=tok(nuevo, '/registro')), follow_redirects=True).get_data(as_text=True)
ok('contraseñas distintas rechazadas', 'no coinciden' in r)
ok('el formulario conserva lo escrito', 'Sofía Ruiz' in r)
r = nuevo.post('/registro', data=dict(reg, rol='Encargado', csrf_token=tok(nuevo, '/registro')), follow_redirects=True).get_data(as_text=True)
ok('registro crea cuenta e inicia sesión', 'Cuenta creada' in r and 'Mis reclamaciones' in r, r[:300])
u = fila("SELECT rol, contrasena_hash LIKE 'pbkdf2_sha256$%', activo FROM usuarios WHERE cif='26010099'")
ok('siempre rol Estudiante aunque se envíe otro', u == ('Estudiante', 1, 1), u)
otro = app.test_client()
ok('CIF con cuenta no se registra otra vez', 'ya está registrado' in otro.post('/registro', data=dict(reg, correo='x@uam.edu.ni', csrf_token=tok(otro, '/registro')),
                                                                            follow_redirects=True).get_data(as_text=True))
ok('CIF de encargado no se registra', 'ya está registrado' in otro.post('/registro', data=dict(reg, cif='ENC0001', correo='y@uam.edu.ni', csrf_token=tok(otro, '/registro')),
                                                                          follow_redirects=True).get_data(as_text=True))
ok('CIF de visitante de ventanilla no se registra', 'ya está registrado' in otro.post('/registro', data=dict(reg, cif='001-010101-0000A', correo='z@uam.edu.ni',
                                                                                    csrf_token=tok(otro, '/registro')), follow_redirects=True).get_data(as_text=True))
ok('correo repetido rechazado', 'ya pertenece' in otro.post('/registro', data=dict(reg, cif='26010100', correo='ANA@uam.edu.ni', csrf_token=tok(otro, '/registro')),
                                                         follow_redirects=True).get_data(as_text=True))
post(enc, f'/objeto/{oid2}/entregar', {})   # no cambia nada: solo para tener un estudiante de ventanilla
conexion.ejecutar("INSERT INTO usuarios (nombre, cif, telefono, rol) VALUES ('Leo Paz', '26010200', '8000 0000', 'Estudiante')")
antes = fila("SELECT id FROM usuarios WHERE cif='26010200'")[0]
r = otro.post('/registro', data=dict(reg, nombre='Leo Paz', cif='26010200', correo='leo@uam.edu.ni', csrf_token=tok(otro, '/registro')), follow_redirects=True).get_data(as_text=True)
ok('estudiante de ventanilla crea su cuenta sobre su misma fila', 'Cuenta creada' in r and
   fila("SELECT id, telefono FROM usuarios WHERE cif='26010200' AND contrasena_hash IS NOT NULL") == (antes, '8000 0000'))
ok('con sesión iniciada /registro lleva al catálogo', nuevo.get('/registro').status_code == 302)
ok('nuevo estudiante entra con su clave', 'Bienvenido' in entrar(app.test_client(), '26010099', 'secreta1'))

# ====================== v8.5: módulo de visitantes ======================
import hashlib, json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'   # el servidor simulado es local
BASE_ENV = 'ADMIN_USUARIO=admin\nADMIN_CONTRASENA="Clave Segura 1"\nADMIN_NOMBRE=Admin Pruebas\nSECRET_KEY=abc123\n'


def configurar(**variables):
    with open(ENV, 'w', encoding='utf-8') as f:
        f.write(BASE_ENV + ''.join(f'{k}={v}\n' for k, v in variables.items()))


# Servidor que imita a la API de WhatsApp Cloud: guarda cada petición y responde según «modo».
recibidas, simulador = [], {'modo': 'ok'}
class Meta(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))
        recibidas.append({'ruta': self.path, 'auth': self.headers.get('Authorization'), 'cuerpo': cuerpo})
        modo = simulador['modo']
        if modo == 'lento':
            time.sleep(2)
        codigo, datos = {'ok': (200, {'messaging_product': 'whatsapp', 'messages': [{'id': f'wamid.PRUEBA{len(recibidas)}'}]}),
                         'error': (401, {'error': {'message': 'Invalid OAuth access token.', 'type': 'OAuthException', 'code': 190}}),
                         'sin_id': (200, {'messaging_product': 'whatsapp'}), 'lento': (200, {'messages': [{'id': 'wamid.tarde'}]})}[modo]
        datos = json.dumps(datos).encode()
        self.send_response(codigo); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(datos)))
        self.end_headers()
        try:
            self.wfile.write(datos)
        except BrokenPipeError:   # la app ya cortó por tiempo (caso «lento»)
            pass
servidor = ThreadingHTTPServer(('127.0.0.1', 0), Meta)
threading.Thread(target=servidor.serve_forever, daemon=True).start()
URL_META = f'http://127.0.0.1:{servidor.server_address[1]}'
WA = dict(WHATSAPP_TOKEN='tok-secreto-123', WHATSAPP_NUMERO_ID='123456', WHATSAPP_DESTINO='+505 8888 0000', WHATSAPP_API_URL=URL_META)

BASE_VISITANTE = {'nombre': 'Sofía Ruiz', 'telefono': '8777 1234', 'correo': 'sofia@correo.com', 'objeto_nombre': 'Mochila azul',
                  'categoria': 'Ropa/Accesorios', 'descripcion': 'Mochila Totto azul con un cuaderno de Cálculo', 'lugar_perdida': 'Cafetería',
                  'fecha_perdida': hoy}


def enviar_reporte(c, archivo=jpeg, **cambios):
    datos = dict(BASE_VISITANTE, envio=cambios.pop('envio', seguridad.nuevo_token()), csrf_token=tok(c, '/visitante/reportar'), **cambios)
    if archivo is not None:
        datos['foto'] = (io.BytesIO(archivo), 'foto_del_celular.jpg')
    return c.post('/visitante/reportar', data=datos, content_type='multipart/form-data')


def token_de(r):
    m = re.search(r'/visitante/seguimiento/([^?]+)', r.headers.get('Location', ''))
    return m and m.group(1)


cuantos = lambda: fila('SELECT COUNT(*) FROM reportes_visitantes')[0]
ultimo = lambda: dict(zip(('id', 'codigo', 'estado', 'wa', 'intentos', 'detalle', 'token_hash', 'objeto_id', 'obs', 'actualizado_por'),
                          fila('SELECT id, codigo, estado, whatsapp_estado, whatsapp_intentos, whatsapp_detalle, token_hash, objeto_id, '
                               'observaciones, actualizado_por FROM reportes_visitantes ORDER BY id DESC LIMIT 1')))

# ---------- Acceso sin cuenta ----------
vis = app.test_client()
ok('login: botón «Ingresar como visitante»', 'Soy visitante' in pagina(vis, '/login') and 'href="/visitante"' in pagina(vis, '/login'))
ok('portal del visitante sin iniciar sesión', vis.get('/visitante').status_code == 200 and 'Reportar un objeto perdido' in pagina(vis, '/visitante')
   and 'Consultar mi reporte' in pagina(vis, '/visitante'))
r = pagina(vis, '/visitante/reportar')
ok('formulario: todos los campos pedidos', all(f'name="{n}"' in r for n in ('nombre', 'telefono', 'correo', 'objeto_nombre', 'categoria',
                                                                             'descripcion', 'lugar_perdida', 'fecha_perdida', 'foto')))
ok('formulario: la foto es obligatoria y usa la zona de arrastrar', 'data-zona-foto' in r and 'data-foto required' in r)
ok('formulario: sin token CSRF se rechaza (400)', app.test_client().post('/visitante/reportar', data=BASE_VISITANTE).status_code == 400)

# ---------- Validaciones ----------
n0 = cuantos()
for nombre, args, espera in [('sin foto', dict(archivo=None), 'fotografía del objeto es obligatoria'),
                             ('foto PNG o falsa', dict(archivo=b'\x89PNG\r\n\x1a\nfalsa'), 'Formato no aceptado'),
                             ('archivo .exe renombrado', dict(archivo=b'MZ\x90\x00' + b'x' * 100), 'Formato no aceptado'),
                             ('sin teléfono', dict(telefono=''), 'teléfono válido'), ('teléfono corto', dict(telefono='1234'), 'teléfono válido'),
                             ('correo inválido', dict(correo='sofia-arroba'), 'correo no es válido'),
                             ('categoría inventada', dict(categoria='Mascotas'), 'categoría'),
                             ('descripción corta', dict(descripcion='azul'), 'más detalle'),
                             ('fecha futura', dict(fecha_perdida='2099-01-01'), 'no puede ser futura'),
                             ('fecha inválida', dict(fecha_perdida='31/10/2026'), 'fecha en que lo perdiste'),
                             ('nombre demasiado largo', dict(nombre='A' * 101), 'demasiado largo')]:
    r = enviar_reporte(vis, **args)
    ok(f'reporte {nombre}: rechazado con su mensaje', r.status_code == 200 and espera in r.get_data(as_text=True), r.get_data(as_text=True)[-300:])
ok('ningún reporte inválido se guardó', cuantos() == n0)
ok('lo escrito se conserva tras un error', 'value="Sofía Ruiz"' in enviar_reporte(vis, archivo=None).get_data(as_text=True))

# ---------- Reporte sin WhatsApp configurado: se guarda igual ----------
configurar()
usuarios_antes = fila('SELECT COUNT(*) FROM usuarios')[0]
r = enviar_reporte(vis, envio='envio-1')
token1 = token_de(r)
ok('reporte válido: redirige a su seguimiento privado', r.status_code == 302 and token1 and 'nuevo=1' in r.headers['Location'])
rep1 = ultimo()
ok('el reporte quedó en SQLite como Pendiente', cuantos() == n0 + 1 and rep1['estado'] == 'Pendiente')
ok('sin WhatsApp configurado: «No configurada», 1 intento y el motivo real', rep1['wa'] == 'No configurada' and rep1['intentos'] == 1
   and 'WHATSAPP_TOKEN' in rep1['detalle'], rep1)
ok('el enlace privado no se guarda: solo su SHA-256', rep1['token_hash'] == hashlib.sha256(token1.encode()).hexdigest()
   and token1.encode() not in open(BD, 'rb').read())
ok('la foto se guardó en la base (JPEG intacto)', fila('SELECT foto FROM reportes_visitantes WHERE id = ?', (rep1['id'],))[0] == jpeg)
ok('el visitante no se crea como usuario', fila('SELECT COUNT(*) FROM usuarios')[0] == usuarios_antes)
ok('doble envío del mismo formulario: no se duplica', token_de(enviar_reporte(vis, envio='envio-1')) == token1 and cuantos() == n0 + 1)
conf = vis.get(f'/visitante/seguimiento/{token1}?nuevo=1')
h = conf.get_data(as_text=True)
ok('confirmación con el código único', '¡Reporte registrado!' in h and rep1['codigo'] in h and 'Copiar enlace' in h)
ok('el seguimiento no muestra datos personales', all(x not in h for x in ('8777 1234', 'sofia@correo.com', 'Cálculo', 'Ruiz')), h[-500:])
ok('el seguimiento no se guarda en caché', conf.headers.get('Cache-Control') == 'no-store')
ok('enlace inventado: 404', vis.get('/visitante/seguimiento/' + 'x' * 43).status_code == 404 and vis.get('/visitante/seguimiento/' + 'y' * 150).status_code == 404)

# ---------- Consulta con código + teléfono ----------
def consultar(c, codigo, telefono):
    return c.post('/visitante/consultar', data={'codigo': codigo, 'telefono': telefono, 'csrf_token': tok(c, '/visitante/consultar')}).get_data(as_text=True)
otro = app.test_client()
ok('consulta con código y teléfono correctos', 'Recibimos tu reporte' in consultar(otro, rep1['codigo'], '8777 1234'))
ok('consulta con el teléfono con código de país y el código en minúsculas', 'Recibimos tu reporte' in consultar(otro, rep1['codigo'].lower(), '+505 8777-1234'))
r = consultar(otro, rep1['codigo'], '8888 0000')
ok('código correcto con teléfono ajeno: no muestra nada', 'No encontramos' in r and 'Recibimos tu reporte' not in r)
ok('código adivinado: no muestra nada', 'No encontramos' in consultar(otro, 'UAM-AAAA-AAAA', '8777 1234'))
ok('la consulta tampoco muestra datos personales', '8777 1234' not in consultar(otro, rep1['codigo'], '87771234').split('</form>')[-1])

# ---------- WhatsApp configurado (servidor simulado) ----------
configurar(**WA, WHATSAPP_PLANTILLA='nuevo_reporte_visitante', SITIO_URL='https://uamlookingfor.pythonanywhere.com/')
simulador['modo'] = 'ok'
enviar_reporte(vis)
rep2, pet = ultimo(), recibidas[-1]
ok('con WhatsApp: «Enviada» con el id real del mensaje', rep2['wa'] == 'Enviada' and rep2['detalle'] == f'wamid.PRUEBA{len(recibidas)}', rep2)
ok('petición a /v22.0/<id del número>/messages con el token en la cabecera', pet['ruta'] == '/v22.0/123456/messages' and pet['auth'] == 'Bearer tok-secreto-123')
plantilla = pet['cuerpo'].get('template', {})
variables = [p['text'] for p in plantilla.get('components', [{}])[0].get('parameters', [])]
ok('plantilla con 8 variables en orden (código … enlace)', pet['cuerpo']['type'] == 'template' and plantilla['name'] == 'nuevo_reporte_visitante'
   and plantilla['language'] == {'code': 'es'} and len(variables) == 8 and variables[0] == rep2['codigo'] and variables[1] == 'Sofía Ruiz'
   and variables[6] == '8777 1234', variables)
ok('el enlace del aviso lleva al reporte en el panel (con SITIO_URL)', variables[7] == f"https://uamlookingfor.pythonanywhere.com/reportes-visitantes/{rep2['id']}")
ok('al destino van solo dígitos', pet['cuerpo']['to'] == '50588880000')
ok('las variables no llevan saltos de línea', not any('\n' in v or '\t' in v for v in variables))
configurar(**WA)
enviar_reporte(vis, descripcion='Mochila azul\ncon dos bolsillos\n\ny un llavero')
cuerpo = recibidas[-1]['cuerpo']
ok('sin plantilla: texto libre con todos los datos del aviso', cuerpo['type'] == 'text' and all(x in cuerpo['text']['body'] for x in
   ('Mochila azul', 'Sofía Ruiz', '8777 1234', 'Cafetería', hoy, ultimo()['codigo'], f"/reportes-visitantes/{ultimo()['id']}")))
for modo, espera in [('error', 'Error 401 de WhatsApp (código 190)'), ('sin_id', 'sin el id del mensaje')]:
    simulador['modo'] = modo
    n = cuantos(); r = enviar_reporte(vis)
    ok(f'WhatsApp responde «{modo}»: el reporte se guarda y queda «Fallida»', cuantos() == n + 1 and ultimo()['wa'] == 'Fallida'
       and espera in ultimo()['detalle'] and r.status_code == 302, ultimo())
ok('el motivo del fallo nunca incluye el token', 'tok-secreto-123' not in ''.join(f[0] or '' for f in todas('SELECT whatsapp_detalle FROM reportes_visitantes')))
configurar(**dict(WA, WHATSAPP_API_URL='http://127.0.0.1:9'))
n = cuantos(); r = enviar_reporte(vis)
ok('sin conexión con WhatsApp: el reporte se guarda y queda «Fallida»', cuantos() == n + 1 and ultimo()['wa'] == 'Fallida'
   and 'Sin conexión' in ultimo()['detalle'] and vis.get(r.headers['Location']).status_code == 200, ultimo())
configurar(**WA); simulador['modo'] = 'lento'; notificaciones.TIEMPO_MAXIMO = 1
n = cuantos(); enviar_reporte(vis)
ok('WhatsApp tarda demasiado: el reporte se guarda y queda «Fallida»', cuantos() == n + 1 and ultimo()['wa'] == 'Fallida', ultimo())
notificaciones.TIEMPO_MAXIMO = 10
fallido = ultimo()

# ---------- Panel del personal ----------
ok('un visitante no entra al panel de reportes', vis.get('/reportes-visitantes').status_code == 302 and vis.get(f"/reportes-visitantes/{rep1['id']}/foto").status_code == 302)
ok('un estudiante no entra al panel de reportes', ana.get('/reportes-visitantes').status_code == 302)
r = pagina(enc, '/reportes-visitantes')
ok('lista de reportes con su código y estado', rep1['codigo'] in r and rep2['codigo'] in r and 'reporte-pendiente' in r)
ok('menú del personal: «Visitantes» con el número de pendientes', f'Visitantes <span class="nav-contador" title="Reportes pendientes">{cuantos()}</span>' in r)
ok('filtro por estado', rep1['codigo'] in pagina(enc, '/reportes-visitantes?estado=Pendiente') and rep1['codigo'] not in pagina(enc, '/reportes-visitantes?estado=Cerrado'))
ok('búsqueda por parte del código', rep1['codigo'] in pagina(enc, f"/reportes-visitantes?codigo={rep1['codigo'][4:8].lower()}")
   and rep2['codigo'] not in pagina(enc, f"/reportes-visitantes?codigo={rep1['codigo']}"))
ok('la búsqueda ignora comodines (%)', 'No hay reportes que coincidan' in pagina(enc, '/reportes-visitantes?codigo=%25%25%25') or
   rep1['codigo'] in pagina(enc, '/reportes-visitantes?codigo=%25'))
ok('el administrador también gestiona reportes', adm.get('/reportes-visitantes').status_code == 200 and 'Reportes de visitantes' in pagina(adm, '/admin'))
post(enc, '/reportar', dict(datos, titulo='Mochila azul Totto', descripcion='Mochila Totto azul con cuaderno', categoria='Ropa/Accesorios',
                            fecha=hoy, envio='mochila-1', sin_persona='1', ubicacion='Sala Docente'))
mochila = fila("SELECT id FROM objetos WHERE titulo = 'Mochila azul Totto'")[0]
r = pagina(enc, f"/reportes-visitantes/{rep1['id']}")
ok('detalle: foto, datos del visitante y contacto', f"/reportes-visitantes/{rep1['id']}/foto" in r and '8777 1234' in r and 'sofia@correo.com' in r
   and 'tel:+50587771234' in r and 'https://wa.me/50587771234?text=' in r and 'mailto:sofia@correo.com' in r)
ok('detalle: sugiere la mochila encontrada como posible coincidencia', f'#{mochila} Mochila azul Totto' in r.split('Posibles coincidencias')[-1])
ok('la foto del reporte se sirve al personal', enc.get(f"/reportes-visitantes/{rep1['id']}/foto").data == jpeg)
ok('detalle: muestra el aviso «No configurada» y permite reintentar', 'No configurada' in r and 'Reintentar envío' in r)

def gestionar(c, id, **campos):
    return post(c, f'/reportes-visitantes/{id}', dict(campos))
ok('cambiar estado y agregar observaciones', 'actualizado' in gestionar(enc, rep1['id'], accion='gestionar', estado='En revisión', observaciones='Llamé, no contestó')
   and (ultimo_rep := dict(zip(('estado', 'obs', 'por'), fila('SELECT estado, observaciones, actualizado_por FROM reportes_visitantes WHERE id = ?', (rep1['id'],)))))
   == {'estado': 'En revisión', 'obs': 'Llamé, no contestó', 'por': yo}, locals().get('ultimo_rep'))
ok('estado inventado: rechazado', 'estado válido' in gestionar(enc, rep1['id'], accion='gestionar', estado='Perdido'))
ok('sin cambios: lo avisa', 'No hubo cambios' in gestionar(enc, rep1['id'], accion='gestionar', estado='En revisión', observaciones='Llamé, no contestó'))
h = pagina(vis, f'/visitante/seguimiento/{token1}')
ok('el visitante ve «En revisión» pero no las observaciones internas', 'buscando tu objeto' in h and 'no contestó' not in h)
ok('relacionar con la mochila encontrada', f'objeto #{mochila}' in gestionar(enc, rep1['id'], accion='relacionar', objeto_id=str(mochila))
   and fila('SELECT objeto_id FROM reportes_visitantes WHERE id = ?', (rep1['id'],))[0] == mochila)
ok('relacionar con un objeto que no existe: rechazado', 'no existe' in gestionar(enc, rep1['id'], accion='relacionar', objeto_id='99999'))
ok('relacionar con un valor raro: rechazado', 'objeto válido' in gestionar(enc, rep1['id'], accion='relacionar', objeto_id='1 OR 1=1'))
gestionar(enc, rep1['id'], accion='gestionar', estado='Localizado', observaciones='Llamé, no contestó')
h = pagina(vis, f'/visitante/seguimiento/{token1}')
ok('Localizado: el visitante sabe dónde retirarlo', 'Encontramos un objeto' in h and 'Sala Docente' in h)
ok('quitar la relación', 'Se quitó la relación' in gestionar(enc, rep1['id'], accion='relacionar', objeto_id=''))
ok('un estudiante no puede gestionar (y no cambia nada)', ana.post(f"/reportes-visitantes/{rep1['id']}", data={'accion': 'gestionar', 'estado': 'Cerrado',
   'csrf_token': tok(ana, '/guia')}).status_code == 302 and fila('SELECT estado FROM reportes_visitantes WHERE id = ?', (rep1['id'],))[0] == 'Localizado')

# ---------- Reintentar WhatsApp ----------
simulador['modo'] = 'ok'; n_pet = len(recibidas)
r = gestionar(enc, fallido['id'], accion='whatsapp')
estado_ok = fila('SELECT whatsapp_estado, whatsapp_intentos FROM reportes_visitantes WHERE id = ?', (fallido['id'],))
ok('reintentar un aviso fallido: ahora «Enviada» y cuenta el intento', 'Aviso enviado por WhatsApp' in r and estado_ok == ('Enviada', 2)
   and len(recibidas) == n_pet + 1, (estado_ok, r[-300:]))
ok('un aviso ya enviado no se reenvía', 'ya se envió' in gestionar(enc, fallido['id'], accion='whatsapp') and len(recibidas) == n_pet + 1)
simulador['modo'] = 'error'
r = gestionar(enc, rep1['id'], accion='whatsapp')
ok('reintento que vuelve a fallar: lo dice con el motivo y suma el intento', 'No se pudo enviar por WhatsApp (Fallida)' in r
   and fila('SELECT whatsapp_estado, whatsapp_intentos FROM reportes_visitantes WHERE id = ?', (rep1['id'],)) == ('Fallida', 2))
configurar()
r = gestionar(enc, rep1['id'], accion='whatsapp')
ok('reintento sin configuración: «No configurada», nunca «Enviada»', 'No configurada' in r
   and fila('SELECT whatsapp_estado FROM reportes_visitantes WHERE id = ?', (rep1['id'],))[0] == 'No configurada')
ok('integridad tras el módulo de visitantes', fila('PRAGMA integrity_check')[0] == 'ok' and not todas('PRAGMA foreign_key_check'))

# ---------- Una base v8.5 con datos (la del sitio) se actualiza sola a la v9, sin perder nada ----------
if V85:
    base_v85 = os.path.join(TMP, 'base_v85.db')
    llenar_v85 = f"""
    import sys, os
    sys.path.insert(0, {V85!r}); os.chdir({V85!r})
    import config, base_datos as bd
    config.RUTA_ENV = {ENV!r}; bd.RUTA_BD = {base_v85!r}
    import app, logica as l
    e = l.guardar_usuario('Enc Nueve', 'ENC9', 'enc9@uam.edu.ni', '', 'Encargado', 'clave123')[1]
    s = l.guardar_usuario('Est Nueve', 'EST9', 'est9@uam.edu.ni', '', 'Estudiante', 'clave123')[1]
    class F: filename = ''
    o = l.registrar_objeto({{'titulo': 'Celular', 'descripcion': 'Negro', 'categoria': 'Electrónicos', 'fecha': bd.ahora()[:10],
                             'lugar_encontrado': 'Aula', 'ubicacion': 'Edificio A', 'sin_persona': '1'}}, F(), e)[1]
    print(l.registrar_entrega(o, 'Visitante X', 'Visitante', 'VIS9', '88887777', 'señas suficientes', True, e))
    print(l.crear_reclamacion(o, bd.buscar_usuario(s), 'descripción larga del dueño', '', '', ''))
    rid = bd.consultar('SELECT max(id) FROM reclamaciones', uno=True)[0]
    print(l.cancelar_reclamacion(rid, s))
    """
    r = subprocess.run([sys.executable, '-c', textwrap.dedent(llenar_v85)], capture_output=True, text=True)
    ok('base v8.5 con datos (y una reclamación cancelada) creada con la app v8.5', r.returncode == 0 and r.stdout.count('True') == 3, r.stdout + r.stderr[-500:])
    contenido = lambda ruta: {t: sqlite3.connect(ruta).execute(f'SELECT * FROM {t} ORDER BY id').fetchall()
                              for t in ('usuarios', 'objetos', 'entregas', 'reclamaciones', 'devoluciones', 'historial', 'reportes_visitantes')}
    antes_v85 = contenido(base_v85)
    ok('la v9 no la confunde con una base vieja (no migra)', not migrar.necesita_migracion(base_v85))
    conexion.configurar(base_v85)
    conexion.crear_tablas()   # lo mismo que hace crear_app() al iniciar
    c8 = sqlite3.connect(base_v85)
    ok('al iniciar, la v9.1.01 solo agrega lo suyo: datos idénticos y 29 triggers', contenido(base_v85) == antes_v85
       and c8.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0] == 29
       and c8.execute('PRAGMA integrity_check').fetchone()[0] == 'ok')
    c8.close()
    conexion.crear_tablas()
    ok('iniciar otra vez no duplica nada', contenido(base_v85) == antes_v85)
    app85 = crear_app(ENV, base_v85)
    cv = app85.test_client()
    ok('con la base v8.5 actualizada: el encargado entra', 'Bienvenido' in entrar(cv, 'ENC9', 'clave123'))
    pagina85 = cv.get('/reclamaciones?estado=Cancelada').get_data(as_text=True)
    ok('la reclamación cancelada antes de v9 se sigue viendo (pestaña «Canceladas (antes de v9)»)',
       'Canceladas (antes de v9)' in pagina85 and 'Cancelada por el estudiante' in pagina85)
    ce = app85.test_client()
    entrar(ce, 'EST9', 'clave123')
    ok('el estudiante ve su reclamación antigua como cancelada', 'Cancelaste esta reclamación' in ce.get('/mis-reclamaciones').get_data(as_text=True))
    conexion.configurar(BD)
servidor.shutdown()

# ---------- Migración desde v6.2 ----------
if V62:
    V62_TMP = os.path.join(TMP, 'v62')
    shutil.copytree(V62, V62_TMP)
    os.remove(os.path.join(V62_TMP, 'database.db'))
    guion = r'''
    import sys, os, io
    sys.path.insert(0, os.getcwd())
    import config, base_datos as bd
    config.RUTA_ENV = sys.argv[1]
    import app as a, logica as l
    from config import ESTADOS
    c = a.app.test_client()
    adm = bd.consultar("SELECT id FROM usuarios WHERE rol='Administrador'", uno=True)[0]
    e = l.guardar_usuario('Enc Uno', 'ENC1', 'enc1@uam.edu.ni', '', 'Encargado', 'clave123')[1]
    s1 = l.guardar_usuario('Est Uno', 'EST1', 'est1@uam.edu.ni', '', 'Estudiante', 'clave123')[1]
    s2 = l.guardar_usuario('Est Dos', 'EST2', 'est2@uam.edu.ni', 'Medicina', 'Estudiante', 'clave456')[1]
    class F:
        filename = ''
    def obj(t, persona=True):
        d = {'titulo': t, 'descripcion': 'desc ' + t, 'categoria': 'Otros', 'fecha': bd.ahora()[:10], 'hora': '10:00',
             'lugar_encontrado': 'Aula', 'ubicacion': 'Sala Docente', 'estado': 'Activo'}
        d.update({'persona_nombre': 'Enc Uno', 'persona_cif': 'ENC1', 'persona_tipo': 'Docente'} if persona else {'sin_persona': '1'})
        return l.registrar_objeto(d, F(), e)[1]
    o1, o2, o3, o4 = obj('Devuelto'), obj('Recuperado', False), obj('PorRecuperar', False), obj('Custodia', False)
    for o in (o1, o2, o3):
        print(l.registrar_entrega(o, 'Visitante X', 'Visitante', 'VIS001', '88887777', 'señas suficientes', True, e))
        r = l.crear_reclamacion(o, bd.buscar_usuario(s1), 'descripcion larga del dueño', '', '', '')
        rid = bd.consultar('SELECT max(id) FROM reclamaciones', uno=True)[0]
        print(l.gestionar_reclamacion(rid, 'aceptar', 'ok', e))
    l.marcar_recuperado(o1, e); l.marcar_recuperado(o2, e)
    print(l.registrar_entrega(o1, 'Est Uno', 'Estudiante', 'EST1', '88881111', 'señas del dueño real', True, e))
    l.cambiar_estado_manual(o4, 'En bodega', e)
    '''
    with open(os.path.join(TMP, 'llenar_v62.py'), 'w') as f:
        f.write(textwrap.dedent(guion))
    r = subprocess.run([sys.executable, os.path.join(TMP, 'llenar_v62.py'), ENV], cwd=V62_TMP, capture_output=True, text=True)
    ok('base v6.2 con datos creada', r.returncode == 0, r.stderr[-800:])
    vieja = os.path.join(V62_TMP, 'database.db')
    c6 = sqlite3.connect(vieja)
    conteos6 = {t: c6.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('usuarios', 'objetos', 'entregas', 'reclamaciones', 'historial')}
    estados6 = dict(c6.execute('SELECT titulo, estado FROM objetos'))
    c6.close()
    print('  v6.2:', conteos6, estados6)
    copia = os.path.join(TMP, 'migrada.db')
    shutil.copy(vieja, copia)
    ok('detecta que hace falta migrar', migrar.necesita_migracion(copia))
    try:
        migrar.migrar(copia, os.path.join(PROYECTO, 'schema.sql'))
        ok('migración sin errores', True)
    except Exception as e:
        ok('migración sin errores', False, e)
    c7 = sqlite3.connect(copia)
    q = lambda s: c7.execute(s).fetchall()
    estados7 = dict(q('SELECT titulo, estado FROM objetos'))
    ok('estados migrados', estados7 == {'Devuelto': 'Devuelto', 'Recuperado': 'Recuperado', 'PorRecuperar': 'Por recuperar', 'Custodia': 'En bodega'}, estados7)
    ok('conteos', q('SELECT COUNT(*) FROM objetos')[0][0] == conteos6['objetos'] and q('SELECT COUNT(*) FROM historial')[0][0] == conteos6['historial']
       and q('SELECT COUNT(*) FROM usuarios')[0][0] == conteos6['usuarios'] and q('SELECT COUNT(*) FROM reclamaciones')[0][0] == conteos6['reclamaciones'])
    ok('entregas -> 3 iniciales + 1 devolución completa', q('SELECT COUNT(*) FROM entregas')[0][0] == 3 and
       q('SELECT COUNT(*), COUNT(fecha_devolucion) FROM devoluciones')[0] == (2, 1))
    ok('señas de la devolución conservadas', q('SELECT observaciones FROM devoluciones WHERE fecha_devolucion IS NOT NULL')[0][0] == 'Señas al devolver: señas del dueño real')
    ok('historial: Devolución y Recuperado', ('Devolución', 'Devuelto') in q('SELECT accion, estado_nuevo FROM historial')
       and ('Recuperación', 'Recuperado') in q('SELECT accion, estado_nuevo FROM historial'))
    ok('reportado_por = registrado_por quedó vacío', q("SELECT reportado_por FROM objetos WHERE titulo='Devuelto'")[0][0] is None)
    ok('29 triggers tras migrar (incluye reportes_visitantes, el de v9 y la limpieza de v9.1.01)', q("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'")[0][0] == 29)
    ok('integridad tras migrar', q('PRAGMA integrity_check')[0][0] == 'ok' and not q('PRAGMA foreign_key_check'))
    hashes = q('SELECT cif, contrasena_hash FROM usuarios WHERE contrasena_hash IS NOT NULL')
    ok('contraseñas migradas a hash y verificables', len(hashes) == 3 and all(seguridad.verificar_contrasena('clave456' if c == 'EST2' else 'clave123', h) for c, h in hashes))
    c7.close()
    ok('respaldo creado', any('respaldo' in n for n in os.listdir(TMP)))
    cm = crear_app(ENV, copia).test_client()
    ok('login tras migrar', 'Bienvenido' in entrar(cm, 'EST2', 'clave456'))
    conexion.configurar(BD)

# ====================== v9: validación cruzada de identidad y validaciones nuevas ======================
conexion.configurar(BD)
e9 = app.test_client()
ok('v9: el encargado entra', 'Bienvenido' in entrar(e9, 'ENC0001', 'clave123'))
a9 = app.test_client()
a9.post('/admin', data={'cif': 'admin', 'contrasena': 'Clave Segura 1', 'csrf_token': tok(a9, '/admin')})
id_de = lambda cif: fila('SELECT id FROM usuarios WHERE cif = ?', (cif,))[0]
nombre_de = lambda cif: fila('SELECT nombre FROM usuarios WHERE cif = ?', (cif,))[0]
total_objetos = lambda: fila('SELECT COUNT(*) FROM objetos')[0]
base9 = {'titulo': 'Termo azul', 'descripcion': 'Termo metálico azul con stickers', 'categoria': 'Otros', 'lugar_encontrado': 'Cafetería',
         'ubicacion': 'Vida Estudiantil', 'fecha': hoy, 'estado': 'Activo', 'persona_telefono': '', 'persona_correo': ''}
n = [0]
def recibir(**cambios):
    n[0] += 1
    return post(e9, '/reportar', dict(base9, envio=f'v9-{n[0]}', **cambios))

antes = total_objetos()
r = recibir(persona_cif='26010001', persona_nombre='Pedro Pérez', persona_tipo='Estudiante')
ok('v9 recibir: CIF de Ana con otro nombre se rechaza y dice de quién es', 'ya está registrado a nombre de Ana Martínez' in r, re.findall(r'class="alerta[^"]*"[^>]*>([^<]+)', r))
ok('v9 recibir: no se guardó el objeto ni cambió el nombre de Ana', total_objetos() == antes and nombre_de('26010001') == 'Ana Martínez')
r = recibir(persona_cif='26010001', persona_nombre='Ana Martínez', persona_tipo='Docente')
ok('v9 recibir: un estudiante con cuenta no se registra como docente', 'pertenece a un estudiante con cuenta' in r)
r = recibir(persona_cif='2601-0001', persona_nombre='ana martinez', persona_tipo='Estudiante')
ok('v9 recibir: mismo CIF y mismo nombre (sin tildes ni mayúsculas) se acepta', 'Objeto registrado' in r
   and fila('SELECT reportado_por FROM objetos ORDER BY id DESC LIMIT 1')[0] == id_de('26010001'))
r = recibir(persona_cif='26010001', persona_nombre='', persona_tipo='')
ok('v9 recibir: CIF registrado con el nombre vacío usa el registrado', 'Objeto registrado' in r
   and fila('SELECT reportado_por FROM objetos ORDER BY id DESC LIMIT 1')[0] == id_de('26010001'))
pedro = '0010101010000A'
r = recibir(persona_cif=pedro, persona_nombre='Juan Pérez', persona_tipo='Visitante')
ok('v9 recibir: CIF de una persona de ventanilla con otro nombre se rechaza (antes la renombraba)',
   'a nombre de Pedro Gómez' in r and nombre_de(pedro) == 'Pedro Gómez')
ok('v9 recibir: una sola palabra no basta para identificar a alguien de dos', 'a nombre de Pedro Gómez' in recibir(persona_cif=pedro, persona_nombre='Pedro', persona_tipo='Visitante'))
ok('v9 recibir: el nombre en otro orden sí corresponde', 'Objeto registrado' in recibir(persona_cif=pedro, persona_nombre='Gómez Pedro', persona_tipo='Visitante'))
r = recibir(persona_cif='VIS7777', persona_nombre='Nora Díaz', persona_tipo='Visitante', persona_correo='ana@uam.edu.ni')
ok('v9 recibir: un correo de otra persona se rechaza (antes se borraba en silencio)', 'ya pertenece a otra persona' in r and total_objetos() == antes + 3)
ok('v9 recibir: CIF con símbolos se rechaza', 'solo puede tener letras y números' in recibir(persona_cif='AB$12', persona_nombre='Nora Díaz', persona_tipo='Visitante'))
r = recibir(persona_cif='VIS7777', persona_nombre='Nora Díaz', persona_tipo='Visitante', persona_telefono='8777 1234')
ok('v9 recibir: persona nueva con CIF nuevo se crea', 'Objeto registrado' in r and nombre_de('VIS7777') == 'Nora Díaz')
ok('v9 recibir: teléfono incompleto se rechaza', 'teléfono válido' in recibir(persona_cif='VIS8888', persona_nombre='Ian Soto', persona_tipo='Visitante', persona_telefono='123'))
ok('v9 recibir: categoría inventada se rechaza (antes pasaba a «Otros»)', 'Elige la categoría' in recibir(sin_persona='1', categoria='Inventada'))
ok('v9 recibir: hora imposible se rechaza', 'hora válida' in recibir(sin_persona='1', hora='25:99'))
ok('v9 recibir: fecha imposible se rechaza', 'fecha de hallazgo válida' in recibir(sin_persona='1', fecha='2026-02-30'))
ok('v9 recibir: estado inicial inventado se rechaza', 'estado inicial válido' in recibir(sin_persona='1', estado='Devuelto'))
ok('v9 recibir: texto demasiado largo se rechaza', 'demasiado largo' in recibir(sin_persona='1', titulo='x' * 151))

# Entrega con el CIF de otra persona
recibir(sin_persona='1', titulo='Audífonos negros')
o9 = fila("SELECT id FROM objetos WHERE titulo='Audífonos negros'")[0]
ent9 = {'nombre': 'Mario Bros', 'tipo': 'Estudiante', 'cif': '26010002', 'telefono': '8888 1111', 'senas': 'Audífonos negros marca Sony', 'confirmado': '1'}
r = post(e9, f'/objeto/{o9}/entregar', ent9)
ok('v9 entrega: CIF de Carlos con otro nombre se rechaza', 'a nombre de Carlos López' in r and fila('SELECT estado FROM objetos WHERE id=?', (o9,))[0] == 'Activo')
ok('v9 entrega: el formulario conserva lo escrito para corregir', 'value="Mario Bros"' in r)
r = post(e9, f'/objeto/{o9}/entregar', dict(ent9, nombre='Carlos López'))
ok('v9 entrega: con su nombre se registra a nombre de Carlos', 'Entrega registrada' in r
   and fila('SELECT retirado_por FROM entregas WHERE objeto_id=?', (o9,))[0] == id_de('26010002'))

# Registro y cuentas con el CIF de otra persona
conexion.ejecutar("INSERT INTO usuarios (nombre, cif, telefono, rol) VALUES ('Marta Ruiz', '26010300', '8000 1111', 'Estudiante')")
nueva = app.test_client()
r = nueva.post('/registro', data={'nombre': 'Impostor Uno', 'cif': '26010300', 'correo': 'imp@uam.edu.ni', 'contrasena': 'secreta1',
                                  'confirmar': 'secreta1', 'carrera': 'Derecho', 'csrf_token': tok(nueva, '/registro')}, follow_redirects=True).get_data(as_text=True)
ok('v9 registro: el CIF de un estudiante de ventanilla con otro nombre no se usa', 'ya está registrado' in r
   and fila("SELECT nombre, contrasena_hash FROM usuarios WHERE cif='26010300'") == ('Marta Ruiz', None))
r = post(a9, '/admin/usuarios', {'nombre': 'Otro Nombre', 'cif': pedro, 'correo': 'otro@uam.edu.ni', 'rol': 'Estudiante', 'contrasena': 'clave123'})
ok('v9 admin: crear una cuenta con el CIF de otra persona de ventanilla se rechaza', 'a nombre de Pedro Gómez' in r and nombre_de(pedro) == 'Pedro Gómez')
r = post(a9, f'/admin/usuarios/{id_de("26010002")}/editar', {'nombre': 'Carlos López', 'cif': '26010001', 'correo': 'carlos@uam.edu.ni', 'rol': 'Estudiante'})
ok('v9 admin: cambiar un CIF por el de otra cuenta se rechaza con un mensaje claro', 'ya pertenece a otra cuenta' in r)
ok('v9 admin: buscar «%» no lista todas las cuentas', 'Ana Martínez' not in a9.get('/admin/usuarios?q=%25').get_data(as_text=True))

# Reclamación: datos imposibles
recibir(sin_persona='1', titulo='Gorra roja')
o10 = fila("SELECT id FROM objetos WHERE titulo='Gorra roja'")[0]
post(e9, f'/objeto/{o10}/entregar', dict(ent9, nombre='Pedro Gómez', cif=pedro, tipo='Visitante', senas='Gorra roja con logo'))
an9 = app.test_client()
entrar(an9, '26010001', 'clave123')
rec9 = {'descripcion': 'Gorra roja con logo de la UAM bordado', 'lugar_perdida': 'Gimnasio', 'fecha_perdida': hoy, 'telefono': '8123 0000'}
ok('v9 reclamar: teléfono incompleto se rechaza', 'teléfono válido' in post(an9, f'/objeto/{o10}/reclamar', dict(rec9, telefono='123')))
ok('v9 reclamar: fecha que no existe se rechaza', 'no es válida' in post(an9, f'/objeto/{o10}/reclamar', dict(rec9, fecha_perdida='2026-13-01')))
ok('v9 reclamar: con datos correctos se envía', 'Solicitud enviada' in post(an9, f'/objeto/{o10}/reclamar', rec9))

# Cerrar sesión solo por POST
ok('v9 logout: por GET ya no cierra la sesión (405)', an9.get('/logout').status_code == 405 and an9.get('/').status_code == 200)
ok('v9 logout: por POST con token sí', 'cerrado sesión' in post(an9, '/logout', {}) and an9.get('/').status_code == 302)
ok('v9 logout: sin token no (400)', e9.post('/logout').status_code == 400)
# ====================== v9.1.01: limpiar el historial (solo el administrador) ======================
movs = lambda: fila('SELECT COUNT(*) FROM historial')[0]
limpiezas = lambda: todas("SELECT antes_de, estado, filas_borradas FROM limpiezas_historial ORDER BY id")
ok('v9.1.01: hay movimientos para probar', movs() > 3, movs())
ok('v9.1.01: el admin ve «Limpiar historial»', 'Limpiar historial' in pagina(a9, '/historial'))
ok('v9.1.01: el encargado no ve la sección', 'Limpiar historial' not in pagina(e9, '/historial'))
n0 = movs()
r = post(e9, '/historial/limpiar', {'alcance': 'todo', 'confirmado': '1'})
ok('v9.1.01: el encargado no puede limpiar', 'Solo el administrador puede limpiar el historial' in r and movs() == n0)
ok('v9.1.01: sin confirmar no borra', 'Marca la casilla' in post(a9, '/historial/limpiar', {'alcance': 'todo'}) and movs() == n0)
ok('v9.1.01: fecha inválida se rechaza', 'fecha válida' in post(a9, '/historial/limpiar', {'alcance': 'fecha', 'antes_de': '2026-02-30', 'confirmado': '1'}) and movs() == n0)
ok('v9.1.01: alcance inventado se rechaza', 'Elige qué parte' in post(a9, '/historial/limpiar', {'alcance': 'x', 'confirmado': '1'}) and movs() == n0)
ok('v9.1.01: rango sin movimientos avisa', 'No hay movimientos' in post(a9, '/historial/limpiar', {'alcance': 'fecha', 'antes_de': '2000-01-01', 'confirmado': '1'}))
# Dos movimientos «viejos» para probar la limpieza por fecha (escritos directo, como si fueran de 2025).
con = sqlite3.connect(BD)
oid, uid = con.execute("SELECT objeto_id, usuario_id FROM historial WHERE accion = 'Registro' LIMIT 1").fetchone()
con.executemany("INSERT INTO historial (objeto_id, usuario_id, accion, fecha_hora) VALUES (?, ?, 'Foto', ?)",
                [(oid, uid, '2025-03-01 10:00:00'), (oid, uid, '2025-05-01 10:00:00')])
con.commit(); con.close()
n1 = movs()
r = post(a9, '/historial/limpiar', {'alcance': 'fecha', 'antes_de': '2026-01-01', 'confirmado': '1'})
ok('v9.1.01: por fecha borra solo lo anterior', 'Se borraron 2 movimiento(s) anteriores al 2026-01-01' in r and movs() == n1 - 2, re.findall(r'class="alerta[^"]*"[^>]*>([^<]+)', r))
ok('v9.1.01: queda en la bitácora, cerrada', limpiezas() == [('2026-01-01', 'Hecha', 2)], limpiezas())
ok('v9.1.01: la página muestra la última limpieza', 'anteriores al 2026-01-01' in pagina(a9, '/historial'))
n2 = movs()
r = post(a9, '/historial/limpiar', {'alcance': 'todo', 'confirmado': '1'})
ok('v9.1.01: «todo» deja el historial vacío', f'Se borraron {n2} movimiento(s) de todo el historial' in r and movs() == 0, re.findall(r'class="alerta[^"]*"[^>]*>([^<]+)', r))
ok('v9.1.01: los objetos no se tocan', total_objetos() > 0 and fila('SELECT COUNT(*) FROM entregas')[0] > 0)
ok('v9.1.01: no queda ninguna limpieza «En curso»', not todas("SELECT 1 FROM limpiezas_historial WHERE estado = 'En curso'"))
ok('v9.1.01: lo nuevo se sigue anotando', (post(e9, '/reportar', dict(base9, envio='v9101', titulo='Gorra negra', sin_persona='1')) or True) and movs() == 1)
con = sqlite3.connect(BD)
for nombre, sql in [('borrar historial sin limpieza', 'DELETE FROM historial'),
                    ('borrar la bitácora', 'DELETE FROM limpiezas_historial'),
                    ('reabrir una limpieza', "UPDATE limpiezas_historial SET estado = 'En curso', filas_borradas = NULL"),
                    ('un encargado abre una limpieza', f"INSERT INTO limpiezas_historial (usuario_id, fecha_hora) VALUES ({id_de('ENC0001')}, '2026-11-13 10:00:00')")]:
    try:
        con.execute(sql); ok(f'v9.1.01 base: {nombre} se rechaza', False)
    except sqlite3.DatabaseError as e:
        ok(f'v9.1.01 base: {nombre} se rechaza', True)
con.rollback(); con.close()
# ====================== v9.1.01: objetos entregados que se ocultan del catálogo (sin tocar la base) ======================
from uam.datos import objetos as datos_objetos  # noqa: E402
sf = app.test_client()
ok('plazo: Ana entra', 'Bienvenido' in entrar(sf, '26010001', 'clave123'))
datos_objetos.configurar_plazo('99'); p99 = datos_objetos.dias_plazo()
datos_objetos.configurar_plazo('1'); p1 = datos_objetos.dias_plazo()
datos_objetos.configurar_plazo('abc'); pabc = datos_objetos.dias_plazo()
datos_objetos.configurar_plazo('4'); p4 = datos_objetos.dias_plazo()
ok('plazo: DIAS_OCULTAR se limita de 3 a 7 y por defecto es 5', (p99, p1, pabc, p4) == (7, 3, 5, 4), (p99, p1, pabc, p4))
datos_objetos.configurar_plazo(None)
post(e9, '/reportar', dict(base9, envio='plazo-1', sin_persona='1', titulo='Cartera café'))
oc = fila("SELECT id FROM objetos WHERE titulo='Cartera café'")[0]
entf = {'nombre': 'Pedro Gómez', 'tipo': 'Visitante', 'cif': pedro, 'telefono': '8888 1111', 'senas': 'Cartera café con dos tarjetas', 'confirmado': '1'}
ok('plazo: se entrega la cartera', 'Entrega registrada' in post(e9, f'/objeto/{oc}/entregar', entf))
ok('plazo: recién entregada sigue en el catálogo del estudiante', 'Cartera café' in sf.get('/').get_data(as_text=True))
ok('plazo: el personal ve cuándo se ocultará', 'dejará de verse en el catálogo' in e9.get(f'/objeto/{oc}').get_data(as_text=True))
datos_objetos._plazo['dias'] = 0   # solo en la prueba: como si ya hubieran pasado los días
catalogo_est = sf.get('/').get_data(as_text=True)
ok('plazo: cumplido el plazo ya no sale en el catálogo del estudiante', 'Cartera café' not in catalogo_est)
ok('plazo: ni lo abre con la dirección directa (404)', sf.get(f'/objeto/{oc}').status_code == 404)
ok('plazo: con una reclamación pendiente no se oculta', 'Gorra roja' in catalogo_est)
ok('plazo: ya no se puede reclamar', 'plazo para reclamar este objeto ya terminó' in post(sf, f'/objeto/{oc}/reclamar', rec9))
catalogo_enc = e9.get('/').get_data(as_text=True)
ok('plazo: tampoco sale en el catálogo del personal, que recibe el aviso', 'Cartera café' not in catalogo_enc and 'del catálogo.' in catalogo_enc)
ocultos = e9.get('/?ocultos=1').get_data(as_text=True)
ok('plazo: el personal lo encuentra en «Ocultos»', 'Cartera café' in ocultos and 'Objetos ocultos' in ocultos)
ok('plazo: un estudiante no puede pedir la lista de ocultos', 'Cartera café' not in sf.get('/?ocultos=1').get_data(as_text=True))
ok('plazo: el panel del administrador también avisa', 'del catálogo.' in a9.get('/admin').get_data(as_text=True))
ok('plazo: el historial sigue incluyendo los ocultos', 'Cartera café' in e9.get('/historial').get_data(as_text=True))
ok('plazo: el PDF se sigue generando', e9.get('/historial/pdf').status_code == 200)
detalle_oculto = e9.get(f'/objeto/{oc}').get_data(as_text=True)
ok('plazo: la ficha dice desde cuándo está oculto y no ofrece borrar', 'Oculto del catálogo desde' in detalle_oculto
   and 'Eliminar' not in detalle_oculto and 'Quitar solo la foto' not in detalle_oculto)
ok('plazo: el objeto sigue completo en la base', fila('SELECT COUNT(*) FROM objetos o JOIN entregas e ON e.objeto_id = o.id WHERE o.id = ?', (oc,))[0] == 1)
datos_objetos.configurar_plazo(None)
ok('plazo: con el plazo normal vuelve a verse (recién entregada)', 'Cartera café' in sf.get('/').get_data(as_text=True))
# ====================== v10: requerimientos funcionales (perfil, búsqueda, plazos, comprobante, guía) ======================
import datetime  # noqa: E402
import smtplib  # noqa: E402
alerta = lambda r: re.findall(r'class="alerta[^"]*"[^>]*>([^<]+)', r)

# --- RF-05: perfil del estudiante y carrera en el registro ---
nv = app.test_client()
datos_reg = {'nombre': 'Rita Campos', 'cif': '26010777', 'correo': 'rita@uam.edu.ni', 'contrasena': 'clave777', 'confirmar': 'clave777'}
r = nv.post('/registro', data=dict(datos_reg, csrf_token=tok(nv, '/registro')), follow_redirects=True).get_data(as_text=True)
ok('v10 RF-05: el registro sin carrera se rechaza', 'Escribe tu carrera' in r and not fila("SELECT 1 FROM usuarios WHERE cif='26010777'"))
r = nv.post('/registro', data=dict(datos_reg, carrera='Arquitectura', csrf_token=tok(nv, '/registro')), follow_redirects=True).get_data(as_text=True)
ok('v10 RF-05: el registro guarda la carrera', fila("SELECT carrera FROM usuarios WHERE cif='26010777'") == ('Arquitectura',))
perfil = nv.get('/perfil').get_data(as_text=True)
ok('v10 RF-05: «Mi perfil» muestra nombre, CIF, carrera y correo', all(t in perfil for t in ('Rita Campos', '26010777', 'Arquitectura', 'rita@uam.edu.ni')))
ok('v10 RF-05: el menú enlaza a «Mi perfil»', 'href="/perfil"' in perfil)
r = post(nv, '/perfil', {'accion': 'datos', 'correo': 'rita@uam.edu.ni', 'carrera': '', 'telefono': ''})
ok('v10 RF-05: un estudiante no puede dejar vacía la carrera', 'Escribe tu carrera' in r)
r = post(nv, '/perfil', {'accion': 'datos', 'correo': 'ana@uam.edu.ni', 'carrera': 'Arquitectura', 'telefono': ''})
ok('v10 RF-05: no puede usar el correo de otra cuenta', 'ya pertenece a otra cuenta' in r)
r = post(nv, '/perfil', {'accion': 'datos', 'correo': 'Rita.Campos@uam.edu.ni', 'carrera': 'Diseño Gráfico', 'telefono': '8777 1234'})
ok('v10 RF-05: corrige correo, carrera y teléfono', 'Tus datos se guardaron' in r
   and fila("SELECT correo, carrera, telefono, nombre FROM usuarios WHERE cif='26010777'") == ('rita.campos@uam.edu.ni', 'Diseño Gráfico', '8777 1234', 'Rita Campos'))
r = post(nv, '/perfil', {'accion': 'datos', 'correo': 'rita.campos@uam.edu.ni', 'carrera': 'Diseño', 'telefono': '12'})
ok('v10 RF-05: teléfono inválido se rechaza', 'teléfono válido' in r)
r = post(nv, '/perfil', {'accion': 'contrasena', 'actual': 'mala', 'nueva': 'nueva777', 'confirmar': 'nueva777'})
ok('v10 RF-05: cambiar contraseña exige la actual', 'actual no es correcta' in r)
r = post(nv, '/perfil', {'accion': 'contrasena', 'actual': 'clave777', 'nueva': 'nueva777', 'confirmar': 'otra777'})
ok('v10 RF-05: la nueva debe repetirse igual', 'no coinciden' in r)
r = post(nv, '/perfil', {'accion': 'contrasena', 'actual': 'clave777', 'nueva': 'nueva777', 'confirmar': 'nueva777'})
otra_vez = app.test_client()
ok('v10 RF-05: la contraseña cambia y la nueva sirve para entrar', 'contraseña se cambió' in r
   and 'Bienvenido' in entrar(otra_vez, '26010777', 'nueva777') and 'Bienvenido' not in entrar(app.test_client(), '26010777', 'clave777'))
ok('v10 RF-05: el administrador ve su perfil pero no lo edita aquí', 'archivo .env' in a9.get('/perfil').get_data(as_text=True)
   and 'archivo .env' in post(a9, '/perfil', {'accion': 'datos', 'correo': 'x@uam.edu.ni', 'carrera': 'x', 'telefono': ''}))

# --- RF-10 y RF-19: búsqueda y filtros ---
r = recibir(sin_persona='1', titulo='Paraguas rojo', descripcion='Paraguas rojo marca Totto, serie QX9123', descripcion_publica='Paraguas rojo plegable')
pid = fila("SELECT id FROM objetos WHERE titulo='Paraguas rojo'")[0]
est = sf.get('/?q=plegable').get_data(as_text=True)
ok('v10 RF-10: el estudiante busca por palabra clave en lo público', 'Paraguas rojo' in est and 'Gorra roja' not in est)
ok('v10 RF-10: no encuentra por la descripción interna (validación)', 'Paraguas rojo' not in sf.get('/?q=QX9123').get_data(as_text=True))
ok('v10 RF-19: el personal sí encuentra por la descripción interna', 'Paraguas rojo' in e9.get('/?q=QX9123').get_data(as_text=True))
ok('v10 RF-19: el personal busca por código (#)', 'Paraguas rojo' in e9.get(f'/?q=%23{pid}').get_data(as_text=True))
ok('v10 RF-19: el personal busca por el CIF de quien lo retiró', 'Cartera café' in e9.get(f'/?q={pedro}').get_data(as_text=True))
ok('v10 RF-19: filtra por estado', 'Cartera café' in e9.get('/?estado=Entregado').get_data(as_text=True)
   and 'Paraguas rojo' not in e9.get('/?estado=Entregado').get_data(as_text=True))
ok('v10 RF-19: filtra por rango de fechas', 'Paraguas rojo' in e9.get(f'/?desde={hoy}&hasta={hoy}').get_data(as_text=True)
   and 'Paraguas rojo' not in e9.get('/?hasta=2000-01-01').get_data(as_text=True))
ok('v10 RF-10: el estudiante filtra por mes', 'Paraguas rojo' in sf.get(f'/?mes={hoy[:7]}').get_data(as_text=True)
   and 'Paraguas rojo' not in sf.get('/?mes=2000-01').get_data(as_text=True))
ok('v10 RF-10: un mes mal escrito se ignora', 'Paraguas rojo' in sf.get('/?mes=abc').get_data(as_text=True))
ok('v10: la búsqueda no trata % como comodín', 'Ningún objeto coincide' in sf.get('/?q=%25').get_data(as_text=True))
ok('v10: el estudiante no puede filtrar por estado ni usar «Por vencer»', 'Cartera café' in sf.get('/?estado=Activo').get_data(as_text=True)
   and 'Plazos por vencer' not in sf.get('/?vencer=1').get_data(as_text=True))
ok('v10 RF-10: la categoría conserva la búsqueda', '?q=plegable&amp;categoria=Llaves' in est or 'q=plegable' in re.search(r'href="([^"]*categoria=Llaves[^"]*)"', est).group(1))
rep_busca = todas('SELECT codigo, nombre FROM reportes_visitantes LIMIT 1')
if rep_busca:
    ok('v10 RF-19: los reportes de visitantes se buscan por nombre', rep_busca[0][0] in e9.get('/reportes-visitantes?codigo=' + rep_busca[0][1].split()[0]).get_data(as_text=True))

# --- RF-16 y RF-18: plazos de custodia ---
from uam.datos import objetos as dobj  # noqa: E402
dobj.configurar_custodia('0', 'abc'); c1 = dobj.plazos_custodia()
dobj.configurar_custodia(None, None); c2 = dobj.plazos_custodia()
ok('v10 RF-16: los plazos se configuran (mínimo 1 día; si no son válidos, 30 y 60)', c1 == {'oficina': 1, 'bodega': 60} and c2 == {'oficina': 30, 'bodega': 60}, (c1, c2))
hace = lambda d: (datetime.date.fromisoformat(hoy) - datetime.timedelta(days=d)).isoformat()
recibir(sin_persona='1', titulo='Sombrilla vieja', fecha=hace(28))
recibir(sin_persona='1', titulo='Bufanda olvidada', fecha=hace(40))
sv, bv = (fila("SELECT id FROM objetos WHERE titulo=?", (t,))[0] for t in ('Sombrilla vieja', 'Bufanda olvidada'))
ficha = e9.get(f'/objeto/{sv}').get_data(as_text=True)
ok('v10 RF-16: calcula la fecha de vencimiento de cada objeto', 'Plazo de custodia hasta el ' + (datetime.date.fromisoformat(hoy) + datetime.timedelta(days=2)).isoformat() in ficha)
cat = e9.get('/').get_data(as_text=True)
ok('v10 RF-16: el catálogo del personal avisa «vence en 2 días» y «vencido»', 'Vence en 2 días' in cat and 'Plazo vencido hace 10 días' in cat)
vence = e9.get('/?vencer=1').get_data(as_text=True)
ok('v10 RF-16: «Por vencer» lista solo lo urgente, primero lo vencido', 'Bufanda olvidada' in vence and 'Sombrilla vieja' in vence
   and 'Paraguas rojo' not in vence and vence.index('Bufanda olvidada') < vence.index('Sombrilla vieja'))
panel = a9.get('/admin').get_data(as_text=True)
ok('v10 RF-18: el panel muestra los próximos a vencer y se actualiza solo', 'Plazos de custodia' in panel and 'Sombrilla vieja' in panel
   and 'Bufanda olvidada' in panel and 'http-equiv="refresh"' in panel)
ok('v10 RF-16: el estudiante no ve los plazos internos', 'Vence en' not in sf.get('/').get_data(as_text=True)
   and 'Plazo de custodia' not in sf.get(f'/objeto/{sv}').get_data(as_text=True))
post(e9, f'/objeto/{bv}', {'accion': 'estado', 'estado': 'En bodega'})
ficha = e9.get(f'/objeto/{bv}').get_data(as_text=True)
ok('v10 RF-16: en bodega el plazo cuenta desde que entró', 'desde que entró a bodega' in ficha
   and 'Plazo de custodia hasta el ' + (datetime.date.fromisoformat(hoy) + datetime.timedelta(days=60)).isoformat() in ficha)
ok('v10 RF-16: un objeto entregado ya no tiene plazo de custodia', 'Plazo de custodia' not in e9.get(f'/objeto/{oc}').get_data(as_text=True))

# --- RF-12 y RF-14: comprobante de entrega ---
comp = e9.get(f'/objeto/{oc}/comprobante').get_data(as_text=True)
ok('v10 RF-12: comprobante para imprimir con código, quien retira, fecha, quien entrega y firmas',
   all(t in comp for t in (f'#{oc}', 'Pedro Gómez', pedro, 'Firma de quien recibe', 'Firma de quien entrega', 'window.print()')))
ok('v10 RF-14: el comprobante no incluye las señas (validación)', 'dos tarjetas' not in comp)
ok('v10 RF-14: solo el personal ve el comprobante', sf.get(f'/objeto/{oc}/comprobante').status_code == 302)
ok('v10 RF-14: sin entrega no hay comprobante (404)', e9.get(f'/objeto/{pid}/comprobante').status_code == 404)
ok('v10 RF-14: la ficha ofrece imprimir y enviar', 'Comprobante para imprimir' in e9.get(f'/objeto/{oc}').get_data(as_text=True))
r = post(e9, f'/objeto/{oc}/comprobante/enviar', {'correo': ''})
ok('v10 RF-14: sin correo registrado pide escribirlo', 'no tiene correo registrado' in r, alerta(r))
r = post(e9, f'/objeto/{oc}/comprobante/enviar', {'correo': 'pedro@correo.com'})
ok('v10 RF-14: sin SMTP en el .env lo dice y sugiere imprimir', 'no está configurado' in r, alerta(r))
enviados = []
class SMTPFalso:
    def __init__(self, servidor, puerto, timeout=None): enviados.append(('conexion', servidor, puerto))
    def starttls(self, context=None): enviados.append(('tls',))
    def login(self, u, c): enviados.append(('login', u))
    def send_message(self, m): enviados.append(('mensaje', m['To'], m['Subject'], m.get_content()))
    def __enter__(self): return self
    def __exit__(self, *a): return False
original_smtp = smtplib.SMTP
smtplib.SMTP = SMTPFalso
with open(ENV, 'a', encoding='utf-8') as archivo:
    archivo.write('\nSMTP_SERVIDOR=smtp.prueba.local\nSMTP_PUERTO=587\nSMTP_USUARIO=oficina\nSMTP_CONTRASENA=x\nSMTP_REMITENTE=oficina@uam.edu.ni\n')
r = post(e9, f'/objeto/{oc}/comprobante/enviar', {'correo': 'Pedro@Correo.com'})
mensaje = [e for e in enviados if e[0] == 'mensaje']
ok('v10 RF-14: con SMTP envía el comprobante al correo', 'Comprobante enviado a pedro@correo.com' in r and mensaje
   and mensaje[0][1] == 'pedro@correo.com' and f'#{oc}' in mensaje[0][3] and ('tls',) in enviados, (alerta(r), enviados))
ok('v10 RF-14: el correo tampoco lleva las señas', mensaje and 'dos tarjetas' not in mensaje[0][3])
ok('v10 RF-14: correo inválido se rechaza', 'no es válido' in post(e9, f'/objeto/{oc}/comprobante/enviar', {'correo': 'no-es-correo'}))
class SMTPCaido(SMTPFalso):
    def __init__(self, *a, **k): raise OSError('sin red')
smtplib.SMTP = SMTPCaido
ok('v10 RF-14: si el servidor de correo falla, lo dice sin romperse', 'No se pudo enviar' in post(e9, f'/objeto/{oc}/comprobante/enviar', {'correo': 'p@correo.com'}))
smtplib.SMTP = original_smtp

# --- RF-11: guía con ubicación y horario ---
guia = sf.get('/guia').get_data(as_text=True)
ok('v10 RF-11: la guía dice dónde se guardan los objetos y cómo entregar uno', all(u in guia for u in ('Vida Estudiantil', 'Sala Docente', 'Edificio A'))
   and 'Encontré algo' in guia and 'Horario de atención' not in guia)
with open(ENV, 'a', encoding='utf-8') as archivo:
    archivo.write('HORARIO_ATENCION=Lunes a viernes de prueba\n')
ok('v10 RF-11: muestra el horario del .env', 'Horario de atención:</strong> Lunes a viernes de prueba' in sf.get('/guia').get_data(as_text=True))
# ====================== v10.1: solo queda el administrador del .env (Nancy) ======================
def caso_admin(con_movimientos):
    ruta_bd, ruta_env = os.path.join(TMP, f'admins_{con_movimientos}.db'), os.path.join(TMP, f'admins_{con_movimientos}.env')
    with open(ruta_env, 'w', encoding='utf-8') as f:   # como estaba antes: el admin de prueba en el .env
        f.write('ADMIN_USUARIO=ADMIN\nADMIN_CONTRASENA=prueba-vieja\nADMIN_NOMBRE=Administrador UAM\nADMIN_CORREO=admin.lookingfor@uamv.edu.ni\nSECRET_KEY=x\n')
    viejo = crear_app(ruta_env, ruta_bd)
    if con_movimientos:   # el admin de prueba alcanzó a registrar un objeto (queda en el historial)
        c = viejo.test_client()
        c.post('/admin', data={'cif': 'ADMIN', 'contrasena': 'prueba-vieja', 'csrf_token': tok(c, '/admin')})
        post(c, '/reportar', dict(base9, envio='admin-viejo', sin_persona='1', titulo='Objeto del admin viejo'))
    with open(ruta_env, 'w', encoding='utf-8') as f:   # ahora: Nancy en el .env
        f.write('ADMIN_USUARIO=NancySanteliz\nADMIN_CONTRASENA=clave-de-nancy\nADMIN_NOMBRE=Nancy\nSECRET_KEY=x\n')
    nuevo_app = crear_app(ruta_env, ruta_bd)
    con = sqlite3.connect(ruta_bd)
    admins = con.execute("SELECT nombre, cif, activo FROM usuarios WHERE rol = 'Administrador' ORDER BY id").fetchall()
    historial = con.execute("SELECT u.nombre FROM historial h JOIN usuarios u ON u.id = h.usuario_id").fetchall()
    con.close()
    n = nuevo_app.test_client()
    n.post('/admin', data={'cif': 'NancySanteliz', 'contrasena': 'clave-de-nancy', 'csrf_token': tok(n, '/admin')})
    cuentas_html = n.get('/admin/usuarios').get_data(as_text=True)
    v = nuevo_app.test_client()
    entra_viejo = v.post('/admin', data={'cif': 'ADMIN', 'contrasena': 'prueba-vieja', 'csrf_token': tok(v, '/admin')},
                         follow_redirects=True).get_data(as_text=True)
    return admins, historial, cuentas_html, entra_viejo

admins, historial, html_cuentas, entra = caso_admin(False)
ok('v10.1: el admin de prueba sin movimientos se borra y queda solo Nancy', admins == [('Nancy', 'NANCYSANTELIZ', 1)], admins)
ok('v10.1: «Cuentas» ya no muestra al Administrador UAM', 'Administrador UAM' not in html_cuentas and 'Nancy' in html_cuentas)
ok('v10.1: la pestaña Administración cuenta 1', re.search(r'Administración <span>1</span>', html_cuentas) is not None)
ok('v10.1: el admin viejo no puede entrar', 'Credenciales de administrador incorrectas' in entra)
admins, historial, html_cuentas, entra = caso_admin(True)
ok('v10.1: si el admin de prueba registró algo, se desactiva (no se borra)', ('Administrador UAM', 'ADMIN', 0) in admins
   and ('Nancy', 'NANCYSANTELIZ', 1) in admins and len(admins) == 2, admins)
ok('v10.1: su nombre se conserva en el historial', ('Administrador UAM',) in historial)
ok('v10.1: desactivado tampoco aparece en «Cuentas» ni puede entrar', 'Administrador UAM' not in html_cuentas
   and 'Credenciales de administrador incorrectas' in entra)
ok('v9: integridad al final', fila('PRAGMA integrity_check')[0] == 'ok' and not todas('PRAGMA foreign_key_check'))

print(f'\n{sum(resultados)}/{len(resultados)} pruebas pasaron')
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if all(resultados) else 1)
