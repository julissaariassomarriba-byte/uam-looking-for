"""UAM Looking For v8.5: sistema de objetos perdidos y encontrados del campus (Flask + SQLite)."""
import functools
import hmac
import re

from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, abort, g

import base_datos as bd
import imagenes
import logica
import migrar
import notificaciones
import reporte_pdf
from config import (CATEGORIAS, ESTADOS, ESTADOS_MANUALES, ESTADOS_RECLAMACION, ESTADOS_REPORTE, ROL_ADMIN, ROL_ESTUDIANTE,
                    ROLES_GESTIONABLES, ROLES_PERSONAL, TIPOS_PERSONA, UBICACIONES, leer_env)

app = Flask(__name__)
env_inicial = leer_env()
app.secret_key = env_inicial.get('SECRET_KEY') or bd.token()  # sin SECRET_KEY, las sesiones duran hasta reiniciar
# MAX_CONTENT_LENGTH: Flask corta cualquier envío de más de 2 MB antes de leerlo (las fotos llegan ya reducidas).
# COOKIE_SEGURA=1 en el .env: la cookie de sesión solo viaja por HTTPS (actívalo junto con «Force HTTPS»).
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=2 * 1024 * 1024,
                  SESSION_COOKIE_SECURE=env_inicial.get('COOKIE_SEGURA') == '1')
app.jinja_env.filters['mes'] = logica.mes_legible
migrar.migrar_si_hace_falta(bd.RUTA_BD)
bd.crear_tablas()
logica.sincronizar_admin(env_inicial)


# Sesión, permisos y token CSRF (se revisan en el servidor en cada petición)

@app.before_request
def cargar_usuario():
    g.usuario = bd.buscar_usuario(session['usuario_id']) if 'usuario_id' in session else None
    if 'usuario_id' in session and (not g.usuario or not g.usuario['activo']):
        session.clear()
        flash('Tu cuenta no está activa. Comunícate con el administrador.', 'error')
        return redirect(url_for('login'))
    # El administrador solo vale mientras coincida con el .env y haya entrado por /admin.
    if tiene_rol(ROL_ADMIN) and not (session.get('acceso_admin') and logica.es_admin_del_env(g.usuario, leer_env())):
        session.clear()
        return redirect(url_for('admin_panel'))
    # El token debe existir y coincidir (comparación de tiempo constante, en bytes para aceptar cualquier texto).
    esperado = session.get('csrf_token', '')
    if request.method == 'POST' and not (esperado and hmac.compare_digest(
            request.form.get('csrf_token', '').encode('utf-8'), esperado.encode('utf-8'))):
        abort(400, 'Formulario vencido o inválido. Recarga la página e inténtalo de nuevo.')


# Cabeceras de seguridad en todas las respuestas: no mostrar el sitio dentro de otro (clickjacking), no adivinar
# tipos de archivo y no enviar la dirección completa a otros sitios. setdefault respeta las que ya puso una ruta.
@app.after_request
def cabeceras_seguridad(respuesta):
    for nombre, valor in (('X-Frame-Options', 'DENY'), ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'same-origin')):
        respuesta.headers.setdefault(nombre, valor)
    return respuesta


def tiene_rol(*roles):
    return bool(g.get('usuario')) and g.usuario['rol'] in roles


def token_csrf():
    if 'csrf_token' not in session:
        session['csrf_token'] = bd.token()
    return session['csrf_token']


# Muestra el mensaje de una función de logica.py (verde si salió bien, rojo si no) y devuelve si salió bien.
def avisar(ok, mensaje):
    flash(mensaje, 'exito' if ok else 'error')
    return ok


# Filtro de la URL (?categoria=, ?estado=…): solo vale si es uno de los permitidos; si no, None (sin filtro).
def opcion(nombre, permitidos, defecto=None):
    valor = request.args.get(nombre, defecto)
    return valor if valor in permitidos else None


