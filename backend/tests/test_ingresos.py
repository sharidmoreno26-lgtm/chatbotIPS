import datetime as dt

import pytest


def cuerpo(hoy, **cambios):
    base = {
        "medicamento_id": 1,
        "cantidad": 100,
        "lote": "L-2026-041",
        "fecha_vencimiento": str(hoy + dt.timedelta(days=100)),
        "fecha_ingreso": str(hoy),
    }
    base.update(cambios)
    return base


NUEVO = {
    "nombre": "Ranitidina",
    "principio_activo": "Ranitidina clorhidrato",
    "presentacion": "Tabletas 150 mg",
    "stock_minimo": 20,
    "ubicacion": "Estante E1",
}


def _movimiento_por_lote(client, cab, lote):
    return next(m for m in client.get("/movimientos", headers=cab).json() if m["lote"] == lote)


def test_ingreso_a_medicamento_existente(client, farmacia, hoy):
    r = client.post("/ingresos", headers=farmacia, json=cuerpo(hoy))
    assert r.status_code == 201
    datos = r.json()
    assert datos["medicamento_id"] == 1
    assert datos["cantidad_actual"] == 115
    inv = client.get("/medicamentos/1/inventario", headers=farmacia).json()
    assert inv["cantidad_actual"] == 115
    mov = _movimiento_por_lote(client, farmacia, "L-2026-041")
    assert mov["tipo"] == "ENTRADA" and mov["cantidad"] == 100
    assert mov["fecha_vencimiento"] == str(hoy + dt.timedelta(days=100))
    assert mov["usuario"] == "Responsable de Farmacia Demo"
    assert mov["fecha"].startswith(str(hoy))


def test_el_responsable_sale_del_token_y_no_del_cuerpo(client, almacen, hoy):
    r = client.post("/ingresos", headers=almacen, json=cuerpo(hoy, usuario_id=1, responsable="Otra Persona"))
    assert r.status_code == 201
    assert _movimiento_por_lote(client, almacen, "L-2026-041")["usuario"] == "Almacenista Demo"


def test_la_fecha_de_ingreso_pasada_se_respeta(client, farmacia, hoy):
    antes = hoy - dt.timedelta(days=3)
    client.post("/ingresos", headers=farmacia, json=cuerpo(hoy, fecha_ingreso=str(antes)))
    assert _movimiento_por_lote(client, farmacia, "L-2026-041")["fecha"].startswith(str(antes))


def test_vencimiento_toma_el_mas_proximo(client, farmacia, hoy):
    # lote que vence antes que el actual (hoy+400) -> el medicamento pasa a vencer con el lote
    client.post("/ingresos", headers=farmacia, json=cuerpo(hoy))
    med = client.get("/medicamentos/1", headers=farmacia).json()
    assert med["fecha_vencimiento"] == str(hoy + dt.timedelta(days=100))


def test_vencimiento_se_conserva_si_el_lote_vence_despues(client, farmacia, hoy):
    lejos = str(hoy + dt.timedelta(days=900))
    client.post("/ingresos", headers=farmacia, json=cuerpo(hoy, fecha_vencimiento=lejos))
    med = client.get("/medicamentos/1", headers=farmacia).json()
    assert med["fecha_vencimiento"] == str(hoy + dt.timedelta(days=400))


def test_si_el_actual_ya_vencio_toma_el_del_lote(client, farmacia, conn, hoy):
    conn.execute("UPDATE medicamentos SET fecha_vencimiento = CURRENT_DATE - 5 WHERE id = 1")
    conn.commit()
    lote_vence = str(hoy + dt.timedelta(days=50))
    client.post("/ingresos", headers=farmacia, json=cuerpo(hoy, fecha_vencimiento=lote_vence))
    assert client.get("/medicamentos/1", headers=farmacia).json()["fecha_vencimiento"] == lote_vence


def test_ingreso_de_medicamento_nuevo(client, almacen, hoy):
    r = client.post("/ingresos", headers=almacen,
                    json=cuerpo(hoy, medicamento_id=None, nuevo_medicamento=NUEVO, cantidad=40))
    assert r.status_code == 201
    med_id = r.json()["medicamento_id"]
    assert r.json()["cantidad_actual"] == 40
    med = client.get(f"/medicamentos/{med_id}", headers=almacen).json()
    assert med["nombre"] == "Ranitidina" and med["ubicacion"] == "Estante E1"
    assert med["stock_minimo"] == 20 and med["cantidad_actual"] == 40
    assert med["fecha_vencimiento"] == str(hoy + dt.timedelta(days=100))
    assert len(client.get("/medicamentos", headers=almacen).json()) == 13


def test_nombre_repetido_da_409_sin_crear_nada(client, farmacia, conn, hoy):
    for nombre in ("Amoxicilina", "AMOXICILINA", "amoxicilina", "  Amoxicilina  "):
        r = client.post("/ingresos", headers=farmacia,
                        json=cuerpo(hoy, medicamento_id=None, nuevo_medicamento={**NUEVO, "nombre": nombre}))
        assert r.status_code == 409, nombre
    assert conn.execute("SELECT count(*) AS n FROM medicamentos").fetchone()["n"] == 12
    assert conn.execute("SELECT count(*) AS n FROM movimientos").fetchone()["n"] == 15


def test_medicamento_inexistente_da_404(client, farmacia, hoy):
    assert client.post("/ingresos", headers=farmacia, json=cuerpo(hoy, medicamento_id=9999)).status_code == 404


