def test_requiere_autenticacion(client):
    assert client.get("/medicamentos").status_code == 401


def test_lista_los_12_medicamentos(client, almacen):
    r = client.get("/medicamentos", headers=almacen)
    assert r.status_code == 200
    assert len(r.json()) == 12


def test_obtener_por_id(client, admin):
    r = client.get("/medicamentos/1", headers=admin)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Acetaminofén"


def test_id_inexistente_da_404_y_texto_da_422(client, admin):
    assert client.get("/medicamentos/9999", headers=admin).status_code == 404
    assert client.get("/medicamentos/abc", headers=admin).status_code == 422


def test_bajo_stock(client, admin, farmacia):
    for cab in (admin, farmacia):
        r = client.get("/medicamentos/bajo-stock", headers=cab)
        assert r.status_code == 200
        assert [m["nombre"] for m in r.json()] == ["Acetaminofén", "Amoxicilina", "Losartán"]


def test_bajo_stock_no_permitido_para_almacenista(client, almacen):
    assert client.get("/medicamentos/bajo-stock", headers=almacen).status_code == 403


def test_proximos_a_vencer_ordenados_por_fecha(client, almacen):
    r = client.get("/medicamentos/proximos-vencer", headers=almacen)
    assert r.status_code == 200
    assert [m["nombre"] for m in r.json()] == ["Omeprazol", "Insulina", "Ibuprofeno"]
    assert [m["dias_restantes"] for m in r.json()] == [15, 20, 25]


def test_inventario_de_un_medicamento(client, admin):
    bajo = client.get("/medicamentos/1/inventario", headers=admin).json()
    assert bajo["cantidad_actual"] == 15 and bajo["stock_minimo"] == 50 and bajo["bajo_minimo"] is True
    normal = client.get("/medicamentos/7/inventario", headers=admin).json()
    assert normal["bajo_minimo"] is False


def test_servicios(client, admin):
    r = client.get("/servicios", headers=admin)
    assert r.status_code == 200
    assert len(r.json()) == 3
