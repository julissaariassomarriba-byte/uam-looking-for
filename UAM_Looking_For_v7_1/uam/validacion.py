"""Validación de los datos que escribe la gente. Funciones puras: no tocan la base ni la petición.

Cada servicio arma una lista de (condición_de_error, mensaje) y usa primer_error() para quedarse con el primero,
así el usuario recibe un mensaje claro a la vez y el orden de las revisiones es el del formulario.
"""
import datetime
import re
import unicodedata

from .config import LARGO_MAXIMO, MESES

PATRON_CORREO = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')
PATRON_CIF = re.compile(r'[A-Z0-9]{4,20}')
PATRON_HORA = re.compile(r'([01]\d|2[0-3]):[0-5]\d')
MINIMO_DIGITOS_TELEFONO = 8


def texto(valor):
    return (valor or '').strip()


def limpiar_cif(cif):
    """El CIF o cédula se guarda en mayúsculas y sin guiones ni espacios: «001-010101-0000a» -> «0010101010000A»."""
    return re.sub(r'[\s-]', '', texto(cif)).upper()


def cif_valido(cif):
    return bool(PATRON_CIF.fullmatch(cif or ''))


def correo_valido(correo):
    return bool(PATRON_CORREO.fullmatch(correo or '')) and len(correo) <= LARGO_MAXIMO['correo']


def digitos(valor):
    return re.sub(r'\D', '', valor or '')


def telefono_valido(telefono):
    return len(digitos(telefono)) >= MINIMO_DIGITOS_TELEFONO and len(texto(telefono)) <= LARGO_MAXIMO['telefono']


def fecha_valida(valor):
    """Fecha real en formato AAAA-MM-DD (rechaza 2026-02-30, textos y fechas a medias)."""
    try:
        return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', valor or '')) and bool(datetime.date.fromisoformat(valor))
    except ValueError:
        return False


def hora_valida(valor):
    return bool(PATRON_HORA.fullmatch(valor or ''))


def muy_largo(valor, campo):
    return len(valor or '') > LARGO_MAXIMO[campo]


def mensaje_largo(campo, etiqueta):
    return f'{etiqueta} es demasiado largo (máximo {LARGO_MAXIMO[campo]} caracteres).'


def primer_error(revisiones):
    """Devuelve el mensaje de la primera revisión que falla, o None si todas pasan."""
    return next((mensaje for falla, mensaje in revisiones if falla), None)


# ---------- Comparación de nombres (validación cruzada de identidad) ----------

def palabras_nombre(nombre):
    """«  José   Pérez-López » -> ['jose', 'perez', 'lopez']: sin tildes, sin mayúsculas, sin signos."""
    sin_tildes = ''.join(c for c in unicodedata.normalize('NFKD', nombre or '') if not unicodedata.combining(c))
    return re.findall(r'[a-zñ]+', sin_tildes.casefold())


def mismo_nombre(escrito, registrado):
    """¿El nombre escrito corresponde a la persona registrada con ese CIF?

    Basta con escribir parte del nombre registrado (por ejemplo «María Torres» para «María José Torres López»),
    pero con al menos dos palabras (o la única que tenga el registro) y todas deben estar en el registro.
    Así no pasa un nombre distinto con el CIF de otra persona, y tampoco hace falta escribirlo idéntico.
    """
    escritas, registradas = palabras_nombre(escrito), palabras_nombre(registrado)
    if not escritas or not registradas:
        return False
    return len(escritas) >= min(2, len(registradas)) and all(p in registradas for p in escritas)


def mes_legible(periodo):
    """'2026-10' -> 'Octubre 2026' (lo que ve el estudiante en lugar de la fecha exacta)."""
    try:
        anio, mes = periodo.split('-')[:2]
        return f'{MESES[int(mes) - 1].capitalize()} {anio}'
    except (AttributeError, ValueError, IndexError):
        return 'Sin fecha'
