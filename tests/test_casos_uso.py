"""Pruebas de la capa de aplicación: los 7 casos de uso de RutaNorte Logistics.

Cada prueba usa un repositorio en memoria y un reloj controlado, así los tiempos son exactos.
Las últimas pruebas son de integración con el repositorio CSV real.
"""
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from aplicacion.casos_uso import (
    CasosDeUso,
    DobleVerificacionUseCase,
    ServicioDobleVerificacion,
    construir_casos_de_uso,
)
from aplicacion.errores import DatosInvalidosError, OrdenNoEncontradaError, OrdenYaExisteError
from aplicacion.registros import RegistroDeAutorizaciones, RegistroDeFases
from dominio.entidades.entidades import Cotizacion, Operador, OrdenServicio
from dominio.errores.errores import (
    AutorizacionRequeridaError,
    CotizacionVencidaError,
    DomainException,
    OperadorOcupadoError,
    TransicionInvalidaError,
)
from dominio.servicios.carga_alto_valor import CargaAltoValorSpec, UMBRAL_ALTO_VALOR_MXN
from dominio.servicios.maquina_estados import EstadoOperacion as E
from dominio.valores.value_objects import CotizacionId, OperadorId, ValorCarga
from infraestructura.repositorios.ordenes_repositorio import RepositorioOrdenesCSV

INICIO = datetime(2026, 11, 2, 8, 0, 0)
DATOS = Path(__file__).resolve().parent.parent / "datos"


# ----------------------------------------------------------------------------- apoyo
class RepositorioEnMemoria:
    def __init__(self):
        self.ordenes = {}

    def obtener_por_id(self, orden_id):
        return self.ordenes.get(orden_id)

    def guardar(self, orden):
        self.ordenes[orden.orden_id] = orden

    def listar_todas(self):
        return list(self.ordenes.values())


class RelojControlado:
    def __init__(self, inicio=INICIO):
        self.ahora = inicio

    def __call__(self):
        return self.ahora

    def avanzar(self, **kwargs):
        self.ahora += timedelta(**kwargs)


def operador(id_="OP-1", disponible=True, ruta_aceptada=True):
    return Operador(OperadorId(id_), disponible=disponible, ruta_aceptada=ruta_aceptada)


def cotizacion(id_="COT-1", dias_atras=0, dias_vigencia=5):
    return Cotizacion(CotizacionId(id_), INICIO - timedelta(days=dias_atras), dias_vigencia)


def carga(monto="5000"):
    return ValorCarga(Decimal(monto))


@pytest.fixture
def repo():
    return RepositorioEnMemoria()


@pytest.fixture
def reloj():
    return RelojControlado()


@pytest.fixture
def cu(repo, reloj) -> CasosDeUso:
    return construir_casos_de_uso(repo, reloj)


def registrar(cu, orden_id="ORD-1", op="OP-1", monto="5000", cliente="CLI-1", direccion="Monterrey/Apodaca"):
    return cu.registrar_orden.ejecutar(
        orden_id, cotizacion(f"COT-{orden_id}"), operador(op), direccion, carga(monto), cliente)


def llevar_a(cu, orden_id, destino):
    """Avanza la orden por el camino normal hasta la fase indicada."""
    camino = [E.CONFIRMADA, E.UNIDAD_ASIGNADA, E.RECOLECTADO, E.EN_TRANSITO, E.LLEGADA_A_DESTINO, E.ENTREGADA]
    for fase in camino:
        cu.transicionar_fase.ejecutar(orden_id, fase)
        if fase == destino:
            return
    raise AssertionError(f"{destino} no está en el camino normal")


