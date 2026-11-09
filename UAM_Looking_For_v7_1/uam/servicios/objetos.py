"""Recepción de objetos y cambios mientras están bajo custodia (estado, ubicación, foto, descripción pública)."""
from ..config import CATEGORIAS, ESTADOS_MANUALES, UBICACIONES
from ..datos import objetos
from ..datos.conexion import hoy
from ..utilidades import imagenes
from ..validacion import fecha_valida, hora_valida, mensaje_largo, muy_largo, primer_error, texto
from . import en_transaccion, personas


def revisar_objeto(d):
    return primer_error([
        (not d['titulo'], 'Escribe el nombre del objeto.'),
        (muy_largo(d['titulo'], 'titulo'), mensaje_largo('titulo', 'El nombre del objeto')),
        (d['categoria'] not in CATEGORIAS, 'Elige la categoría del objeto.'),
        (not d['descripcion'], 'Escribe la descripción interna del objeto.'),
        (muy_largo(d['descripcion'], 'descripcion'), mensaje_largo('descripcion', 'El texto de la descripción')),
        (muy_largo(d['descripcion_publica'], 'descripcion_publica'), mensaje_largo('descripcion_publica', 'El texto público')),
        (not d['lugar_encontrado'], 'Escribe dónde se encontró el objeto.'),
        (muy_largo(d['lugar_encontrado'], 'lugar'), mensaje_largo('lugar', 'El lugar')),
        (not fecha_valida(d['fecha']), 'Escribe una fecha de hallazgo válida.'),
        (fecha_valida(d['fecha']) and d['fecha'] > hoy(), 'La fecha del hallazgo no puede ser futura.'),
        (d['hora'] is not None and not hora_valida(d['hora']), 'Escribe una hora válida (HH:MM) o déjala vacía.'),
        (d['ubicacion'] not in UBICACIONES, 'Elige dónde quedará guardado el objeto.'),
        (d['estado'] not in ESTADOS_MANUALES, 'Elige un estado inicial válido.'),
    ])


def registrar_objeto(datos, archivo, usuario_id):
    """Recepción: quién lo trae, el objeto, su foto y dónde queda guardado, en una sola transacción.
    El «Registro» del historial lo escribe la base. Devuelve (True, id del objeto) o (False, mensaje)."""
    d = {campo: texto(datos.get(campo)) for campo in ('titulo', 'descripcion', 'lugar_encontrado', 'fecha')}
    d.update(descripcion_publica=texto(datos.get('descripcion_publica')) or None, categoria=datos.get('categoria'),
             ubicacion=datos.get('ubicacion'), estado=datos.get('estado') or 'Activo', hora=texto(datos.get('hora'))[:5] or None)
    error = revisar_objeto(d)
    if error:
        return False, error
    ok, foto = imagenes.revisar(archivo)
    if not ok:
        return False, foto
    sin_persona = datos.get('sin_persona') == '1'

    def guardar(con):
        reportado = None
        if not sin_persona:
            ok, reportado = personas.resolver(con, datos.get('persona_nombre'), datos.get('persona_tipo'), datos.get('persona_cif'),
                                              datos.get('persona_telefono'), datos.get('persona_correo'),
                                              papel='quien entrega el objeto')
            if not ok:
                return False, reportado + ' (O marca «Lo encontró el personal».)' if 'nombre completo' in reportado else reportado
        return True, objetos.insertar(con, dict(
            d, registrado_por=usuario_id, foto=foto, foto_publica=int(bool(foto) and datos.get('foto_publica') == '1'),
            reportado_por=None if reportado == usuario_id else reportado))   # si lo trajo quien lo registra, lo encontró el personal
    return en_transaccion(guardar)


def cambiar_ubicacion(id, ubicacion, usuario_id):
    def guardar(con):
        objeto = objetos.buscar(id, con=con)
        if not objeto:
            return False, 'El objeto no existe.'
        if ubicacion not in UBICACIONES:
            return False, 'Elige una ubicación válida.'
        if ubicacion == objeto['ubicacion']:
            return False, 'La ubicación no cambió.'
        objetos.actualizar(con, id, 'ubicacion', ubicacion)
        objetos.anotar(con, id, 'Cambio de ubicación', usuario_id)
        return True, 'Ubicación actualizada.'
    return en_transaccion(guardar)


def actualizar_foto(id, archivo, publica, usuario_id):
    """Sube o reemplaza la foto (la nueva ocupa el lugar de la anterior) y decide si la ven los estudiantes."""
    ok, foto = imagenes.revisar(archivo)
    if not ok:
        return False, foto

    def guardar(con):
        objeto = objetos.buscar(id, con=con)
        if not objeto:
            return False, 'El objeto no existe.'
        if not foto and not objeto['tiene_foto']:
            return False, 'Elige una foto.'
        if not foto and int(publica) == objeto['foto_publica']:
            return False, 'La foto no cambió.'
        if foto:
            objetos.actualizar(con, id, 'foto', foto)
        objetos.actualizar(con, id, 'foto_publica', int(publica))
        objetos.anotar(con, id, 'Foto', usuario_id)
        return True, 'Foto guardada.' if foto else 'Visibilidad de la foto actualizada.'
    return en_transaccion(guardar)


def cambiar_estado_manual(id, nuevo_estado, usuario_id):
    """Cambio hecho a mano, solo mientras el objeto está bajo custodia. Después de la entrega, el estado lo pone la
    base según los hechos (entrega, reclamación, devolución)."""
    def guardar(con):
        objeto = objetos.buscar(id, con=con)
        if not objeto:
            return False, 'El objeto no existe.'
        if objeto['estado'] not in ESTADOS_MANUALES:
            return False, f'Un objeto «{objeto["estado"]}» cambia de estado solo con la entrega, la reclamación o la devolución.'
        if nuevo_estado not in ESTADOS_MANUALES:
            return False, 'Para marcarlo como entregado, registra la entrega con los datos de quien lo retira.'
        if nuevo_estado == objeto['estado']:
            return False, 'El estado no cambió.'
        objetos.actualizar(con, id, 'estado', nuevo_estado)
        objetos.anotar(con, id, 'Cambio de estado', usuario_id, nuevo_estado)
        return True, 'Estado actualizado.'
    return en_transaccion(guardar)


def actualizar_descripcion_publica(id, nueva, usuario_id):
    nueva = texto(nueva) or None
    if muy_largo(nueva, 'descripcion_publica'):
        return False, mensaje_largo('descripcion_publica', 'El texto público')

    def guardar(con):
        objeto = objetos.buscar(id, con=con)
        if not objeto:
            return False, 'El objeto no existe.'
        if nueva == objeto['descripcion_publica']:
            return False, 'La descripción pública no cambió.'
        objetos.actualizar(con, id, 'descripcion_publica', nueva)
        objetos.anotar(con, id, 'Descripción pública', usuario_id)
        return True, 'Descripción pública actualizada.'
    return en_transaccion(guardar)

