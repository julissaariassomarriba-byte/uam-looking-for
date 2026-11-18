# Contraseñas, tokens y comparaciones seguras.
import hashlib
import hmac
import secrets

ALGORITMO, ITERACIONES = 'pbkdf2_sha256', 600_000


# Huella de una contraseña (PBKDF2-SHA256).
def hash_contrasena(clave, iteraciones=ITERACIONES):
    sal = secrets.token_hex(16)
    calculado = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal.encode('ascii'), iteraciones).hex()
    return f'{ALGORITMO}${iteraciones}${sal}${calculado}'


# Comprueba una contraseña contra su huella.
def verificar_contrasena(clave, guardado):
    try:
        algoritmo, iteraciones, sal, esperado = guardado.split('$')
        if algoritmo != ALGORITMO:
            return False
        calculado = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal.encode('ascii'), int(iteraciones)).hex()
    except (AttributeError, ValueError):
        return False
    return hmac.compare_digest(calculado, esperado)   # compara sin filtrar tiempos


# Dice si la huella usa menos vueltas de las actuales.
def necesita_rehash(guardado):
    algoritmo, iteraciones = (guardado.split('$') + ['', ''])[:2]
    return algoritmo != ALGORITMO or not iteraciones.isdigit() or int(iteraciones) < ITERACIONES


# Compara dos textos en tiempo constante.
def iguales(a, b):
    return hmac.compare_digest((a or '').encode('utf-8'), (b or '').encode('utf-8'))


# Genera un token al azar.
def nuevo_token(bytes_azar=24):
    return secrets.token_hex(bytes_azar)


# Huella SHA-256 de un token.
def hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


# Solo permite volver a páginas de este sitio.
def ruta_interna(destino):
    destino = destino or ''
    if destino.startswith('/') and not destino.startswith('//') and not any(c in destino for c in '\\\t\r\n'):
        return destino
    return None
