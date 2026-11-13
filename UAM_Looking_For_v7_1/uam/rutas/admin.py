"""Panel de administración (/admin). Las credenciales del administrador están en el .env."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from ..config import ROL_ADMIN, ROLES_GESTIONABLES
from ..datos import objetos, reclamaciones, usuarios, visitantes
from ..servicios import cuentas
from .comun import admin_requerido, avisar, entorno, opcion, tiene_rol

bp = Blueprint('admin', __name__, url_prefix='/admin')
MOVIMIENTOS_RECIENTES = 8


@bp.route('', methods=['GET', 'POST'])
def panel():
    if g.usuario and not tiene_rol(ROL_ADMIN):
        flash('Acceso restringido: el panel de administración es solo para el administrador.', 'error')
        return redirect(url_for('objetos.inicio'))
    env = entorno()
    if not g.usuario:
        if request.method == 'POST':
            if not cuentas.admin_configurado(env):
                flash('Falta configurar ADMIN_USUARIO y ADMIN_CONTRASENA en el archivo .env.', 'error')
            elif cuentas.validar_admin(request.form.get('cif', ''), request.form.get('contrasena', ''), env):
                admin_id = cuentas.sincronizar_admin(env)
                session.clear()
                session.update(usuario_id=admin_id, acceso_admin=True)
                return redirect(url_for('admin.panel'))
            else:
                flash('Credenciales de administrador incorrectas.', 'error')
        return render_template('admin/admin_login.html', env_listo=cuentas.admin_configurado(env))
    por_estado = objetos.contar_por('estado')
    return render_template('admin/admin_panel.html', por_rol=usuarios.contar_cuentas_por_rol(), por_estado=por_estado,
                           total_objetos=sum(por_estado.values()), reclamaciones_pendientes=reclamaciones.listar('Pendiente'),
                           por_reporte=visitantes.contar_por_estado(), movimientos=objetos.listar_historial(limite=MOVIMIENTOS_RECIENTES),
                           fotos=objetos.uso_fotos())


@bp.route('/usuarios', methods=['GET', 'POST'])
@bp.route('/usuarios/<int:id>/editar', methods=['GET', 'POST'])
@admin_requerido
def usuarios_lista(id=None):
    usuario = (usuarios.buscar(id) or abort(404)) if id else None
    if usuario and (usuario['rol'] not in ROLES_GESTIONABLES or not usuario['contrasena_hash']):
        flash('Esta cuenta no se edita desde el panel (el administrador se configura en el archivo .env).', 'error')
        return redirect(url_for('admin.usuarios_lista'))
    f = request.form
    if request.method == 'POST' and avisar(*cuentas.guardar_usuario(
            f.get('nombre'), f.get('cif'), f.get('correo'), f.get('carrera'), f.get('rol'), f.get('contrasena'), id)):
        return redirect(url_for('admin.usuarios_lista'))
    if usuario:
        return render_template('admin/admin_editar_usuario.html', usuario=usuario, datos=f or usuario, roles=ROLES_GESTIONABLES)
    rol = opcion('rol', (ROL_ADMIN, *ROLES_GESTIONABLES))
    busqueda = (request.args.get('q') or '').strip()[:100]
    return render_template('admin/admin_usuarios.html', usuarios=usuarios.listar_cuentas(rol, busqueda), rol_actual=rol,
                           busqueda=busqueda, roles=ROLES_GESTIONABLES, datos=f, por_rol=usuarios.contar_cuentas_por_rol())


@bp.route('/usuarios/<int:id>/estado', methods=['POST'])
@admin_requerido
def estado_usuario(id):
    avisar(*cuentas.cambiar_activo(id, request.form.get('activo') == '1'))
    return redirect(url_for('admin.usuarios_lista'))
