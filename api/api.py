from fastapi import FastAPI, HTTPException
from decimal import Decimal
from datetime import datetime
from typing import Optional

from infraestructura.repositorios.ordenes_repositorio import RepositorioOrdenesCSV
from aplicacion.casos_uso import construir_casos_de_uso
from aplicacion.dtos import (
    OrdenRegistradaDTO, 
    TransicionDTO, 
    IncidenteRegistradoDTO, 
    ResultadoDobleVerificacionDTO, 
    ReporteOperativoFinanciero
)
from dominio.entidades.entidades import Cotizacion, Operador, ValorCarga
from dominio.valores.value_objects import OperadorId, CotizacionId, ValorCarga

app = FastAPI(
    title="RutaNorte Logistics API",
    description="API REST basada en Arquitectura Limpia para la gestión logística de RutaNorte.",
    version="1.0.0"
)

# Inicializamos el repositorio apuntando al CSV real y construimos los casos de uso
repo_ordenes = RepositorioOrdenesCSV("datos/operaciones.csv")
casos_uso = construir_casos_de_uso(repo_ordenes)

@app.get("/", tags=["General"])
def health_check():
    return {"status": "ok", "sistema": "RutaNorte Logistics API operando correctamente"}

@app.post("/ordenes/", response_model=OrdenRegistradaDTO, tags=["Órdenes"])
def registrar_orden(
    orden_id: str,
    cotizacion_id: str,
    operador_id: str,
    direccion: str,
    valor_carga: str,
    cliente_id: Optional[str] = None
):
    try:
        cot_id = CotizacionId(valor=cotizacion_id)
        op_id = OperadorId(valor=operador_id)
        carga_obj = ValorCarga(monto=Decimal(str(valor_carga)))

        cotizacion = Cotizacion(cotizacion_id=cot_id, fecha_emision=datetime.now(), dias_vigencia=5)
        operador = Operador(operador_id=op_id, disponible=True, ruta_aceptada=True)
        
        dto = casos_uso.registrar_orden.ejecutar(
            orden_id=orden_id,
            cotizacion=cotizacion,
            operador=operador,
            direccion=direccion,
            valor_carga=carga_obj,
            cliente_id=cliente_id
        )
        return dto
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/ordenes/{orden_id}/transicionar", response_model=TransicionDTO, tags=["Órdenes"])
def transicionar_fase(orden_id: str, nueva_fase: str):
    try:
        dto = casos_uso.transicionar_fase.ejecutar(orden_id=orden_id, nueva_fase=nueva_fase)
        return dto
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/reportes/operativo-financiero", response_model=ReporteOperativoFinanciero, tags=["Reportes"])
def obtener_reporte_financiero():
    try:
        return casos_uso.generar_reporte.generar()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))