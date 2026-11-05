"""Reglas del sistema. Las funciones que cambian datos devuelven (True, resultado) o (False, mensaje de error).

Python revisa lo que depende de quién está conectado y da mensajes claros; la base (schema.sql) vuelve a revisar
cada regla con CHECK y triggers, así que aunque alguien se salte la app no se guarda nada incoherente.
"""
import hashlib
import hmac
import secrets
import sqlite3

import base_datos as bd
import imagenes
from config import CATEGORIAS, ESTADOS_MANUALES, MESES, ROL_ADMIN, ROLES_GESTIONABLES, TIPOS_PERSONA, UBICACIONES


def texto(valor):
    return (valor or '').strip()


def limpiar_cif(cif):
    return texto(cif).replace('-', '').replace(' ', '').upper()


# '2026-10' -> 'Octubre 2026' (lo que ve el estudiante en lugar de la fecha exacta)
def mes_legible(periodo):
    try:
        anio, mes = periodo.split('-')[:2]
        return f'{MESES[int(mes) - 1].capitalize()} {anio}'
    except (AttributeError, ValueError, IndexError):
        return 'Sin fecha'


# Ejecuta una operación en una transacción. Si la base la rechaza, se deshace todo y se muestra el motivo:
# los triggers ya traen el mensaje en español; un CHECK solo dice qué columna falló.
def en_transaccion(operacion):
    try:
        with bd.conectar() as con:
            return operacion(con)
    except sqlite3.IntegrityError as error:
        motivo = str(error)
        return False, ('La base de datos rechazó los datos: revisa el formulario.' if 'constraint failed' in motivo else motivo)


# Contraseñas: PBKDF2 de la biblioteca estándar (hashlib). Formato «algoritmo$iteraciones$sal$hash», así el
# algoritmo se puede cambiar después sin tocar la tabla: al iniciar sesión, un hash viejo se vuelve a calcular.

ALGORITMO, ITERACIONES = 'pbkdf2_sha256', 600_000


def hash_contrasena(clave, iteraciones=ITERACIONES):
    sal = secrets.token_hex(16)
    calculado = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal.encode('ascii'), iteraciones).hex()
    return f'{ALGORITMO}${iteraciones}${sal}${calculado}'


def verificar_contrasena(clave, guardado):
    try:
        algoritmo, iteraciones, sal, esperado = guardado.split('$')
        calculado = hashlib.pbkdf2_hmac('sha256', clave.encode('utf-8'), sal.encode('ascii'), int(iteraciones)).hex()
    except (AttributeError, ValueError):
        return False
    return algoritmo == ALGORITMO and hmac.compare_digest(calculado, esperado)   # compara sin filtrar tiempos


def necesita_rehash(guardado):
    algoritmo, iteraciones = (guardado.split('$') + ['', ''])[:2]
    return algoritmo != ALGORITMO or not iteraciones.isdigit() or int(iteraciones) < ITERACIONES


# Administrador definido en el .env

def admin_configurado(env):
    return bool(env.get('ADMIN_USUARIO') and env.get('ADMIN_CONTRASENA'))


def es_admin_del_env(usuario, env):
    return admin_configurado(env) and usuario['cif'] == limpiar_cif(env['ADMIN_USUARIO'])


def validar_admin(usuario, contrasena, env):
    return (admin_configurado(env) and limpiar_cif(usuario) == limpiar_cif(env['ADMIN_USUARIO'])
            and hmac.compare_digest(contrasena.encode('utf-8'), env['ADMIN_CONTRASENA'].encode('utf-8')))


# Guarda al administrador en usuarios (sin hash) para que su nombre salga en el historial.
def sincronizar_admin(env):
    if admin_configurado(env):
        cif = limpiar_cif(env['ADMIN_USUARIO'])
        return bd.guardar_admin(env.get('ADMIN_NOMBRE') or 'Administrador', cif,
                                (env.get('ADMIN_CORREO') or f'{cif.lower()}@admin.local').lower())


# Cuentas de estudiantes y encargados

