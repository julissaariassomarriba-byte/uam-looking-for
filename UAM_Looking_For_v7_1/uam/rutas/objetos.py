"""Catálogo, ficha de cada objeto, recepción, entrega e historial."""
from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, session, url_for

from ..config import CATEGORIAS, UBICACIONES
from ..datos import objetos, reclamaciones
from ..datos.conexion import ahora, hoy
from ..seguridad import nuevo_token
from ..servicios import objetos as servicio_objetos
from ..servicios import reclamaciones as servicio_reclamaciones
from ..utilidades import imagenes, reporte_pdf
from .comun import avisar, es_personal, login_requerido, opcion, personal_requerido

bp = Blueprint('objetos', __name__)
ENVIOS_RECORDADOS = 10   # formularios de recepción recordados para no guardar dos veces el mismo objeto


@bp.route('/')
@login_requerido
def inicio():
    categoria, ubicacion = opcion('categoria', CATEGORIAS), opcion('ubicacion', UBICACIONES)
    return render_template('objetos/index.html', objetos=objetos.listar(categoria, ubicacion, publicos=not es_personal()),
                           categoria_actual=categoria, ubicacion_actual=ubicacion, por_categoria=objetos.contar_por('categoria'),
                           por_estado=objetos.contar_por('estado'), por_ubicacion=objetos.contar_por('ubicacion'))


@bp.route('/objeto/<int:id>/foto')
@login_requerido
def foto(id):
    """Foto leída de la base. El personal ve todas; un estudiante solo las marcadas como públicas."""
    f = objetos.buscar_foto(id)
    if not f or not (es_personal() or f['foto_publica']):
        abort(404)
    return Response(f['foto'], mimetype=imagenes.formato(f['foto']), headers={'Cache-Control': 'private, max-age=86400'})


@bp.route('/guia')
@login_requerido
def guia():
    return render_template('objetos/guia.html')


@bp.route('/objeto/<int:id>', methods=['GET', 'POST'])
@login_requerido
def detalle(id):
    if request.method == 'POST':
        if not es_personal():
            abort(403)
        f, yo = request.form, g.usuario['id']
        acciones = {
            'descripcion_publica': lambda: servicio_objetos.actualizar_descripcion_publica(id, f.get('descripcion_publica'), yo),
            'ubicacion': lambda: servicio_objetos.cambiar_ubicacion(id, f.get('ubicacion'), yo),
            'foto': lambda: servicio_objetos.actualizar_foto(id, request.files.get('foto'), f.get('foto_publica') == '1', yo),
            'recuperado': lambda: servicio_reclamaciones.registrar_recuperacion(id, f.get('observaciones'), yo),
            'devolver': lambda: servicio_reclamaciones.devolver_al_dueno(id, f.get('confirmado') == '1', f.get('observaciones'), yo),
            'estado': lambda: servicio_objetos.cambiar_estado_manual(id, f.get('estado'), yo),
        }
        accion = acciones.get(f.get('accion') or 'estado')
        if not accion:
            abort(400)
        avisar(*accion())
        return redirect(url_for('objetos.detalle', id=id))
    return mostrar_detalle(id)


def mostrar_detalle(id, datos_entrega=None):
    """El personal ve el registro completo; un estudiante, solo la parte pública.
    Si una entrega no se pudo guardar, se vuelve a mostrar con lo que escribió el encargado (datos_entrega)."""
    personal = es_personal()
    objeto = objetos.buscar(id, publico=not personal) or abort(404)
    entrega = reclamaciones.buscar_entrega(id)
    if not personal:
        return render_template('objetos/detalle.html', objeto=objeto,
                               lo_retire_yo=bool(entrega) and entrega['retirado_por'] == g.usuario['id'],
                               mi_reclamacion=reclamaciones.listar('Pendiente', id, g.usuario['id']))
    return render_template('objetos/detalle.html', objeto=objeto, entrega=entrega, aceptada=reclamaciones.aceptada_de_objeto(id),
                           reclamaciones=reclamaciones.listar(objeto_id=id), movimientos=objetos.listar_historial(id),
                           datos_entrega=datos_entrega or {})


@bp.route('/objeto/<int:id>/entregar', methods=['POST'])
@personal_requerido
def entregar(id):
    """Registra quién retira el objeto (entrega inicial). Es la única forma de marcarlo como «Entregado»."""
    f = request.form
    if avisar(*servicio_reclamaciones.registrar_entrega(id, f.get('nombre'), f.get('tipo'), f.get('cif'), f.get('telefono'),
                                                         f.get('senas'), f.get('confirmado') == '1', g.usuario['id'])):
        return redirect(url_for('objetos.detalle', id=id))
    return mostrar_detalle(id, datos_entrega=f)


@bp.route('/reportar', methods=['GET', 'POST'])
@personal_requerido
def reportar():
    """Recepción de un objeto. Cada formulario lleva un código «envio»: si llega dos veces (doble clic o recarga),
    no se crea un objeto repetido, se abre el que ya se guardó."""
    envios = session.get('envios', {})
    if request.method == 'POST':
        envio = request.form.get('envio', '')
        if envio in envios:
            flash('Este objeto ya estaba registrado; no se guardó dos veces.', 'exito')
            return redirect(url_for('objetos.detalle', id=envios[envio]))
        ok, resultado = servicio_objetos.registrar_objeto(request.form, request.files.get('foto'), g.usuario['id'])
        if avisar(ok, 'Objeto registrado exitosamente.' if ok else resultado):
            session['envios'] = dict(list(envios.items())[-(ENVIOS_RECORDADOS - 1):] + [(envio, resultado)])
            return redirect(url_for('objetos.detalle', id=resultado))
    return render_template('objetos/reportar.html', datos=request.form, hoy=hoy(), envio=request.form.get('envio') or nuevo_token())


@bp.route('/historial')
@personal_requerido
def historial():
    return render_template('objetos/historial.html', objetos=objetos.listar(), movimientos=objetos.listar_historial(),
                           conteo=objetos.contar_por('estado'))


@bp.route('/historial/pdf')
@personal_requerido
def historial_pdf():
    """Descarga el historial como PDF (reporte_pdf lo arma sin librerías)."""
    fecha = ahora()
    pdf = reporte_pdf.generar_historial(objetos.listar(), objetos.listar_historial(), objetos.contar_por('estado'),
                                        g.usuario['nombre'], fecha)
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename=historial_objetos_{fecha[:10]}.pdf'})

