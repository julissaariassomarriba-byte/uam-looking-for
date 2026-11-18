# Identifica a la persona por su CIF (validación cruzada).
from ..config import ROL_ESTUDIANTE, TIPOS_PERSONA
from ..datos import usuarios
from ..validacion import (cif_valido, correo_valido, limpiar_cif, mismo_nombre, muy_largo, primer_error, telefono_valido,
                          texto)


# Dice si la persona tiene cuenta.
def es_cuenta(fila):
    return bool(fila['contrasena_hash']) or fila['rol'] == 'Administrador'


# Mensaje si el nombre no coincide con el del CIF.
def conflicto_de_identidad(fila, nombre, tipo):
    if nombre and not mismo_nombre(nombre, fila['nombre']):
        return (f'El CIF {fila["cif"]} ya está registrado a nombre de {fila["nombre"]}. Revisa el carné: '
                f'si es otra persona, corrige el CIF; si es la misma, escribe su nombre como está registrado.')
    if es_cuenta(fila) and fila['rol'] == ROL_ESTUDIANTE and tipo and tipo != ROL_ESTUDIANTE:
        return f'El CIF {fila["cif"]} pertenece a un estudiante con cuenta: no se puede registrar como {tipo.lower()}.'
    return None


# Busca o registra a la persona y devuelve su id.
def resolver(con, nombre, tipo, cif, telefono, correo, papel='quien entrega el objeto'):
    nombre, cif, telefono = texto(nombre), limpiar_cif(cif) or None, texto(telefono) or None
    correo = texto(correo).lower() or None
    error = primer_error([
        (cif is not None and not cif_valido(cif), 'El CIF o cédula solo puede tener letras y números (de 4 a 20).'),
        (muy_largo(nombre, 'nombre'), 'El nombre es demasiado largo (máximo 100 caracteres).'),
        (telefono is not None and not telefono_valido(telefono), 'Escribe un número de teléfono válido (al menos 8 dígitos).'),
        (correo is not None and not correo_valido(correo), 'El correo no es válido (o déjalo vacío).'),
    ])
    if error:
        return False, error

    registrada = usuarios.buscar_por_cif(cif, con) if cif else None
    if registrada:
        error = conflicto_de_identidad(registrada, nombre, tipo)
    else:
        error = primer_error([
            (len(nombre) < 3, f'Escribe el nombre completo de {papel}.'),
            (tipo not in TIPOS_PERSONA, f'Elige si {papel} es estudiante, docente, personal administrativo o visitante.'),
        ])
    if not error and correo:
        dueno = usuarios.buscar_por_correo(correo, con)
        if dueno and (not registrada or dueno['id'] != registrada['id']):
            error = f'El correo {correo} ya pertenece a otra persona registrada. Revísalo o déjalo vacío.'
    if error:
        return False, error

    if registrada:
        cuenta = es_cuenta(registrada)
        usuarios.completar_contacto(con, registrada['id'], telefono, correo, telefono_nuevo=not cuenta)
        if not cuenta and tipo in TIPOS_PERSONA and tipo != registrada['rol']:
            usuarios.actualizar_tipo_persona(con, registrada['id'], tipo)
        return True, registrada['id']

    if not cif:   # sin CIF: se reutiliza la persona con el mismo nombre y teléfono, si ya vino antes
        anterior = usuarios.buscar_persona_sin_cif(nombre, telefono, con)
        if anterior:
            usuarios.completar_contacto(con, anterior['id'], None, correo)
            return True, anterior['id']
    return True, usuarios.insertar_persona(con, nombre, tipo, cif, telefono, correo)