# Solo se vuelve a páginas de este sitio: «//otro» y «/\otro» llevarían a otra página, y los navegadores
# ignoran tabuladores y saltos de línea dentro de una dirección.
def ruta_interna(destino):
    if destino.startswith('/') and not destino.startswith('//') and not any(c in destino for c in '\\\t\r\n'):
        return destino
    return None


# Decorador: exige sesión y, si se indican, alguno de los roles.
def requiere(*roles, mensaje='', acceso='login'):
    def decorador(vista):
        @functools.wraps(vista)   # conserva el nombre de la función: Flask lo usa como nombre de la ruta
        def envoltura(*args, **kwargs):
            if not g.usuario:
                flash('Debes iniciar sesión para continuar.', 'error')
                return redirect(url_for(acceso))
            if roles and not tiene_rol(*roles):
                flash(mensaje, 'error')
                return redirect(url_for('inicio'))
            return vista(*args, **kwargs)
        return envoltura
    return decorador


login_requerido = requiere()
encargado_requerido = requiere(*ROLES_PERSONAL, mensaje='Acceso restringido: solo el encargado puede entrar a esta sección.')
estudiante_requerido = requiere(ROL_ESTUDIANTE, mensaje='Solo los estudiantes pueden enviar solicitudes de reclamación.')
admin_requerido = requiere(ROL_ADMIN, mensaje='Acceso restringido: solo el administrador puede gestionar cuentas.',
                           acceso='admin_panel')


@app.context_processor
def variables_globales():
    estudiante = tiene_rol(ROL_ESTUDIANTE)
    return dict(categorias=CATEGORIAS, estados=ESTADOS, estados_manuales=ESTADOS_MANUALES, usuario_actual=g.get('usuario'),
                tipos_persona=TIPOS_PERSONA, ubicaciones=UBICACIONES,
                es_admin=tiene_rol(ROL_ADMIN), es_encargado=tiene_rol(*ROLES_PERSONAL), es_estudiante=estudiante,
                csrf_token=token_csrf,
                pendientes=bd.contar_reclamaciones().get('Pendiente', 0) if tiene_rol(*ROLES_PERSONAL) else 0,
                estados_reporte=ESTADOS_REPORTE,
                reportes_nuevos=bd.contar_reportes_visitantes().get('Pendiente', 0) if tiene_rol(*ROLES_PERSONAL) else 0,
                por_retirar=bd.contar_por_retirar(g.usuario['id']) if estudiante else 0)


MENSAJES_ERROR = {403: 'No tienes permiso para realizar esta acción.', 404: 'La página solicitada no existe.',
                  413: 'El archivo es demasiado grande. Vuelve a elegir la foto desde el formulario: se reduce sola antes de enviarse.',
                  500: 'Ocurrió un error inesperado. Inténtalo de nuevo.'}


def error(e):
    codigo = getattr(e, 'code', 500)
    return render_template('error.html', codigo=codigo, mensaje=MENSAJES_ERROR.get(codigo, getattr(e, 'description', ''))), codigo


for codigo in (400, 403, 404, 413, 500):
    app.register_error_handler(codigo, error)


# Rutas de acceso

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.usuario:
        return redirect(url_for('inicio'))
    if request.method == 'POST':
        usuario = logica.validar_login(request.form.get('cif'), request.form.get('contrasena'))
        if not usuario:
            flash('CIF o contraseña incorrectos.', 'error')
        elif not usuario['activo']:
            flash('Tu cuenta está desactivada. Comunícate con el administrador del sistema.', 'error')
        else:
            session.clear()
            session['usuario_id'] = usuario['id']
            flash(f'¡Bienvenido/a {usuario["nombre"]}!', 'exito')
            return redirect(url_for('inicio'))
    return render_template('login.html')


