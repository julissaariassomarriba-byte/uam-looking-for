"""Limpieza del historial (v9.1.01). Solo el administrador.

Se puede borrar todo el historial o solo los movimientos anteriores a un día. La base vuelve a revisar quién lo
hace y deja constancia en la tabla limpiezas_historial (cuándo, quién, qué rango y cuántas filas). Los objetos,
entregas, reclamaciones y devoluciones no se tocan: solo se borra la lista de movimientos.
"""
from ..config import ROL_ADMIN
from ..datos import objetos
from ..validacion import fecha_valida, texto
from . import en_transaccion


def limpiar(alcance, antes_de, confirmado, usuario):
    """alcance 'todo' o 'fecha' (con antes_de = AAAA-MM-DD). Devuelve (True, mensaje) o (False, motivo)."""
    if not usuario or usuario['rol'] != ROL_ADMIN:
        return False, 'Solo el administrador puede limpiar el historial.'
    if alcance not in ('todo', 'fecha'):
        return False, 'Elige qué parte del historial quieres limpiar.'
    antes_de = texto(antes_de)
    if alcance == 'fecha' and not fecha_valida(antes_de):
        return False, 'Escribe una fecha válida.'
    limite = antes_de if alcance == 'fecha' else None
    if not objetos.contar_historial(limite):
        return False, 'No hay movimientos que limpiar en ese rango.'
    if not confirmado:
        return False, 'Marca la casilla para confirmar la limpieza: no se puede deshacer.'

    def borrar(con):
        borrados = objetos.limpiar_historial(con, limite, usuario['id'])
        rango = f'anteriores al {limite}' if limite else 'de todo el historial'
        return True, f'Se borraron {borrados} movimiento(s) {rango}.'
    return en_transaccion(borrar)
