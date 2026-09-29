# Baja de usuarios e ingreso de medicamentos — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el administrador pueda dar de baja usuarios (con confirmación) y que farmacia y almacenista registren ingresos de medicamentos con lote, vencimiento, fecha y responsable.

**Architecture:** Se extiende el backend FastAPI existente: `DELETE /usuarios/{id}` (baja lógica) y un endpoint nuevo `POST /ingresos` que ejecuta todo en una transacción (crear medicamento si es nuevo, sumar stock, ajustar vencimiento, insertar el movimiento `ENTRADA` con lote). `movimientos` gana dos columnas (`lote`, `fecha_vencimiento`). El frontend agrega el botón de eliminar en *Usuarios* y las acciones "Ingreso de medicamentos" / "Registrar salida" en *Movimientos*.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, psycopg 3 (SQL parametrizado), PostgreSQL 16, pytest, HTML/CSS/JS puro.

**Spec:** `docs/superpowers/specs/2026-09-29-usuarios-e-ingresos-design.md` (extiende `2026-09-29-chatbot-ips-design.md`)

## Global Constraints

- SQL siempre parametrizado (`%s`); nunca concatenar entrada del usuario en SQL.
- Roles exactos: `ADMINISTRADOR`, `FARMACIA`, `ALMACENISTA`. `DELETE /usuarios/{id}` solo ADMINISTRADOR; `POST /ingresos` solo FARMACIA y ALMACENISTA; `POST /movimientos` solo FARMACIA y ALMACENISTA y solo `SALIDA`.
- Texto de confirmación exacto (con signos): `¿Está seguro de que desea eliminar este usuario?`
- El responsable de un ingreso sale del token, nunca del cuerpo de la petición.
- Baja de usuario = `estado = 'INACTIVO'` (no se borra la fila); el administrador no puede eliminarse a sí mismo (409); `GET /usuarios` lista solo `ACTIVO`.
- Validación de ingreso: `cantidad` entero 1–100000; `lote` 1–40 caracteres (tras `strip`) con solo letras, dígitos y `. _ / -`; `fecha_vencimiento` > `fecha_ingreso` y ≥ hoy; `fecha_ingreso` ≤ hoy; textos del medicamento nuevo: `nombre` ≤ 80, `principio_activo` ≤ 80, `presentacion` ≤ 60, `ubicacion` ≤ 60, no vacíos y sin NUL; `stock_minimo` entero 0–100000. "Hoy" es `CURRENT_DATE` de la base (zona America/Bogota).
- Regla de vencimiento del medicamento: si el actual ya venció → el del lote; si no → `LEAST(actual, lote)`.
- Nombre de medicamento repetido (sin distinguir mayúsculas) → 409, garantizado por índice único `lower(nombre)`.
- Errores de negocio con `detail` en texto español (el frontend lo muestra tal cual). Mensajes de la interfaz en español.
- No modificar el chatbot, sus tests ni la prueba de humo. Las 88 pruebas existentes siguen en verde (salvo los ajustes de `test_movimientos.py` indicados en la Tarea 2).
- **Commits:** identidad de git ya configurada en el repo (`sharidmoreno26-lgtm`); **sin** líneas `Co-Authored-By` ni mención a IA en mensajes de commit. Commits directos a `main`; no hacer `git push` (lo hace la usuaria).
- Sin sobreingeniería: sin cantidad por lote, sin edición/reactivación de usuarios, sin borrado físico.

## Review Focus

Casos que el spec implica pero no detalla, ordenados por probabilidad:

1. **Lote ya vencido, fecha de ingreso futura o vencimiento ≤ ingreso** → 422 y nada se guarda. → Tarea 2 (`test_ingresos.py::test_fechas_invalidas_dan_422`).
2. **Medicamento nuevo con nombre repetido en otra capitalización o con espacios alrededor** → 409 y no se crea ninguna fila. → Tarea 2 (`test_nombre_repetido_da_409_sin_crear_nada`).
3. **Campos solo con espacios, NUL o emojis en el medicamento nuevo o el lote** → 422 (nunca 500). → Tarea 2 (`test_textos_invalidos_dan_422`).
4. **Eliminar a uno mismo, eliminar dos veces, usar el token o el nombre de un usuario eliminado** → 409 / 404 / 401 / 409; sus movimientos quedan intactos. → Tarea 1 (`test_usuarios.py`).
5. **Doble clic en "Guardar ingreso"** crearía ingresos duplicados. → Tarea 3 (botón deshabilitado mientras se envía; verificación manual).

---

## Mapa de archivos

