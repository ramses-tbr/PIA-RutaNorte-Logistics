from datetime import datetime
from decimal import Decimal

class Specification:
    def is_satisfied_by(self, entidad):
        raise NotImplementedError

    def __and__(self, other: 'Specification'):
        return AndSpec(self, other)

    def __or__(self, other: 'Specification'):
        return OrSpec(self, other)

    def __invert__(self):
        return NotSpec(self)

class AndSpec(Specification):
    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, entidad):
        return self.left.is_satisfied_by(entidad) and self.right.is_satisfied_by(entidad)

class OrSpec(Specification):
    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, entidad):
        return self.left.is_satisfied_by(entidad) or self.right.is_satisfied_by(entidad)


class NotSpec(Specification):
    def __init__(self, spec: Specification):
        self.spec = spec

    def is_satisfied_by(self, entidad):
        return not self.spec.is_satisfied_by(entidad)

class CotizacionVigenteSpec(Specification):
    def __init__(self, fecha_referencia: datetime):
        self.fecha_referencia = fecha_referencia

    def is_satisfied_by(self, cotizacion):
        delta = (self.fecha_referencia - cotizacion.fecha_emision).days
        return delta <= cotizacion.dias_vigencia

class OperadorDisponibleSpec(Specification):
    def is_satisfied_by(self, operador):
        return operador.disponible and operador.ruta_aceptada

class ActorActivoSpec(Specification):
    def is_satisfied_by(self, context):
        actor = context.get("actor", {}) if isinstance(context, dict) else getattr(context, "actor", {})
        return actor.get("activo", False)

class OperacionConLineasSpec(Specification):
    def is_satisfied_by(self, operacion):
        lineas = operacion.get("lineas", []) if isinstance(operacion, dict) else getattr(operacion, "lineas", [])
        return len(lineas) > 0

class AutorizacionSpec(Specification):
    def is_satisfied_by(self, operacion):
        autorizado = operacion.get("autorizado", False) if isinstance(operacion, dict) else getattr(operacion, "autorizado", False)
        return bool(autorizado)

class ActorPreferenteSpec(Specification):
    def is_satisfied_by(self, context):
        actor = context.get("actor", {}) if isinstance(context, dict) else getattr(context, "actor", {})
        return actor.get("es_preferente", False)

class MontoMinimoSpec(Specification):
    def __init__(self, minimo: Decimal = Decimal("1500")):
        self.minimo = minimo

    def is_satisfied_by(self, operacion) -> bool:
        if isinstance(operacion, dict):
            total = operoperacion_total = operacion.get("valor_carga", Decimal("0"))
        else:
            total = getattr(operacion, "valor_carga", Decimal("0"))
            
        monto = getattr(total, "monto", total)
        if isinstance(monto, (int, float, str)):
            monto = Decimal(str(monto))
            
        return monto >= self.minimo

class PromocionActivaSpec(Specification):
    def is_satisfied_by(self, operacion):
        promo = operacion.get("promocion_activa", False) if isinstance(operacion, dict) else getattr(operacion, "promocion_activa", False)
        return bool(promo)




    