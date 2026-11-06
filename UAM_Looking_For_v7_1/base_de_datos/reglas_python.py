"""Validaciones de UAM Looking For v8.5 que la base de datos no puede hacer sola.

La base revisa QUÉ se guarda (roles de quien firma cada hecho, estados, fechas). Lo que no sabe es QUIÉN
ESTÁ CONECTADO: eso lo revisa este módulo antes de cada operación. También calcula los hashes de las
contraseñas. Solo usa la biblioteca estándar de Python (hashlib, hmac, secrets): no se instala nada.
"""
import hashlib
import hmac
import secrets

# ---------- Contraseñas ----------
# Formato auto-descriptivo «algoritmo$iteraciones$sal$hash». Como el algoritmo va dentro del texto, se puede
# cambiar en el futuro (por ejemplo a más iteraciones o a otro algoritmo) sin tocar la tabla: al iniciar sesión,
# si el hash es de un esquema viejo, se vuelve a calcular con el actual.
ALGORITMO, ITERACIONES = 'pbkdf2_sha256', 600_000


def hash_contrasena(clave, iteraciones=ITERACIONES):
    sal = secrets.token_hex(16)
    calculado = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal.encode('ascii'), iteraciones).hex()
    return f'{ALGORITMO}${iteraciones}${sal}${calculado}'


def verificar_contrasena(clave, guardado):
    try:
        algoritmo, iteraciones, sal, esperado = guardado.split('$')
    except (AttributeError, ValueError):
        return False
    if algoritmo != 'pbkdf2_sha256':
        return False   # aquí se agregarían otros algoritmos si se adoptan (por ejemplo, argon2)
    calculado = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal.encode('ascii'), int(iteraciones)).hex()
    return hmac.compare_digest(calculado, esperado)   # compara sin filtrar tiempos


def necesita_rehash(guardado):
    algoritmo, iteraciones = (guardado.split('$') + ['', ''])[:2]
    return algoritmo != ALGORITMO or not iteraciones.isdigit() or int(iteraciones) < ITERACIONES


# ---------- Permisos según quién está conectado ----------
PERSONAL = ('Administrador', 'Encargado')

# operación -> regla sobre el usuario conectado (y, si hace falta, el registro sobre el que actúa)
PERMISOS = {
    'registrar_objeto':      lambda u, x=None: u['rol'] in PERSONAL,
    'cambiar_estado_manual': lambda u, x=None: u['rol'] in PERSONAL,
    'registrar_entrega':     lambda u, x=None: u['rol'] in PERSONAL,
    'resolver_reclamacion':  lambda u, x=None: u['rol'] in PERSONAL,
    'registrar_devolucion':  lambda u, x=None: u['rol'] in PERSONAL,
    'completar_devolucion':  lambda u, x=None: u['rol'] in PERSONAL,
    'presentar_reclamacion': lambda u, x=None: u['contrasena_hash'] is not None,
    # solo el autor cancela su propia reclamación (la base no sabe quién pulsó el botón)
    'cancelar_reclamacion':  lambda u, r=None: r is not None and r['usuario_id'] == u['id'],
    # v8.5: reportar como visitante no necesita cuenta (no pasa por aquí); gestionar el reporte es del personal
    'gestionar_reporte_visitante': lambda u, x=None: u['rol'] in PERSONAL,
}


def puede(usuario, operacion, registro=None):
    """True si el usuario conectado puede hacer la operación. El usuario debe estar activo."""
    return bool(usuario) and usuario['activo'] == 1 and PERMISOS[operacion](usuario, registro)
