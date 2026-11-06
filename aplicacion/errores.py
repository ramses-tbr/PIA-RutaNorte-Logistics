"""Errores de la capa de aplicación.

Los errores del negocio viven en dominio/errores. Estos son errores de los casos de uso
(la orden no existe, datos de entrada inválidos). Una API puede traducirlos así:
OrdenNoEncontradaError -> 404, OrdenYaExisteError -> 409, DatosInvalidosError -> 422.
"""


class ErrorDeAplicacion(Exception):
    pass


class OrdenNoEncontradaError(ErrorDeAplicacion):
    pass


class OrdenYaExisteError(ErrorDeAplicacion):
    pass


class DatosInvalidosError(ErrorDeAplicacion):
    pass
