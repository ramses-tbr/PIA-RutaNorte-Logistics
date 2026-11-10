"""Interfaz web de RutaNorte Logistics.

Este módulo NO contiene reglas de negocio: solo traduce entre el navegador (JSON) y los casos
de uso que ya existen en `aplicacion/`. Las reglas (máquina de estados, vigencia de la
cotización, doble verificación, etc.) siguen viviendo en `dominio/`.

Se conecta a la API existente con una sola llamada en `api/api.py`:

    montar_interfaz(app, repo_ordenes, casos_uso)

Rutas nuevas:
    GET  /ui                                   página de la interfaz
    GET  /api/meta                             fases, transiciones válidas y umbral de alto valor
    GET  /api/ordenes                          lista de órdenes
    GET  /api/ordenes/{id}                     detalle (incidentes, cambios, devoluciones, historial)
    POST /api/ordenes                          registrar orden
    POST /api/ordenes/{id}/transicion          avanzar de fase
    POST /api/ordenes/{id}/incidentes          reportar incidente
    POST /api/ordenes/{id}/cambios             registrar orden de cambio
    POST /api/ordenes/{id}/devolucion          registrar devolución
    POST /api/ordenes/{id}/doble-verificacion  registrar segunda firma
    GET  /api/reporte                          reporte operativo y financiero
"""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from aplicacion.errores import DatosInvalidosError, OrdenNoEncontradaError, OrdenYaExisteError
from dominio.entidades.entidades import Cotizacion, Operador
from dominio.errores.errores import DomainException
from dominio.servicios.carga_alto_valor import UMBRAL_ALTO_VALOR_MXN, CargaAltoValorSpec
from dominio.servicios.maquina_estados import EstadoOperacion, MaquinaEstadosOperacion
from dominio.valores.value_objects import CotizacionId, OperadorId, ValorCarga

PAGINA = Path(__file__).resolve().parent / "static" / "index.html"

# Camino normal de una orden, de izquierda a derecha en la interfaz.
RUTA_NORMAL = [
    EstadoOperacion.REGISTRADO,
    EstadoOperacion.CONFIRMADA,
    EstadoOperacion.UNIDAD_ASIGNADA,
    EstadoOperacion.RECOLECTADO,
    EstadoOperacion.EN_TRANSITO,
    EstadoOperacion.LLEGADA_A_DESTINO,
    EstadoOperacion.ENTREGADA,
]


# ----------------------------------------------------------------------------- cuerpos de petición
# Todos los campos tienen valor por defecto para que los casos de uso (y no FastAPI) den el
# mensaje de error cuando algo falta.
class NuevaOrden(BaseModel):
    orden_id: str = ""
    direccion: str = ""
    valor_carga: str = "0"
    operador_id: str = ""
    cliente_id: Optional[str] = None
    cotizacion_id: Optional[str] = None
    dias_desde_emision: int = 0      # para probar cotizaciones vencidas (vigencia: 5 días)
    operador_disponible: bool = True
    ruta_aceptada: bool = True


class CuerpoTransicion(BaseModel):
    nueva_fase: str = ""


class CuerpoIncidente(BaseModel):
    descripcion: str = ""
    severidad: str = "MEDIA"


class CuerpoMotivo(BaseModel):
    motivo: str = ""


class CuerpoFirma(BaseModel):
    segunda_firma: Optional[str] = None


# ----------------------------------------------------------------------------- utilidades
def _fecha(valor: datetime) -> str:
    """Fecha con zona horaria, para que el navegador la muestre en su hora local."""
    return valor.astimezone().isoformat(timespec="seconds")


def _estado_http(error: Exception) -> int:
    if isinstance(error, OrdenNoEncontradaError):
        return 404
    if isinstance(error, OrdenYaExisteError):
        return 409
    if isinstance(error, (DatosInvalidosError, ValueError)):
        return 422
    if isinstance(error, DomainException):
        return 409      # una regla del negocio no permite la operación
    return 500


def _limpiar(mensaje: str) -> str:
    """Python 3.11+ imprime los Enum como 'EstadoOperacion.EN_TRANSITO'; se muestra el valor legible."""
    for estado in EstadoOperacion:
        mensaje = mensaje.replace(f"EstadoOperacion.{estado.name}", estado.value)
    return mensaje


