# Reglas de los reportes de visitantes.
import hmac
import re
import secrets
import sqlite3
import urllib.parse

from ..config import CATEGORIAS, CODIGO_PAIS, ESTADOS_REPORTE, LARGO_MAXIMO
from ..datos import objetos, visitantes
from ..datos.conexion import hoy, transaccion
from ..seguridad import hash_token
from ..utilidades import imagenes, notificaciones
from ..validacion import correo_valido, digitos, fecha_valida, primer_error, telefono_valido, texto
from . import MENSAJE_RECHAZO_BD, en_transaccion

ALFABETO_CODIGO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'   # sin I, O, 0 ni 1, que se confunden al copiarlos
PATRON_CODIGO = re.compile(r'UAM-[A-Z0-9]{4}-[A-Z0-9]{4}')
LARGOS = {'nombre': 100, 'telefono': 30, 'correo': 120, 'objeto_nombre': 100, 'descripcion': 1000, 'lugar_perdida': 150}
ETIQUETAS = {'nombre': 'tu nombre', 'telefono': 'teléfono', 'correo': 'correo', 'objeto_nombre': 'nombre del objeto',
             'descripcion': 'descripción', 'lugar_perdida': 'lugar'}
INTENTOS_CODIGO = 5


# Genera un código UAM-XXXX-XXXX.
def nuevo_codigo():
    letras = ''.join(secrets.choice(ALFABETO_CODIGO) for _ in range(8))
    return f'UAM-{letras[:4]}-{letras[4:]}'


# Deja solo letras, números y guiones en un código.
def limpiar_codigo(codigo, maximo=13):
    return re.sub(r'[^A-Z0-9-]', '', texto(codigo).upper())[:maximo]


# Revisa los datos de un reporte.
def revisar_reporte(d):
    revisiones = [
        (len(d['nombre']) < 3, 'Escribe tu nombre completo.'),
        (not telefono_valido(d['telefono']), 'Escribe un número de teléfono válido (al menos 8 dígitos) para poder contactarte.'),
        (d['correo'] is not None and not correo_valido(d['correo']), 'El correo no es válido (o déjalo vacío).'),
        (len(d['objeto_nombre']) < 3, 'Escribe qué objeto perdiste.'),
        (d['categoria'] not in CATEGORIAS, 'Elige la categoría del objeto.'),
        (len(d['descripcion']) < 15, 'Describe el objeto con más detalle (al menos 15 caracteres): color, marca, contenido…'),
        (len(d['lugar_perdida']) < 3, 'Escribe dónde lo perdiste dentro de la universidad.'),
        (not fecha_valida(d['fecha_perdida']), 'Escribe la fecha en que lo perdiste.'),
        (fecha_valida(d['fecha_perdida']) and d['fecha_perdida'] > hoy(), 'La fecha de pérdida no puede ser futura.'),
    ]
    revisiones += [(len(d[campo] or '') > maximo, f'El campo «{ETIQUETAS[campo]}» es demasiado largo (máximo {maximo} caracteres).')
                   for campo, maximo in LARGOS.items()]
    return primer_error(revisiones)


# Guarda el reporte con su foto.
def registrar_reporte(datos, archivo):
    d = {campo: texto(datos.get(campo)) for campo in LARGOS}
    d.update(correo=d['correo'].lower() or None, categoria=datos.get('categoria'), fecha_perdida=texto(datos.get('fecha_perdida')))
    error = revisar_reporte(d)
    if error:
        return False, error
    ok, foto = imagenes.revisar(archivo)
    if not ok:
        return False, foto
    if not foto:
        return False, 'La fotografía del objeto es obligatoria: ayuda al encargado a reconocerlo.'
    token = secrets.token_urlsafe(32)
    d.update(foto=foto, token_hash=hash_token(token))
    for _ in range(INTENTOS_CODIGO):   # el código es al azar: si por casualidad ya existe, se genera otro
        d['codigo'] = nuevo_codigo()
        try:
            with transaccion() as con:
                return True, {'id': visitantes.insertar(con, d), 'codigo': d['codigo'], 'token': token}
        except sqlite3.IntegrityError as error:
            if 'reportes_visitantes.codigo' not in str(error):
                return False, MENSAJE_RECHAZO_BD
    return False, 'No se pudo generar un código para el reporte. Inténtalo de nuevo.'


# Avisa por WhatsApp y guarda el resultado.
def notificar(id, enlace, env):
    reporte = visitantes.buscar(id)
    try:
        estado, detalle = notificaciones.enviar(env, reporte, enlace)
    except Exception as error:   # un fallo inesperado del aviso no debe perder ni bloquear el reporte
        estado, detalle = 'Fallida', f'Error inesperado al avisar: {type(error).__name__}'
    visitantes.anotar_whatsapp(id, estado, (detalle or 'Sin detalle')[:300])
    return estado, detalle


# Vuelve a intentar el aviso por WhatsApp.
def reintentar_whatsapp(id, enlace, env):
    reporte = visitantes.buscar(id)
    if not reporte:
        return False, 'El reporte no existe.'
    if reporte['whatsapp_estado'] == 'Enviada':
        return False, 'El aviso de este reporte ya se envió por WhatsApp.'
    estado, detalle = notificar(id, enlace, env)
    if estado == 'Enviada':
        return True, 'Aviso enviado por WhatsApp.'
    return False, f'No se pudo enviar por WhatsApp ({estado}): {detalle}'