def validar_login(cif, contrasena):
    usuario = bd.buscar_cuenta(limpiar_cif(cif))
    if not usuario or not verificar_contrasena(contrasena or '', usuario['contrasena_hash']):
        return None
    if necesita_rehash(usuario['contrasena_hash']):
        bd.cambiar_hash(usuario['id'], hash_contrasena(contrasena))
    return usuario


# Crea (id=None) o edita una cuenta. Al editar, la contraseña es opcional.
# Si el CIF ya está registrado como persona de ventanilla (sin cuenta), la cuenta se crea sobre esa misma fila.
def guardar_usuario(nombre, cif, correo, carrera, rol, contrasena, id=None):
    nueva = id is None
    previa = bd.buscar_por_cif(limpiar_cif(cif)) if nueva else None
    if previa and not previa['contrasena_hash'] and previa['rol'] != ROL_ADMIN:
        id = previa['id']
    elif not nueva:
        usuario = bd.buscar_usuario(id)
        if not usuario or usuario['rol'] not in ROLES_GESTIONABLES:
            return False, 'Esta cuenta no se puede editar desde el panel.'
    for hay_error, mensaje in [(not texto(nombre), 'El nombre es obligatorio.'), (len(limpiar_cif(cif)) < 4, 'El CIF ingresado no es válido.'),
                               ('@' not in texto(correo), 'El correo no es válido.'), (rol not in ROLES_GESTIONABLES, 'Rol no permitido.'),
                               ((nueva or contrasena) and len(contrasena or '') < 6, 'La contraseña debe tener al menos 6 caracteres.')]:
        if hay_error:
            return False, mensaje
    try:
        return True, bd.guardar_usuario(texto(nombre), limpiar_cif(cif), texto(correo).lower(), texto(carrera) or None, rol,
                                        hash_contrasena(contrasena) if contrasena else None, id)
    except sqlite3.IntegrityError as error:
        return False, ('El correo o CIF ya pertenece a otra cuenta.' if 'UNIQUE' in str(error) else 'El correo no es válido.')


# Registro público: un estudiante crea su propia cuenta y siempre recibe el rol Estudiante.
# Si ya vino a ventanilla como estudiante (sin cuenta), la cuenta se crea sobre esa misma fila.
def registrar_estudiante(nombre, cif, correo, contrasena, confirmar):
    if contrasena != confirmar:
        return False, 'Las contraseñas no coinciden.'
    previa = bd.buscar_por_cif(limpiar_cif(cif))
    if previa and (previa['contrasena_hash'] or previa['rol'] != 'Estudiante'):
        return False, 'Este CIF ya está registrado. Si es tuyo, comunícate con la oficina de Vida Estudiantil.'
    return guardar_usuario(nombre, cif, correo, None, 'Estudiante', contrasena)


def cambiar_activo(id, activo):
    usuario = bd.buscar_usuario(id)
    if not usuario or usuario['rol'] not in ROLES_GESTIONABLES:
        return False, 'Esta cuenta no se puede modificar desde el panel.'
    bd.cambiar_activo(id, activo)
    return True, 'Cuenta reactivada.' if activo else 'Cuenta desactivada. Ya no podrá iniciar sesión.'


# Registro y estado de los objetos

# Datos de quien trae el objeto. Si ya está registrado (con o sin cuenta), basta con su CIF.
# Devuelve (True, None) si lo encontró el personal, (True, datos) o (False, mensaje).
def datos_reportante(f):
    if f.get('sin_persona') == '1':
        return True, None
    nombre, cif, tipo = texto(f.get('persona_nombre')), limpiar_cif(f.get('persona_cif')) or None, f.get('persona_tipo')
    conocida = bd.buscar_por_cif(cif) if cif else None
    if conocida:
        nombre = nombre or conocida['nombre']
        tipo = tipo or (conocida['rol'] if conocida['rol'] in TIPOS_PERSONA else None)
    if len(nombre) < 3:
        return False, 'Escribe el nombre de quien entrega el objeto (o marca «Lo encontró el personal»).'
    if tipo not in TIPOS_PERSONA:
        return False, 'Elige si quien lo entrega es estudiante, docente, personal administrativo o visitante.'
    return True, (nombre, tipo, cif, texto(f.get('persona_telefono')) or None, texto(f.get('persona_correo')).lower() or None)


