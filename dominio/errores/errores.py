class DomainException(Exception): pass

class CotizacionVencidaError(DomainException): pass

class CotizacionIdInvalidaError(DomainException): pass

class OperadorOcupadoError(DomainException): pass

class AutorizacionRequeridaError(DomainException): pass

class TransicionInvalidaError(DomainException):
    def __init__(self, estado_actual: str, estado_siguiente: str):
        super().__init__(f"No se puede cambiar de '{estado_actual}' a '{estado_siguiente}'.")
        self.estado_actual = estado_actual
        self.estado_siguiente = estado_siguiente