# ----------------------------------------------------------------------------- 1. RegistrarOrden
class TestRegistrarOrden:
    def test_registra_en_fase_registrado(self, cu, repo):
        dto = registrar(cu)
        assert dto.fase == "REGISTRADO"
        assert dto.operador_id == "OP-1"
        assert dto.cliente_id == "CLI-1"
        assert repo.obtener_por_id("ORD-1").fase == E.REGISTRADO

    def test_guarda_la_hora_de_registro(self, cu):
        registrar(cu)
        historial = cu.registro_fases.historial("ORD-1")
        assert len(historial) == 1
        assert historial[0].fase_origen is None
        assert historial[0].fase_destino == "REGISTRADO"
        assert historial[0].momento == INICIO

    def test_cotizacion_vencida_se_rechaza_y_no_se_guarda(self, cu, repo):
        with pytest.raises(CotizacionVencidaError):
            cu.registrar_orden.ejecutar("ORD-1", cotizacion(dias_atras=6), operador(), "Monterrey", carga())
        assert repo.listar_todas() == []

    def test_cotizacion_en_el_ultimo_dia_de_vigencia_es_valida(self, cu):
        cu.registrar_orden.ejecutar("ORD-1", cotizacion(dias_atras=5), operador(), "Monterrey", carga())

    def test_operador_ocupado_se_rechaza(self, cu, repo):
        with pytest.raises(OperadorOcupadoError):
            cu.registrar_orden.ejecutar("ORD-1", cotizacion(), operador(disponible=False), "Monterrey", carga())
        assert repo.listar_todas() == []

    def test_operador_que_no_acepto_la_ruta_se_rechaza(self, cu):
        with pytest.raises(OperadorOcupadoError):
            cu.registrar_orden.ejecutar("ORD-1", cotizacion(), operador(ruta_aceptada=False), "Monterrey", carga())

    def test_orden_duplicada(self, cu):
        registrar(cu)
        with pytest.raises(OrdenYaExisteError):
            registrar(cu)

    @pytest.mark.parametrize("orden_id,direccion", [("", "Monterrey"), ("  ", "Monterrey"), ("ORD-9", ""), ("ORD-9", None)])
    def test_datos_obligatorios(self, cu, orden_id, direccion):
        with pytest.raises(DatosInvalidosError):
            cu.registrar_orden.ejecutar(orden_id, cotizacion(), operador(), direccion, carga())


