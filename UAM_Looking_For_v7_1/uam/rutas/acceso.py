# Rutas de inicio de sesión, registro y perfil.
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from ..servicios import cuentas
from .comun import avisar, login_requerido

bp = Blueprint('acceso', __name__)


# Inicio de sesión de estudiantes y encargados.
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.usuario:
        return redirect(url_for('objetos.inicio'))
    if request.method == 'POST':
        usuario = cuentas.validar_login(request.form.get('cif'), request.form.get('contrasena'))
        if not usuario:
            flash('CIF o contraseña incorrectos.', 'error')
        elif not usuario['activo']:
            flash('Tu cuenta está desactivada. Comunícate con el administrador del sistema.', 'error')
        else:
            session.clear()   # sesión nueva al entrar: evita reutilizar una sesión anterior
            session['usuario_id'] = usuario['id']
            flash(f'¡Bienvenido/a {usuario["nombre"]}!', 'exito')
            return redirect(url_for('objetos.inicio'))
    return render_template('acceso/login.html')


# Registro de estudiantes.
@bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if g.usuario:
        return redirect(url_for('objetos.inicio'))
    f = request.form
    if request.method == 'POST':
        ok, resultado = cuentas.registrar_estudiante(f.get('nombre'), f.get('cif'), f.get('correo'), f.get('contrasena'),
                                                     f.get('confirmar'), f.get('carrera'))
        if ok:
            session.clear()   # antes del aviso: clear() también borraría el mensaje
            session['usuario_id'] = resultado
        if avisar(ok, '¡Cuenta creada! Ya puedes buscar y reclamar tus objetos.' if ok else resultado):
            return redirect(url_for('objetos.inicio'))
    return render_template('acceso/login.html', registro=True, datos=f)


# Cierra la sesión (solo por POST).
@bp.route('/logout', methods=['POST'])
def logout():
    era_admin = session.get('acceso_admin')
    session.clear()
    flash('Has cerrado sesión correctamente.', 'exito')
    return redirect(url_for('admin.panel' if era_admin else 'acceso.login'))


# Página «Mi perfil».
@bp.route('/perfil', methods=['GET', 'POST'])
@login_requerido
def perfil():
    f = request.form
    if request.method == 'POST':
        if f.get('accion') == 'contrasena':
            avisar(*cuentas.cambiar_contrasena(g.usuario, f.get('actual'), f.get('nueva'), f.get('confirmar')))
        else:
            avisar(*cuentas.actualizar_perfil(g.usuario, f.get('correo'), f.get('carrera'), f.get('telefono')))
        return redirect(url_for('acceso.perfil'))
    return render_template('acceso/perfil.html')