def test_solo_farmacia_y_almacenista(client, admin, hoy):
    assert client.post("/ingresos", headers=admin, json=cuerpo(hoy)).status_code == 403
    assert client.post("/ingresos", json=cuerpo(hoy)).status_code == 401


def test_exactamente_un_medicamento(client, farmacia, hoy):
    ambos = cuerpo(hoy, nuevo_medicamento=NUEVO)
    ninguno = cuerpo(hoy, medicamento_id=None)
    for malo in (ambos, ninguno):
        r = client.post("/ingresos", headers=farmacia, json=malo)
        assert r.status_code == 422
        assert isinstance(r.json()["detail"], str)


def test_fechas_invalidas_dan_422(client, farmacia, hoy):
    d = dt.timedelta
    casos = [
        cuerpo(hoy, fecha_ingreso=str(hoy + d(days=1)), fecha_vencimiento=str(hoy + d(days=30))),  # ingreso futuro
        cuerpo(hoy, fecha_vencimiento=str(hoy)),                                                   # vence el mismo día del ingreso
        cuerpo(hoy, fecha_vencimiento=str(hoy - d(days=1))),                                       # antes del ingreso
        cuerpo(hoy, fecha_ingreso=str(hoy - d(days=10)), fecha_vencimiento=str(hoy - d(days=1))),  # lote ya vencido
        cuerpo(hoy, fecha_vencimiento="no-es-fecha"),
        cuerpo(hoy, fecha_ingreso="2026-13-45"),
    ]
    for malo in casos:
        assert client.post("/ingresos", headers=farmacia, json=malo).status_code == 422, malo


@pytest.mark.parametrize("cambios", [
    {"cantidad": 0}, {"cantidad": -1}, {"cantidad": 100001}, {"cantidad": "abc"}, {"cantidad": 1.5},
    {"lote": ""}, {"lote": "   "}, {"lote": "a" * 41}, {"lote": "lote con espacio"},
    {"lote": "L1'; DROP TABLE medicamentos; --"}, {"lote": "L\u0000X"}, {"lote": "L😀"},
    {"medicamento_id": 0}, {"medicamento_id": -3},
])
def test_datos_del_ingreso_invalidos_dan_422(client, farmacia, conn, hoy, cambios):
    assert client.post("/ingresos", headers=farmacia, json=cuerpo(hoy, **cambios)).status_code == 422
    assert conn.execute("SELECT count(*) AS n FROM movimientos").fetchone()["n"] == 15
    assert conn.execute("SELECT cantidad_actual AS c FROM medicamentos WHERE id = 1").fetchone()["c"] == 15


@pytest.mark.parametrize("cambios", [
    {"nombre": ""}, {"nombre": "   "}, {"nombre": "N\u0000M"}, {"nombre": "x" * 81},
    {"principio_activo": ""}, {"principio_activo": "😀" * 81},
    {"presentacion": "   "}, {"presentacion": "p" * 61},
    {"ubicacion": ""}, {"ubicacion": "u" * 61}, {"ubicacion": "U\u0000"},
    {"stock_minimo": -1}, {"stock_minimo": 100001}, {"stock_minimo": "x"},
])
def test_textos_invalidos_dan_422(client, farmacia, conn, hoy, cambios):
    r = client.post("/ingresos", headers=farmacia,
                    json=cuerpo(hoy, medicamento_id=None, nuevo_medicamento={**NUEVO, **cambios}))
    assert r.status_code == 422
    assert conn.execute("SELECT count(*) AS n FROM medicamentos").fetchone()["n"] == 12


def test_el_ingreso_se_refleja_en_el_chatbot(client, almacen, farmacia, hoy):
    client.post("/ingresos", headers=almacen, json=cuerpo(hoy, cantidad=7))
    r = client.post("/chat", headers=almacen,
                    json={"mensaje": "¿Cuándo fue registrada la última entrada de acetaminofén?"})
    assert f"{hoy:%d/%m/%Y}, con 7 unidades" in r.json()["respuesta"]
    r = client.post("/chat", headers=farmacia,
                    json={"mensaje": "¿Cuántas unidades hay disponibles de acetaminofén?"})
    assert "22 unidades disponibles" in r.json()["respuesta"]


def test_fecha_de_ingreso_muy_antigua_da_422(client, farmacia, conn, hoy):
    d = dt.timedelta
    for antigua in (hoy - d(days=400), dt.date(26, 9, 29)):  # más de un año atrás / año 0026 por error de digitación
        r = client.post("/ingresos", headers=farmacia,
                        json=cuerpo(hoy, fecha_ingreso=str(antigua), fecha_vencimiento=str(hoy + d(days=10))))
        assert r.status_code == 422, antigua
        assert isinstance(r.json()["detail"], str)
    assert conn.execute("SELECT count(*) AS n FROM movimientos").fetchone()["n"] == 15


def test_fecha_de_ingreso_de_hace_un_anio_se_acepta(client, farmacia, hoy):
    d = dt.timedelta
    r = client.post("/ingresos", headers=farmacia,
                    json=cuerpo(hoy, fecha_ingreso=str(hoy - d(days=365)), fecha_vencimiento=str(hoy + d(days=10))))
    assert r.status_code == 201


def test_el_ingreso_conserva_el_nombre_del_responsable_aunque_se_elimine_su_usuario(client, admin, farmacia, hoy):
    client.post("/ingresos", headers=farmacia, json=cuerpo(hoy))
    assert client.delete("/usuarios/2", headers=admin).status_code == 204
    assert _movimiento_por_lote(client, admin, "L-2026-041")["usuario"] == "Responsable de Farmacia Demo"