# Datos del reporte que puede ver el visitante.
def vista_publica(r):
    return {'codigo': r['codigo'], 'objeto_nombre': r['objeto_nombre'], 'categoria': r['categoria'], 'estado': r['estado'],
            'fecha_perdida': r['fecha_perdida'], 'fecha_registro': r['fecha_registro'],
            'fecha_actualizacion': r['fecha_actualizacion'], 'nombre': r['nombre'].split()[0],
            'retiro': r['objeto_ubicacion'] if r['estado'] == 'Localizado' and r['objeto_id'] else None}


# Seguimiento con el enlace privado.
def seguimiento(token):
    if not token or len(token) > 100:
        return None
    reporte = visitantes.buscar_por_token(hash_token(token))
    return vista_publica(reporte) if reporte else None


# Compara dos teléfonos por sus dígitos.
def mismo_telefono(guardado, escrito):
    a, b = digitos(guardado), digitos(escrito)
    if len(a) < 8 or len(b) < 8:
        return False
    return hmac.compare_digest(a[-8:], b[-8:])   # acepta el número con o sin código de país


# Consulta con código y teléfono.
def consultar(codigo, telefono):
    codigo = limpiar_codigo(codigo, maximo=20)
    if not PATRON_CODIGO.fullmatch(codigo):
        return None
    reporte = visitantes.buscar_por_codigo(codigo)
    return vista_publica(reporte) if reporte and mismo_telefono(reporte['telefono'], telefono) else None


# Cambia el estado y las observaciones de un reporte.
def gestionar(id, estado, observaciones, usuario_id):
    observaciones = texto(observaciones) or None
    if estado not in ESTADOS_REPORTE:
        return False, 'Elige un estado válido.'
    if observaciones and len(observaciones) > LARGO_MAXIMO['observaciones']:
        return False, 'Las observaciones son demasiado largas (máximo 2000 caracteres).'

    # Guarda la gestión.
    def guardar(con):
        r = visitantes.buscar(id, con)
        if not r:
            return False, 'El reporte no existe.'
        if (estado, observaciones) == (r['estado'], r['observaciones']):
            return False, 'No hubo cambios.'
        visitantes.gestionar(con, id, estado, observaciones, r['objeto_id'], usuario_id)
        return True, f'Reporte {r["codigo"]} actualizado.'
    return en_transaccion(guardar)


# Relaciona el reporte con un objeto del catálogo.
def relacionar_objeto(id, objeto_id, usuario_id):
    objeto_id = texto(objeto_id)
    if objeto_id and not objeto_id.isdigit():
        return False, 'Elige un objeto válido.'
    objeto_id = int(objeto_id) if objeto_id else None

    # Guarda la relación.
    def guardar(con):
        r = visitantes.buscar(id, con)
        if not r:
            return False, 'El reporte no existe.'
        if objeto_id == r['objeto_id']:
            return False, 'No hubo cambios.'
        if objeto_id and not objetos.buscar(objeto_id, con=con):
            return False, 'El objeto no existe.'
        visitantes.gestionar(con, id, r['estado'], r['observaciones'], objeto_id, usuario_id)
        return True, f'Reporte relacionado con el objeto #{objeto_id}.' if objeto_id else 'Se quitó la relación con el objeto.'
    return en_transaccion(guardar)


# Palabras de un texto, sin tildes ni signos.
def palabras(texto_libre):
    return {p for p in re.findall(r'\w+', (texto_libre or '').lower()) if len(p) > 3}


# Objetos que podrían ser el del reporte.
def posibles_coincidencias(reporte, limite=5):
    buscadas = palabras(f"{reporte['objeto_nombre']} {reporte['descripcion']}")
    candidatos = objetos.candidatos(reporte['categoria'], reporte['fecha_perdida'])

    # Cuántas palabras comparte el objeto con el reporte.
    def puntaje(o):
        return len(buscadas & palabras(f"{o['titulo']} {o['descripcion']} {o['descripcion_publica']}"))
    return sorted(candidatos, key=lambda o: (-puntaje(o), o['fecha'], o['id']))[:limite]


# Enlaces para llamar o escribir al visitante.
def enlaces_contacto(reporte):
    numero = digitos(reporte['telefono'])
    internacional = CODIGO_PAIS + numero if len(numero) == 8 else numero
    saludo = (f"Hola {reporte['nombre'].split()[0]}, te escribimos de objetos perdidos de la UAM por tu reporte "
              f"{reporte['codigo']} ({reporte['objeto_nombre']}).")
    enlaces = {'llamar': f'tel:+{internacional}', 'whatsapp': f'https://wa.me/{internacional}?text={urllib.parse.quote(saludo)}'}
    if reporte['correo']:
        enlaces['correo'] = (f"mailto:{reporte['correo']}?subject={urllib.parse.quote('Tu reporte ' + reporte['codigo'])}"
                             f"&body={urllib.parse.quote(saludo)}")
    return enlaces
