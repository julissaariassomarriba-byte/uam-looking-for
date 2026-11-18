# Cuentas: administrador, inicio de sesión, registro y perfil.
import sqlite3

from ..config import LARGO_MAXIMO, ROL_ADMIN, ROL_ESTUDIANTE, ROLES_GESTIONABLES
from ..datos import usuarios
from ..seguridad import hash_contrasena, iguales, necesita_rehash, verificar_contrasena
from ..validacion import (cif_valido, correo_valido, limpiar_cif, mismo_nombre, muy_largo, primer_error, telefono_valido,
                          texto)
from .personas import es_cuenta

MINIMO_CONTRASENA = 6
MENSAJE_CIF_OCUPADO = 'Este CIF ya está registrado. Si es tuyo, comunícate con la oficina de Vida Estudiantil.'


# ---------- Administrador definido en el .env ----------

# Dice si el .env tiene usuario y contraseña de administrador.
def admin_configurado(env):
    return bool(env.get('ADMIN_USUARIO') and env.get('ADMIN_CONTRASENA'))


# Dice si ese usuario es el administrador del .env.
def es_admin_del_env(usuario, env):
    return admin_configurado(env) and usuario['cif'] == limpiar_cif(env['ADMIN_USUARIO'])


# Valida el usuario y la contraseña del administrador.
def validar_admin(usuario, contrasena, env):
    return (admin_configurado(env) and limpiar_cif(usuario) == limpiar_cif(env['ADMIN_USUARIO'])
            and iguales(contrasena, env['ADMIN_CONTRASENA']))


# Guarda al administrador del .env y quita a los anteriores.
def sincronizar_admin(env):
    if not admin_configurado(env):
        return None
    cif = limpiar_cif(env['ADMIN_USUARIO'])
    admin_id = usuarios.guardar_admin(env.get('ADMIN_NOMBRE') or 'Administrador', cif,
                                      (env.get('ADMIN_CORREO') or f'{cif.lower()}@admin.local').lower())
    usuarios.quitar_admins_sobrantes(cif)   # v10.1: el único administrador es el del .env
    return admin_id


# ---------- Inicio de sesión ----------

# Valida el CIF y la contraseña al iniciar sesión.
def validar_login(cif, contrasena):
    contrasena = contrasena or ''
    if len(contrasena) > LARGO_MAXIMO['contrasena']:
        return None
    usuario = usuarios.buscar_cuenta(limpiar_cif(cif))
    if not usuario or not verificar_contrasena(contrasena, usuario['contrasena_hash']):
        return None
    if necesita_rehash(usuario['contrasena_hash']):
        usuarios.cambiar_hash(usuario['id'], hash_contrasena(contrasena))
    return usuario


# ---------- Crear y editar cuentas ----------

# Revisa los datos de una cuenta antes de guardarla.
def revisar_datos_cuenta(nombre, cif, correo, carrera, rol, contrasena, contrasena_obligatoria):
    return primer_error([
        (len(nombre) < 3, 'Escribe el nombre completo.'),
        (muy_largo(nombre, 'nombre'), 'El nombre es demasiado largo (máximo 100 caracteres).'),
        (not cif_valido(cif), 'El CIF solo puede tener letras y números (de 4 a 20).'),
        (not correo_valido(correo), 'El correo no es válido.'),
        (muy_largo(carrera, 'carrera'), 'La carrera es demasiado larga (máximo 100 caracteres).'),
        (rol not in ROLES_GESTIONABLES, 'Rol no permitido.'),
        ((contrasena_obligatoria or contrasena) and len(contrasena) < MINIMO_CONTRASENA,
         f'La contraseña debe tener al menos {MINIMO_CONTRASENA} caracteres.'),
        (muy_largo(contrasena, 'contrasena'), 'La contraseña es demasiado larga (máximo 128 caracteres).'),
    ])


# Dice si un dato ya pertenece a otra persona.
def ocupado_por_otro(fila, id_propio):
    return fila is not None and fila['id'] != id_propio