# Recepción de un objeto: quién lo trae, el objeto, su foto y dónde queda guardado, en una sola transacción.
# El «Registro» del historial lo escribe la base.
def registrar_objeto(datos, archivo, usuario_id):
    if any(not texto(datos.get(campo)) for campo in ('titulo', 'descripcion', 'categoria', 'fecha', 'lugar_encontrado')):
        return False, 'Completa todos los campos obligatorios.'
    if datos.get('ubicacion') not in UBICACIONES:
        return False, 'Elige dónde quedará guardado el objeto.'
    if datos['fecha'] > bd.ahora()[:10]:
        return False, 'La fecha del hallazgo no puede ser futura.'
    ok, persona = datos_reportante(datos)
    if not ok:
        return False, persona
    ok, foto = imagenes.revisar(archivo)
    if not ok:
        return False, foto

    def guardar(con):
        reportado = bd.guardar_persona(con, *persona) if persona else None
        return True, bd.insertar_objeto(con, {
            'titulo': texto(datos['titulo']), 'descripcion': texto(datos['descripcion']),
            'descripcion_publica': texto(datos.get('descripcion_publica')) or None,
            'categoria': datos['categoria'] if datos['categoria'] in CATEGORIAS else 'Otros',
            'lugar_encontrado': texto(datos['lugar_encontrado']), 'ubicacion': datos['ubicacion'],
            'fecha': datos['fecha'], 'hora': texto(datos.get('hora'))[:5] or None,
            'estado': datos.get('estado') if datos.get('estado') in ESTADOS_MANUALES else 'Activo', 'registrado_por': usuario_id,
            'reportado_por': None if reportado == usuario_id else reportado,   # si lo trajo quien lo registra, lo encontró el personal
            'foto': foto, 'foto_publica': int(bool(foto) and datos.get('foto_publica') == '1')})
    return en_transaccion(guardar)


def cambiar_ubicacion(id, ubicacion, usuario_id):
    def guardar(con):
        objeto = bd.buscar_objeto(id, con=con)
        if not objeto or ubicacion not in UBICACIONES:
            return False, 'Elige una ubicación válida.'
        if ubicacion == objeto['ubicacion']:
            return False, 'La ubicación no cambió.'
        bd.actualizar_objeto(con, id, 'ubicacion', ubicacion)
        bd.anotar(con, id, 'Cambio de ubicación', usuario_id)
        return True, 'Ubicación actualizada.'
    return en_transaccion(guardar)


# Sube o reemplaza la foto de un objeto (la nueva ocupa el lugar de la anterior) y decide si la ven los estudiantes.
def actualizar_foto(id, archivo, publica, usuario_id):
    ok, foto = imagenes.revisar(archivo)
    if not ok:
        return False, foto

    def guardar(con):
        objeto = bd.buscar_objeto(id, con=con)
        if not objeto:
            return False, 'El objeto no existe.'
        if not foto and not objeto['tiene_foto']:
            return False, 'Elige una foto.'
        if not foto and int(publica) == objeto['foto_publica']:
            return False, 'La foto no cambió.'
        if foto:
            bd.actualizar_objeto(con, id, 'foto', foto)
        bd.actualizar_objeto(con, id, 'foto_publica', int(publica))
        bd.anotar(con, id, 'Foto', usuario_id)
        return True, 'Foto guardada.' if foto else 'Visibilidad de la foto actualizada.'
    return en_transaccion(guardar)


