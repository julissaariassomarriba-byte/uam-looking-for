# Aviso por WhatsApp Cloud API (con urllib).
import json
import re
import urllib.error
import urllib.request

API = 'https://graph.facebook.com'
OBLIGATORIAS = ('WHATSAPP_TOKEN', 'WHATSAPP_NUMERO_ID', 'WHATSAPP_DESTINO')
TIEMPO_MAXIMO = 10   # segundos: si WhatsApp no responde, el reporte ya está guardado y se puede reintentar


# Variables de WhatsApp que faltan en el .env.
def faltantes(env):
    return [c for c in OBLIGATORIAS if not (env.get(c) or '').strip()]


# Deja solo los dígitos de un número.
def solo_digitos(numero):
    return re.sub(r'\D', '', numero or '')


# Limpia y recorta un texto para la plantilla (sin saltos de línea).
def variable(texto, maximo=200):
    texto = re.sub(r'\s+', ' ', str(texto or '')).strip() or '-'
    return texto if len(texto) <= maximo else texto[:maximo - 1] + '…'


# Datos del aviso, en el orden de la plantilla ({{1}} a {{8}}).
def datos_aviso(reporte, enlace):
    return [reporte['codigo'], reporte['nombre'], reporte['objeto_nombre'], reporte['descripcion'],
            reporte['lugar_perdida'], reporte['fecha_perdida'], reporte['telefono'], enlace]


# Texto del aviso.
def texto_aviso(reporte, enlace):
    codigo, nombre, objeto, descripcion, lugar, fecha, telefono, enlace = datos_aviso(reporte, enlace)
    return (f'UAM Looking For · Nuevo reporte de objeto perdido {codigo}\n'
            f'Visitante: {nombre}\nObjeto: {objeto}\nDescripción: {descripcion}\n'
            f'Lugar: {lugar}\nFecha de pérdida: {fecha}\nTeléfono: {telefono}\n'
            f'Revisar (requiere iniciar sesión): {enlace}')


# Mensaje que se envía a WhatsApp.
def mensaje(env, reporte, enlace):
    cuerpo = {'messaging_product': 'whatsapp', 'to': solo_digitos(env['WHATSAPP_DESTINO'])}
    if (env.get('WHATSAPP_PLANTILLA') or '').strip():
        cuerpo.update(type='template', template={
            'name': env['WHATSAPP_PLANTILLA'].strip(), 'language': {'code': (env.get('WHATSAPP_IDIOMA') or 'es').strip()},
            'components': [{'type': 'body', 'parameters': [{'type': 'text', 'text': variable(v)} for v in datos_aviso(reporte, enlace)]}]})
    else:
        cuerpo.update(type='text', text={'preview_url': False, 'body': texto_aviso(reporte, enlace)[:4096]})
    return cuerpo


# Mensaje claro del error que devuelve WhatsApp.
def motivo_http(error, token):
    try:
        datos = json.loads(error.read().decode('utf-8')).get('error', {})
        detalle = datos.get('error_data', {}).get('details') or datos.get('message') or ''
        texto = f"Error {error.code} de WhatsApp (código {datos.get('code', '?')}): {detalle}"
    except (ValueError, AttributeError, OSError):
        texto = f'Error {error.code} de WhatsApp'
    return texto.replace(token, '***')[:300]


# Envía el aviso por WhatsApp.
def enviar(env, reporte, enlace):
    falta = faltantes(env)
    if falta:
        return 'No configurada', 'Falta en el .env: ' + ', '.join(falta)
    token = env['WHATSAPP_TOKEN'].strip()
    # WHATSAPP_API_URL solo sirve para pruebas (un servidor simulado); en producción no se define.
    url = (f"{(env.get('WHATSAPP_API_URL') or API).rstrip('/')}/{(env.get('WHATSAPP_VERSION') or 'v22.0').strip()}"
           f"/{env['WHATSAPP_NUMERO_ID'].strip()}/messages")
    peticion = urllib.request.Request(url, data=json.dumps(mensaje(env, reporte, enlace)).encode('utf-8'), method='POST',
                                      headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_MAXIMO) as respuesta:
            datos = json.loads(respuesta.read().decode('utf-8') or '{}')
        mensaje_id = ((datos.get('messages') or [{}])[0] or {}).get('id')
        return ('Enviada', str(mensaje_id)[:200]) if mensaje_id else ('Fallida', 'WhatsApp respondió sin el id del mensaje')
    except urllib.error.HTTPError as error:
        return 'Fallida', motivo_http(error, token)
    except (urllib.error.URLError, OSError, ValueError, AttributeError, IndexError, TypeError) as error:
        motivo = getattr(error, 'reason', None) or error
        return 'Fallida', f'Sin conexión con WhatsApp: {motivo}'.replace(token, '***')[:300]