# ----------------------------------------------------------------------------- 2. TransicionarFase
class TestTransicionarFase:
    def test_ciclo_completo_registra_la_hora_de_cada_fase(self, cu, reloj):
        registrar(cu)
        fases = [E.CONFIRMADA, E.UNIDAD_ASIGNADA, E.RECOLECTADO, E.EN_TRANSITO, E.LLEGADA_A_DESTINO, E.ENTREGADA]
        for fase in fases:
            reloj.avanzar(hours=2)
            dto = cu.transicionar_fase.ejecutar("ORD-1", fase)
            assert dto.fase_nueva == fase.value
            assert dto.momento == reloj.ahora
        historial = cu.registro_fases.historial("ORD-1")
        assert [h.fase_destino for h in historial] == ["REGISTRADO"] + [f.value for f in fases]
        assert historial[-1].momento - historial[0].momento == timedelta(hours=12)

    def test_transicion_ilegal_no_cambia_nada(self, cu, repo):
        registrar(cu)
        with pytest.raises(TransicionInvalidaError):
            cu.transicionar_fase.ejecutar("ORD-1", E.ENTREGADA)  # nunca salió de almacén
        assert repo.obtener_por_id("ORD-1").fase == E.REGISTRADO
        assert len(cu.registro_fases.historial("ORD-1")) == 1

    def test_fase_final_no_admite_mas_cambios(self, cu):
        registrar(cu)
        cu.transicionar_fase.ejecutar("ORD-1", E.CANCELADA)
        with pytest.raises(TransicionInvalidaError):
            cu.transicionar_fase.ejecutar("ORD-1", E.CONFIRMADA)

    def test_orden_inexistente(self, cu):
        with pytest.raises(OrdenNoEncontradaError):
            cu.transicionar_fase.ejecutar("NO-EXISTE", E.CONFIRMADA)

    @pytest.mark.parametrize("fase", ["CONFIRMADA", "confirmada", " Confirmada "])
    def test_acepta_la_fase_como_texto(self, cu, fase):
        registrar(cu)
        assert cu.transicionar_fase.ejecutar("ORD-1", fase).fase_nueva == "CONFIRMADA"

    def test_acepta_valor_con_espacio_y_nombre_con_guion_bajo(self, cu):
        registrar(cu)
        cu.transicionar_fase.ejecutar("ORD-1", "UNIDAD ASIGNADA")
        cu.transicionar_fase.ejecutar("ORD-1", "RECOLECTADO")
        assert cu.transicionar_fase.ejecutar("ORD-1", "EN_TRANSITO").fase_nueva == "EN TRANSITO"

    @pytest.mark.parametrize("fase", ["VOLANDO", "", None, 7])
    def test_fase_inexistente(self, cu, fase):
        registrar(cu)
        with pytest.raises(DatosInvalidosError):
            cu.transicionar_fase.ejecutar("ORD-1", fase)

    def test_carga_de_alto_valor_no_se_entrega_sin_segunda_firma(self, cu, repo):
        registrar(cu, monto="150000")
        llevar_a(cu, "ORD-1", E.LLEGADA_A_DESTINO)
        with pytest.raises(AutorizacionRequeridaError):
            cu.transicionar_fase.ejecutar("ORD-1", E.ENTREGADA)
        assert repo.obtener_por_id("ORD-1").fase == E.LLEGADA_A_DESTINO

    def test_carga_de_alto_valor_se_entrega_con_doble_verificacion(self, cu, repo):
        registrar(cu, monto="150000")
        llevar_a(cu, "ORD-1", E.LLEGADA_A_DESTINO)
        cu.doble_verificacion.ejecutar("ORD-1", "FIRMA-GERENTE")
        cu.transicionar_fase.ejecutar("ORD-1", E.ENTREGADA)
        assert repo.obtener_por_id("ORD-1").fase == E.ENTREGADA

    def test_alto_valor_solo_se_exige_al_entregar(self, cu):
        registrar(cu, monto="150000")
        assert cu.transicionar_fase.ejecutar("ORD-1", E.CONFIRMADA).fase_nueva == "CONFIRMADA"

    def test_transicion_ilegal_tiene_prioridad_sobre_la_autorizacion(self, cu):
        registrar(cu, monto="150000")
        with pytest.raises(TransicionInvalidaError):
            cu.transicionar_fase.ejecutar("ORD-1", E.ENTREGADA)


# ----------------------------------------------------------------------------- 3. ReportarIncidente
class TestReportarIncidente:
    def test_vincula_el_incidente_a_la_orden(self, cu, repo):
        registrar(cu)
        dto = cu.reportar_incidente.ejecutar("ORD-1", "Falla mecánica en la carretera", "MEDIA")
        orden = repo.obtener_por_id("ORD-1")
        assert len(orden.incidentes) == 1
        assert orden.incidentes[0].orden_id == "ORD-1"
        assert orden.incidentes[0].severidad == "MEDIA"
        assert dto.incidente_id.startswith("INC-")

    @pytest.mark.parametrize("texto,esperado", [("baja", "BAJA"), ("Media", "MEDIA"), ("crítica", "CRITICA"), (" CRITICA ", "CRITICA")])
    def test_normaliza_la_severidad(self, cu, texto, esperado):
        registrar(cu)
        assert cu.reportar_incidente.ejecutar("ORD-1", "Retraso", texto).severidad == esperado

    def test_acepta_un_id_propio(self, cu):
        registrar(cu)
        assert cu.reportar_incidente.ejecutar("ORD-1", "Retraso", "BAJA", incidente_id="INC-99").incidente_id == "INC-99"

    @pytest.mark.parametrize("severidad", ["GRAVE", "", None])
    def test_severidad_invalida(self, cu, severidad):
        registrar(cu)
        with pytest.raises(DatosInvalidosError):
            cu.reportar_incidente.ejecutar("ORD-1", "Retraso", severidad)

    def test_descripcion_vacia(self, cu):
        registrar(cu)
        with pytest.raises(DatosInvalidosError):
            cu.reportar_incidente.ejecutar("ORD-1", "  ", "BAJA")

    def test_orden_inexistente(self, cu):
        with pytest.raises(OrdenNoEncontradaError):
            cu.reportar_incidente.ejecutar("NO-EXISTE", "Retraso", "BAJA")


