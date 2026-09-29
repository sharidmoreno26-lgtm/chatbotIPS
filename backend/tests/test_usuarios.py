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
