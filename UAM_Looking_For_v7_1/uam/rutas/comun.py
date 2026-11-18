# Funciones que comparten todas las rutas.
import functools

from flask import current_app, flash, g, redirect, request, url_for

from ..config import ROL_ADMIN, ROL_ESTUDIANTE, ROLES_PERSONAL, leer_env


# Valores actuales del .env.
def entorno():
    return leer_env(current_app.config['RUTA_ENV'])


# Dice si el usuario tiene alguno de esos roles.
def tiene_rol(*roles):
    return bool(g.get('usuario')) and g.usuario['rol'] in roles


# Dice si el usuario es personal (encargado o admin).
def es_personal():
    return tiene_rol(*ROLES_PERSONAL)


# Muestra el mensaje de un servicio en verde o rojo.
def avisar(ok, mensaje):
    flash(mensaje, 'exito' if ok else 'error')
    return ok


# Valor de un filtro de la URL, solo si está permitido.
def opcion(nombre, permitidos, defecto=None):
    valor = request.args.get(nombre, defecto)
    return valor if valor in permitidos else None


# Evita que el navegador guarde páginas privadas.
def sin_cache(respuesta):
    respuesta.headers['Cache-Control'] = 'no-store'
    return respuesta


# Decorador: exige sesión y, si se indica, un rol.
def requiere(*roles, mensaje='', acceso='acceso.login'):
    # Envuelve la vista.
    def decorador(vista):
        # Revisa la sesión y el rol antes de abrir la página.
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
