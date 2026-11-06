import csv
from pathlib import Path
from typing import List, Dict, Optional

class RepositorioActoresCSV:
    def __init__(self, ruta_csv: str):
        self.ruta_csv = Path(ruta_csv)
        self._actores: Dict[str, dict] = {}
        self._cargar_actores()

    def _cargar_actores(self):
        if not self.ruta_csv.exists():
            return
        with open(self.ruta_csv, mode='r', encoding='utf-8-sig') as archivo:
            lector = csv.DictReader(archivo)
            for fila in lector:
                fila_limpia = {k.strip(): v.strip() for k, v in fila.items() if k}
                actor_id = fila_limpia.get("actor_id")
                if actor_id:
                    self._actores[actor_id] = fila_limpia

    def obtener_por_id(self, actor_id: str) -> Optional[dict]:
        return self._actores.get(actor_id)