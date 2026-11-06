import csv
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from dominio.servicios.specifications import (
    ActorActivoSpec, 
    ActorPreferenteSpec,
    AutorizacionSpec,
    MontoMinimoSpec,
    OperacionConLineasSpec,
    PromocionActivaSpec
)
from dominio.valores.value_objects import CotizacionId, OperadorId, ValorCarga
from dominio.errores.errores import (
    DomainException,
    CotizacionVencidaError,
    OperadorOcupadoError,
    AutorizacionRequeridaError,
    TransicionInvalidaError,
    CotizacionIdInvalidaError
)
from dominio.servicios.maquina_estados import MaquinaEstadosOperacion, EstadoOperacion
from dominio.entidades.entidades import Operador, Cotizacion, OrdenServicio

def load_fixtures():
    base_dir = Path(__file__).resolve().parent.parent / "datos"
    
    actores = {}
    p_actores = base_dir / "actores.csv"
    if p_actores.exists():
        with open(p_actores, mode='r', encoding='utf-8-sig') as f:
            for fila in csv.DictReader(f):
                f_limpia = {k.strip(): v.strip() for k, v in fila.items() if k}
                if "actor_id" in f_limpia:
                    actores[f_limpia["actor_id"]] = f_limpia

    catalogos = {}
    p_cat = base_dir / "catalogo.csv"
    if p_cat.exists():
        with open(p_cat, mode='r', encoding='utf-8-sig') as f:
            for fila in csv.DictReader(f):
                f_limpia = {k.strip(): v.strip() for k, v in fila.items() if k}
                if "recurso_id" in f_limpia:
                    catalogos[f_limpia["recurso_id"]] = f_limpia

    detalles = {}
    p_det = base_dir / "detalle_operaciones.csv"
    if p_det.exists():
        with open(p_det, mode='r', encoding='utf-8-sig') as f:
            for fila in csv.DictReader(f):
                f_limpia = {k.strip(): v.strip() for k, v in fila.items() if k}
                op_id = f_limpia.get("operacion_id")
                if op_id:
                    if op_id not in detalles:
                        detalles[op_id] = []
                    detalles[op_id].append({
                        "recurso_id": f_limpia.get("recurso_id"),
                        "cantidad": int(f_limpia.get("cantidad", 0))
                    })

    operaciones = {}
    p_op = base_dir / "operaciones.csv"
    if p_op.exists():
        with open(p_op, mode='r', encoding='utf-8-sig') as f:
            for fila in csv.DictReader(f):
                f_limpia = {k.strip(): v.strip() for k, v in fila.items() if k}
                op_id = f_limpia.get("operacion_id")
                if op_id:
                    operaciones[op_id] = {
                        "actor_id": f_limpia.get("actor_id"),
                        "estado_inicial": f_limpia.get("estado_inicial"),
                        "promocion_activa": bool(int(f_limpia.get("promocion_activa", 0))),
                        "autorizado": bool(int(f_limpia.get("autorizado", 0))),
                        "lineas": detalles.get(op_id, [])  # <--- Esto es lo que usa la regla de negocio
                    }

    return actores, catalogos, operaciones

def test_cargar_fixtures():
    actores, catalogo, operaciones = load_fixtures()
    assert len(actores) > 0
    assert len(catalogo) > 0
    assert len(operaciones) > 0

def test_especificacion_puede_procesarse():
    spec_puede_procesarse = ActorActivoSpec() & OperacionConLineasSpec() & AutorizacionSpec()
    actores, catalogo, operaciones = load_fixtures()
    
    for op_id, op_data in operaciones.items():
        actor_id = op_data["actor_id"]
        actor = actores.get(actor_id, {})
        
        contexto = {
            "actor": actor,
            "lineas": op_data["lineas"],
            "autorizado": op_data["autorizado"]
        }
        
        resultado = spec_puede_procesarse.is_satisfied_by(contexto)
        assert isinstance(resultado, bool)
        break


def test_especificacion_beneficio_referencia():
    spec_beneficio = ActorPreferenteSpec() & MontoMinimoSpec(Decimal("1500")) & (~PromocionActivaSpec())
    actores, catalogo, operaciones = load_fixtures()
    
    for op_id, op_data in operaciones.items():
        actor_id = op_data["actor_id"]
        actor = actores.get(actor_id, {})
        
        contexto = {
            "actor": actor,
            "valor_carga": Decimal("2000"),
            "promocion_activa": op_data["promocion_activa"]
        }
        
        resultado = spec_beneficio.is_satisfied_by(contexto)
        assert isinstance(resultado, bool)
        break

def test_value_objects():
    op = OperadorId(valor="OP-123")
    assert op.valor == "OP-123"
    with pytest.raises(ValueError):
        OperadorId(valor="")

    cot = CotizacionId(valor="COT-123")
    assert cot.valor == "COT-123"
    with pytest.raises(ValueError):
        CotizacionId(valor="")

    vc = ValorCarga(monto=Decimal("1500.00"))
    assert vc.monto == Decimal("1500.00")
    with pytest.raises(ValueError):
        ValorCarga(monto=Decimal("-5.00"))

def test_errores_dominio():
    with pytest.raises(DomainException):
        raise DomainException("Test error")
    with pytest.raises(CotizacionVencidaError):
        raise CotizacionVencidaError()
    with pytest.raises(OperadorOcupadoError):
        raise OperadorOcupadoError("Ocupado")
    with pytest.raises(AutorizacionRequeridaError):
        raise AutorizacionRequeridaError()

def test_maquina_estados():
    sig = MaquinaEstadosOperacion.validar_y_transicionar(
        EstadoOperacion.SOLICITADA, EstadoOperacion.COTIZADA
    )
    assert sig == EstadoOperacion.COTIZADA

    with pytest.raises(TransicionInvalidaError):
        MaquinaEstadosOperacion.validar_y_transicionar(
            EstadoOperacion.ENTREGADA, EstadoOperacion.EN_TRANSITO
        )

def test_entidades_dominio():
    op = Operador(operador_id=OperadorId("OP-01"), disponible=True, ruta_aceptada=True)
    op.verificar_disponibilidad()

    cot = Cotizacion(
        cotizacion_id=CotizacionId("COT-01"),
        fecha_emision=datetime.now() - timedelta(days=2),
        dias_vigencia=5
    )
    cot.validar_vigencia(datetime.now())

    orden = OrdenServicio(
        orden_id="ORD-01",
        cotizacion=cot,
        operador=op,
        direccion="Monterrey",
        valor_carga=ValorCarga(Decimal("5000"))
    )
    assert orden.fase == EstadoOperacion.REGISTRADO
    orden.cambiar_fase(EstadoOperacion.CONFIRMADA)
    assert orden.fase == EstadoOperacion.CONFIRMADA




