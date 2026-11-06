import csv
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal

from dominio.entidades.entidades import OrdenServicio, Operador, Cotizacion
from dominio.valores.value_objects import OperadorId, CotizacionId, ValorCarga
from dominio.servicios.maquina_estados import EstadoOperacion

class RepositorioOrdenesCSV:
    def __init__(self, ruta_csv: str):
        self.ruta_csv = Path(ruta_csv)
        self._ordenes: Dict[str, OrdenServicio] = {}
        self._cargar_y_mapear_datos()

    def _cargar_y_mapear_datos(self):
        if not self.ruta_csv.exists():
            return 

        with open(self.ruta_csv, mode='r', encoding='utf-8-sig') as archivo:
            lector = csv.DictReader(archivo)
            for fila in lector:
                fila_limpia = {k.strip(): v.strip() for k, v in fila.items() if k}
                orden_id = fila_limpia.get("operacion_id")
                if not orden_id:
                    continue

                actor_id = fila_limpia.get("actor_id", "ACT-DEFAULT")
                estado_str = fila_limpia.get("estado_inicial", "REGISTRADO")
                
                try:
                    fase_inicial = EstadoOperacion[estado_str.upper()]
                except KeyError:
                    fase_inicial = EstadoOperacion.REGISTRADO

                cotizacion = Cotizacion(
                    cotizacion_id=CotizacionId(f"COT-{orden_id}"),
                    fecha_emision=datetime.now()
                )
                
                operador = Operador(
                    operador_id=OperadorId(actor_id),
                    disponible=True
                )

                valor_carga = ValorCarga(monto=Decimal("1500.00"))

                orden = OrdenServicio(
                    orden_id=orden_id,
                    cotizacion=cotizacion,
                    operador=operador,
                    direccion="Monterrey/Apodaca",
                    valor_carga=valor_carga,
                    fase=fase_inicial
                )

                self._ordenes[orden_id] = orden

    def obtener_por_id(self, orden_id: str) -> Optional[OrdenServicio]:
        return self._ordenes.get(orden_id)

    def guardar(self, orden: OrdenServicio):
        self._ordenes[orden.orden_id] = orden

    def listar_todas(self) -> List[OrdenServicio]:
        return list(self._ordenes.values())

