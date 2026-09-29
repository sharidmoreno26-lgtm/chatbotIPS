NUEVO = {"nombre": "Persona Nueva", "usuario": "nueva_1", "password": "clave12345", "rol": "FARMACIA"}


def test_admin_lista_usuarios_sin_exponer_password(client, admin):
    r = client.get("/usuarios", headers=admin)
    assert r.status_code == 200
    assert [u["usuario"] for u in r.json()] == ["admin", "farmacia", "almacen"]
    assert all("password" not in k for u in r.json() for k in u)


def test_otros_roles_no_pueden_ver_usuarios(client, farmacia, almacen):
    assert client.get("/usuarios", headers=farmacia).status_code == 403
    assert client.get("/usuarios", headers=almacen).status_code == 403
    assert client.post("/usuarios", headers=farmacia, json=NUEVO).status_code == 403


def test_admin_crea_usuario_que_luego_puede_iniciar_sesion(client, admin):
    r = client.post("/usuarios", headers=admin, json=NUEVO)
    assert r.status_code == 201
    login = client.post("/auth/login", json={"usuario": "nueva_1", "password": "clave12345"})
    assert login.status_code == 200
    assert login.json()["usuario"]["rol"] == "FARMACIA"


def test_usuario_duplicado_da_409(client, admin):
    client.post("/usuarios", headers=admin, json=NUEVO)
    assert client.post("/usuarios", headers=admin, json=NUEVO).status_code == 409


def test_validacion_de_datos_de_usuario(client, admin):
    malos = [
        {**NUEVO, "usuario": "a"},                 # muy corto
        {**NUEVO, "usuario": "con espacio"},       # caracteres no permitidos
        {**NUEVO, "password": "corta"},            # menos de 8
        {**NUEVO, "password": "ñ" * 40},           # más de 72 bytes
        {**NUEVO, "rol": "SUPERUSUARIO"},          # rol inexistente
        {**NUEVO, "nombre": ""},
    ]
    for cuerpo in malos:
        assert client.post("/usuarios", headers=admin, json=cuerpo).status_code == 422, cuerpo


def test_nombre_con_caracter_nul_da_422(client, admin):
    r = client.post("/usuarios", headers=admin, json={**NUEVO, "nombre": "Per\u0000sona"})
    assert r.status_code == 422


def test_admin_elimina_usuario_y_desaparece_del_listado(client, admin):
    assert client.delete("/usuarios/2", headers=admin).status_code == 204
    r = client.get("/usuarios", headers=admin)
    assert [u["usuario"] for u in r.json()] == ["admin", "almacen"]


def test_usuario_eliminado_no_puede_iniciar_sesion(client, admin):
    client.delete("/usuarios/2", headers=admin)
    r = client.post("/auth/login", json={"usuario": "farmacia", "password": "demo1234"})
    assert r.status_code == 401


def test_token_de_usuario_eliminado_deja_de_funcionar(client, admin, farmacia):
    client.delete("/usuarios/2", headers=admin)
    assert client.get("/auth/me", headers=farmacia).status_code == 401


def test_eliminar_dos_veces_da_404(client, admin):
    assert client.delete("/usuarios/2", headers=admin).status_code == 204
    assert client.delete("/usuarios/2", headers=admin).status_code == 404


def test_admin_no_puede_eliminarse_a_si_mismo(client, admin):
    r = client.delete("/usuarios/1", headers=admin)
    assert r.status_code == 409
    assert "admin" in [u["usuario"] for u in client.get("/usuarios", headers=admin).json()]


def test_eliminar_id_inexistente_o_invalido(client, admin):
    assert client.delete("/usuarios/9999", headers=admin).status_code == 404
    assert client.delete("/usuarios/abc", headers=admin).status_code == 422
    assert client.delete("/usuarios/0", headers=admin).status_code == 422


def test_otros_roles_y_sin_token_no_pueden_eliminar(client, farmacia, almacen):
    assert client.delete("/usuarios/3", headers=farmacia).status_code == 403
    assert client.delete("/usuarios/2", headers=almacen).status_code == 403
    assert client.delete("/usuarios/3").status_code == 401


def test_eliminar_borra_la_fila_y_libera_el_nombre_de_usuario(client, admin, conn):
    assert client.delete("/usuarios/3", headers=admin).status_code == 204
    assert conn.execute("SELECT count(*) AS n FROM usuarios WHERE id = 3").fetchone()["n"] == 0
    nuevo = {"nombre": "Nuevo Almacenista", "usuario": "almacen", "password": "clave12345", "rol": "ALMACENISTA"}
    assert client.post("/usuarios", headers=admin, json=nuevo).status_code == 201
    login = client.post("/auth/login", json={"usuario": "almacen", "password": "clave12345"})
    assert login.status_code == 200
    assert login.json()["usuario"]["nombre"] == "Nuevo Almacenista"


def test_los_movimientos_del_usuario_eliminado_conservan_el_nombre_del_responsable(client, admin, conn):
    antes = conn.execute("SELECT count(*) AS n FROM movimientos WHERE usuario_id = 3").fetchone()["n"]
    assert antes > 0
    assert client.delete("/usuarios/3", headers=admin).status_code == 204
    movs = client.get("/movimientos", headers=admin).json()
    assert len(movs) == 15
    assert sum(1 for m in movs if m["usuario"] == "Almacenista Demo") == antes
    assert conn.execute("SELECT count(*) AS n FROM movimientos WHERE usuario_id IS NULL").fetchone()["n"] == antes
    # un usuario nuevo con el mismo nombre de usuario no hereda esos movimientos
    nuevo = {"nombre": "Otra Persona", "usuario": "almacen", "password": "clave12345", "rol": "ALMACENISTA"}
    client.post("/usuarios", headers=admin, json=nuevo)
    movs = client.get("/movimientos", headers=admin).json()
    assert not any(m["usuario"] == "Otra Persona" for m in movs)