```
db/init.sql                              # modifica: columnas lote/fecha_vencimiento + índice único
backend/app/consultas.py                 # modifica: listar_movimientos + registrar_ingreso
backend/app/routers/usuarios.py          # modifica: DELETE y filtro ACTIVO
backend/app/routers/movimientos.py       # modifica: solo SALIDA
backend/app/routers/ingresos.py          # crea: POST /ingresos
backend/app/main.py                      # modifica: registra router ingresos
backend/tests/conftest.py                # modifica: fixture `hoy`
backend/tests/test_usuarios.py           # modifica: tests de baja
backend/tests/test_movimientos.py        # reemplaza: entradas ya no van por aquí
backend/tests/test_ingresos.py           # crea
frontend/js/vistas.js                    # modifica: Usuarios y Movimientos
frontend/js/app.js                       # modifica: pasa el usuario a vistaUsuarios (ya lo recibe)
frontend/css/estilos.css                 # modifica: botón peligro, acciones, tarjeta aviso
README.md                                # modifica: roles, endpoints, límite de lotes
```

Comando de pruebas: `docker compose run --rm -T backend pytest -q` (reinicia la BD de la demo con `db/init.sql`, que ya incluye el esquema nuevo). Todas las tareas parten de las 88 pruebas en verde.

---

### Task 1: Baja de usuarios (backend)

**Files:**
- Modify: `backend/app/routers/usuarios.py`
- Test: `backend/tests/test_usuarios.py` (agregar al final)

**Interfaces:**
- Consumes: `requiere_roles`, `get_conn`, `roles.ADMIN`; fixtures `client`, `conn`, `admin`, `farmacia`, `almacen`. Ids sembrados: admin=1, farmacia=2, almacen=3.
- Produces: `DELETE /usuarios/{usuario_id}` → 204; 409 si es el propio usuario; 404 si no existe o ya está `INACTIVO`; 422 si el id no es entero > 0. `GET /usuarios` lista solo `ACTIVO`.

- [ ] **Step 1: Escribir los tests que fallan** (agregar al final de `backend/tests/test_usuarios.py`)

```python
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


def test_usuario_eliminado_conserva_sus_movimientos_y_su_nombre_no_se_reutiliza(client, admin, conn):
    antes = conn.execute("SELECT count(*) AS n FROM movimientos WHERE usuario_id = 3").fetchone()["n"]
    assert antes > 0
    assert client.delete("/usuarios/3", headers=admin).status_code == 204
    despues = conn.execute("SELECT count(*) AS n FROM movimientos WHERE usuario_id = 3").fetchone()["n"]
    assert despues == antes
    assert len(client.get("/movimientos", headers=admin).json()) == 15
    nuevo = {"nombre": "Otra Persona", "usuario": "almacen", "password": "clave12345", "rol": "ALMACENISTA"}
    assert client.post("/usuarios", headers=admin, json=nuevo).status_code == 409
```

- [ ] **Step 2: Ejecutar y ver fallar**

Run: `docker compose run --rm -T backend pytest tests/test_usuarios.py -q`
Expected: FAIL (los `DELETE` devuelven 405 Method Not Allowed).

- [ ] **Step 3: Implementar**

En `backend/app/routers/usuarios.py` cambiar el import de FastAPI a:

```python
from fastapi import APIRouter, Depends, HTTPException, Path
```

Reemplazar la función `listar` por:

```python
@router.get("")
def listar(conn=Depends(get_conn), usuario=Depends(requiere_roles(ADMIN))):
    return conn.execute(
        """SELECT u.id, u.nombre, u.usuario, r.nombre AS rol, u.estado
           FROM usuarios u JOIN roles r ON r.id = u.rol_id
           WHERE u.estado = 'ACTIVO' ORDER BY u.id"""
    ).fetchall()
```

Agregar al final del archivo:

```python
@router.delete("/{usuario_id}", status_code=204)
def eliminar(
    usuario_id: int = Path(gt=0),
    conn=Depends(get_conn),
    actual=Depends(requiere_roles(ADMIN)),
):
    """Baja lógica: el usuario queda INACTIVO para conservar la trazabilidad de sus movimientos."""
    if usuario_id == actual["id"]:
        raise HTTPException(409, "No puedes eliminar tu propio usuario")
    fila = conn.execute(
        "UPDATE usuarios SET estado = 'INACTIVO' WHERE id = %s AND estado = 'ACTIVO' RETURNING id",
        (usuario_id,),
    ).fetchone()
    if fila is None:
        raise HTTPException(404, "Usuario no encontrado")
    conn.commit()
```

- [ ] **Step 4: Ejecutar la suite completa**