# Registro público de estudiantes (botón debajo de «Acceder»). Solo crea cuentas con rol Estudiante.
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if g.usuario:
        return redirect(url_for('inicio'))
    f = request.form
    if request.method == 'POST':
        ok, resultado = logica.registrar_estudiante(f.get('nombre'), f.get('cif'), f.get('correo'), f.get('contrasena'), f.get('confirmar'))
        if ok:
            session.clear()   # antes del aviso: clear() también borraría el mensaje
            session['usuario_id'] = resultado
        if avisar(ok, '¡Cuenta creada! Ya puedes buscar y reclamar tus objetos.' if ok else resultado):
            return redirect(url_for('inicio'))
    return render_template('login.html', registro=True, datos=f)


@app.route('/logout')
def logout():
    era_admin = session.get('acceso_admin')
    session.clear()
    flash('Has cerrado sesión correctamente.', 'exito')
    return redirect(url_for('admin_panel' if era_admin else 'login'))


# Rutas del catálogo y los objetos

@app.route('/')
@login_requerido
def inicio():
    categoria, ubicacion = opcion('categoria', CATEGORIAS), opcion('ubicacion', UBICACIONES)
    return render_template('index.html', objetos=bd.listar_objetos(categoria, ubicacion, publicos=not tiene_rol(*ROLES_PERSONAL)),
                           categoria_actual=categoria, ubicacion_actual=ubicacion, por_categoria=bd.contar_objetos_por('categoria'),
                           por_estado=bd.contar_objetos_por('estado'), por_ubicacion=bd.contar_objetos_por('ubicacion'))


# Foto de un objeto, leída de la base. El personal ve todas; un estudiante solo las marcadas como públicas.
@app.route('/objeto/<int:id>/foto')
@login_requerido
def foto(id):
    f = bd.buscar_foto(id)
    if not f or not (tiene_rol(*ROLES_PERSONAL) or f['foto_publica']):
        abort(404)
    return Response(f['foto'], mimetype=imagenes.formato(f['foto']),
                    headers={'Cache-Control': 'private, max-age=86400', 'X-Content-Type-Options': 'nosniff'})


@app.route('/guia')
@login_requerido
def guia():
    return render_template('guia.html')


@app.route('/objeto/<int:id>', methods=['GET', 'POST'])
@login_requerido
def detalle(id):
    if request.method == 'POST':
        if not tiene_rol(*ROLES_PERSONAL):
            abort(403)
        f, yo = request.form, g.usuario['id']
        avisar(*{'descripcion_publica': lambda: logica.actualizar_descripcion_publica(id, f.get('descripcion_publica'), yo),
                 'ubicacion': lambda: logica.cambiar_ubicacion(id, f.get('ubicacion'), yo),
                 'foto': lambda: logica.actualizar_foto(id, request.files.get('foto'), f.get('foto_publica') == '1', yo),
                 'recuperado': lambda: logica.registrar_recuperacion(id, f.get('observaciones'), yo),
                 'devolver': lambda: logica.devolver_al_dueno(id, f.get('confirmado') == '1', f.get('observaciones'), yo)
                 }.get(f.get('accion'), lambda: logica.cambiar_estado_manual(id, f.get('estado'), yo))())
        return redirect(url_for('detalle', id=id))
    return mostrar_detalle(id)


# Página de un objeto: el personal ve el registro completo; un estudiante, solo la parte pública.
# Si una entrega no se pudo guardar, se vuelve a mostrar con lo que escribió el encargado (datos_entrega).
def mostrar_detalle(id, datos_entrega=None):
    personal = tiene_rol(*ROLES_PERSONAL)
    objeto = bd.buscar_objeto(id, publico=not personal) or abort(404)
    entrega = bd.buscar_entrega(id)
    if not personal:
        return render_template('detalle.html', objeto=objeto, lo_retire_yo=bool(entrega) and entrega['retirado_por'] == g.usuario['id'],
                               mi_reclamacion=bd.listar_reclamaciones('Pendiente', id, g.usuario['id']))
    return render_template('detalle.html', objeto=objeto, entrega=entrega, aceptada=bd.reclamacion_aceptada(id),
                           reclamaciones=bd.listar_reclamaciones(objeto_id=id), movimientos=bd.listar_historial(id),
                           datos_entrega=datos_entrega or {})