# Cambio hecho a mano por el encargado, solo mientras el objeto está bajo custodia.
# Después de la entrega, el estado lo pone la base según los hechos (entrega, reclamación, devolución).
def cambiar_estado_manual(id, nuevo_estado, usuario_id):
    def guardar(con):
        objeto = bd.buscar_objeto(id, con=con)
        if not objeto:
            return False, 'El objeto no existe.'
        if objeto['estado'] not in ESTADOS_MANUALES:
            return False, f'Un objeto «{objeto["estado"]}» cambia de estado solo con la entrega, la reclamación o la devolución.'
        if nuevo_estado not in ESTADOS_MANUALES:
            return False, 'Para marcarlo como entregado, registra la entrega con los datos de quien lo retira.'
        if nuevo_estado == objeto['estado']:
            return False, 'El estado no cambió.'
        bd.actualizar_objeto(con, id, 'estado', nuevo_estado)
        bd.anotar(con, id, 'Cambio de estado', usuario_id, nuevo_estado)
        return True, 'Estado actualizado.'
    return en_transaccion(guardar)


def actualizar_descripcion_publica(id, nueva, usuario_id):
    nueva = texto(nueva) or None

    def guardar(con):
        objeto = bd.buscar_objeto(id, con=con)
        if objeto and nueva != objeto['descripcion_publica']:
            bd.actualizar_objeto(con, id, 'descripcion_publica', nueva)
            bd.anotar(con, id, 'Descripción pública', usuario_id)
        return True, 'Descripción pública actualizada.'
    return en_transaccion(guardar)


# Entrega inicial: registra quién retira. La base pasa el objeto a «Entregado» y lo anota.

def registrar_entrega(objeto_id, nombre, tipo, cif, telefono, senas, confirmado, encargado_id):
    nombre, cif = texto(nombre), limpiar_cif(cif)
    errores = [(len(nombre) < 3, 'Escribe el nombre completo de quien retira el objeto.'),
               (tipo not in TIPOS_PERSONA, 'Elige si quien lo retira es estudiante, docente, administrativo o visitante.'),
               (len(cif) < 4, 'Escribe el CIF (o cédula) de quien retira el objeto.'),
               (sum(c.isdigit() for c in telefono or '') < 8, 'Escribe un número de teléfono válido (al menos 8 dígitos).'),
               (len(texto(senas)) < 10, 'Anota las señas que dio la persona para comprobar que el objeto es suyo.'),
               (not confirmado, 'Confirma que revisaste el carné y que las señas coinciden con el registro.')]

    def guardar(con):
        objeto = bd.buscar_objeto(objeto_id, con=con)
        if not objeto:
            return False, 'El objeto no existe.'
        if objeto['estado'] not in ESTADOS_MANUALES:
            return False, 'Este objeto ya fue entregado.'
        for hay_error, mensaje in errores:
            if hay_error:
                return False, mensaje
        retirado_por = bd.guardar_persona(con, nombre, tipo, cif, texto(telefono), None)
        bd.insertar_entrega(con, objeto_id, retirado_por, texto(senas), encargado_id)
        return True, 'Entrega registrada. El objeto pasó a «Entregado».'
    return en_transaccion(guardar)


# Reclamaciones: Pendiente -> Aceptada (el objeto pasa a «Por recuperar») o Rechazada; el dueño puede cancelarla.

def crear_reclamacion(objeto_id, usuario, descripcion, lugar_perdida, fecha_perdida, telefono):
    entrega = bd.buscar_entrega(objeto_id)
    objeto = bd.buscar_objeto(objeto_id)
    if not entrega or objeto['estado'] != 'Entregado':
        return False, 'Solo se pueden reclamar objetos que ya fueron entregados a otra persona.'
    if usuario['id'] == entrega['retirado_por']:
        return False, 'Tú retiraste este objeto; no puedes reclamarlo.'
    if len(texto(descripcion)) < 15:
        return False, 'Describe el objeto con más detalle (al menos 15 caracteres) para comprobar que era tuyo.'
    if fecha_perdida and fecha_perdida > bd.ahora()[:10]:
        return False, 'La fecha en que lo perdiste no puede ser futura.'
    if bd.listar_reclamaciones('Pendiente', objeto_id, usuario['id']):   # la base también lo impide (índice único)
        return False, 'Ya tienes una reclamación pendiente para este objeto.'

    def guardar(con):
        bd.insertar_reclamacion(con, entrega['id'], usuario['id'], texto(descripcion), texto(lugar_perdida) or None,
                                fecha_perdida or None)
        if texto(telefono):   # el teléfono se guarda en su cuenta, no en cada reclamación
            bd.actualizar_telefono(con, usuario['id'], texto(telefono))
        return True, 'Solicitud enviada. Verás la respuesta del encargado en «Mis reclamaciones».'
    return en_transaccion(guardar)


