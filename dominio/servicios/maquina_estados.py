from enum import Enum
from dominio.errores.errores import DomainException, TransicionInvalidaError

class EstadoOperacion(str, Enum):
    REGISTRADO = "REGISTRADO"
    SOLICITADA = "SOLICITADA"
    COTIZADA = "COTIZADA"
    CONFIRMADA = "CONFIRMADA"
    UNIDAD_ASIGNADA = "UNIDAD ASIGNADA"
    RECOLECTADO = "RECOLECTADO"
    EN_TRANSITO = "EN TRANSITO"
    LLEGADA_A_DESTINO = "LLEGADA A DESTINO"
    ENTREGADA = "ENTREGADA"
    VENCIDA = "VENCIDA"
    CANCELADA = "CANCELADA"
    EN_DEVOLUCION = "EN DEVOLUCION"

class MaquinaEstadosOperacion:
    TRANSICIONES_VALIDAS = {
        EstadoOperacion.REGISTRADO: [EstadoOperacion.CONFIRMADA, EstadoOperacion.UNIDAD_ASIGNADA, EstadoOperacion.CANCELADA],
        EstadoOperacion.SOLICITADA: [EstadoOperacion.COTIZADA, EstadoOperacion.CANCELADA],
        EstadoOperacion.COTIZADA: [EstadoOperacion.CONFIRMADA, EstadoOperacion.VENCIDA, EstadoOperacion.CANCELADA],
        EstadoOperacion.CONFIRMADA: [EstadoOperacion.UNIDAD_ASIGNADA, EstadoOperacion.CANCELADA],
        EstadoOperacion.UNIDAD_ASIGNADA: [EstadoOperacion.RECOLECTADO, EstadoOperacion.CANCELADA],
        EstadoOperacion.RECOLECTADO: [EstadoOperacion.EN_TRANSITO, EstadoOperacion.CANCELADA],

        EstadoOperacion.EN_TRANSITO: [EstadoOperacion.LLEGADA_A_DESTINO, EstadoOperacion.EN_DEVOLUCION, EstadoOperacion.CANCELADA],
        EstadoOperacion.LLEGADA_A_DESTINO: [EstadoOperacion.ENTREGADA, EstadoOperacion.EN_DEVOLUCION],
        EstadoOperacion.ENTREGADA: [],
        EstadoOperacion.VENCIDA: [],
        EstadoOperacion.CANCELADA: [],
        EstadoOperacion.EN_DEVOLUCION: []
    }

    @classmethod
    def validar_y_transicionar(cls, estado_actual: str, nuevo_estado: str) -> str:
        if nuevo_estado not in cls.TRANSICIONES_VALIDAS.get(estado_actual, []):
            raise TransicionInvalidaError(estado_actual, nuevo_estado)
        return nuevo_estado