# Crea o edita una cuenta desde el panel.
def guardar_usuario(nombre, cif, correo, carrera, rol, contrasena, id=None):
    nombre, cif, correo = texto(nombre), limpiar_cif(cif), texto(correo).lower()
    carrera, contrasena = texto(carrera) or None, contrasena or ''
    nueva = id is None
    if not nueva:
        actual = usuarios.buscar(id)
        if not actual or actual['rol'] not in ROLES_GESTIONABLES or not actual['contrasena_hash']:
            return False, 'Esta cuenta no se puede editar desde el panel.'
    error = revisar_datos_cuenta(nombre, cif, correo, carrera, rol, contrasena, contrasena_obligatoria=nueva)
    if error:
        return False, error

    con_cif, con_correo = usuarios.buscar_por_cif(cif), usuarios.buscar_por_correo(correo)
    previa = con_cif if nueva and con_cif and not es_cuenta(con_cif) else None
    if previa and not mismo_nombre(nombre, previa['nombre']):
        return False, (f'El CIF {cif} ya está registrado a nombre de {previa["nombre"]} (vino a ventanilla). '
                       'Si es la misma persona, escribe su nombre como está registrado.')
    propio = previa['id'] if previa else id
    if ocupado_por_otro(con_cif, propio):
        return False, f'El CIF {cif} ya pertenece a otra cuenta.'
    if ocupado_por_otro(con_correo, propio):
        return False, f'El correo {correo} ya pertenece a otra persona.'

    hash_nuevo = hash_contrasena(contrasena) if contrasena else None
    try:
        if previa:
            return True, usuarios.activar_cuenta_de_persona(previa['id'], correo, carrera, rol, hash_nuevo)
        if nueva:
            return True, usuarios.insertar_cuenta(nombre, cif, correo, carrera, rol, hash_nuevo)
        return True, usuarios.actualizar_cuenta(id, nombre, cif, correo, carrera, rol, hash_nuevo)
    except sqlite3.IntegrityError:
        return False, 'El correo o el CIF ya pertenece a otra cuenta.'


# Registra a un estudiante.
def registrar_estudiante(nombre, cif, correo, contrasena, confirmar, carrera=None):
    if (contrasena or '') != (confirmar or ''):
        return False, 'Las contraseñas no coinciden.'
    if len(texto(carrera)) < 3:
        return False, 'Escribe tu carrera (forma parte de tu perfil de estudiante).'
    previa = usuarios.buscar_por_cif(limpiar_cif(cif))
    if previa and (es_cuenta(previa) or previa['rol'] != ROL_ESTUDIANTE or not mismo_nombre(nombre, previa['nombre'])):
        return False, MENSAJE_CIF_OCUPADO
    return guardar_usuario(nombre, cif, correo, carrera, ROL_ESTUDIANTE, contrasena)


# Activa o desactiva una cuenta.
def cambiar_activo(id, activo):
    usuario = usuarios.buscar(id)
    if not usuario or usuario['rol'] not in ROLES_GESTIONABLES or not usuario['contrasena_hash']:
        return False, 'Esta cuenta no se puede modificar desde el panel.'
    usuarios.cambiar_activo(id, activo)
    return True, 'Cuenta reactivada.' if activo else 'Cuenta desactivada. Ya no podrá iniciar sesión.'


# Dice si el usuario es administrador.
def es_admin(usuario):
    return usuario is not None and usuario['rol'] == ROL_ADMIN


# ---------- Mi perfil (RF-05) ----------

# Guarda los cambios de «Mi perfil».
def actualizar_perfil(usuario, correo, carrera, telefono):
    if usuario['rol'] == ROL_ADMIN:
        return False, 'Los datos del administrador se cambian en el archivo .env del servidor.'
    correo, carrera, telefono = texto(correo).lower(), texto(carrera), texto(telefono)
    dueno = usuarios.buscar_por_correo(correo) if correo else None
    error = primer_error([
        (not correo_valido(correo), 'Escribe un correo válido.'),
        (muy_largo(correo, 'correo'), 'El correo es demasiado largo (máximo 120 caracteres).'),
        (usuario['rol'] == ROL_ESTUDIANTE and len(carrera) < 3, 'Escribe tu carrera.'),
        (muy_largo(carrera, 'carrera'), 'La carrera es demasiado larga (máximo 100 caracteres).'),
        (bool(telefono) and not telefono_valido(telefono), 'Escribe un número de teléfono válido (al menos 8 dígitos) o déjalo vacío.'),
        (ocupado_por_otro(dueno, usuario['id']), 'Ese correo ya pertenece a otra cuenta.'),
    ])
    if error:
        return False, error
    usuarios.actualizar_perfil(usuario['id'], correo, carrera or None, telefono or None)
    return True, 'Tus datos se guardaron.'


# Cambia la contraseña desde «Mi perfil».
def cambiar_contrasena(usuario, actual, nueva, confirmar):
    if usuario['rol'] == ROL_ADMIN:
        return False, 'La contraseña del administrador se cambia en el archivo .env del servidor.'
    actual, nueva = actual or '', nueva or ''
    error = primer_error([
        (len(actual) > LARGO_MAXIMO['contrasena'] or not verificar_contrasena(actual, usuario['contrasena_hash']),
         'La contraseña actual no es correcta.'),
        (len(nueva) < MINIMO_CONTRASENA, f'La contraseña nueva debe tener al menos {MINIMO_CONTRASENA} caracteres.'),
        (muy_largo(nueva, 'contrasena'), 'La contraseña es demasiado larga (máximo 128 caracteres).'),
        (nueva != (confirmar or ''), 'Las contraseñas nuevas no coinciden.'),
        (nueva == actual, 'La contraseña nueva debe ser distinta de la actual.'),
    ])
    if error:
        return False, error
    usuarios.cambiar_hash(usuario['id'], hash_contrasena(nueva))
    return True, 'Tu contraseña se cambió.'
