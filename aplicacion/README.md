# Capa de aplicación — RutaNorte Logistics

Coordina los casos de uso: recibe la solicitud, obtiene la orden del repositorio, le pide al
dominio que ejecute el cambio, guarda y devuelve un resultado. Las reglas del negocio viven en
`dominio/`.

## Casos de uso (`aplicacion/casos_uso.py`)

| Caso de uso | Método | Qué coordina | Errores posibles |
| --- | --- | --- | --- |
| `RegistrarOrdenUseCase` | `ejecutar(orden_id, cotizacion, operador, direccion, valor_carga, cliente_id=None)` | Cotización vigente, operador disponible y con ruta aceptada; la orden nace en `REGISTRADO` | `CotizacionVencidaError`, `OperadorOcupadoError`, `OrdenYaExisteError`, `DatosInvalidosError` |
| `TransicionarFaseUseCase` | `ejecutar(orden_id, nueva_fase)` | Máquina de estados, doble verificación al entregar y hora de cada fase | `TransicionInvalidaError`, `AutorizacionRequeridaError`, `OrdenNoEncontradaError`, `DatosInvalidosError` |
| `ReportarIncidenteUseCase` | `ejecutar(orden_id, descripcion, severidad, incidente_id=None)` | Crea el `Incidente` (BAJA, MEDIA o CRITICA) y lo vincula a la orden | `DatosInvalidosError`, `OrdenNoEncontradaError` |
| `RegistrarOrdenDeCambioUseCase` | `ejecutar(orden_id, motivo, cambio_id=None)` | Registra el cambio; el dominio lo rechaza si la orden está `ENTREGADA` o `CANCELADA` | `DomainException`, `DatosInvalidosError`, `OrdenNoEncontradaError` |
| `RegistrarDevolucionUseCase` | `ejecutar(orden_id, motivo, devolucion_id=None)` | Solo en `EN TRANSITO` o `LLEGADA A DESTINO`; la orden pasa a `EN DEVOLUCION` | `DomainException`, `DatosInvalidosError`, `OrdenNoEncontradaError` |
| `DobleVerificacionUseCase` | `ejecutar(orden_id, segunda_firma=None)` | Evalúa si la carga supera $100,000 MXN y registra la segunda firma | `AutorizacionRequeridaError`, `OrdenNoEncontradaError` |
| `GenerarReporteUseCase` | `generar()`, `rendimiento_por_operador()`, `estado_cuenta_por_cliente()`, `incidencias_criticas_por_ruta()`, `tiempos_de_fase(orden_id)` | Métricas por operador, por cliente y por ruta | `OrdenNoEncontradaError` |

## Cómo conectarlo (consola o API)

```python
from aplicacion.casos_uso import construir_casos_de_uso
from dominio.servicios.maquina_estados import EstadoOperacion
from infraestructura.repositorios.ordenes_repositorio import RepositorioOrdenesCSV

cu = construir_casos_de_uso(RepositorioOrdenesCSV("datos/operaciones.csv"))
cu.transicionar_fase.ejecutar("ENV-O001", EstadoOperacion.CONFIRMADA)   # también acepta "CONFIRMADA"
cu.reportar_incidente.ejecutar("ENV-O001", "Falla mecánica", "CRITICA")
reporte = cu.generar_reporte.generar()
```

Traducción sugerida de errores a HTTP: `OrdenNoEncontradaError` a 404, `OrdenYaExisteError` y
`TransicionInvalidaError` a 409, `DatosInvalidosError`, `CotizacionVencidaError` y
`AutorizacionRequeridaError` a 422, `OperadorOcupadoError` a 409.

## Reglas de la doble verificación

Una carga es de alto valor cuando su valor declarado es **mayor a $100,000 MXN** (entrevista con el
stakeholder). Las categorías sensibles (electrónicos, medicamentos, metales) también cuentan, pero
el dominio todavía no guarda la categoría de la carga. Para entregar una orden de alto valor hace
falta primero `doble_verificacion.ejecutar(orden_id, segunda_firma)`.

## Supuestos pendientes de validar

- El historial de fases (`RegistroDeFases`) y las segundas firmas (`RegistroDeAutorizaciones`) están en
  memoria. Si se guardan en el Aggregate o en la base de datos, se sustituyen esas clases.
- La "ruta" de una orden es su `direccion`, y el "estado de cuenta" usa el valor declarado de la carga
  porque el dominio todavía no guarda tarifa ni cobros.
- La devolución deja la orden en `EN DEVOLUCION` con estado de devolución `PENDIENTE`.

## Cambios en archivos fuera de `aplicacion/`

- `dominio/entidades/entidades.py`: `OrdenServicio` recibe `cliente_id: Optional[str] = None`
  (necesario para el estado de cuenta por cliente).
- `infraestructura/repositorios/*.py`: se abren los CSV con `encoding='utf-8-sig'`. Los archivos de
  `datos/` traen BOM y con `utf-8` los repositorios no cargaban ninguna fila.
- Archivos nuevos: `dominio/servicios/carga_alto_valor.py` y `pytest.ini`.

## Pruebas

```
pytest -q --cov=aplicacion --cov=dominio --cov=infraestructura --cov-report=term-missing
```
