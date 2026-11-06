"""Resultados de los casos de uso. Son datos simples, sin reglas de negocio."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional


@dataclass(frozen=True)
class OrdenRegistradaDTO:
    orden_id: str
    fase: str
    operador_id: str
    cliente_id: Optional[str]


@dataclass(frozen=True)
class TransicionDTO:
    orden_id: str
    fase_anterior: str
    fase_nueva: str
    momento: datetime


@dataclass(frozen=True)
class IncidenteRegistradoDTO:
    incidente_id: str
    orden_id: str
    severidad: str


@dataclass(frozen=True)
class OrdenDeCambioRegistradaDTO:
    cambio_id: str
    orden_id: str
    motivo: str


@dataclass(frozen=True)
class DevolucionRegistradaDTO:
    devolucion_id: str
    orden_id: str
    fase_orden: str


@dataclass(frozen=True)
class ResultadoDobleVerificacionDTO:
    orden_id: str
    requiere_doble_verificacion: bool
    autorizada: bool
    mensaje: str


@dataclass(frozen=True)
class RendimientoOperadorDTO:
    operador_id: str
    total_ordenes: int
    entregadas: int
    canceladas: int
    en_devolucion: int
    en_curso: int
    incidentes: int
    incidentes_criticos: int
    tasa_entrega_pct: Decimal
    tiempo_promedio_entrega_horas: Optional[Decimal]


@dataclass(frozen=True)
class EstadoCuentaClienteDTO:
    cliente_id: str
    total_ordenes: int
    valor_total: Decimal
    valor_entregado: Decimal
    valor_en_curso: Decimal
    valor_cancelado_o_devuelto: Decimal


@dataclass(frozen=True)
class IncidenciasRutaDTO:
    ruta: str
    incidentes_totales: int
    incidentes_criticos: int


@dataclass(frozen=True)
class ReporteOperativoFinanciero:
    generado_en: datetime
    rendimiento_por_operador: List[RendimientoOperadorDTO] = field(default_factory=list)
    estado_cuenta_por_cliente: List[EstadoCuentaClienteDTO] = field(default_factory=list)
    incidencias_por_ruta: List[IncidenciasRutaDTO] = field(default_factory=list)
