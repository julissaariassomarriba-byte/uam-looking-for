# Validaciones de los datos de los formularios.
import datetime
import re
import unicodedata

from .config import LARGO_MAXIMO, MESES

PATRON_CORREO = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')
PATRON_CIF = re.compile(r'[A-Z0-9]{4,20}')
PATRON_HORA = re.compile(r'([01]\d|2[0-3]):[0-5]\d')
MINIMO_DIGITOS_TELEFONO = 8


# Texto sin espacios de más.
def texto(valor):
    return (valor or '').strip()


# CIF en mayúsculas y sin guiones ni espacios.
def limpiar_cif(cif):
    return re.sub(r'[\s-]', '', texto(cif)).upper()


# Dice si el CIF tiene un formato válido.
def cif_valido(cif):
    return bool(PATRON_CIF.fullmatch(cif or ''))


# Dice si el correo tiene un formato válido.
def correo_valido(correo):
    return bool(PATRON_CORREO.fullmatch(correo or '')) and len(correo) <= LARGO_MAXIMO['correo']


# Deja solo los dígitos.
def digitos(valor):
    return re.sub(r'\D', '', valor or '')


# Dice si el teléfono tiene al menos 8 dígitos.
def telefono_valido(telefono):
    return len(digitos(telefono)) >= MINIMO_DIGITOS_TELEFONO and len(texto(telefono)) <= LARGO_MAXIMO['telefono']


# Dice si es una fecha real (AAAA-MM-DD).
def fecha_valida(valor):
    try:
        return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', valor or '')) and bool(datetime.date.fromisoformat(valor))
    except ValueError:
        return False


# Dice si es una hora real (HH:MM).
def hora_valida(valor):
    return bool(PATRON_HORA.fullmatch(valor or ''))


# Dice si un texto pasa del largo máximo.
def muy_largo(valor, campo):
    return len(valor or '') > LARGO_MAXIMO[campo]


# Mensaje de «demasiado largo».
def mensaje_largo(campo, etiqueta):
    return f'{etiqueta} es demasiado largo (máximo {LARGO_MAXIMO[campo]} caracteres).'


# Primer error de una lista de revisiones.
def primer_error(revisiones):
    return next((mensaje for falla, mensaje in revisiones if falla), None)


# ---------- Comparación de nombres (validación cruzada de identidad) ----------

# Palabras de un nombre, sin tildes ni mayúsculas.
def palabras_nombre(nombre):
    sin_tildes = ''.join(c for c in unicodedata.normalize('NFKD', nombre or '') if not unicodedata.combining(c))
    return re.findall(r'[a-zñ]+', sin_tildes.casefold())


# Dice si el nombre escrito es el de la persona registrada.
def mismo_nombre(escrito, registrado):
    escritas, registradas = palabras_nombre(escrito), palabras_nombre(registrado)
    if not escritas or not registradas:
        return False
    return len(escritas) >= min(2, len(registradas)) and all(p in registradas for p in escritas)


# Mes en texto: «2026-10» -> «Octubre 2026».
def mes_legible(periodo):
    try:
        anio, mes = periodo.split('-')[:2]
        return f'{MESES[int(mes) - 1].capitalize()} {anio}'
    except (AttributeError, ValueError, IndexError):
        return 'Sin fecha'
