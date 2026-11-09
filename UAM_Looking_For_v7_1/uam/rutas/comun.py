"""Ayudas que comparten todas las rutas: usuario conectado, permisos por rol, avisos y filtros de la URL."""
import functools

from flask import current_app, flash, g, redirect, request, url_for

from ..config import ROL_ADMIN, ROL_ESTUDIANTE, ROLES_PERSONAL, leer_env


def entorno():
    """Valores del .env (se leen en cada uso: así un cambio en el .env vale tras recargar la app)."""
    return leer_env(current_app.config['RUTA_ENV'])


def tiene_rol(*roles):
    return bool(g.get('usuario')) and g.usuario['rol'] in roles


def es_personal():
    return tiene_rol(*ROLES_PERSONAL)


def avisar(ok, mensaje):
    """Muestra el mensaje de un servicio (verde si salió bien, rojo si no) y devuelve si salió bien."""
    flash(mensaje, 'exito' if ok else 'error')
    return ok


def opcion(nombre, permitidos, defecto=None):
    """Filtro de la URL (?categoria=, ?estado=…): solo vale si es uno de los permitidos; si no, None (sin filtro)."""
    valor = request.args.get(nombre, defecto)
    return valor if valor in permitidos else None


def sin_cache(respuesta):
    """Para páginas con datos privados: que el navegador no las guarde."""
    respuesta.headers['Cache-Control'] = 'no-store'
    return respuesta


def requiere(*roles, mensaje='', acceso='acceso.login'):
    """Decorador: exige sesión iniciada y, si se indican, alguno de los roles."""
    def decorador(vista):
        @functools.wraps(vista)   # conserva el nombre de la función: Flask lo usa como nombre de la ruta
        def envoltura(*args, **kwargs):
            if not g.usuario:
                flash('Debes iniciar sesión para continuar.', 'error')
                return redirect(url_for(acceso))
            if roles and not tiene_rol(*roles):
                flash(mensaje, 'error')
                return redirect(url_for('objetos.inicio'))
            return vista(*args, **kwargs)
        return envoltura
    return decorador


login_requerido = requiere()
personal_requerido = requiere(*ROLES_PERSONAL, mensaje='Acceso restringido: solo el encargado puede entrar a esta sección.')
estudiante_requerido = requiere(ROL_ESTUDIANTE, mensaje='Solo los estudiantes pueden enviar solicitudes de reclamación.')
admin_requerido = requiere(ROL_ADMIN, mensaje='Acceso restringido: solo el administrador puede gestionar cuentas.',
                           acceso='admin.panel')
