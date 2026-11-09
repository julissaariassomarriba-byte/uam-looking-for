"""Seguridad sin librerías externas: contraseñas, tokens y comparación segura.

Contraseñas: PBKDF2-SHA256 de la biblioteca estándar (hashlib) con formato «algoritmo$iteraciones$sal$hash».
Como el algoritmo va dentro del texto, se puede subir el costo después sin tocar la tabla: al iniciar sesión,
un hash con menos iteraciones se vuelve a calcular.
"""
import hashlib
import hmac
import secrets

ALGORITMO, ITERACIONES = 'pbkdf2_sha256', 600_000


def hash_contrasena(clave, iteraciones=ITERACIONES):
    sal = secrets.token_hex(16)
    calculado = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal.encode('ascii'), iteraciones).hex()
    return f'{ALGORITMO}${iteraciones}${sal}${calculado}'


def verificar_contrasena(clave, guardado):
    try:
        algoritmo, iteraciones, sal, esperado = guardado.split('$')
        if algoritmo != ALGORITMO:
            return False
        calculado = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal.encode('ascii'), int(iteraciones)).hex()
    except (AttributeError, ValueError):
        return False
    return hmac.compare_digest(calculado, esperado)   # compara sin filtrar tiempos


def necesita_rehash(guardado):
    algoritmo, iteraciones = (guardado.split('$') + ['', ''])[:2]
    return algoritmo != ALGORITMO or not iteraciones.isdigit() or int(iteraciones) < ITERACIONES


def iguales(a, b):
    """Compara dos textos en tiempo constante (en bytes, para aceptar cualquier carácter)."""
    return hmac.compare_digest((a or '').encode('utf-8'), (b or '').encode('utf-8'))


def nuevo_token(bytes_azar=24):
    return secrets.token_hex(bytes_azar)


def hash_token(token):
    """El enlace privado del visitante solo se guarda así: quien lea la base no puede abrir reportes ajenos."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def ruta_interna(destino):
    """Solo se vuelve a páginas de este sitio: «//otro» y «/\\otro» llevarían a otra página, y los navegadores
    ignoran tabuladores y saltos de línea dentro de una dirección."""
    destino = destino or ''
    if destino.startswith('/') and not destino.startswith('//') and not any(c in destino for c in '\\\t\r\n'):
        return destino
    return None