def gestionar_reclamacion(id, accion, nota, encargado_id):
    nota = texto(nota) or None

    def guardar(con):
        r = bd.buscar_reclamacion(id, con)
        if not r:
            return False, 'La reclamación no existe.'
        if r['estado'] != 'Pendiente' or accion not in ('aceptar', 'rechazar'):
            return False, 'Esta reclamación ya fue resuelta.'
        if accion == 'rechazar':
            if not nota:
                return False, 'Escribe el motivo del rechazo para informar al estudiante.'
            bd.cerrar_reclamacion(con, id, 'Rechazada', nota, encargado_id)
            return True, f'Reclamación #{id} rechazada.'
        # Aceptar: las demás pendientes de la misma entrega se rechazan con su motivo (solo una puede aceptarse).
        for otra in bd.pendientes_de_entrega(con, r['entrega_id']):
            if otra != id:
                bd.cerrar_reclamacion(con, otra, 'Rechazada', 'Otra persona comprobó que el objeto era suyo.', encargado_id)
        bd.cerrar_reclamacion(con, id, 'Aceptada', nota, encargado_id)
        return True, (f'Reclamación #{id} aceptada. Contacta a {r["retiro_nombre"]} (tel. {r["retiro_telefono"]}) para recuperar '
                      f'el objeto y regístralo como recuperado; después devuélveselo a {r["usuario_nombre"]}.')
    return en_transaccion(guardar)


# El dueño cancela su propia reclamación mientras está pendiente (la base anota la cancelación a su nombre).
def cancelar_reclamacion(id, usuario_id):
    def guardar(con):
        r = bd.buscar_reclamacion(id, con)
        if not r or r['usuario_id'] != usuario_id or r['estado'] != 'Pendiente':
            return False, 'Solo puedes cancelar tus solicitudes pendientes.'
        bd.cerrar_reclamacion(con, id, 'Cancelada', None, None)
        return True, f'Solicitud #{id} cancelada.'
    return en_transaccion(guardar)


# Devolución en dos momentos (tabla devoluciones). La base pone el estado y lo anota en el historial.

# Momento 1: el encargado recibe el objeto de quien se lo llevó -> «Recuperado».
def registrar_recuperacion(objeto_id, observaciones, encargado_id):
    def guardar(con):
        r = bd.reclamacion_aceptada(objeto_id, con)
        if not r or r['objeto_estado'] != 'Por recuperar':
            return False, 'Este objeto no está pendiente de recuperar.'
        bd.insertar_devolucion(con, r['id'], encargado_id, texto(observaciones) or None)
        return True, f'Objeto recuperado. Ya puedes devolvérselo a {r["usuario_nombre"]}.'
    return en_transaccion(guardar)


# Momento 2: el encargado se lo entrega a su dueño, después de revisar su carné -> «Devuelto».
def devolver_al_dueno(objeto_id, confirmado, observaciones, encargado_id):
    def guardar(con):
        r = bd.reclamacion_aceptada(objeto_id, con)
        if not r or r['objeto_estado'] != 'Recuperado':
            return False, 'Este objeto no está listo para devolverse.'
        if not confirmado:
            return False, f'Confirma que revisaste el carné de {r["usuario_nombre"]} antes de devolverle el objeto.'
        bd.completar_devolucion(con, r['devolucion_id'], encargado_id, texto(observaciones) or None)
        return True, f'Objeto devuelto a {r["usuario_nombre"]}.'
    return en_transaccion(guardar)