# El encargado registra quién retira el objeto (entrega inicial). Es la única forma de marcarlo como «Entregado».
@app.route('/objeto/<int:id>/entregar', methods=['POST'])
@encargado_requerido
def entregar(id):
    f = request.form
    if avisar(*logica.registrar_entrega(id, f.get('nombre'), f.get('tipo'), f.get('cif'), f.get('telefono'), f.get('senas'),
                                        f.get('confirmado') == '1', g.usuario['id'])):
        return redirect(url_for('detalle', id=id))
    return mostrar_detalle(id, datos_entrega=f)


# Recepción de un objeto. Cada formulario lleva un código «envio»: si llega dos veces (doble clic o recarga),
# no se crea un objeto repetido, se abre el que ya se guardó.
@app.route('/reportar', methods=['GET', 'POST'])
@encargado_requerido
def reportar():
    envios = session.get('envios', {})
    if request.method == 'POST':
        envio = request.form.get('envio', '')
        if envio in envios:
            flash('Este objeto ya estaba registrado; no se guardó dos veces.', 'exito')
            return redirect(url_for('detalle', id=envios[envio]))
        ok, resultado = logica.registrar_objeto(request.form, request.files.get('foto'), g.usuario['id'])
        if avisar(ok, 'Objeto registrado exitosamente.' if ok else resultado):
            session['envios'] = dict(list(envios.items())[-9:] + [(envio, resultado)])
            return redirect(url_for('detalle', id=resultado))
    return render_template('reportar.html', datos=request.form, hoy=bd.ahora()[:10], envio=request.form.get('envio') or bd.token())


@app.route('/historial')
@encargado_requerido
def historial():
    return render_template('historial.html', objetos=bd.listar_objetos(), movimientos=bd.listar_historial(),
                           conteo=bd.contar_objetos_por('estado'))


# Descarga el historial como PDF (reporte_pdf.py lo arma sin librerías).
@app.route('/historial/pdf')
@encargado_requerido
def historial_pdf():
    fecha = bd.ahora()
    pdf = reporte_pdf.generar_historial(bd.listar_objetos(), bd.listar_historial(), bd.contar_objetos_por('estado'),
                                        g.usuario['nombre'], fecha)
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename=historial_objetos_{fecha[:10]}.pdf'})


# Rutas de reclamaciones

@app.route('/objeto/<int:id>/reclamar', methods=['POST'])
@estudiante_requerido
def reclamar(id):
    f = request.form
    if avisar(*logica.crear_reclamacion(id, g.usuario, f.get('descripcion'), f.get('lugar_perdida'),
                                        f.get('fecha_perdida'), f.get('telefono'))):
        return redirect(url_for('mis_reclamaciones'))
    return redirect(url_for('detalle', id=id))


@app.route('/mis-reclamaciones')
@estudiante_requerido
def mis_reclamaciones():
    return render_template('mis_reclamaciones.html', reclamaciones=bd.listar_reclamaciones(usuario_id=g.usuario['id']))


@app.route('/mis-reclamaciones/<int:id>/cancelar', methods=['POST'])
@estudiante_requerido
def cancelar_reclamacion(id):
    avisar(*logica.cancelar_reclamacion(id, g.usuario['id']))
    return redirect(url_for('mis_reclamaciones'))


@app.route('/reclamaciones')
@encargado_requerido
def reclamaciones():
    estado = opcion('estado', ESTADOS_RECLAMACION, 'Pendiente')
    return render_template('reclamaciones.html', reclamaciones=bd.listar_reclamaciones(estado), estado_actual=estado,
                           conteo=bd.contar_reclamaciones())


@app.route('/reclamaciones/<int:id>', methods=['POST'])
@encargado_requerido
def gestionar_reclamacion(id):
    avisar(*logica.gestionar_reclamacion(id, request.form.get('accion'), request.form.get('nota'), g.usuario['id']))
    return redirect(ruta_interna(request.form.get('volver', '')) or url_for('reclamaciones'))


