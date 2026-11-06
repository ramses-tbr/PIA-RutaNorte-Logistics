"""Registros de la capa de aplicación: historial de fases y autorizaciones.

Son implementaciones en memoria. Si el equipo decide guardar el historial dentro del
Aggregate OrdenServicio o en la base de datos, basta con sustituir estas clases.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class TransicionRegistrada:
    orden_id: str
    fase_origen: Optional[str]  # None cuando la orden se registra por primera vez
    fase_destino: str
    momento: datetime


class RegistroDeFases:
    """Guarda cuándo entró cada orden a cada fase, para medir el tiempo de cada una."""

    def __init__(self) -> None:
        self._por_orden: Dict[str, List[TransicionRegistrada]] = {}

    def registrar(self, orden_id: str, fase_origen: Optional[str],
                  fase_destino: str, momento: datetime) -> TransicionRegistrada:
        registro = TransicionRegistrada(orden_id, fase_origen, fase_destino, momento)
        self._por_orden.setdefault(orden_id, []).append(registro)
        return registro

    def historial(self, orden_id: str) -> List[TransicionRegistrada]:
        return list(self._por_orden.get(orden_id, []))

    def duraciones(self, orden_id: str, ahora: datetime) -> List[Tuple[str, timedelta]]:
        """Tiempo en cada fase. La fase actual se mide hasta 'ahora'."""
        historial = self._por_orden.get(orden_id, [])
        resultado = []
        for i, actual in enumerate(historial):
            fin = historial[i + 1].momento if i + 1 < len(historial) else ahora
            resultado.append((actual.fase_destino, fin - actual.momento))
        return resultado

    def tiempo_hasta(self, orden_id: str, fase: str) -> Optional[timedelta]:
        """Tiempo desde el registro de la orden hasta que entró a 'fase' (None si no hay datos)."""
        historial = self._por_orden.get(orden_id, [])
        if not historial:
            return None
        for registro in historial:
            if registro.fase_destino == fase:
                return registro.momento - historial[0].momento
        return None


class RegistroDeAutorizaciones:
    """Guarda la segunda firma de la doble verificación de las cargas de alto valor."""

    def __init__(self) -> None:
        self._firmas: Dict[str, str] = {}

    def registrar(self, orden_id: str, segunda_firma: str) -> None:
        self._firmas[orden_id] = segunda_firma

    def tiene(self, orden_id: str) -> bool:
        return orden_id in self._firmas

    def firma_de(self, orden_id: str) -> Optional[str]:
        return self._firmas.get(orden_id)
