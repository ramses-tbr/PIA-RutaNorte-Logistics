"""Casos de uso de RutaNorte Logistics (capa de aplicación).

Cada caso de uso COORDINA: recibe la solicitud, obtiene la orden del repositorio, le pide al
dominio que ejecute el cambio (máquina de estados, invariantes, Specifications), guarda y
devuelve un resultado. Las reglas del negocio viven en dominio/, no aquí.

Casos de uso (lista oficial del equipo):
  1. RegistrarOrdenUseCase           4. RegistrarOrdenDeCambioUseCase
  2. TransicionarFaseUseCase         5. RegistrarDevolucionUseCase
  3. ReportarIncidenteUseCase        6. DobleVerificacionUseCase
  7. GenerarReporteUseCase
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union
from uuid import uuid4

from aplicacion.dtos import (
    DevolucionRegistradaDTO,
    EstadoCuentaClienteDTO,
    IncidenciasRutaDTO,
    IncidenteRegistradoDTO,
    OrdenDeCambioRegistradaDTO,
    OrdenRegistradaDTO,
    RendimientoOperadorDTO,
    ReporteOperativoFinanciero,
    ResultadoDobleVerificacionDTO,
    TransicionDTO,
)
from aplicacion.errores import DatosInvalidosError, OrdenNoEncontradaError, OrdenYaExisteError
from aplicacion.puertos import RepositorioOrdenes, Reloj
from aplicacion.registros import RegistroDeAutorizaciones, RegistroDeFases
from dominio.entidades.entidades import (
    Cotizacion,
    Incidente,
    Operador,
    OrdenDeCambio,
    OrdenDeDevolucion,
    OrdenServicio,
)
from dominio.errores.errores import AutorizacionRequeridaError
from dominio.servicios.carga_alto_valor import CargaAltoValorSpec
from dominio.servicios.maquina_estados import EstadoOperacion, MaquinaEstadosOperacion
from dominio.servicios.specifications import AutorizacionSpec, Specification
from dominio.valores.value_objects import IncidenteId, ValorCarga

SEVERIDADES = ("BAJA", "MEDIA", "CRITICA")
SIN_CLIENTE = "SIN CLIENTE"
_FASES_TERMINALES_CUENTA = (EstadoOperacion.CANCELADA, EstadoOperacion.EN_DEVOLUCION, EstadoOperacion.VENCIDA)


# ----------------------------------------------------------------------------- utilidades
def _texto_obligatorio(valor, nombre: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise DatosInvalidosError(f"'{nombre}' es obligatorio y no puede estar vacío.")
    return valor.strip()


def _obtener_orden(repositorio: RepositorioOrdenes, orden_id: str) -> OrdenServicio:
    orden = repositorio.obtener_por_id(orden_id)
    if orden is None:
        raise OrdenNoEncontradaError(f"La orden '{orden_id}' no existe.")
    return orden


def _a_estado(fase: Union[EstadoOperacion, str]) -> EstadoOperacion:
    """Acepta el Enum, su valor ('EN TRANSITO') o su nombre ('EN_TRANSITO')."""
    if isinstance(fase, EstadoOperacion):
        return fase
    if isinstance(fase, str):
        texto = fase.strip().upper()
        for estado in EstadoOperacion:
            if texto in (estado.value, estado.name):
                return estado
    raise DatosInvalidosError(f"La fase '{fase}' no existe.")


def _normalizar_severidad(severidad: str) -> str:
    texto = _texto_obligatorio(severidad, "severidad").upper().replace("Í", "I")
    if texto not in SEVERIDADES:
        raise DatosInvalidosError(f"Severidad '{severidad}' inválida. Use: {', '.join(SEVERIDADES)}.")
    return texto


# ----------------------------------------------------------------------------- doble verificación
class ServicioDobleVerificacion:
    """Regla de la doble verificación de las cargas de alto valor.

    Usa dos Specifications del dominio: CargaAltoValorSpec (¿supera el umbral?) y
    AutorizacionSpec (¿ya hay autorización?). Si la carga es de alto valor y no hay segunda
    firma registrada, no se permite que la orden avance a ENTREGADA.
    """

    def __init__(self, autorizaciones: RegistroDeAutorizaciones,
                 spec_alto_valor: Optional[Specification] = None) -> None:
        self._autorizaciones = autorizaciones
        self._alto_valor = spec_alto_valor or CargaAltoValorSpec()

    def requiere(self, orden: OrdenServicio) -> bool:
        return self._alto_valor.is_satisfied_by(orden)

    def exigir_para_entrega(self, orden: OrdenServicio) -> None:
        if not self.requiere(orden):
            return
        contexto = {"autorizado": self._autorizaciones.tiene(orden.orden_id)}
        if not AutorizacionSpec().is_satisfied_by(contexto):
            raise AutorizacionRequeridaError(
                f"La orden '{orden.orden_id}' es de alto valor: falta la segunda firma "
                "(doble verificación) para poder entregarla."
            )


class DobleVerificacionUseCase:
    """Caso de uso 6: evalúa si la carga es de alto valor y registra la segunda firma."""

    def __init__(self, repositorio: RepositorioOrdenes, servicio: ServicioDobleVerificacion,
                 autorizaciones: RegistroDeAutorizaciones) -> None:
        self._repo = repositorio
        self._servicio = servicio
        self._autorizaciones = autorizaciones

    def ejecutar(self, orden_id: str, segunda_firma: Optional[str] = None) -> ResultadoDobleVerificacionDTO:
        orden = _obtener_orden(self._repo, orden_id)
        if not self._servicio.requiere(orden):
            return ResultadoDobleVerificacionDTO(
                orden_id, False, True, "No aplica: la carga no supera el umbral de alto valor.")
        if segunda_firma is None or not str(segunda_firma).strip():
            raise AutorizacionRequeridaError(
                f"La orden '{orden_id}' es de alto valor: se requiere autorización especial o segunda firma.")
        self._autorizaciones.registrar(orden_id, str(segunda_firma).strip())
        return ResultadoDobleVerificacionDTO(
            orden_id, True, True, "Doble verificación registrada: la orden puede avanzar a la entrega.")


# ----------------------------------------------------------------------------- casos de uso
class RegistrarOrdenUseCase:
    """Caso de uso 1: da de alta una orden en la fase REGISTRADO.

    Reglas que coordina: la cotización debe estar vigente y el operador debe estar
    disponible y haber aceptado la ruta. Ambas las decide el dominio.
    """

    def __init__(self, repositorio: RepositorioOrdenes, registro_fases: RegistroDeFases,
                 reloj: Reloj = datetime.now) -> None:
        self._repo = repositorio
        self._registro = registro_fases
        self._reloj = reloj

    def ejecutar(self, orden_id: str, cotizacion: Cotizacion, operador: Operador, direccion: str,
                 valor_carga: ValorCarga, cliente_id: Optional[str] = None) -> OrdenRegistradaDTO:
        orden_id = _texto_obligatorio(orden_id, "orden_id")
        direccion = _texto_obligatorio(direccion, "direccion")
        if self._repo.obtener_por_id(orden_id) is not None:
            raise OrdenYaExisteError(f"La orden '{orden_id}' ya existe.")

        ahora = self._reloj()
        cotizacion.validar_vigencia(ahora)       # CotizacionVencidaError si ya venció
        operador.verificar_disponibilidad()      # OperadorOcupadoError si no está disponible/apto

        orden = OrdenServicio(
            orden_id=orden_id, cotizacion=cotizacion, operador=operador, direccion=direccion,
            valor_carga=valor_carga, fase=EstadoOperacion.REGISTRADO, cliente_id=cliente_id,
        )
        self._repo.guardar(orden)
        self._registro.registrar(orden_id, None, EstadoOperacion.REGISTRADO.value, ahora)
        return OrdenRegistradaDTO(orden_id, orden.fase.value, operador.operador_id.valor, cliente_id)


class TransicionarFaseUseCase:
    """Caso de uso 2: avanza la orden por su ciclo de vida y registra la hora de cada fase."""

    def __init__(self, repositorio: RepositorioOrdenes, registro_fases: RegistroDeFases,
                 doble_verificacion: ServicioDobleVerificacion, reloj: Reloj = datetime.now) -> None:
        self._repo = repositorio
        self._registro = registro_fases
        self._doble = doble_verificacion
        self._reloj = reloj

    def ejecutar(self, orden_id: str, nueva_fase: Union[EstadoOperacion, str]) -> TransicionDTO:
        orden = _obtener_orden(self._repo, orden_id)
        destino = _a_estado(nueva_fase)
        anterior = orden.fase

        # 1) La máquina de estados decide primero si el cambio es legal.
        MaquinaEstadosOperacion.validar_y_transicionar(anterior, destino)
        # 2) Para entregar una carga de alto valor se exige la doble verificación.
        if destino == EstadoOperacion.ENTREGADA:
            self._doble.exigir_para_entrega(orden)
        # 3) Solo si todo es válido se cambia la fase, se guarda y se registra la hora.
        orden.cambiar_fase(destino)
        ahora = self._reloj()
        self._repo.guardar(orden)
        self._registro.registrar(orden_id, anterior.value, destino.value, ahora)
        return TransicionDTO(orden_id, anterior.value, destino.value, ahora)


class ReportarIncidenteUseCase:
    """Caso de uso 3: el operador registra un imprevisto en ruta y se vincula a la orden."""

    def __init__(self, repositorio: RepositorioOrdenes) -> None:
        self._repo = repositorio

    def ejecutar(self, orden_id: str, descripcion: str, severidad: str,
                 incidente_id: Optional[str] = None) -> IncidenteRegistradoDTO:
        descripcion = _texto_obligatorio(descripcion, "descripcion")
        severidad = _normalizar_severidad(severidad)
        orden = _obtener_orden(self._repo, orden_id)
        identificador = incidente_id or f"INC-{uuid4().hex[:8].upper()}"
        incidente = Incidente(
            incidente_id=IncidenteId(identificador), orden_id=orden.orden_id,
            descripcion=descripcion, severidad=severidad,
        )
        orden.registrar_incidente(incidente)
        self._repo.guardar(orden)
        return IncidenteRegistradoDTO(identificador, orden.orden_id, severidad)


class RegistrarOrdenDeCambioUseCase:
    """Caso de uso 4: registra un cambio de ruta, destinatario o carga sobre una orden en curso.

    La invariante (no se puede cambiar una orden ENTREGADA o CANCELADA) la protege el dominio.
    """

    def __init__(self, repositorio: RepositorioOrdenes, reloj: Reloj = datetime.now) -> None:
        self._repo = repositorio
        self._reloj = reloj

    def ejecutar(self, orden_id: str, motivo: str, cambio_id: Optional[str] = None) -> OrdenDeCambioRegistradaDTO:
        motivo = _texto_obligatorio(motivo, "motivo")
        orden = _obtener_orden(self._repo, orden_id)
        identificador = cambio_id or f"CAM-{uuid4().hex[:8].upper()}"
        orden.agregar_orden_cambio(OrdenDeCambio(identificador, motivo, self._reloj()))
        self._repo.guardar(orden)
        return OrdenDeCambioRegistradaDTO(identificador, orden.orden_id, motivo)


class RegistrarDevolucionUseCase:
    """Caso de uso 5: el cliente rechaza la mercancía; se registra la devolución.

    El dominio solo la permite en EN TRANSITO o LLEGADA A DESTINO. Si la acepta, la orden pasa
    a EN DEVOLUCION (ambas fases tienen esa transición válida, así que no puede quedar a medias).
    """

    def __init__(self, repositorio: RepositorioOrdenes, registro_fases: RegistroDeFases,
                 reloj: Reloj = datetime.now) -> None:
        self._repo = repositorio
        self._registro = registro_fases
        self._reloj = reloj

    def ejecutar(self, orden_id: str, motivo: str, devolucion_id: Optional[str] = None) -> DevolucionRegistradaDTO:
        motivo = _texto_obligatorio(motivo, "motivo")
        orden = _obtener_orden(self._repo, orden_id)
        anterior = orden.fase
        identificador = devolucion_id or f"DEV-{uuid4().hex[:8].upper()}"
        orden.agregar_devolucion(OrdenDeDevolucion(identificador, motivo, "PENDIENTE"))
        orden.cambiar_fase(EstadoOperacion.EN_DEVOLUCION)
        self._repo.guardar(orden)
        self._registro.registrar(orden.orden_id, anterior.value, EstadoOperacion.EN_DEVOLUCION.value, self._reloj())
        return DevolucionRegistradaDTO(identificador, orden.orden_id, orden.fase.value)


class GenerarReporteUseCase:
    """Caso de uso 7: métricas para el cliente (rendimiento, estado de cuenta e incidencias).

    Supuestos: la 'ruta' de una orden es su dirección, y el 'estado de cuenta' usa el valor
    declarado de la carga porque el dominio todavía no guarda tarifa ni cobros.
    """

    def __init__(self, repositorio: RepositorioOrdenes, registro_fases: RegistroDeFases,
                 reloj: Reloj = datetime.now) -> None:
        self._repo = repositorio
        self._registro = registro_fases
        self._reloj = reloj

    def rendimiento_por_operador(self) -> List[RendimientoOperadorDTO]:
        grupos: Dict[str, List[OrdenServicio]] = {}
        for orden in self._repo.listar_todas():
            grupos.setdefault(orden.operador.operador_id.valor, []).append(orden)

        resultado = []
        for operador_id in sorted(grupos):
            ordenes = grupos[operador_id]
            entregadas = [o for o in ordenes if o.fase == EstadoOperacion.ENTREGADA]
            canceladas = [o for o in ordenes if o.fase == EstadoOperacion.CANCELADA]
            devoluciones = [o for o in ordenes if o.fase == EstadoOperacion.EN_DEVOLUCION]
            en_curso = len(ordenes) - len(entregadas) - len(canceladas) - len(devoluciones) \
                - len([o for o in ordenes if o.fase == EstadoOperacion.VENCIDA])
            incidentes = [i for o in ordenes for i in o.incidentes]

            tiempos = [self._registro.tiempo_hasta(o.orden_id, EstadoOperacion.ENTREGADA.value) for o in entregadas]
            tiempos = [t for t in tiempos if t is not None]
            promedio = None
            if tiempos:
                segundos = Decimal(str(sum(t.total_seconds() for t in tiempos)))
                promedio = (segundos / Decimal(len(tiempos)) / Decimal(3600)).quantize(Decimal("0.01"))

            resultado.append(RendimientoOperadorDTO(
                operador_id=operador_id,
                total_ordenes=len(ordenes),
                entregadas=len(entregadas),
                canceladas=len(canceladas),
                en_devolucion=len(devoluciones),
                en_curso=en_curso,
                incidentes=len(incidentes),
                incidentes_criticos=len([i for i in incidentes if i.severidad == "CRITICA"]),
                tasa_entrega_pct=(Decimal(len(entregadas)) * 100 / Decimal(len(ordenes))).quantize(Decimal("0.01")),
                tiempo_promedio_entrega_horas=promedio,
            ))
        return resultado

    def estado_cuenta_por_cliente(self) -> List[EstadoCuentaClienteDTO]:
        grupos: Dict[str, List[OrdenServicio]] = {}
        for orden in self._repo.listar_todas():
            grupos.setdefault(orden.cliente_id or SIN_CLIENTE, []).append(orden)

        resultado = []
        for cliente_id in sorted(grupos):
            ordenes = grupos[cliente_id]
            total = sum((o.valor_carga.monto for o in ordenes), Decimal("0"))
            entregado = sum((o.valor_carga.monto for o in ordenes if o.fase == EstadoOperacion.ENTREGADA), Decimal("0"))
            perdido = sum((o.valor_carga.monto for o in ordenes if o.fase in _FASES_TERMINALES_CUENTA), Decimal("0"))
            resultado.append(EstadoCuentaClienteDTO(
                cliente_id=cliente_id, total_ordenes=len(ordenes), valor_total=total,
                valor_entregado=entregado, valor_en_curso=total - entregado - perdido,
                valor_cancelado_o_devuelto=perdido,
            ))
        return resultado

    def incidencias_criticas_por_ruta(self) -> List[IncidenciasRutaDTO]:
        rutas: Dict[str, List[Incidente]] = {}
        for orden in self._repo.listar_todas():
            rutas.setdefault(orden.direccion, []).extend(orden.incidentes)
        resultado = [
            IncidenciasRutaDTO(ruta, len(incidentes), len([i for i in incidentes if i.severidad == "CRITICA"]))
            for ruta, incidentes in rutas.items()
        ]
        return sorted(resultado, key=lambda r: (-r.incidentes_criticos, r.ruta))

    def tiempos_de_fase(self, orden_id: str):
        """Cuánto tiempo estuvo (o lleva) la orden en cada fase."""
        _obtener_orden(self._repo, orden_id)
        return self._registro.duraciones(orden_id, self._reloj())

    def generar(self) -> ReporteOperativoFinanciero:
        return ReporteOperativoFinanciero(
            generado_en=self._reloj(),
            rendimiento_por_operador=self.rendimiento_por_operador(),
            estado_cuenta_por_cliente=self.estado_cuenta_por_cliente(),
            incidencias_por_ruta=self.incidencias_criticas_por_ruta(),
        )


# ----------------------------------------------------------------------------- ensamblado
@dataclass
class CasosDeUso:
    """Todos los casos de uso ya conectados entre sí. La consola (main.py) o la API solo
    necesitan llamar a construir_casos_de_uso(repositorio)."""

    registrar_orden: RegistrarOrdenUseCase
    transicionar_fase: TransicionarFaseUseCase
    reportar_incidente: ReportarIncidenteUseCase
    registrar_orden_de_cambio: RegistrarOrdenDeCambioUseCase
    registrar_devolucion: RegistrarDevolucionUseCase
    doble_verificacion: DobleVerificacionUseCase
    generar_reporte: GenerarReporteUseCase
    registro_fases: RegistroDeFases


def construir_casos_de_uso(repositorio: RepositorioOrdenes, reloj: Reloj = datetime.now) -> CasosDeUso:
    registro = RegistroDeFases()
    autorizaciones = RegistroDeAutorizaciones()
    servicio_doble = ServicioDobleVerificacion(autorizaciones)
    return CasosDeUso(
        registrar_orden=RegistrarOrdenUseCase(repositorio, registro, reloj),
        transicionar_fase=TransicionarFaseUseCase(repositorio, registro, servicio_doble, reloj),
        reportar_incidente=ReportarIncidenteUseCase(repositorio),
        registrar_orden_de_cambio=RegistrarOrdenDeCambioUseCase(repositorio, reloj),
        registrar_devolucion=RegistrarDevolucionUseCase(repositorio, registro, reloj),
        doble_verificacion=DobleVerificacionUseCase(repositorio, servicio_doble, autorizaciones),
        generar_reporte=GenerarReporteUseCase(repositorio, registro, reloj),
        registro_fases=registro,
    )
