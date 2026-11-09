"""Avisos al encargado por WhatsApp Business Cloud API (Meta), sin librerías: urllib de la biblioteca estándar.

Las credenciales van en el .env, nunca en el código (ver .env.example y la guía en README.md):
  WHATSAPP_TOKEN      token de acceso de Meta (permanente, de un usuario del sistema de Meta Business)
  WHATSAPP_NUMERO_ID  «Phone number ID» del número que envía (es un id de Meta, no el número de teléfono)
  WHATSAPP_DESTINO    número del encargado que recibe los avisos, con código de país (ej. 50588887777)
  WHATSAPP_PLANTILLA  (recomendado) nombre de la plantilla aprobada con 8 variables. Sin plantilla se envía texto
                      libre, que Meta solo entrega si el encargado le escribió a ese número en las últimas 24 horas.
  WHATSAPP_IDIOMA     idioma de la plantilla (por defecto es)
  WHATSAPP_VERSION    versión de la API Graph (por defecto v22.0)

enviar() nunca lanza excepciones ni finge un envío. Devuelve una de estas tres respuestas:
  ('Enviada', id del mensaje)   WhatsApp aceptó el mensaje y devolvió su id (wamid…)
  ('Fallida', motivo)           error de Meta, de red o respuesta inesperada
  ('No configurada', qué falta) faltan datos en el .env: no se intenta la conexión
"""
import json
import re
import urllib.error
import urllib.request

API = 'https://graph.facebook.com'
OBLIGATORIAS = ('WHATSAPP_TOKEN', 'WHATSAPP_NUMERO_ID', 'WHATSAPP_DESTINO')
TIEMPO_MAXIMO = 10   # segundos: si WhatsApp no responde, el reporte ya está guardado y se puede reintentar


def faltantes(env):
    """Variables obligatorias que faltan en el .env (lista vacía = configurado)."""
    return [c for c in OBLIGATORIAS if not (env.get(c) or '').strip()]


def solo_digitos(numero):
    return re.sub(r'\D', '', numero or '')


# Meta no acepta saltos de línea, tabuladores ni más de 4 espacios seguidos en las variables de una plantilla.
def variable(texto, maximo=200):
    texto = re.sub(r'\s+', ' ', str(texto or '')).strip() or '-'
    return texto if len(texto) <= maximo else texto[:maximo - 1] + '…'


# Datos del aviso, en el orden de las variables {{1}} a {{8}} de la plantilla.
def datos_aviso(reporte, enlace):
    return [reporte['codigo'], reporte['nombre'], reporte['objeto_nombre'], reporte['descripcion'],
            reporte['lugar_perdida'], reporte['fecha_perdida'], reporte['telefono'], enlace]


def texto_aviso(reporte, enlace):
    codigo, nombre, objeto, descripcion, lugar, fecha, telefono, enlace = datos_aviso(reporte, enlace)
    return (f'UAM Looking For · Nuevo reporte de objeto perdido {codigo}\n'
            f'Visitante: {nombre}\nObjeto: {objeto}\nDescripción: {descripcion}\n'
            f'Lugar: {lugar}\nFecha de pérdida: {fecha}\nTeléfono: {telefono}\n'
            f'Revisar (requiere iniciar sesión): {enlace}')


def mensaje(env, reporte, enlace):
    """Cuerpo JSON que se envía a /messages: plantilla si hay WHATSAPP_PLANTILLA, si no, texto libre."""
    cuerpo = {'messaging_product': 'whatsapp', 'to': solo_digitos(env['WHATSAPP_DESTINO'])}
    if (env.get('WHATSAPP_PLANTILLA') or '').strip():
        cuerpo.update(type='template', template={
            'name': env['WHATSAPP_PLANTILLA'].strip(), 'language': {'code': (env.get('WHATSAPP_IDIOMA') or 'es').strip()},
            'components': [{'type': 'body', 'parameters': [{'type': 'text', 'text': variable(v)} for v in datos_aviso(reporte, enlace)]}]})
    else:
        cuerpo.update(type='text', text={'preview_url': False, 'body': texto_aviso(reporte, enlace)[:4096]})
    return cuerpo


def motivo_http(error, token):
    """Mensaje claro a partir del error que devuelve Meta (nunca incluye el token)."""
    try:
        datos = json.loads(error.read().decode('utf-8')).get('error', {})
        detalle = datos.get('error_data', {}).get('details') or datos.get('message') or ''
        texto = f"Error {error.code} de WhatsApp (código {datos.get('code', '?')}): {detalle}"
    except (ValueError, AttributeError, OSError):
        texto = f'Error {error.code} de WhatsApp'
    return texto.replace(token, '***')[:300]


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
