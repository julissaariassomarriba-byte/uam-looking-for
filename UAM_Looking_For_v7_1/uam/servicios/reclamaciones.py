"""Entrega inicial, reclamaciones y devolución al dueño.

Recorrido: bajo custodia -> Entregado (alguien lo retira) -> Por recuperar (se acepta la reclamación del dueño)
-> Recuperado (el personal lo recibe de quien se lo llevó) -> Devuelto (se entrega al dueño).
Una reclamación pasa de Pendiente a Aceptada o Rechazada; desde la v9 el estudiante ya no puede cancelarla.
"""
from ..config import ESTADOS_MANUALES
from ..datos import objetos, reclamaciones, usuarios
from ..datos.conexion import hoy
from ..validacion import fecha_valida, limpiar_cif, mensaje_largo, muy_largo, primer_error, telefono_valido, texto
from . import en_transaccion, personas

MINIMO_DESCRIPCION_RECLAMO, MINIMO_SENAS = 15, 10


# ---------- Entrega inicial: registra quién retira. La base pasa el objeto a «Entregado» y lo anota. ----------

def registrar_entrega(objeto_id, nombre, tipo, cif, telefono, senas, confirmado, encargado_id):
    nombre, senas = texto(nombre), texto(senas)
    error = primer_error([
        (len(nombre) < 3, 'Escribe el nombre completo de quien retira el objeto.'),
        (len(limpiar_cif(cif)) < 4, 'Escribe el CIF (o cédula) de quien retira el objeto.'),
        (not telefono_valido(telefono), 'Escribe un número de teléfono válido (al menos 8 dígitos).'),
        (len(senas) < MINIMO_SENAS, 'Anota las señas que dio la persona para comprobar que el objeto es suyo.'),
        (muy_largo(senas, 'senas'), mensaje_largo('senas', 'El texto de las señas')),
        (not confirmado, 'Confirma que revisaste el carné y que las señas coinciden con el registro.'),
    ])

    def guardar(con):
        objeto = objetos.buscar(objeto_id, con=con)
        if not objeto:
            return False, 'El objeto no existe.'
        if objeto['estado'] not in ESTADOS_MANUALES:
            return False, 'Este objeto ya fue entregado.'
        if error:
            return False, error
        ok, retirado_por = personas.resolver(con, nombre, tipo, cif, telefono, None, papel='quien retira el objeto')
        if not ok:
            return False, retirado_por
        reclamaciones.insertar_entrega(con, objeto_id, retirado_por, senas, encargado_id)
        return True, 'Entrega registrada. El objeto pasó a «Entregado».'
    return en_transaccion(guardar)


# ---------- Reclamaciones ----------

def crear_reclamacion(objeto_id, usuario, descripcion, lugar_perdida, fecha_perdida, telefono):
    """Un estudiante reclama un objeto que otra persona ya retiró. El teléfono se guarda en su cuenta."""
    descripcion, lugar_perdida = texto(descripcion), texto(lugar_perdida) or None
    fecha_perdida, telefono = texto(fecha_perdida) or None, texto(telefono) or None
    error = primer_error([
        (len(descripcion) < MINIMO_DESCRIPCION_RECLAMO,
         f'Describe el objeto con más detalle (al menos {MINIMO_DESCRIPCION_RECLAMO} caracteres) para comprobar que era tuyo.'),
        (muy_largo(descripcion, 'descripcion'), mensaje_largo('descripcion', 'El texto de la descripción')),
        (muy_largo(lugar_perdida, 'lugar'), mensaje_largo('lugar', 'El lugar')),
        (fecha_perdida is not None and not fecha_valida(fecha_perdida), 'La fecha en que lo perdiste no es válida.'),
        (fecha_perdida is not None and fecha_valida(fecha_perdida) and fecha_perdida > hoy(),
         'La fecha en que lo perdiste no puede ser futura.'),
        (telefono is not None and not telefono_valido(telefono), 'Escribe un número de teléfono válido (al menos 8 dígitos).'),
    ])

    def guardar(con):
        objeto = objetos.buscar(objeto_id, con=con)
        entrega = reclamaciones.buscar_entrega(objeto_id, con)
        if not objeto or not entrega or objeto['estado'] != 'Entregado':
            return False, 'Solo se pueden reclamar objetos que ya fueron entregados a otra persona.'
        if usuario['id'] == entrega['retirado_por']:
            return False, 'Tú retiraste este objeto; no puedes reclamarlo.'
        if error:
            return False, error
        if reclamaciones.listar('Pendiente', objeto_id, usuario['id'], con=con):   # la base también lo impide (índice único)
            return False, 'Ya tienes una reclamación pendiente para este objeto.'
        reclamaciones.insertar(con, entrega['id'], usuario['id'], descripcion, lugar_perdida, fecha_perdida)
        if telefono:
            usuarios.actualizar_telefono(con, usuario['id'], telefono)
        return True, 'Solicitud enviada. Verás la respuesta del encargado en «Mis reclamaciones».'
    return en_transaccion(guardar)