# ----------------------------------------------------------------------------- 4. RegistrarOrdenDeCambio
class TestRegistrarOrdenDeCambio:
    def test_registra_el_cambio_con_su_hora(self, cu, repo, reloj):
        registrar(cu)
        reloj.avanzar(hours=1)
        dto = cu.registrar_orden_de_cambio.ejecutar("ORD-1", "Cambio de destinatario")
        cambios = repo.obtener_por_id("ORD-1").ordenes_cambio
        assert len(cambios) == 1
        assert cambios[0].motivo == "Cambio de destinatario"
        assert cambios[0].fecha_registro == reloj.ahora
        assert dto.cambio_id.startswith("CAM-")

    def test_acepta_un_id_propio(self, cu):
        registrar(cu)
        assert cu.registrar_orden_de_cambio.ejecutar("ORD-1", "Cambio de ruta", cambio_id="CAM-7").cambio_id == "CAM-7"

    @pytest.mark.parametrize("fase_final", [E.ENTREGADA, E.CANCELADA])
    def test_el_dominio_rechaza_cambios_en_ordenes_terminadas(self, cu, repo, fase_final):
        registrar(cu)
        if fase_final == E.ENTREGADA:
            llevar_a(cu, "ORD-1", E.ENTREGADA)
        else:
            cu.transicionar_fase.ejecutar("ORD-1", E.CANCELADA)
        with pytest.raises(DomainException):
            cu.registrar_orden_de_cambio.ejecutar("ORD-1", "Tarde")
        assert repo.obtener_por_id("ORD-1").ordenes_cambio == []

    def test_motivo_vacio(self, cu):
        registrar(cu)
        with pytest.raises(DatosInvalidosError):
            cu.registrar_orden_de_cambio.ejecutar("ORD-1", "")

    def test_orden_inexistente(self, cu):
        with pytest.raises(OrdenNoEncontradaError):
            cu.registrar_orden_de_cambio.ejecutar("NO-EXISTE", "Cambio")


# ----------------------------------------------------------------------------- 5. RegistrarDevolucion
class TestRegistrarDevolucion:
    @pytest.mark.parametrize("fase", [E.EN_TRANSITO, E.LLEGADA_A_DESTINO])
    def test_devolucion_en_fases_avanzadas(self, cu, repo, reloj, fase):
        registrar(cu)
        llevar_a(cu, "ORD-1", fase)
        reloj.avanzar(hours=3)
        dto = cu.registrar_devolucion.ejecutar("ORD-1", "El cliente rechazó la mercancía")
        orden = repo.obtener_por_id("ORD-1")
        assert orden.fase == E.EN_DEVOLUCION
        assert dto.fase_orden == "EN DEVOLUCION"
        assert dto.devolucion_id.startswith("DEV-")
        assert len(orden.ordenes_devolucion) == 1
        assert orden.ordenes_devolucion[0].estado == "PENDIENTE"
        ultimo = cu.registro_fases.historial("ORD-1")[-1]
        assert (ultimo.fase_origen, ultimo.fase_destino, ultimo.momento) == (fase.value, "EN DEVOLUCION", reloj.ahora)

    def test_acepta_un_id_propio(self, cu):
        registrar(cu)
        llevar_a(cu, "ORD-1", E.EN_TRANSITO)
        assert cu.registrar_devolucion.ejecutar("ORD-1", "Rechazo", devolucion_id="DEV-5").devolucion_id == "DEV-5"

    @pytest.mark.parametrize("fase", [E.REGISTRADO, E.UNIDAD_ASIGNADA, E.ENTREGADA])
    def test_el_dominio_rechaza_devoluciones_fuera_de_transito_o_destino(self, cu, repo, fase):
        registrar(cu)
        if fase != E.REGISTRADO:
            llevar_a(cu, "ORD-1", fase)
        with pytest.raises(DomainException):
            cu.registrar_devolucion.ejecutar("ORD-1", "Rechazo")
        orden = repo.obtener_por_id("ORD-1")
        assert orden.fase == fase
        assert orden.ordenes_devolucion == []

    def test_motivo_vacio(self, cu):
        registrar(cu)
        with pytest.raises(DatosInvalidosError):
            cu.registrar_devolucion.ejecutar("ORD-1", " ")

    def test_orden_inexistente(self, cu):
        with pytest.raises(OrdenNoEncontradaError):
            cu.registrar_devolucion.ejecutar("NO-EXISTE", "Rechazo")