# Visitantes (v8.5): reportan un objeto perdido y siguen su estado SIN cuenta ni sesión iniciada.

# Enlace al reporte en el panel (para el aviso de WhatsApp). SITIO_URL en el .env fija el dominio público
# (por ejemplo https://uamlookingfor.pythonanywhere.com); sin él se usa la dirección con la que llegó la petición.
def enlace_reporte(id):
    base = (leer_env().get('SITIO_URL') or '').strip().rstrip('/')
    return base + url_for('reporte_visitante', id=id) if base else url_for('reporte_visitante', id=id, _external=True)


@app.route('/visitante')
def visitante():
    return render_template('visitante.html')


# Igual que en «Recibir objeto», el código «envio» evita que un doble clic o una recarga guarde el reporte dos veces.
@app.route('/visitante/reportar', methods=['GET', 'POST'])
def visitante_reportar():
    envios = session.get('envios_visitante', {})
    if request.method == 'POST':
        envio = request.form.get('envio', '')
        if envio in envios:
            return redirect(url_for('visitante_seguimiento', token=envios[envio]))
        ok, resultado = logica.registrar_reporte_visitante(request.form, request.files.get('foto'))
        if ok:   # el reporte ya está guardado: el aviso por WhatsApp no puede hacer que se pierda
            logica.notificar_reporte(resultado['id'], enlace_reporte(resultado['id']))
            session['envios_visitante'] = dict(list(envios.items())[-4:] + [(envio, resultado['token'])])
            return redirect(url_for('visitante_seguimiento', token=resultado['token'], nuevo=1))
        flash(resultado, 'error')
    return render_template('visitante_reportar.html', datos=request.form, hoy=bd.ahora()[:10],
                           envio=request.form.get('envio') or bd.token())


# Enlace privado: solo quien lo tiene ve el estado (el token no se guarda en la base, solo su hash).
@app.route('/visitante/seguimiento/<token>')
def visitante_seguimiento(token):
    reporte = logica.seguimiento(token) or abort(404)
    respuesta = app.make_response(render_template(
        'visitante_seguimiento.html', r=reporte, nuevo=request.args.get('nuevo') == '1',
        enlace=url_for('visitante_seguimiento', token=token, _external=True)))
    respuesta.headers['Cache-Control'] = 'no-store'   # la página lleva el enlace privado: que el navegador no la guarde
    return respuesta


@app.route('/visitante/consultar', methods=['GET', 'POST'])
def visitante_consultar():
    reporte = None
    if request.method == 'POST':
        reporte = logica.consultar_reporte(request.form.get('codigo'), request.form.get('telefono'))
        if not reporte:
            flash('No encontramos un reporte con ese código y ese teléfono. Revisa los datos que diste al reportar.', 'error')
    respuesta = app.make_response(render_template('visitante_consultar.html', r=reporte, datos=request.form))
    respuesta.headers['Cache-Control'] = 'no-store'
    return respuesta


# Panel del personal: reportes de visitantes

@app.route('/reportes-visitantes')
@encargado_requerido
def reportes_visitantes():
    estado = opcion('estado', ESTADOS_REPORTE)
    codigo = re.sub(r'[^A-Z0-9-]', '', (request.args.get('codigo') or '').upper())[:13]   # sin comodines de LIKE
    return render_template('reportes_visitantes.html', reportes=bd.listar_reportes_visitantes(estado, codigo),
                           estado_actual=estado, codigo=codigo, conteo=bd.contar_reportes_visitantes())