def _correr(accion: Callable[[], dict]) -> JSONResponse:
    """Ejecuta la acción y convierte los errores del sistema en respuestas JSON claras."""
    try:
        return JSONResponse(jsonable_encoder(accion()))
    except Exception as error:  # noqa: BLE001 - se traduce cualquier error a JSON
        estado = _estado_http(error)
        mensaje = _limpiar(str(error)) if estado != 500 else "Ocurrió un error inesperado en el servidor."
        return JSONResponse({"error": mensaje, "tipo": type(error).__name__}, status_code=estado)


# ----------------------------------------------------------------------------- ensamblado
def montar_interfaz(app: FastAPI, repositorio, casos) -> None:
    """Agrega la interfaz web y sus rutas JSON a la aplicación FastAPI existente."""
    router = APIRouter()
    alto_valor = CargaAltoValorSpec()

    def resumen(orden) -> dict:
        return {
            "orden_id": orden.orden_id,
            "fase": orden.fase.value,
            "operador_id": orden.operador.operador_id.valor,
            "cliente_id": orden.cliente_id,
            "direccion": orden.direccion,
            "valor_carga": orden.valor_carga.monto,
            "moneda": orden.valor_carga.moneda,
            "alto_valor": alto_valor.is_satisfied_by(orden),
            "incidentes": len(orden.incidentes),
            "siguientes": [e.value for e in MaquinaEstadosOperacion.TRANSICIONES_VALIDAS.get(orden.fase, [])],
        }

    def detalle(orden) -> dict:
        autorizaciones = casos.doble_verificacion._autorizaciones  # registro de segundas firmas
        ahora = datetime.now()
        datos = resumen(orden)
        datos.update({
            "cotizacion_id": orden.cotizacion.cotizacion_id.valor,
            "cotizacion_emitida": _fecha(orden.cotizacion.fecha_emision),
            "cotizacion_vigencia_dias": orden.cotizacion.dias_vigencia,
            "autorizada": autorizaciones.tiene(orden.orden_id),
            "segunda_firma": autorizaciones.firma_de(orden.orden_id),
            "incidentes_detalle": [
                {"incidente_id": i.incidente_id.valor, "descripcion": i.descripcion,
                 "severidad": i.severidad, "resuelto": i.resuelto}
                for i in orden.incidentes
            ],
            "cambios": [
                {"cambio_id": c.cambio_id, "motivo": c.motivo, "fecha": _fecha(c.fecha_registro)}
                for c in orden.ordenes_cambio
            ],
            "devoluciones": [
                {"devolucion_id": d.devolucion_id, "motivo": d.motivo, "estado": d.estado}
                for d in orden.ordenes_devolucion
            ],
            "historial": [
                {"origen": t.fase_origen, "destino": t.fase_destino, "momento": _fecha(t.momento)}
                for t in casos.registro_fases.historial(orden.orden_id)
            ],
            "duraciones": [
                {"fase": fase, "segundos": int(duracion.total_seconds())}
                for fase, duracion in casos.registro_fases.duraciones(orden.orden_id, ahora)
            ],
        })
        return datos

    def obtener(orden_id: str):
        orden = repositorio.obtener_por_id(orden_id)
        if orden is None:
            raise OrdenNoEncontradaError(f"La orden '{orden_id}' no existe.")
        return orden

    # ------------------------------------------------------------------------- lectura
    @router.get("/ui", include_in_schema=False)
    def pagina():
        return FileResponse(PAGINA, media_type="text/html")

    @router.get("/api/meta", tags=["Interfaz"])
    def meta():
        return {
            "fases": [e.value for e in EstadoOperacion],
            "ruta": [e.value for e in RUTA_NORMAL],
            "transiciones": {
                e.value: [s.value for s in siguientes]
                for e, siguientes in MaquinaEstadosOperacion.TRANSICIONES_VALIDAS.items()
            },
            "umbral_alto_valor": UMBRAL_ALTO_VALOR_MXN,
            "severidades": ["BAJA", "MEDIA", "CRITICA"],
        }

    @router.get("/api/ordenes", tags=["Interfaz"])
    def listar():
        return _correr(lambda: {
            "ordenes": [resumen(o) for o in sorted(repositorio.listar_todas(), key=lambda o: o.orden_id)]
        })

    @router.get("/api/ordenes/{orden_id}", tags=["Interfaz"])
    def ver(orden_id: str):
        return _correr(lambda: detalle(obtener(orden_id)))

    @router.get("/api/reporte", tags=["Interfaz"])
    def reporte():
        return _correr(lambda: casos.generar_reporte.generar())

    # ------------------------------------------------------------------------- acciones
    @router.post("/api/ordenes", tags=["Interfaz"])
    def registrar(cuerpo: NuevaOrden):
        def accion():
            try:
                monto = Decimal(cuerpo.valor_carga.strip().replace(",", ""))
            except InvalidOperation:
                raise DatosInvalidosError("El valor de la carga debe ser un número, por ejemplo 25000.")
            orden_id = cuerpo.orden_id.strip()
            cotizacion = Cotizacion(
                cotizacion_id=CotizacionId((cuerpo.cotizacion_id or "").strip() or f"COT-{orden_id}"),
                fecha_emision=datetime.now() - timedelta(days=cuerpo.dias_desde_emision),
                dias_vigencia=5,
            )
            operador = Operador(
                operador_id=OperadorId(cuerpo.operador_id.strip()),
                disponible=cuerpo.operador_disponible,
                ruta_aceptada=cuerpo.ruta_aceptada,
            )
            casos.registrar_orden.ejecutar(
                orden_id=orden_id,
                cotizacion=cotizacion,
                operador=operador,
                direccion=cuerpo.direccion,
                valor_carga=ValorCarga(monto=monto),
                cliente_id=(cuerpo.cliente_id or "").strip() or None,
            )
            return {"mensaje": f"Orden {orden_id} registrada.", "orden": detalle(obtener(orden_id))}
        return _correr(accion)

    @router.post("/api/ordenes/{orden_id}/transicion", tags=["Interfaz"])
    def transicionar(orden_id: str, cuerpo: CuerpoTransicion):
        def accion():
            r = casos.transicionar_fase.ejecutar(orden_id, cuerpo.nueva_fase)
            return {"mensaje": f"{r.orden_id}: {r.fase_anterior} → {r.fase_nueva}.",
                    "orden": detalle(obtener(orden_id))}
        return _correr(accion)

    @router.post("/api/ordenes/{orden_id}/incidentes", tags=["Interfaz"])
    def incidente(orden_id: str, cuerpo: CuerpoIncidente):
        def accion():
            r = casos.reportar_incidente.ejecutar(orden_id, cuerpo.descripcion, cuerpo.severidad)
            return {"mensaje": f"Incidente {r.incidente_id} reportado ({r.severidad}).",
                    "orden": detalle(obtener(orden_id))}
        return _correr(accion)

    @router.post("/api/ordenes/{orden_id}/cambios", tags=["Interfaz"])
    def cambio(orden_id: str, cuerpo: CuerpoMotivo):
        def accion():
            r = casos.registrar_orden_de_cambio.ejecutar(orden_id, cuerpo.motivo)
            return {"mensaje": f"Orden de cambio {r.cambio_id} registrada.",
                    "orden": detalle(obtener(orden_id))}
        return _correr(accion)

    @router.post("/api/ordenes/{orden_id}/devolucion", tags=["Interfaz"])
    def devolucion(orden_id: str, cuerpo: CuerpoMotivo):
        def accion():
            r = casos.registrar_devolucion.ejecutar(orden_id, cuerpo.motivo)
            return {"mensaje": f"Devolución {r.devolucion_id} registrada. La orden pasó a {r.fase_orden}.",
                    "orden": detalle(obtener(orden_id))}
        return _correr(accion)

    @router.post("/api/ordenes/{orden_id}/doble-verificacion", tags=["Interfaz"])
    def doble_verificacion(orden_id: str, cuerpo: CuerpoFirma):
        def accion():
            r = casos.doble_verificacion.ejecutar(orden_id, cuerpo.segunda_firma)
            return {"mensaje": r.mensaje, "orden": detalle(obtener(orden_id))}
        return _correr(accion)

    app.include_router(router)
