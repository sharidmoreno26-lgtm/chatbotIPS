import pytest

from app.chatbot.servicio import NO_ENTENDIDO, SIN_PERMISO


def preguntar(client, cabecera, mensaje):
    r = client.post("/chat", headers=cabecera, json={"mensaje": mensaje})
    assert r.status_code == 200, r.text
    return r.json()["respuesta"]


# ---------- Administrador ----------
def test_admin_total_medicamentos(client, admin):
    r = preguntar(client, admin, "¿Cuántos medicamentos tenemos registrados actualmente?")
    assert r == "Actualmente hay 12 medicamentos registrados en el sistema."


def test_admin_bajo_stock(client, admin):
    r = preguntar(client, admin, "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?")
    assert r.startswith("Actualmente hay 3 medicamentos por debajo del mínimo establecido:")
    assert "• Acetaminofén — 15 unidades" in r
    assert "• Amoxicilina — 8 unidades" in r
    assert "• Losartán — 12 unidades" in r


def test_admin_proximos_a_vencer(client, admin):
    r = preguntar(client, admin, "¿Qué medicamentos están próximos a vencer durante los próximos 30 días?")
    assert r.startswith("Hay 3 medicamentos próximos a vencer durante los próximos 30 días:")
    assert r.index("Omeprazol") < r.index("Insulina") < r.index("Ibuprofeno")
    assert "en 15 días" in r


def test_admin_entradas_y_salidas_del_mes(client, admin):
    r = preguntar(client, admin, "¿Cuántas entradas y salidas de medicamentos se registraron durante este mes?")
    assert r == "Durante este mes se registraron 5 entradas y 7 salidas de medicamentos."


def test_admin_mayor_movimiento(client, admin):
    r = preguntar(client, admin, "¿Qué medicamento tiene mayor movimiento durante este mes?")
    assert r == "El medicamento con mayor movimiento durante este mes ha sido Acetaminofén, con 3 movimientos registrados."


# ---------- Responsable de farmacia ----------
def test_farmacia_unidades_disponibles(client, farmacia):
    r = preguntar(client, farmacia, "¿Cuántas unidades hay disponibles de acetaminofén?")
    assert r == "Actualmente hay 15 unidades disponibles de Acetaminofén."


def test_farmacia_bajo_stock(client, farmacia):
    r = preguntar(client, farmacia, "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?")
    assert "3 medicamentos por debajo del mínimo" in r


def test_farmacia_proximos_a_vencer(client, farmacia):
    r = preguntar(client, farmacia, "¿Qué medicamentos están próximos a vencer?")
    assert r.startswith("Hay 3 medicamentos próximos a vencer")


def test_farmacia_ingresos_y_salidas_del_mes_de_un_medicamento(client, farmacia):
    assert preguntar(client, farmacia, "¿Cuántas unidades de acetaminofén ingresaron durante este mes?") == \
        "Durante este mes ingresaron 100 unidades de Acetaminofén."
    assert preguntar(client, farmacia, "¿Cuántas unidades de acetaminofén salieron durante este mes?") == \
        "Durante este mes salieron 115 unidades de Acetaminofén."


# ---------- Almacenista ----------
def test_almacen_ubicacion(client, almacen):
    assert preguntar(client, almacen, "¿Dónde está ubicada la insulina?") == "Insulina se encuentra en: Nevera 1."


def test_almacen_unidades(client, almacen):
    r = preguntar(client, almacen, "¿Cuántas unidades hay disponibles de insulina?")
    assert r == "Actualmente hay 30 unidades disponibles de Insulina."


def test_almacen_ultima_entrada_y_salida(client, almacen, fecha_mes):
    r = preguntar(client, almacen, "¿Cuándo fue registrada la última entrada de acetaminofén?")
    assert r == f"La última entrada de Acetaminofén fue registrada el {fecha_mes(2)}, con 100 unidades."
    r = preguntar(client, almacen, "¿Cuándo fue registrada la última salida de acetaminofén?")
    assert r == f"La última salida de Acetaminofén fue registrada el {fecha_mes(9)}, con 30 unidades."


def test_almacen_revisar_por_vencimiento(client, almacen):
    r = preguntar(client, almacen, "¿Qué medicamentos debo revisar por vencimiento?")
    assert r.startswith("Hay 3 medicamentos que requieren revisión por vencimiento:")


# ---------- Variantes de redacción ----------
@pytest.mark.parametrize("pregunta", [
    "¿Cuánto acetaminofén queda?",
    "¿Cuántas unidades de acetaminofén hay?",
    "¿Qué cantidad de acetaminofén tenemos?",
    "CUÁNTAS UNIDADES DE ACETAMINOFEN HAY???",
])
def test_variantes_del_mismo_inventario(client, farmacia, pregunta):
    assert "15 unidades disponibles de Acetaminofén" in preguntar(client, farmacia, pregunta)


# ---------- Roles ----------
@pytest.mark.parametrize("cabecera, pregunta", [
    ("farmacia", "¿Cuántos medicamentos tenemos registrados actualmente?"),
    ("almacen", "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?"),
    ("admin", "¿Dónde está ubicada la insulina?"),
    ("admin", "¿Cuándo fue registrada la última entrada de acetaminofén?"),
    ("almacen", "¿Cuántas unidades de acetaminofén ingresaron durante este mes?"),
    ("almacen", "¿Qué medicamento tiene mayor movimiento durante este mes?"),
])
def test_consultas_de_otro_rol_son_rechazadas(client, admin, farmacia, almacen, cabecera, pregunta):
    cabeceras = {"admin": admin, "farmacia": farmacia, "almacen": almacen}
    assert preguntar(client, cabeceras[cabecera], pregunta) == SIN_PERMISO


# ---------- No entendidas y casos raros ----------
@pytest.mark.parametrize("mensaje", [
    "hola",
    "¿Cuál es la capital de Francia?",
    "¿Cuántas unidades de paracetamol hay?",          # medicamento inexistente
    "'; DROP TABLE medicamentos; --",
    "acetaminofen%s %% {} \\ 😀",
])
def test_preguntas_no_reconocidas_no_inventan(client, admin, mensaje):
    assert preguntar(client, admin, mensaje) == NO_ENTENDIDO


def test_texto_con_comillas_sql_no_daña_las_tablas(client, admin, conn):
    preguntar(client, admin, "cuantas unidades de acetaminofen' OR 1=1; DROP TABLE medicamentos; --")
    assert conn.execute("SELECT count(*) AS n FROM medicamentos").fetchone()["n"] == 12


def test_mensaje_vacio_o_muy_largo_da_422(client, admin):
    for malo in ("", "   ", "a" * 501):
        assert client.post("/chat", headers=admin, json={"mensaje": malo}).status_code == 422
    assert client.post("/chat", headers=admin, json={}).status_code == 422


def test_chat_requiere_autenticacion(client):
    assert client.post("/chat", json={"mensaje": "hola"}).status_code == 401