def gestionar_reclamacion(id, accion, nota, encargado_id):
    """Aceptar o rechazar (con motivo). Al aceptar, las demás pendientes del mismo objeto se rechazan."""
    nota = texto(nota) or None
    if muy_largo(nota, 'nota'):
        return False, mensaje_largo('nota', 'El texto de la nota')

    def guardar(con):
        r = reclamaciones.buscar(id, con)
        if not r:
            return False, 'La reclamación no existe.'
        if r['estado'] != 'Pendiente':
            return False, 'Esta reclamación ya fue resuelta.'
        if accion not in ('aceptar', 'rechazar'):
            return False, 'Acción no válida.'
        if accion == 'rechazar':
            if not nota:
                return False, 'Escribe el motivo del rechazo para informar al estudiante.'
            reclamaciones.resolver(con, id, 'Rechazada', nota, encargado_id)
            return True, f'Reclamación #{id} rechazada.'
        for otra in reclamaciones.pendientes_de_entrega(con, r['entrega_id']):
            if otra != id:
                reclamaciones.resolver(con, otra, 'Rechazada', 'Otra persona comprobó que el objeto era suyo.', encargado_id)
        reclamaciones.resolver(con, id, 'Aceptada', nota, encargado_id)
        return True, (f'Reclamación #{id} aceptada. Contacta a {r["retiro_nombre"]} (tel. {r["retiro_telefono"]}) para recuperar '
                      f'el objeto y regístralo como recuperado; después devuélveselo a {r["usuario_nombre"]}.')
    return en_transaccion(guardar)


# ---------- Devolución en dos momentos. La base pone el estado y lo anota en el historial. ----------

def registrar_recuperacion(objeto_id, observaciones, encargado_id):
    """Momento 1: el encargado recibe el objeto de quien se lo llevó -> «Recuperado»."""
    observaciones = texto(observaciones) or None
    if muy_largo(observaciones, 'observaciones'):
        return False, mensaje_largo('observaciones', 'El texto de las observaciones')

    def guardar(con):
        r = reclamaciones.aceptada_de_objeto(objeto_id, con)
        if not r or r['objeto_estado'] != 'Por recuperar':
            return False, 'Este objeto no está pendiente de recuperar.'
        reclamaciones.insertar_devolucion(con, r['id'], encargado_id, observaciones)
        return True, f'Objeto recuperado. Ya puedes devolvérselo a {r["usuario_nombre"]}.'
    return en_transaccion(guardar)


def devolver_al_dueno(objeto_id, confirmado, observaciones, encargado_id):
    """Momento 2: el encargado se lo entrega a su dueño, después de revisar su carné -> «Devuelto»."""
    observaciones = texto(observaciones) or None
    if muy_largo(observaciones, 'observaciones'):
        return False, mensaje_largo('observaciones', 'El texto de las observaciones')

    def guardar(con):
        r = reclamaciones.aceptada_de_objeto(objeto_id, con)
        if not r or r['objeto_estado'] != 'Recuperado':
            return False, 'Este objeto no está listo para devolverse.'
        if not confirmado:
            return False, f'Confirma que revisaste el carné de {r["usuario_nombre"]} antes de devolverle el objeto.'
        reclamaciones.completar_devolucion(con, r['devolucion_id'], encargado_id, observaciones)
        return True, f'Objeto devuelto a {r["usuario_nombre"]}.'
    return en_transaccion(guardar)
