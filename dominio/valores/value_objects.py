from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class OperadorId:
    valor: str

    def __post_init__(self):
        if not self.valor or not self.valor.strip():
            raise ValueError("El ID del operador no puede estar vacío.")

@dataclass(frozen=True)
class CotizacionId:
    valor: str

    def __post_init__(self):
        if not self.valor or not self.valor.strip():
            raise ValueError("El ID de la cotización no puede estar vacío.")

@dataclass(frozen=True)
class ValorCarga:
    monto: Decimal
    moneda: str = "MXN"

    def __post_init__(self):
        if self.monto < Decimal("0"):
            raise ValueError("El valor declarado de la carga no puede ser negativo.")

@dataclass(frozen=True)
class IncidenteId:
    valor: str

    def __post_init__(self):
        if not self.valor or not self.valor.strip():
            raise ValueError("El ID del incidente no puede estar vacío.")

@dataclass(frozen=True)
class MontoPenalizacion:
    monto: Decimal

    def __post_init__(self):
        if self.monto < Decimal("0"):
            raise ValueError("El monto de penalización no puede ser negativo.")