Run: `docker compose run --rm -T backend pytest -q`
Expected: `96 passed` (88 + 8 nuevos), 0 failed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/usuarios.py backend/tests/test_usuarios.py
git commit -m "feat: baja lógica de usuarios (DELETE /usuarios/{id})"
```

---

### Task 2: Ingreso de medicamentos (esquema, consultas y endpoint)

**Files:**
- Modify: `db/init.sql`, `backend/app/consultas.py`, `backend/app/routers/movimientos.py`, `backend/app/main.py`, `backend/tests/conftest.py`
- Create: `backend/app/routers/ingresos.py`, `backend/tests/test_ingresos.py`
- Replace: `backend/tests/test_movimientos.py`

**Interfaces:**
- Consumes: `get_conn`, `requiere_roles`, `roles.FARMACIA/ALMACEN`, fixtures de la Tarea 1 del plan anterior. Medicamento 1 (Acetaminofén) tiene 15 unidades y vence hoy+400; medicamento 7 (Metformina) vence hoy+500.
- Produces:
  - `consultas.registrar_ingreso(conn, usuario_id:int, cantidad:int, lote:str, fecha_vencimiento:date, fecha_ingreso:date, medicamento_id:int|None=None, nuevo:dict|None=None) -> dict` con `{"movimiento_id","medicamento_id","cantidad_actual","fecha_vencimiento"}`; lanza `LookupError` (medicamento inexistente) y `ValueError` (nombre repetido); **no** hace commit. `nuevo` tiene las llaves `nombre, principio_activo, presentacion, stock_minimo, ubicacion`.
  - `consultas.listar_movimientos` agrega las llaves `lote` y `fecha_vencimiento` (nulas en el seed y en salidas).
  - `POST /ingresos` → 201 con el dict anterior.
  - `POST /movimientos` solo acepta `tipo: "SALIDA"`.
  - Fixture de tests `hoy` → `datetime.date` (`CURRENT_DATE` de la BD).

- [ ] **Step 1: Cambiar el esquema en `db/init.sql`**

Insertar justo antes de la línea `CREATE TABLE movimientos (`:

```sql
CREATE UNIQUE INDEX ux_medicamentos_nombre ON medicamentos (lower(nombre));

```

Reemplazar el bloque `CREATE TABLE movimientos (...);` por:

```sql
CREATE TABLE movimientos (
    id SERIAL PRIMARY KEY,
    medicamento_id INT NOT NULL REFERENCES medicamentos(id),
    tipo VARCHAR(7) NOT NULL CHECK (tipo IN ('ENTRADA', 'SALIDA')),
    cantidad INT NOT NULL CHECK (cantidad > 0),
    fecha TIMESTAMP NOT NULL DEFAULT now(),
    usuario_id INT NOT NULL REFERENCES usuarios(id),
    lote VARCHAR(40),
    fecha_vencimiento DATE,
    CHECK (tipo = 'ENTRADA' OR (lote IS NULL AND fecha_vencimiento IS NULL))
);
```

(El seed de movimientos no cambia: sus entradas quedan sin lote.)

- [ ] **Step 2: Fixture `hoy` en `backend/tests/conftest.py`** (agregar al final)

```python
@pytest.fixture
def hoy(conn):
    """Fecha de hoy según la base de datos (zona America/Bogota)."""
    return conn.execute("SELECT CURRENT_DATE AS hoy").fetchone()["hoy"]
```

- [ ] **Step 3: Reemplazar `backend/tests/test_movimientos.py`** (las entradas ya no se registran aquí)

```python
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
```

- [ ] **Step 4: Escribir `backend/tests/test_ingresos.py` (falla)**

```python
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
```

- [ ] **Step 5: Ejecutar y ver fallar**

Run: `docker compose run --rm -T backend pytest tests/test_ingresos.py tests/test_movimientos.py -q`
Expected: FAIL (`/ingresos` da 404 y `POST /movimientos` con ENTRADA aún da 201).

- [ ] **Step 6: Implementar `consultas.py`**

Agregar al inicio de `backend/app/consultas.py` (antes de `DIAS_VENCIMIENTO`):

```python
from psycopg.errors import UniqueViolation

```

Reemplazar la función `listar_movimientos` por:

```python
def listar_movimientos(conn, tipo=None):
    return conn.execute(
        """SELECT mv.id, mv.medicamento_id, m.nombre AS medicamento, mv.tipo, mv.cantidad,
                  mv.fecha, u.nombre AS usuario, mv.lote, mv.fecha_vencimiento
           FROM movimientos mv
           JOIN medicamentos m ON m.id = mv.medicamento_id
           JOIN usuarios u ON u.id = mv.usuario_id
           WHERE (%s::text IS NULL OR mv.tipo = %s)
           ORDER BY mv.fecha DESC, mv.id DESC""",
        (tipo, tipo),
    ).fetchall()
```

Agregar al final del archivo:

```python
def registrar_ingreso(
    conn, usuario_id, cantidad, lote, fecha_vencimiento, fecha_ingreso, medicamento_id=None, nuevo=None
):
    """Registra un ingreso (ENTRADA con lote) y actualiza stock y vencimiento. No hace commit.

    Lanza LookupError si el medicamento no existe y ValueError si el nombre nuevo ya existe.
    """
    if nuevo is not None:
        try:
            medicamento_id = conn.execute(
                """INSERT INTO medicamentos (nombre, principio_activo, presentacion, cantidad_actual,
                                             stock_minimo, fecha_vencimiento, ubicacion)
                   VALUES (%s, %s, %s, 0, %s, %s, %s) RETURNING id""",
                (
                    nuevo["nombre"],
                    nuevo["principio_activo"],
                    nuevo["presentacion"],
                    nuevo["stock_minimo"],
                    fecha_vencimiento,
                    nuevo["ubicacion"],
                ),
            ).fetchone()["id"]
        except UniqueViolation:
            raise ValueError("Ya existe un medicamento con ese nombre")
    actualizado = conn.execute(
        """UPDATE medicamentos
           SET cantidad_actual = cantidad_actual + %s,
               fecha_vencimiento = CASE WHEN fecha_vencimiento < CURRENT_DATE THEN %s
                                        ELSE LEAST(fecha_vencimiento, %s) END
           WHERE id = %s AND estado = 'ACTIVO'
           RETURNING cantidad_actual, fecha_vencimiento""",
        (cantidad, fecha_vencimiento, fecha_vencimiento, medicamento_id),
    ).fetchone()
    if actualizado is None:
        raise LookupError("Medicamento no encontrado")
    movimiento = conn.execute(
        """INSERT INTO movimientos (medicamento_id, tipo, cantidad, fecha, usuario_id, lote, fecha_vencimiento)
           VALUES (%s, 'ENTRADA', %s, %s::date + localtime, %s, %s, %s) RETURNING id""",
        (medicamento_id, cantidad, fecha_ingreso, usuario_id, lote, fecha_vencimiento),
    ).fetchone()
    return {
        "movimiento_id": movimiento["id"],
        "medicamento_id": medicamento_id,
        "cantidad_actual": actualizado["cantidad_actual"],
        "fecha_vencimiento": actualizado["fecha_vencimiento"],
    }
```

- [ ] **Step 7: Crear `backend/app/routers/ingresos.py`**

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .. import consultas
from ..auth import requiere_roles
from ..db import get_conn
from ..roles import ALMACEN, FARMACIA

router = APIRouter(prefix="/ingresos", tags=["ingresos"])

_SIN_NUL = r"^[^\x00]*$"


class NuevoMedicamento(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=80, pattern=_SIN_NUL)
    principio_activo: str = Field(min_length=1, max_length=80, pattern=_SIN_NUL)
    presentacion: str = Field(min_length=1, max_length=60, pattern=_SIN_NUL)
    stock_minimo: int = Field(ge=0, le=100000)
    ubicacion: str = Field(min_length=1, max_length=60, pattern=_SIN_NUL)


class IngresoNuevo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    medicamento_id: int | None = Field(default=None, gt=0)
    nuevo_medicamento: NuevoMedicamento | None = None
    cantidad: int = Field(ge=1, le=100000)
    lote: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9._/-]+$")
    fecha_vencimiento: date
    fecha_ingreso: date


@router.post("", status_code=201)
def registrar(
    datos: IngresoNuevo,
    conn=Depends(get_conn),
    usuario=Depends(requiere_roles(FARMACIA, ALMACEN)),
):
    if (datos.medicamento_id is None) == (datos.nuevo_medicamento is None):
        raise HTTPException(422, "Elija un medicamento existente o indique uno nuevo, no ambos ni ninguno")
    if datos.fecha_vencimiento <= datos.fecha_ingreso:
        raise HTTPException(422, "La fecha de vencimiento debe ser posterior a la fecha de ingreso")
    hoy = conn.execute("SELECT CURRENT_DATE AS hoy").fetchone()["hoy"]
    if datos.fecha_ingreso > hoy:
        raise HTTPException(422, "La fecha de ingreso no puede ser futura")
    if datos.fecha_vencimiento < hoy:
        raise HTTPException(422, "El lote ya está vencido")
    nuevo = datos.nuevo_medicamento.model_dump() if datos.nuevo_medicamento else None
    try:
        resultado = consultas.registrar_ingreso(
            conn,
            usuario["id"],
            datos.cantidad,
            datos.lote,
            datos.fecha_vencimiento,
            datos.fecha_ingreso,
            datos.medicamento_id,
            nuevo,
        )
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(409, str(error))
    conn.commit()
    return resultado
```

- [ ] **Step 8: `POST /movimientos` solo acepta salidas y se registra el router nuevo**

En `backend/app/routers/movimientos.py` cambiar en `MovimientoNuevo`:

```python
    tipo: Literal["SALIDA"]
```

En `backend/app/main.py` cambiar el import y agregar el router:

```python
from .routers import auth, chat, ingresos, medicamentos, movimientos, servicios, usuarios
...
app.include_router(ingresos.router)
```
(el `include_router(ingresos.router)` va después de `app.include_router(movimientos.router)`).

- [ ] **Step 9: Ejecutar la suite completa**

Run: `docker compose run --rm -T backend pytest -q`
Expected: todo en verde, 0 failed (las 96 anteriores menos los 2 tests de entradas de `test_movimientos.py` reemplazados, más los nuevos). Si un test de `test_ingresos.py` falla por el orden de `fecha` o por el redondeo de `localtime`, corregir la implementación, no el test.

- [ ] **Step 10: Verificar que el chatbot y la prueba de humo siguen igual**

Run: `python3 scripts/smoke.py http://localhost:8080` (usa el puerto de su `.env`; el stack debe estar levantado con la BD reiniciada por los tests).
Expected: 15 `OK`, `TODO BIEN`.

- [ ] **Step 11: Commit**

```bash
git add db/init.sql backend
git commit -m "feat: ingreso de medicamentos con lote, vencimiento y trazabilidad (POST /ingresos)"
```

---

### Task 3: Frontend (Usuarios y Movimientos)

**Files:**
- Modify: `frontend/js/vistas.js`, `frontend/js/app.js`, `frontend/css/estilos.css`

**Interfaces:**
- Consumes: `DELETE /usuarios/{id}` (204), `POST /ingresos`, `POST /movimientos` (solo `SALIDA`), `GET /movimientos` con `lote` y `fecha_vencimiento`; globals existentes `el`, `tabla`, `insignia`, `fechaCorta`, `Api.pedir`, `mostrar`, `encabezadoVista`, `formularioMovimiento` (se reemplaza).
- Produces: `vistaUsuarios(usuario)` (recibe el usuario en sesión), `vistaMovimientos(usuario)` con acciones "Ingreso de medicamentos" y "Registrar salida".

No hay pruebas automáticas del frontend; se verifica con revisión de sintaxis en Docker y un recorrido manual.

- [ ] **Step 1: CSS** (agregar al final de `frontend/css/estilos.css`)

```css
.boton-peligro { background: var(--alerta); padding: 6px 12px; }
.boton-peligro:hover { background: #962d22; }
.boton-secundario { background: #fff; color: var(--azul); border: 1px solid var(--azul); }
.boton-secundario:hover, .boton-secundario.activo { background: var(--azul); color: #fff; }
.acciones-movimiento { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.bloque-nuevo { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; padding: 12px; border: 1px dashed var(--borde); border-radius: 8px; }
.bloque-nuevo[hidden] { display: none; }
input[readonly] { background: #eef3f8; }
```

- [ ] **Step 2: Reemplazar `formularioMovimiento` y `vistaMovimientos` en `frontend/js/vistas.js`**

Borrar las funciones `formularioMovimiento` y `vistaMovimientos` actuales y poner en su lugar:

```javascript
let avisoMovimientos = "";

function hoyISO() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function formularioSalida(meds) {
  const medicamento = el("select", { required: "" }, meds.map((m) => el("option", { value: m.id }, m.nombre)));
  const cantidad = el("input", { type: "number", min: "1", max: "100000", required: "", placeholder: "Cantidad" });
  const mensaje = el("p", { class: "error", role: "status" });
  const boton = el("button", { class: "boton", type: "submit" }, "Registrar salida");

  async function enviar(evento) {
    evento.preventDefault();
    mensaje.textContent = "";
    boton.disabled = true;
    try {
      await Api.pedir("/movimientos", {
        method: "POST",
        body: JSON.stringify({ medicamento_id: Number(medicamento.value), tipo: "SALIDA", cantidad: Number(cantidad.value) }),
      });
      avisoMovimientos = "Salida registrada correctamente.";
      mostrar("movimientos");
    } catch (error) {
      mensaje.textContent = error.message;
      boton.disabled = false;
    }
  }

  return el(
    "form",
    { class: "tarjeta formulario-linea", onsubmit: enviar },
    el("label", {}, "Medicamento", medicamento),
    el("label", {}, "Cantidad", cantidad),
    boton,
    mensaje
  );
}

function formularioIngreso(meds, usuario) {
  const medicamento = el(
    "select",
    { required: "" },
    meds.map((m) => el("option", { value: m.id }, m.nombre)),
    el("option", { value: "nuevo" }, "➕ Nuevo medicamento")
  );
  const nombre = el("input", { maxlength: "80", placeholder: "Nombre" });
  const principio = el("input", { maxlength: "80", placeholder: "Principio activo" });
  const presentacion = el("input", { maxlength: "60", placeholder: "Presentación (ej. Tabletas 500 mg)" });
  const stockMinimo = el("input", { type: "number", min: "0", max: "100000", placeholder: "Stock mínimo" });
  const ubicacion = el("input", { maxlength: "60", placeholder: "Ubicación (ej. Estante A1)" });
  const camposNuevo = [nombre, principio, presentacion, stockMinimo, ubicacion];
  const bloqueNuevo = el(
    "div",
    { class: "bloque-nuevo", hidden: "" },
    el("label", {}, "Nombre", nombre),
    el("label", {}, "Principio activo", principio),
    el("label", {}, "Presentación", presentacion),
    el("label", {}, "Stock mínimo", stockMinimo),
    el("label", {}, "Ubicación", ubicacion)
  );
  const cantidad = el("input", { type: "number", min: "1", max: "100000", required: "", placeholder: "Cantidad ingresada" });
  const lote = el("input", {
    required: "",
    maxlength: "40",
    pattern: "[A-Za-z0-9._\\/\\-]+",
    title: "Letras, números y . _ / -",
    placeholder: "Número de lote",
  });
  const hoy = hoyISO();
  const vencimiento = el("input", { type: "date", required: "", min: hoy });
  const ingreso = el("input", { type: "date", required: "", max: hoy, value: hoy });
  const responsable = el("input", { readonly: "", value: usuario.nombre });
  const mensaje = el("p", { class: "error", role: "status" });
  const boton = el("button", { class: "boton", type: "submit" }, "Guardar ingreso");

  medicamento.addEventListener("change", () => {
    const esNuevo = medicamento.value === "nuevo";
    bloqueNuevo.hidden = !esNuevo;
    camposNuevo.forEach((campo) => (campo.required = esNuevo));
  });

  async function enviar(evento) {
    evento.preventDefault();
    mensaje.textContent = "";
    if (vencimiento.value <= ingreso.value) {
      mensaje.textContent = "La fecha de vencimiento debe ser posterior a la fecha de ingreso.";
      return;
    }
    const cuerpo = {
      cantidad: Number(cantidad.value),
      lote: lote.value.trim(),
      fecha_vencimiento: vencimiento.value,
      fecha_ingreso: ingreso.value,
    };
    if (medicamento.value === "nuevo") {
      cuerpo.nuevo_medicamento = {
        nombre: nombre.value.trim(),
        principio_activo: principio.value.trim(),
        presentacion: presentacion.value.trim(),
        stock_minimo: Number(stockMinimo.value),
        ubicacion: ubicacion.value.trim(),
      };
    } else {
      cuerpo.medicamento_id = Number(medicamento.value);
    }
    boton.disabled = true;
    try {
      const datos = await Api.pedir("/ingresos", { method: "POST", body: JSON.stringify(cuerpo) });
      avisoMovimientos = `Ingreso registrado. Cantidad disponible: ${datos.cantidad_actual}.`;
      mostrar("movimientos");
    } catch (error) {
      mensaje.textContent = error.message;
      boton.disabled = false;
    }
  }

  return el(
    "form",
    { class: "tarjeta formulario-linea", onsubmit: enviar },
    el("label", {}, "Medicamento", medicamento),
    bloqueNuevo,
    el("label", {}, "Cantidad ingresada", cantidad),
    el("label", {}, "Número de lote", lote),
    el("label", {}, "Fecha de vencimiento", vencimiento),
    el("label", {}, "Fecha de ingreso", ingreso),
    el("label", {}, "Responsable del ingreso", responsable),
    boton,
    mensaje
  );
}

async function vistaMovimientos(usuario) {
  const [movs, meds] = await Promise.all([Api.pedir("/movimientos"), Api.pedir("/medicamentos")]);
  const contenedor = el("div", {}, encabezadoVista("Movimientos"));
  const aviso = avisoMovimientos;
  avisoMovimientos = "";
  if (aviso) contenedor.append(el("p", { class: "aviso", role: "status" }, aviso));
  if (usuario.rol !== "ADMINISTRADOR") {
    const panel = el("div");
    const botonIngreso = el("button", { class: "boton boton-secundario", type: "button" }, "Ingreso de medicamentos");
    const botonSalida = el("button", { class: "boton boton-secundario", type: "button" }, "Registrar salida");
    const abrir = (boton, formulario) => {
      [botonIngreso, botonSalida].forEach((b) => b.classList.toggle("activo", b === boton));
      panel.replaceChildren(formulario);
    };
    botonIngreso.addEventListener("click", () => abrir(botonIngreso, formularioIngreso(meds, usuario)));
    botonSalida.addEventListener("click", () => abrir(botonSalida, formularioSalida(meds)));
    contenedor.append(el("div", { class: "acciones-movimiento" }, botonIngreso, botonSalida), panel);
  }
  contenedor.append(
    tabla(
      ["Fecha", "Medicamento", "Tipo", "Cantidad", "Lote", "Vence", "Responsable"],
      movs.map((m) => [
        fechaCorta(m.fecha),
        m.medicamento,
        insignia(m.tipo === "ENTRADA" ? "Entrada" : "Salida", m.tipo === "ENTRADA" ? "ok" : "alerta"),
        m.cantidad,
        m.lote ?? "—",
        m.fecha_vencimiento ? fechaCorta(m.fecha_vencimiento) : "—",
        m.usuario,
      ])
    )
  );
  return contenedor;
}
```

- [ ] **Step 3: Reemplazar `vistaUsuarios` en `frontend/js/vistas.js`**

Reemplazar la función completa por (ahora recibe el usuario en sesión):

```javascript
async function vistaUsuarios(usuarioActual) {
  const usuarios = await Api.pedir("/usuarios");
  const nombre = el("input", { required: "", maxlength: "100" });
  const login = el("input", { required: "", pattern: "[a-z0-9_]{3,30}", title: "3 a 30 letras minúsculas, números o _" });
  const clave = el("input", { type: "password", required: "", minlength: "8", maxlength: "72" });
  const rol = el(
    "select",
    {},
    el("option", { value: "FARMACIA" }, "Responsable de farmacia"),
    el("option", { value: "ALMACENISTA" }, "Almacenista"),
    el("option", { value: "ADMINISTRADOR" }, "Administrador")
  );
  const mensaje = el("p", { class: "error", role: "status" });

  async function crear(evento) {
    evento.preventDefault();
    try {
      await Api.pedir("/usuarios", {
        method: "POST",
        body: JSON.stringify({ nombre: nombre.value, usuario: login.value, password: clave.value, rol: rol.value }),
      });
      mostrar("usuarios");
    } catch (error) {
      mensaje.textContent = error.message;
    }
  }

  async function eliminar(u) {
    if (!confirm("¿Está seguro de que desea eliminar este usuario?")) return;
    try {
      await Api.pedir(`/usuarios/${u.id}`, { method: "DELETE" });
      mostrar("usuarios");
    } catch (error) {
      mensaje.textContent = error.message;
    }
  }

  return el(
    "div",
    {},
    encabezadoVista("Usuarios"),
    el(
      "form",
      { class: "tarjeta formulario-linea", onsubmit: crear },
      el("label", {}, "Nombre", nombre),
      el("label", {}, "Usuario", login),
      el("label", {}, "Contraseña", clave),
      el("label", {}, "Rol", rol),
      el("button", { class: "boton", type: "submit" }, "Crear usuario"),
      mensaje
    ),
    tabla(
      ["Nombre", "Usuario", "Rol", "Estado", "Acciones"],
      usuarios.map((u) => [
        u.nombre,
        u.usuario,
        u.rol,
        u.estado,
        u.usuario === usuarioActual.usuario
          ? "—"
          : el("button", { class: "boton boton-peligro", type: "button", onclick: () => eliminar(u) }, "Eliminar"),
      ])
    )
  );
}
```

`frontend/js/app.js` no necesita cambios: `mostrar` ya llama `item.vista(usuarioActual)`.

- [ ] **Step 4: Verificar sintaxis JS con Docker (no hay Node local)**

Run:
```bash
for f in util api vistas chat app; do docker run --rm -v "$PWD/frontend/js:/w:ro" node:22-alpine node --check /w/$f.js && echo "OK $f.js"; done
```
Expected: cinco líneas `OK`.

- [ ] **Step 5: Reconstruir y comprobar que se sirve**

Run:
```bash
docker compose up -d --build frontend
PUERTO=$(grep FRONTEND_PORT .env | cut -d= -f2); PUERTO=${PUERTO:-80}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:$PUERTO/js/vistas.js
curl -s http://localhost:$PUERTO/js/vistas.js | grep -c "Ingreso de medicamentos"
```
Expected: `200` y un número mayor que 0.

- [ ] **Step 6: Recorrido manual (anotar y corregir cualquier defecto; no se puede automatizar aquí)**

Abrir `http://localhost:<puerto>` y comprobar:
1. **admin → Usuarios:** la tabla tiene columna Acciones; la fila del propio `admin` muestra "—". Crear un usuario de prueba y eliminarlo: primero sale el cuadro "¿Está seguro de que desea eliminar este usuario?"; con **Cancelar** no pasa nada; con **Aceptar** desaparece de la lista.
2. Iniciar sesión con el usuario eliminado → "Usuario o contraseña incorrectos".
3. **farmacia → Movimientos:** hay botones "Ingreso de medicamentos" y "Registrar salida"; el administrador no los ve. Al pulsar "Ingreso…" aparece el formulario con Responsable de solo lectura con el nombre de la sesión y fecha de ingreso = hoy.
4. Guardar un ingreso a Acetaminofén con lote `L-100`, vencimiento futuro: mensaje verde con la cantidad disponible y la fila nueva en la tabla con Lote y Vence. En *Inventario* la cantidad subió.
5. Elegir "➕ Nuevo medicamento": aparecen los 5 campos extra y son obligatorios; guardar crea el medicamento (visible en *Medicamentos*).
6. Casos de error: vencimiento igual o anterior a la fecha de ingreso, lote con espacios, cantidad 0, nombre repetido → mensaje claro en rojo y no se guarda nada.
7. Doble clic rápido en "Guardar ingreso" → se registra **un solo** ingreso.
8. Ventana angosta: el formulario se apila y sigue usable.

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -m "feat: interfaz para eliminar usuarios e ingreso de medicamentos"
```

---

### Task 4: Documentación y verificación final

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: todo lo anterior.

- [ ] **Step 1: Actualizar la tabla de roles del README**

Reemplazar las dos filas:
```
| Registrar entradas/salidas (formulario) | | ✅ | ✅ |
| Crear y ver usuarios | ✅ | | |
```
por:
```
| Ingreso de medicamentos (formulario con lote y vencimiento) | | ✅ | ✅ |
| Registrar salidas (formulario) | | ✅ | ✅ |
| Crear, ver y eliminar usuarios | ✅ | | |
```

- [ ] **Step 2: Agregar una sección antes de `## Pruebas`**

```markdown
## Ingreso de medicamentos y baja de usuarios

**Ingreso de medicamentos** (farmacia y almacenista, en *Movimientos → Ingreso de medicamentos*): se registra el medicamento (existente o nuevo), la cantidad, el número de lote, la fecha de vencimiento, la fecha de ingreso y el responsable, que es siempre quien tiene la sesión iniciada. Al guardar, el sistema suma la cantidad al inventario y deja el movimiento con su lote para poder rastrearlo. No se aceptan lotes ya vencidos, fechas de ingreso futuras ni datos incompletos.

El medicamento conserva **una sola fecha de vencimiento: la más próxima** entre lo que ya tenía y el lote que ingresa. Límite conocido: el sistema no lleva la cantidad de cada lote por separado; las salidas no descuentan de un lote en particular.

**Eliminar usuarios** (administrador, en *Usuarios*): antes de eliminar se pide confirmación. Eliminar es una *baja*: el usuario desaparece de la lista y ya no puede entrar, pero su registro se conserva para no perder la trazabilidad de los movimientos que hizo. No se puede eliminar el propio usuario y el nombre de usuario eliminado no se puede volver a usar.

Endpoints nuevos: `POST /ingresos` y `DELETE /usuarios/{id}`. `POST /movimientos` ahora solo registra salidas.
```

- [ ] **Step 3: Verificación final completa**

Run:
```bash
docker compose run --rm -T backend pytest -q
python3 scripts/smoke.py http://localhost:$(grep FRONTEND_PORT .env | cut -d= -f2)
git status --short
```
Expected: todas las pruebas en verde (0 failed); `TODO BIEN` con 15 `OK`; `git status` limpio salvo archivos sin seguimiento ajenos a este plan (`promptChatBotIpsUsuarios.md`).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README con ingreso de medicamentos y baja de usuarios"
```

---

## Autorevisión

- **Cobertura del spec:** §2.1–3 baja de usuarios → Tareas 1 y 3; §2.4–9 y §4 ingreso → Tareas 2 y 3; §3 datos → Tarea 2 Step 1; §5 frontend → Tarea 3; §6 pruebas → Tareas 1–2 (+ recorrido manual en 3); §8 README → Tarea 4. La aclaración "lote ya vencido → 422" y el índice único están en el spec.
- **Placeholders:** ninguno; todo el código de cada paso es el definitivo.
- **Consistencia de nombres:** `registrar_ingreso`, `hoy`, `avisoMovimientos`, `formularioIngreso`, `formularioSalida` y las llaves `lote` / `fecha_vencimiento` se usan igual en todas las tareas.
- **Interacción con el chatbot:** `ultimo_movimiento`, `unidades_movidas_mes` y demás consultas no cambian; el test `test_el_ingreso_se_refleja_en_el_chatbot` lo comprueba.
- **Riesgo a vigilar al ejecutar:** `lower(nombre)` con tildes depende de la configuración regional de Postgres en Alpine; los tests de nombre repetido usan casos ASCII (`AMOXICILINA`) a propósito.
