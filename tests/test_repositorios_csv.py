"""Pruebas de los repositorios CSV (infraestructura).

Los archivos de datos/ vienen guardados con BOM de UTF-8; si el repositorio los abre con
encoding='utf-8' el encabezado queda como '\\ufeffoperacion_id' y NO carga ninguna fila.
"""
from pathlib import Path

from dominio.servicios.maquina_estados import EstadoOperacion as E
from infraestructura.repositorios.actores_repositorio import RepositorioActoresCSV
from infraestructura.repositorios.ordenes_repositorio import RepositorioOrdenesCSV

DATOS = Path(__file__).resolve().parent.parent / "datos"


def test_actores_se_cargan_desde_el_csv_con_bom():
    repositorio = RepositorioActoresCSV(str(DATOS / "actores.csv"))
    actor = repositorio.obtener_por_id("ENV-C001")
    assert actor["nombre"] == "Cliente 01"
    assert repositorio.obtener_por_id("NO-EXISTE") is None


def test_actores_con_archivo_inexistente_queda_vacio(tmp_path):
    repositorio = RepositorioActoresCSV(str(tmp_path / "no_existe.csv"))
    assert repositorio.obtener_por_id("ENV-C001") is None


def test_ordenes_con_archivo_inexistente_queda_vacio(tmp_path):
    repositorio = RepositorioOrdenesCSV(str(tmp_path / "no_existe.csv"))
    assert repositorio.listar_todas() == []


def test_ordenes_ignora_filas_sin_id_y_usa_registrado_si_la_fase_no_existe(tmp_path):
    archivo = tmp_path / "operaciones.csv"
    archivo.write_text(
        "operacion_id,actor_id,estado_inicial\n"
        ",ACT-1,REGISTRADO\n"            # sin id: se ignora
        "OP-1,ACT-1,CONFIRMADA\n"        # fase válida
        "OP-2,ACT-2,FASE_RARA\n",        # fase inexistente: cae en REGISTRADO
        encoding="utf-8",
    )
    repositorio = RepositorioOrdenesCSV(str(archivo))
    assert sorted(o.orden_id for o in repositorio.listar_todas()) == ["OP-1", "OP-2"]
    assert repositorio.obtener_por_id("OP-1").fase == E.CONFIRMADA
    assert repositorio.obtener_por_id("OP-2").fase == E.REGISTRADO


def test_guardar_y_recuperar_una_orden():
    repositorio = RepositorioOrdenesCSV(str(DATOS / "operaciones.csv"))
    orden = repositorio.obtener_por_id("ENV-O001")
    orden.cambiar_fase(E.CONFIRMADA)
    repositorio.guardar(orden)
    assert repositorio.obtener_por_id("ENV-O001").fase == E.CONFIRMADA
