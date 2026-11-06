"""Puertos: lo que la capa de aplicación necesita del exterior (inversión de dependencias).

Los casos de uso dependen de estas interfaces, no de los repositorios CSV ni de la base de
datos concreta. RepositorioOrdenesCSV (infraestructura) ya cumple este contrato.
"""
from datetime import datetime
from typing import Callable, List, Optional, Protocol

from dominio.entidades.entidades import OrdenServicio

Reloj = Callable[[], datetime]


class RepositorioOrdenes(Protocol):
    def obtener_por_id(self, orden_id: str) -> Optional[OrdenServicio]: ...

    def guardar(self, orden: OrdenServicio) -> None: ...

    def listar_todas(self) -> List[OrdenServicio]: ...
