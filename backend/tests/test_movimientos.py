def _stock(client, cab, med_id):
    return client.get(f"/medicamentos/{med_id}/inventario", headers=cab).json()["cantidad_actual"]


def test_lista_movimientos_con_lote_y_vencimiento_nulos_en_el_seed(client, admin):
    todos = client.get("/movimientos", headers=admin).json()
    assert len(todos) == 15
    assert all("lote" in m and "fecha_vencimiento" in m for m in todos)
    assert all(m["lote"] is None and m["fecha_vencimiento"] is None for m in todos)
    entradas = client.get("/movimientos/entradas", headers=admin).json()
    salidas = client.get("/movimientos/salidas", headers=admin).json()
    assert len(entradas) == 7 and all(m["tipo"] == "ENTRADA" for m in entradas)
    assert len(salidas) == 8 and all(m["tipo"] == "SALIDA" for m in salidas)


def test_registrar_salida_actualiza_stock(client, farmacia):
    r = client.post("/movimientos", headers=farmacia,
                    json={"medicamento_id": 1, "tipo": "SALIDA", "cantidad": 5})
    assert r.status_code == 201
    assert r.json()["cantidad_actual"] == 10
    assert _stock(client, farmacia, 1) == 10


def test_almacenista_tambien_puede_registrar_salidas(client, almacen):
    r = client.post("/movimientos", headers=almacen,
                    json={"medicamento_id": 1, "tipo": "SALIDA", "cantidad": 5})
    assert r.status_code == 201
    assert _stock(client, almacen, 1) == 10


def test_las_entradas_ya_no_se_registran_por_movimientos(client, farmacia):
    r = client.post("/movimientos", headers=farmacia,
                    json={"medicamento_id": 1, "tipo": "ENTRADA", "cantidad": 10})
    assert r.status_code == 422
    assert _stock(client, farmacia, 1) == 15


def test_salida_mayor_al_stock_da_409_y_no_cambia_nada(client, farmacia):
    r = client.post("/movimientos", headers=farmacia,
                    json={"medicamento_id": 1, "tipo": "SALIDA", "cantidad": 16})
    assert r.status_code == 409
    assert _stock(client, farmacia, 1) == 15
    assert len(client.get("/movimientos", headers=farmacia).json()) == 15


def test_administrador_no_registra_movimientos(client, admin):
    r = client.post("/movimientos", headers=admin,
                    json={"medicamento_id": 1, "tipo": "SALIDA", "cantidad": 1})
    assert r.status_code == 403


def test_datos_invalidos_dan_422(client, farmacia):
    base = {"medicamento_id": 1, "tipo": "SALIDA", "cantidad": 1}
    for malo in (
        {**base, "cantidad": 0},
        {**base, "cantidad": -5},
        {**base, "cantidad": 1_000_001},
        {**base, "tipo": "OTRO"},
        {**base, "medicamento_id": 0},
    ):
        assert client.post("/movimientos", headers=farmacia, json=malo).status_code == 422, malo


def test_medicamento_inexistente_da_404(client, farmacia):
    r = client.post("/movimientos", headers=farmacia,
                    json={"medicamento_id": 9999, "tipo": "SALIDA", "cantidad": 1})
    assert r.status_code == 404
