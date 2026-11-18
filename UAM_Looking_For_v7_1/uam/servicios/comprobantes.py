"""Comprobante de entrega (RF-12 y RF-14).

Se puede imprimir (con espacio para la firma de quien recibe y de quien entrega) o enviar por correo a quien retiró
el objeto. No lleva las señas ni la descripción interna: un comprobante puede reenviarse y esos datos sirven para
comprobar quién es el dueño.
"""
from ..datos import objetos, reclamaciones
from ..utilidades import correo
from ..validacion import correo_valido, texto


def buscar(objeto_id):
    """{objeto, entrega} si el objeto tiene una entrega registrada; si no, None."""
    objeto = objetos.buscar(objeto_id)
    entrega = reclamaciones.buscar_entrega(objeto_id) if objeto else None
    return {'objeto': objeto, 'entrega': entrega} if entrega else None


def texto_correo(c):
    o, e = c['objeto'], c['entrega']
    lineas = [
        f'Hola, {e["nombre"]}:', '',
        'Este es el comprobante de la entrega registrada en la oficina de objetos perdidos de la UAM.', '',
        f'Código del objeto: #{o["id"]}',
        f'Objeto: {o["titulo"]} ({o["categoria"]})',
        f'Retirado por: {e["nombre"]} · CIF o cédula: {e["cif"] or "sin registrar"}'
        + (f' · Carrera: {e["carrera"]}' if e['carrera'] else ''),
        f'Fecha y hora de la entrega: {e["fecha_entrega"][:16]}',
        f'Entregado por: {e["entregado_por_nombre"]}', '',
        'Si no retiraste este objeto, comunícate con la oficina de Vida Estudiantil.', '',
        'UAM Looking For',
    ]
    return '\n'.join(lineas)


def enviar(objeto_id, para, env):
    """Envía el comprobante al correo indicado (por defecto, el registrado de quien lo retiró)."""
    c = buscar(objeto_id)
    if not c:
        return False, 'Este objeto todavía no tiene una entrega registrada.'
    para = texto(para).lower() or (c['entrega']['correo'] or '')
    if not para:
        return False, 'Quien retiró el objeto no tiene correo registrado. Escríbelo para enviar el comprobante.'
    if not correo_valido(para):
        return False, 'El correo no es válido.'
    if not correo.configurado(env):
        return False, ('El envío de correos no está configurado en el servidor (datos SMTP en el .env). '
                       'Imprime el comprobante y entrégalo en papel.')
    ok, motivo = correo.enviar(env, para, f'Comprobante de entrega · objeto #{objeto_id}', texto_correo(c))
    if not ok:
        return False, f'No se pudo enviar el correo ({motivo}). Inténtalo más tarde o imprime el comprobante.'
    return True, f'Comprobante enviado a {para}.'