@app.route('/reportes-visitantes/<int:id>', methods=['GET', 'POST'])
@encargado_requerido
def reporte_visitante(id):
    if request.method == 'POST':
        f, yo = request.form, g.usuario['id']
        avisar(*{'whatsapp': lambda: logica.reintentar_whatsapp(id, enlace_reporte(id)),
                 'relacionar': lambda: logica.relacionar_objeto(id, f.get('objeto_id'), yo)
                 }.get(f.get('accion'), lambda: logica.gestionar_reporte_visitante(id, f.get('estado'), f.get('observaciones'), yo))())
        return redirect(url_for('reporte_visitante', id=id))
    reporte = bd.buscar_reporte_visitante(id) or abort(404)
    return render_template('reporte_visitante.html', r=reporte, coincidencias=logica.posibles_coincidencias(reporte),
                           objetos=bd.objetos_para_relacionar(reporte['categoria']), contacto=logica.enlaces_contacto(reporte),
                           whatsapp_falta=notificaciones.faltantes(leer_env()))


@app.route('/reportes-visitantes/<int:id>/foto')
@encargado_requerido
def foto_reporte_visitante(id):
    datos = bd.foto_reporte_visitante(id) or abort(404)
    return Response(datos, mimetype=imagenes.formato(datos), headers={'Cache-Control': 'private, max-age=3600'})


# Panel de administración (/admin, credenciales en el .env)

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if g.usuario and not tiene_rol(ROL_ADMIN):
        flash('Acceso restringido: el panel de administración es solo para el administrador.', 'error')
        return redirect(url_for('inicio'))
    env = leer_env()
    if not g.usuario:
        if request.method == 'POST':
            if not logica.admin_configurado(env):
                flash('Falta configurar ADMIN_USUARIO y ADMIN_CONTRASENA en el archivo .env.', 'error')
            elif logica.validar_admin(request.form.get('cif', ''), request.form.get('contrasena', ''), env):
                admin_id = logica.sincronizar_admin(env)
                session.clear()
                session.update(usuario_id=admin_id, acceso_admin=True)
                return redirect(url_for('admin_panel'))
            else:
                flash('Credenciales de administrador incorrectas.', 'error')
        return render_template('admin_login.html', env_listo=logica.admin_configurado(env))
    por_estado = bd.contar_objetos_por('estado')
    return render_template('admin_panel.html', por_rol=bd.contar_usuarios_por_rol(), por_estado=por_estado,
                           total_objetos=sum(por_estado.values()), reclamaciones_pendientes=bd.listar_reclamaciones('Pendiente'),
                           por_reporte=bd.contar_reportes_visitantes(),
                           movimientos=bd.listar_historial(limite=8), fotos=bd.uso_fotos())


@app.route('/admin/usuarios', methods=['GET', 'POST'])
@app.route('/admin/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@admin_requerido
def admin_usuarios(id=None):
    usuario = (bd.buscar_usuario(id) or abort(404)) if id else None
    if usuario and usuario['rol'] not in ROLES_GESTIONABLES:
        flash('La cuenta del administrador se configura en el archivo .env.', 'error')
        return redirect(url_for('admin_usuarios'))
    f = request.form
    if request.method == 'POST' and avisar(*logica.guardar_usuario(
            f.get('nombre'), f.get('cif'), f.get('correo'), f.get('carrera'), f.get('rol'), f.get('contrasena'), id)):
        return redirect(url_for('admin_usuarios'))
    if usuario:
        return render_template('admin_editar_usuario.html', usuario=usuario, datos=f or usuario, roles=ROLES_GESTIONABLES)
    rol = opcion('rol', (ROL_ADMIN, *ROLES_GESTIONABLES))
    busqueda = (request.args.get('q') or '').strip()
    return render_template('admin_usuarios.html', usuarios=bd.listar_usuarios(rol, busqueda), rol_actual=rol,
                           busqueda=busqueda, roles=ROLES_GESTIONABLES, datos=f)


@app.route('/admin/usuarios/<int:id>/estado', methods=['POST'])
@admin_requerido
def admin_estado_usuario(id):
    avisar(*logica.cambiar_activo(id, request.form.get('activo') == '1'))
    return redirect(url_for('admin_usuarios'))


if __name__ == '__main__':
    app.run(debug=True)
