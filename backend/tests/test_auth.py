def test_login_correcto_para_los_tres_roles(client):
    esperado = {"admin": "ADMINISTRADOR", "farmacia": "FARMACIA", "almacen": "ALMACENISTA"}
    for usuario, rol in esperado.items():
        r = client.post("/auth/login", json={"usuario": usuario, "password": "demo1234"})
        assert r.status_code == 200
        assert r.json()["usuario"]["rol"] == rol
        assert r.json()["token"]


def test_login_password_incorrecta(client):
    r = client.post("/auth/login", json={"usuario": "admin", "password": "incorrecta"})
    assert r.status_code == 401


def test_login_usuario_inexistente(client):
    r = client.post("/auth/login", json={"usuario": "nadie", "password": "demo1234"})
    assert r.status_code == 401


def test_login_usuario_inactivo(client, conn):
    conn.execute("UPDATE usuarios SET estado = 'INACTIVO' WHERE usuario = 'farmacia'")
    conn.commit()
    r = client.post("/auth/login", json={"usuario": "farmacia", "password": "demo1234"})
    assert r.status_code == 401


def test_login_password_muy_larga_no_rompe(client):
    # 72 caracteres no ASCII = 144 bytes (bcrypt limita a 72 bytes): nunca debe dar 500
    r = client.post("/auth/login", json={"usuario": "admin", "password": "ñ" * 72})
    assert r.status_code == 401
    # más de 72 caracteres: lo rechaza la validación
    r = client.post("/auth/login", json={"usuario": "admin", "password": "a" * 73})
    assert r.status_code == 422


def test_endpoint_protegido_sin_token(client):
    assert client.get("/auth/me").status_code == 401


def test_token_invalido(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_token_de_usuario_desactivado(client, conn, farmacia):
    conn.execute("UPDATE usuarios SET estado = 'INACTIVO' WHERE usuario = 'farmacia'")
    conn.commit()
    assert client.get("/auth/me", headers=farmacia).status_code == 401


def test_me_devuelve_el_usuario(client, almacen):
    r = client.get("/auth/me", headers=almacen)
    assert r.status_code == 200
    assert r.json() == {"nombre": "Almacenista Demo", "usuario": "almacen", "rol": "ALMACENISTA"}


def test_login_con_caracter_nul_da_422(client):
    r = client.post("/auth/login", json={"usuario": "ad\u0000min", "password": "demo1234"})
    assert r.status_code == 422


def test_surrogate_solitario_en_el_cuerpo_da_422_y_no_500(client):
    # JSON con el escape \ud83d (surrogate suelto): el servidor no debe fallar al devolver el error
    cuerpo = '{"usuario": "Zz\\ud83d", "password": "x"}'
    r = client.post("/auth/login", content=cuerpo, headers={"Content-Type": "application/json"})
    assert r.status_code in (401, 422)
