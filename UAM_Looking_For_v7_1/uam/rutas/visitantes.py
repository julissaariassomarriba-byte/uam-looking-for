# Rutas del portal de visitantes y su panel.
from flask import (Blueprint, Response, abort, flash, g, make_response, redirect, render_template, request, session,
                   url_for)

from ..config import ESTADOS_REPORTE
from ..datos import objetos, visitantes
from ..datos.conexion import hoy
from ..seguridad import nuevo_token
from ..servicios import visitantes as servicio
from ..utilidades import imagenes, notificaciones
from .comun import avisar, entorno, opcion, personal_requerido, sin_cache

bp = Blueprint('visitantes', __name__)
ENVIOS_RECORDADOS = 5


# Enlace al reporte para el aviso de WhatsApp.
def enlace_reporte(id):
    base = (entorno().get('SITIO_URL') or '').strip().rstrip('/')
    return base + url_for('visitantes.reporte', id=id) if base else url_for('visitantes.reporte', id=id, _external=True)


# ---------- Visitante (sin sesión) ----------

# Portal del visitante.
@bp.route('/visitante')
def portal():
    return render_template('visitantes/visitante.html')


# El visitante reporta un objeto perdido.
@bp.route('/visitante/reportar', methods=['GET', 'POST'])
def reportar():
    envios = session.get('envios_visitante', {})
    if request.method == 'POST':
        envio = request.form.get('envio', '')
        if envio in envios:
            return redirect(url_for('visitantes.seguimiento', token=envios[envio]))
        ok, resultado = servicio.registrar_reporte(request.form, request.files.get('foto'))
        if ok:   # el reporte ya está guardado: el aviso por WhatsApp no puede hacer que se pierda
            servicio.notificar(resultado['id'], enlace_reporte(resultado['id']), entorno())
            session['envios_visitante'] = dict(list(envios.items())[-(ENVIOS_RECORDADOS - 1):] + [(envio, resultado['token'])])
            return redirect(url_for('visitantes.seguimiento', token=resultado['token'], nuevo=1))
        flash(resultado, 'error')
    return render_template('visitantes/visitante_reportar.html', datos=request.form, hoy=hoy(),
                           envio=request.form.get('envio') or nuevo_token())


# Seguimiento con el enlace privado.
@bp.route('/visitante/seguimiento/<token>')
def seguimiento(token):
    reporte = servicio.seguimiento(token) or abort(404)
    return sin_cache(make_response(render_template(
        'visitantes/visitante_seguimiento.html', r=reporte, nuevo=request.args.get('nuevo') == '1',
        enlace=url_for('visitantes.seguimiento', token=token, _external=True))))


# Consulta con código y teléfono.
@bp.route('/visitante/consultar', methods=['GET', 'POST'])
def consultar():
    reporte = None
    if request.method == 'POST':
        reporte = servicio.consultar(request.form.get('codigo'), request.form.get('telefono'))
        if not reporte:
            flash('No encontramos un reporte con ese código y ese teléfono. Revisa los datos que diste al reportar.', 'error')
    return sin_cache(make_response(render_template('visitantes/visitante_consultar.html', r=reporte, datos=request.form)))


# ---------- Panel del personal ----------

# Panel de reportes del personal.
@bp.route('/reportes-visitantes')
@personal_requerido
def panel():
    estado = opcion('estado', ESTADOS_REPORTE)
    buscado = (request.args.get('codigo') or '').strip()[:100]   # código, nombre, teléfono u objeto
    codigo = servicio.limpiar_codigo(buscado)
    return render_template('visitantes/reportes_visitantes.html', reportes=visitantes.listar(estado, codigo, buscado),
                           estado_actual=estado, codigo=codigo, conteo=visitantes.contar_por_estado())


# Ficha de un reporte y su gestión.
@bp.route('/reportes-visitantes/<int:id>', methods=['GET', 'POST'])
@personal_requerido
def reporte(id):
    if request.method == 'POST':
        f, yo = request.form, g.usuario['id']
        acciones = {
            'whatsapp': lambda: servicio.reintentar_whatsapp(id, enlace_reporte(id), entorno()),
            'relacionar': lambda: servicio.relacionar_objeto(id, f.get('objeto_id'), yo),
            'gestionar': lambda: servicio.gestionar(id, f.get('estado'), f.get('observaciones'), yo),
        }
        accion = acciones.get(f.get('accion') or 'gestionar')
        if not accion:
            abort(400)
        avisar(*accion())
        return redirect(url_for('visitantes.reporte', id=id))
    r = visitantes.buscar(id) or abort(404)
    return render_template('visitantes/reporte_visitante.html', r=r, coincidencias=servicio.posibles_coincidencias(r),
                           objetos=objetos.para_relacionar(r['categoria']), contacto=servicio.enlaces_contacto(r),
                           whatsapp_falta=notificaciones.faltantes(entorno()))


# Muestra la foto de un reporte.
@bp.route('/reportes-visitantes/<int:id>/foto')
@personal_requerido
def foto(id):
    datos = visitantes.foto(id) or abort(404)
    return Response(datos, mimetype=imagenes.formato(datos), headers={'Cache-Control': 'private, max-age=3600'})
