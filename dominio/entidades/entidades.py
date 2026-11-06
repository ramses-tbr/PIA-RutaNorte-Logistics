from datetime import datetime
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional
from dominio.valores.value_objects import OperadorId, CotizacionId, ValorCarga, IncidenteId
from dominio.servicios.maquina_estados import EstadoOperacion, MaquinaEstadosOperacion
from dominio.errores.errores import CotizacionVencidaError, OperadorOcupadoError, DomainException

@dataclass
class Operador:
    operador_id: OperadorId
    disponible: bool = True
    ruta_aceptada: bool = False

    def verificar_disponibilidad(self):
        if not self.disponible:
            raise OperadorOcupadoError(f"El operador con ID {self.operador_id} se encuentra ocupado.")
        if not self.ruta_aceptada:
            raise OperadorOcupadoError(f"El operador {self.operador_id} aún no ha aceptado la ruta asignada.")

@dataclass
class Cotizacion:
    cotizacion_id: CotizacionId
    fecha_emision: datetime
    dias_vigencia: int = 5

    def validar_vigencia(self, fecha_solicitud: datetime):
        delta = (fecha_solicitud - self.fecha_emision).days
        if delta > self.dias_vigencia:
            raise CotizacionVencidaError("La cotización ha superado su período de vigencia.")

@dataclass
class Incidente:
    incidente_id: IncidenteId
    orden_id: str
    descripcion: str
    severidad: str 
    resuelto: bool = False

    def resolver_incidente(self):
        self.resuelto = True

@dataclass
class OrdenDeCambio:
    cambio_id: str
    motivo: str
    fecha_registro: datetime

@dataclass
class OrdenDeDevolucion:
    devolucion_id: str
    motivo: str
    estado: str

@dataclass
class OrdenServicio:
    orden_id: str
    cotizacion: Cotizacion
    operador: Operador
    direccion: str
    valor_carga: ValorCarga
    fase: EstadoOperacion = EstadoOperacion.REGISTRADO
    ordenes_cambio: List[OrdenDeCambio] = field(default_factory=list)
    ordenes_devolucion: List[OrdenDeDevolucion] = field(default_factory=list)
    incidentes: List[Incidente] = field(default_factory=list)
    cliente_id: Optional[str] = None

    def cambiar_fase(self, nueva_fase: EstadoOperacion):
        self.fase = MaquinaEstadosOperacion.validar_y_transicionar(self.fase, nueva_fase)

    def registrar_incidente(self, incidente: Incidente):
        self.incidentes.append(incidente)

    def agregar_orden_cambio(self, orden_cambio: OrdenDeCambio):
        if self.fase in [EstadoOperacion.ENTREGADA, EstadoOperacion.CANCELADA]:
            raise DomainException("No se puede registrar un cambio en una orden ya finalizada o cancelada.")
        self.ordenes_cambio.append(orden_cambio)

    def agregar_devolucion(self, devolucion: OrdenDeDevolucion):
        if self.fase not in [EstadoOperacion.EN_TRANSITO, EstadoOperacion.LLEGADA_A_DESTINO]:
            raise DomainException("Solo se puede registrar una devolución en fases de tránsito o destino.")
        self.ordenes_devolucion.append(devolucion)