# ----------------------------------------------------------------------------- 6. DobleVerificacion
class TestDobleVerificacion:
    def test_carga_normal_no_la_requiere(self, cu):
        registrar(cu, monto="5000")
        dto = cu.doble_verificacion.ejecutar("ORD-1")
        assert (dto.requiere_doble_verificacion, dto.autorizada) == (False, True)

    def test_alto_valor_sin_firma_exige_autorizacion(self, cu):
        registrar(cu, monto="150000")
        with pytest.raises(AutorizacionRequeridaError):
            cu.doble_verificacion.ejecutar("ORD-1")

    @pytest.mark.parametrize("firma", [None, "", "   "])
    def test_firma_vacia_no_cuenta(self, cu, firma):
        registrar(cu, monto="150000")
        with pytest.raises(AutorizacionRequeridaError):
            cu.doble_verificacion.ejecutar("ORD-1", firma)

    def test_alto_valor_con_segunda_firma(self, cu):
        registrar(cu, monto="150000")
        dto = cu.doble_verificacion.ejecutar("ORD-1", " FIRMA-GERENTE ")
        assert (dto.requiere_doble_verificacion, dto.autorizada) == (True, True)

    def test_el_umbral_es_estricto(self):
        spec = CargaAltoValorSpec()
        base = dict(cotizacion=cotizacion(), operador=operador(), direccion="X", orden_id="O")
        assert not spec.is_satisfied_by(OrdenServicio(valor_carga=ValorCarga(UMBRAL_ALTO_VALOR_MXN), **base))
        assert spec.is_satisfied_by(OrdenServicio(valor_carga=ValorCarga(UMBRAL_ALTO_VALOR_MXN + Decimal("0.01")), **base))

    def test_umbral_personalizable(self, repo):
        autorizaciones = RegistroDeAutorizaciones()
        servicio = ServicioDobleVerificacion(autorizaciones, CargaAltoValorSpec(Decimal("1000")))
        caso = DobleVerificacionUseCase(repo, servicio, autorizaciones)
        repo.guardar(OrdenServicio("O-1", cotizacion(), operador(), "X", carga("2000")))
        with pytest.raises(AutorizacionRequeridaError):
            caso.ejecutar("O-1")

    def test_orden_inexistente(self, cu):
        with pytest.raises(OrdenNoEncontradaError):
            cu.doble_verificacion.ejecutar("NO-EXISTE", "FIRMA")


