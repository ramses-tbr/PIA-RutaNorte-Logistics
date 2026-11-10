"""Pruebas de la interfaz web: rutas JSON y página, usando la API real con TestClient."""
import pytest
from fastapi.testclient import TestClient

from api.api import app

cliente = TestClient(app)


def _orden(orden_id, **extra):
    cuerpo = {"orden_id": orden_id, "direccion": "Monterrey/Apodaca", "valor_carga": "25000",
              "operador_id": "OP-UI", "cliente_id": "CLI-UI"}
    cuerpo.update(extra)
    return cliente.post("/api/ordenes", json=cuerpo)


def test_pagina_y_meta():
    r = cliente.get("/ui")
    assert r.status_code == 200 and "RutaNorte Logistics" in r.text
    meta = cliente.get("/api/meta").json()
    assert meta["ruta"][0] == "REGISTRADO" and meta["ruta"][-1] == "ENTREGADA"
    assert "EN TRANSITO" in meta["transiciones"]["RECOLECTADO"]


def test_lista_y_detalle_de_ordenes_del_csv():
    ordenes = cliente.get("/api/ordenes").json()["ordenes"]
    assert len(ordenes) > 0
    d = cliente.get(f"/api/ordenes/{ordenes[0]['orden_id']}")
    assert d.status_code == 200 and "historial" in d.json()


def test_orden_inexistente_da_404():
    r = cliente.get("/api/ordenes/NO-EXISTE")
    assert r.status_code == 404 and "no existe" in r.json()["error"]


def test_flujo_completo_hasta_entregada():
    assert _orden("UI-FLUJO").status_code == 200
    for fase in ["CONFIRMADA", "UNIDAD ASIGNADA", "RECOLECTADO", "EN TRANSITO", "LLEGADA A DESTINO", "ENTREGADA"]:
        r = cliente.post("/api/ordenes/UI-FLUJO/transicion", json={"nueva_fase": fase})
        assert r.status_code == 200, r.text
    assert r.json()["orden"]["fase"] == "ENTREGADA"
    assert len(r.json()["orden"]["historial"]) == 7


def test_transicion_invalida_da_409():
    _orden("UI-INVALIDA")
    r = cliente.post("/api/ordenes/UI-INVALIDA/transicion", json={"nueva_fase": "ENTREGADA"})
    assert r.status_code == 409 and r.json()["tipo"] == "TransicionInvalidaError"


def test_orden_duplicada_da_409_y_datos_invalidos_422():
    _orden("UI-DUP")
    assert _orden("UI-DUP").status_code == 409
    assert _orden("UI-MAL", valor_carga="abc").status_code == 422
    assert _orden("UI-MAL2", direccion="").status_code == 422
    assert _orden("UI-MAL3", operador_id="").status_code == 422


def test_cotizacion_vencida_y_operador_no_disponible():
    r = _orden("UI-VENC", dias_desde_emision=6)
    assert r.status_code == 409 and r.json()["tipo"] == "CotizacionVencidaError"
    r = _orden("UI-OCUP", operador_disponible=False)
    assert r.status_code == 409 and r.json()["tipo"] == "OperadorOcupadoError"


def test_alto_valor_exige_segunda_firma_para_entregar():
    r = _orden("UI-ALTO", valor_carga="250000")
    assert r.json()["orden"]["alto_valor"] is True
    for fase in ["CONFIRMADA", "UNIDAD ASIGNADA", "RECOLECTADO", "EN TRANSITO", "LLEGADA A DESTINO"]:
        cliente.post("/api/ordenes/UI-ALTO/transicion", json={"nueva_fase": fase})
    bloqueada = cliente.post("/api/ordenes/UI-ALTO/transicion", json={"nueva_fase": "ENTREGADA"})
    assert bloqueada.status_code == 409 and bloqueada.json()["tipo"] == "AutorizacionRequeridaError"
    sin_firma = cliente.post("/api/ordenes/UI-ALTO/doble-verificacion", json={})
    assert sin_firma.status_code == 409
    firma = cliente.post("/api/ordenes/UI-ALTO/doble-verificacion", json={"segunda_firma": "Gerente"})
    assert firma.status_code == 200 and firma.json()["orden"]["autorizada"] is True
    ok = cliente.post("/api/ordenes/UI-ALTO/transicion", json={"nueva_fase": "ENTREGADA"})
    assert ok.status_code == 200


def test_incidente_cambio_y_devolucion():
    _orden("UI-EVT")
    inc = cliente.post("/api/ordenes/UI-EVT/incidentes", json={"descripcion": "Llanta ponchada", "severidad": "CRITICA"})
    assert inc.status_code == 200 and inc.json()["orden"]["incidentes"] == 1
    assert cliente.post("/api/ordenes/UI-EVT/incidentes", json={"descripcion": "x", "severidad": "ALTA"}).status_code == 422
    assert cliente.post("/api/ordenes/UI-EVT/cambios", json={"motivo": "Nuevo destinatario"}).status_code == 200
    # Devolución solo en tránsito o llegada a destino
    assert cliente.post("/api/ordenes/UI-EVT/devolucion", json={"motivo": "Rechazada"}).status_code == 409
    for fase in ["CONFIRMADA", "UNIDAD ASIGNADA", "RECOLECTADO", "EN TRANSITO"]:
        cliente.post("/api/ordenes/UI-EVT/transicion", json={"nueva_fase": fase})
    dev = cliente.post("/api/ordenes/UI-EVT/devolucion", json={"motivo": "Rechazada"})
    assert dev.status_code == 200 and dev.json()["orden"]["fase"] == "EN DEVOLUCION"


def test_reporte():
    r = cliente.get("/api/reporte")
    assert r.status_code == 200
    cuerpo = r.json()
    assert {"generado_en", "rendimiento_por_operador", "estado_cuenta_por_cliente", "incidencias_por_ruta"} <= set(cuerpo)
