# Arma la aplicación Flask: configuración, base de datos, seguridad y rutas.
import os

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from . import config
from .datos import conexion, migrar, objetos, reclamaciones, usuarios, visitantes
from .rutas import acceso, admin, comun
from .rutas import objetos as rutas_objetos
from .rutas import reclamaciones as rutas_reclamaciones
from .rutas import visitantes as rutas_visitantes
from .seguridad import iguales, nuevo_token
from .servicios import cuentas
from .validacion import mes_legible

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # carpeta del proyecto

MENSAJES_ERROR = {400: 'La solicitud no es válida.', 403: 'No tienes permiso para realizar esta acción.',
                  404: 'La página solicitada no existe.', 405: 'Esa acción no se puede hacer desde aquí.',
                  413: 'El archivo es demasiado grande. Vuelve a elegir la foto desde el formulario: se reduce sola antes de enviarse.',
                  500: 'Ocurrió un error inesperado. Inténtalo de nuevo.'}
CABECERAS_SEGURIDAD = (('X-Frame-Options', 'DENY'),            # no mostrar el sitio dentro de otro (clickjacking)
                       ('X-Content-Type-Options', 'nosniff'),  # no adivinar tipos de archivo
                       ('Referrer-Policy', 'same-origin'))     # no enviar la dirección completa a otros sitios


# Crea la aplicación; las pruebas pueden pasar otro .env y otra base.
def crear_app(ruta_env=None, ruta_bd=None):
    ruta_env = ruta_env or os.path.join(RAIZ, '.env')
    ruta_bd = ruta_bd or os.path.join(RAIZ, 'database.db')
    ruta_esquema = os.path.join(RAIZ, 'schema.sql')
    env = config.leer_env(ruta_env)

    app = Flask(__name__, template_folder=os.path.join(RAIZ, 'templates'), static_folder=os.path.join(RAIZ, 'static'))
    # Sin SECRET_KEY, las sesiones duran hasta reiniciar la app.
    app.secret_key = env.get('SECRET_KEY') or nuevo_token(32)
    # COOKIE_SEGURA=1: la cookie de sesión solo viaja por HTTPS.
    app.config.update(RUTA_ENV=ruta_env, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=env.get('COOKIE_SEGURA') == '1', MAX_CONTENT_LENGTH=config.TAMANO_MAXIMO_ENVIO)
    app.jinja_env.filters['mes'] = mes_legible

    conexion.configurar(ruta_bd, ruta_esquema)
    migrar.migrar_si_hace_falta(ruta_bd, ruta_esquema)
    conexion.crear_tablas()
    cuentas.sincronizar_admin(env)
    objetos.configurar_plazo(env.get('DIAS_OCULTAR'))   # días que un objeto entregado sigue en el catálogo (3 a 7)
    objetos.configurar_custodia(env.get('PLAZO_OFICINA_DIAS'), env.get('PLAZO_BODEGA_DIAS'))   # plazos de custodia (RF-16)

    registrar_seguridad(app)
    for modulo in (acceso, rutas_objetos, rutas_reclamaciones, rutas_visitantes, admin):
        app.register_blueprint(modulo.bp)
    registrar_errores(app)
    app.context_processor(variables_globales)
    return app


# Token CSRF de la sesión (lo crea si no existe).
def token_csrf():
    if 'csrf_token' not in session:
        session['csrf_token'] = nuevo_token()
    return session['csrf_token']


# Registra la revisión de sesión, CSRF y cabeceras de seguridad.
def registrar_seguridad(app):
    # Carga el usuario de la sesión y revisa el token CSRF en cada POST.
    @app.before_request
    def cargar_usuario_y_revisar_csrf():
        g.usuario = usuarios.buscar(session['usuario_id']) if 'usuario_id' in session else None
        if 'usuario_id' in session and (not g.usuario or not g.usuario['activo']):
            session.clear()
            flash('Tu cuenta no está activa. Comunícate con el administrador.', 'error')
            return redirect(url_for('acceso.login'))
        # El administrador solo vale mientras coincida con el .env y haya entrado por /admin.
        if comun.tiene_rol(config.ROL_ADMIN) and not (session.get('acceso_admin') and cuentas.es_admin_del_env(g.usuario, comun.entorno())):
            session.clear()
            return redirect(url_for('admin.panel'))
        # Todo envío de formulario debe traer el token de la sesión (contra CSRF).
        if request.method == 'POST' and not (session.get('csrf_token') and iguales(request.form.get('csrf_token'), session['csrf_token'])):
            abort(400, 'Formulario vencido o inválido. Recarga la página e inténtalo de nuevo.')

    # Agrega cabeceras de seguridad a cada respuesta.
    @app.after_request
    def cabeceras_seguridad(respuesta):
        for nombre, valor in CABECERAS_SEGURIDAD:
            respuesta.headers.setdefault(nombre, valor)   # setdefault respeta las que ya puso una ruta
        return respuesta


# Registra las páginas de error en español.
def registrar_errores(app):
    # Muestra la página de error con un mensaje claro.
    def pagina_error(error):
        codigo = getattr(error, 'code', 500) or 500
        propio = getattr(error, 'description', None)
        if propio == getattr(type(error), 'description', None):
            propio = None   # el texto genérico (en inglés) de Flask no se muestra: se usa el nuestro
        mensaje = (propio if codigo == 400 else None) or MENSAJES_ERROR.get(codigo, MENSAJES_ERROR[500])
        return render_template('error.html', codigo=codigo, mensaje=mensaje), codigo

    for codigo in MENSAJES_ERROR:
        app.register_error_handler(codigo, pagina_error)


# Dirección del catálogo conservando los filtros actuales.
def url_filtro(**cambios):
    args = {k: v for k, v in request.args.items() if v}
    args.update(cambios)
    return url_for('objetos.inicio', **{k: v for k, v in args.items() if v not in (None, '')})


# Variables que usan todas las plantillas (usuario, rol, avisos).
def variables_globales():
    personal, estudiante = comun.es_personal(), comun.tiene_rol(config.ROL_ESTUDIANTE)
    return dict(categorias=config.CATEGORIAS, estados=config.ESTADOS, estados_manuales=config.ESTADOS_MANUALES,
                tipos_persona=config.TIPOS_PERSONA, ubicaciones=config.UBICACIONES, estados_reporte=config.ESTADOS_REPORTE,
                largo=config.LARGO_MAXIMO, usuario_actual=g.get('usuario'), csrf_token=token_csrf,
                es_admin=comun.tiene_rol(config.ROL_ADMIN), es_encargado=personal, es_estudiante=estudiante,
                pendientes=reclamaciones.contar_por_estado().get('Pendiente', 0) if personal else 0,
                reportes_nuevos=visitantes.contar_por_estado().get('Pendiente', 0) if personal else 0,
                objetos_ocultos=objetos.contar_ocultos() if personal else 0, dias_plazo=objetos.dias_plazo(),
                custodia=objetos.plazos_custodia(), dias_aviso=objetos.DIAS_AVISO, url_filtro=url_filtro,
                por_retirar=reclamaciones.contar_por_retirar(g.usuario['id']) if estudiante else 0)