# ----------------------------------------------------------------------------- 7. GenerarReporte
class TestGenerarReporte:
    def escenario(self, cu, reloj):
        # OP-1: una entregada en 10 h, una cancelada, una en curso; OP-2: una en devolución.
        registrar(cu, "ORD-1", "OP-1", "1000", "CLI-A", "Monterrey/Apodaca")
        reloj.avanzar(hours=4)
        llevar_a(cu, "ORD-1", E.LLEGADA_A_DESTINO)
        reloj.avanzar(hours=6)
        cu.transicionar_fase.ejecutar("ORD-1", E.ENTREGADA)

        registrar(cu, "ORD-2", "OP-1", "2000", "CLI-A", "Monterrey/Saltillo")
        cu.transicionar_fase.ejecutar("ORD-2", E.CANCELADA)

        registrar(cu, "ORD-3", "OP-1", "3000", "CLI-A", "Monterrey/Saltillo")
        cu.transicionar_fase.ejecutar("ORD-3", E.CONFIRMADA)

        registrar(cu, "ORD-4", "OP-2", "500", None, "Monterrey/Apodaca")
        llevar_a(cu, "ORD-4", E.EN_TRANSITO)
        cu.registrar_devolucion.ejecutar("ORD-4", "Rechazo")

        cu.reportar_incidente.ejecutar("ORD-1", "Retraso por lluvia", "BAJA")
        cu.reportar_incidente.ejecutar("ORD-3", "Accidente", "CRITICA")
        cu.reportar_incidente.ejecutar("ORD-3", "Falla mecánica", "CRITICA")
        cu.reportar_incidente.ejecutar("ORD-4", "Falla mecánica", "CRITICA")

    def test_rendimiento_por_operador(self, cu, reloj):
        self.escenario(cu, reloj)
        op1, op2 = cu.generar_reporte.rendimiento_por_operador()
        assert op1.operador_id == "OP-1"
        assert (op1.total_ordenes, op1.entregadas, op1.canceladas, op1.en_devolucion, op1.en_curso) == (3, 1, 1, 0, 1)
        assert (op1.incidentes, op1.incidentes_criticos) == (3, 2)
        assert op1.tasa_entrega_pct == Decimal("33.33")
        assert op1.tiempo_promedio_entrega_horas == Decimal("10.00")
        assert op2.operador_id == "OP-2"
        assert (op2.total_ordenes, op2.entregadas, op2.en_devolucion, op2.en_curso) == (1, 0, 1, 0)
        assert op2.tasa_entrega_pct == Decimal("0.00")
        assert op2.tiempo_promedio_entrega_horas is None

    def test_estado_de_cuenta_por_cliente(self, cu, reloj):
        self.escenario(cu, reloj)
        cuentas = {c.cliente_id: c for c in cu.generar_reporte.estado_cuenta_por_cliente()}
        a = cuentas["CLI-A"]
        assert a.total_ordenes == 3
        assert a.valor_total == Decimal("6000")
        assert a.valor_entregado == Decimal("1000")
        assert a.valor_cancelado_o_devuelto == Decimal("2000")
        assert a.valor_en_curso == Decimal("3000")
        sin = cuentas["SIN CLIENTE"]
        assert (sin.total_ordenes, sin.valor_cancelado_o_devuelto) == (1, Decimal("500"))

    def test_incidencias_criticas_por_ruta_ordenadas(self, cu, reloj):
        self.escenario(cu, reloj)
        rutas = cu.generar_reporte.incidencias_criticas_por_ruta()
        assert [(r.ruta, r.incidentes_totales, r.incidentes_criticos) for r in rutas] == [
            ("Monterrey/Saltillo", 2, 2),
            ("Monterrey/Apodaca", 2, 1),
        ]

    def test_tiempos_de_cada_fase(self, cu, reloj):
        self.escenario(cu, reloj)
        duraciones = cu.generar_reporte.tiempos_de_fase("ORD-1")
        assert duraciones[0] == ("REGISTRADO", timedelta(hours=4))
        assert duraciones[-1][0] == "ENTREGADA"
        assert sum((d for _, d in duraciones), timedelta()) == reloj.ahora - INICIO

    def test_tiempos_de_una_orden_inexistente(self, cu):
        with pytest.raises(OrdenNoEncontradaError):
            cu.generar_reporte.tiempos_de_fase("NO-EXISTE")

    def test_reporte_completo(self, cu, reloj):
        self.escenario(cu, reloj)
        reporte = cu.generar_reporte.generar()
        assert reporte.generado_en == reloj.ahora
        assert len(reporte.rendimiento_por_operador) == 2
        assert len(reporte.estado_cuenta_por_cliente) == 2
        assert len(reporte.incidencias_por_ruta) == 2

    def test_reporte_sin_ordenes(self, cu):
        reporte = cu.generar_reporte.generar()
        assert reporte.rendimiento_por_operador == []
        assert reporte.estado_cuenta_por_cliente == []
        assert reporte.incidencias_por_ruta == []

    def test_ordenes_vencidas_no_cuentan_como_en_curso(self, cu, repo):
        repo.guardar(OrdenServicio("O-V", cotizacion(), operador("OP-9"), "X", carga("100"), fase=E.VENCIDA))
        (op,) = cu.generar_reporte.rendimiento_por_operador()
        assert (op.total_ordenes, op.en_curso) == (1, 0)
        (cuenta,) = cu.generar_reporte.estado_cuenta_por_cliente()
        assert cuenta.valor_cancelado_o_devuelto == Decimal("100")


