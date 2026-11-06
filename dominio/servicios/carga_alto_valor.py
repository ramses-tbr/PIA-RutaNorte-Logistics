"""Specification de carga de alto valor.

Regla del negocio (entrevista con el stakeholder): una carga es de alto valor cuando
declara un valor ARRIBA de $100,000 pesos. Las categorías sensibles (electrónicos,
medicamentos, metales) también cuentan, pero el modelo actual no guarda la categoría de la
carga; queda como mejora pendiente.
"""
from decimal import Decimal

from dominio.servicios.specifications import Specification

UMBRAL_ALTO_VALOR_MXN = Decimal("100000")


class CargaAltoValorSpec(Specification):
    def __init__(self, umbral: Decimal = UMBRAL_ALTO_VALOR_MXN):
        self.umbral = umbral

    def is_satisfied_by(self, orden) -> bool:
        return orden.valor_carga.monto > self.umbral
