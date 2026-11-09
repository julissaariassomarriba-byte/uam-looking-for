"""Reclamaciones: el estudiante reclama un objeto ya entregado y el personal las acepta o rechaza."""
from flask import Blueprint, g, redirect, render_template, request, url_for

from ..config import ESTADO_RECLAMACION_ANTIGUO, ESTADOS_RECLAMACION
from ..datos import reclamaciones
from ..seguridad import ruta_interna
from ..servicios import reclamaciones as servicio
from .comun import avisar, estudiante_requerido, opcion, personal_requerido

bp = Blueprint('reclamaciones', __name__)


@bp.route('/objeto/<int:id>/reclamar', methods=['POST'])
@estudiante_requerido
def reclamar(id):
    f = request.form
    if avisar(*servicio.crear_reclamacion(id, g.usuario, f.get('descripcion'), f.get('lugar_perdida'),
                                          f.get('fecha_perdida'), f.get('telefono'))):
        return redirect(url_for('reclamaciones.mias'))
    return redirect(url_for('objetos.detalle', id=id))


@bp.route('/mis-reclamaciones')
@estudiante_requerido
def mias():
    return render_template('reclamaciones/mis_reclamaciones.html', reclamaciones=reclamaciones.listar(usuario_id=g.usuario['id']))


@bp.route('/reclamaciones')
@personal_requerido
def lista():
    conteo = reclamaciones.contar_por_estado()
    # Las reclamaciones canceladas antes de la v9 se siguen pudiendo consultar, pero solo si existe alguna.
    pestanas = ESTADOS_RECLAMACION + ((ESTADO_RECLAMACION_ANTIGUO,) if conteo.get(ESTADO_RECLAMACION_ANTIGUO) else ())
    estado = opcion('estado', pestanas, 'Pendiente')
    return render_template('reclamaciones/reclamaciones.html', reclamaciones=reclamaciones.listar(estado), estado_actual=estado,
                           conteo=conteo, pestanas=pestanas)


@bp.route('/reclamaciones/<int:id>', methods=['POST'])
@personal_requerido
def gestionar(id):
    avisar(*servicio.gestionar_reclamacion(id, request.form.get('accion'), request.form.get('nota'), g.usuario['id']))
    return redirect(ruta_interna(request.form.get('volver')) or url_for('reclamaciones.lista'))