# ----------------------------------------------------------------------------- registros
class TestRegistroDeFases:
    def test_sin_historial(self):
        registro = RegistroDeFases()
        assert registro.historial("X") == []
        assert registro.duraciones("X", INICIO) == []
        assert registro.tiempo_hasta("X", "ENTREGADA") is None

    def test_fase_a_la_que_nunca_llego(self):
        registro = RegistroDeFases()
        registro.registrar("X", None, "REGISTRADO", INICIO)
        assert registro.tiempo_hasta("X", "ENTREGADA") is None

    def test_la_fase_actual_se_mide_hasta_ahora(self):
        registro = RegistroDeFases()
        registro.registrar("X", None, "REGISTRADO", INICIO)
        assert registro.duraciones("X", INICIO + timedelta(hours=5)) == [("REGISTRADO", timedelta(hours=5))]


class TestRegistroDeAutorizaciones:
    def test_registra_y_consulta(self):
        autorizaciones = RegistroDeAutorizaciones()
        assert not autorizaciones.tiene("O-1")
        assert autorizaciones.firma_de("O-1") is None
        autorizaciones.registrar("O-1", "FIRMA")
        assert autorizaciones.tiene("O-1")
        assert autorizaciones.firma_de("O-1") == "FIRMA"


# ----------------------------------------------------------------------------- integración con el CSV real
class TestIntegracionConRepositorioCSV:
    def test_transicionar_una_orden_cargada_desde_el_csv(self):
        repositorio = RepositorioOrdenesCSV(str(DATOS / "operaciones.csv"))
        cu = construir_casos_de_uso(repositorio, RelojControlado())
        dto = cu.transicionar_fase.ejecutar("ENV-O001", E.CONFIRMADA)
        assert dto.fase_anterior == "REGISTRADO"
        assert repositorio.obtener_por_id("ENV-O001").fase == E.CONFIRMADA

    def test_orden_del_csv_inexistente(self):
        repositorio = RepositorioOrdenesCSV(str(DATOS / "operaciones.csv"))
        cu = construir_casos_de_uso(repositorio, RelojControlado())
        with pytest.raises(OrdenNoEncontradaError):
            cu.transicionar_fase.ejecutar("ENV-O999", E.CONFIRMADA)

    def test_el_reporte_cubre_todas_las_ordenes_del_csv(self):
        repositorio = RepositorioOrdenesCSV(str(DATOS / "operaciones.csv"))
        cu = construir_casos_de_uso(repositorio, RelojControlado())
        with open(DATOS / "operaciones.csv", encoding="utf-8-sig") as archivo:
            esperadas = sum(1 for _ in csv.DictReader(archivo))
        total = len(repositorio.listar_todas())
        assert total == esperadas > 0  # si da 0, el repositorio no pudo leer el archivo
        reporte = cu.generar_reporte.generar()
        assert sum(o.total_ordenes for o in reporte.rendimiento_por_operador) == total
        assert sum(c.total_ordenes for c in reporte.estado_cuenta_por_cliente) == total

    def test_registrar_orden_nueva_y_guardarla_en_el_repositorio_csv(self):
        repositorio = RepositorioOrdenesCSV(str(DATOS / "operaciones.csv"))
        cu = construir_casos_de_uso(repositorio, RelojControlado())
        registrar(cu, "NUEVA-1")
        assert repositorio.obtener_por_id("NUEVA-1").fase == E.REGISTRADO
