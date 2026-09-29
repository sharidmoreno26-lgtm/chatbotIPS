# MVP Chatbot IPS — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chatbot web para una IPS que responde, según el rol del usuario, preguntas sobre medicamentos, inventario, movimientos, vencimientos y ubicaciones usando una BD PostgreSQL con datos ficticios.

**Architecture:** Tres contenedores (nginx + HTML/CSS/JS, FastAPI, PostgreSQL) con Docker Compose. El frontend llama a `/api/*` (nginx reenvía al backend). El chatbot es un pipeline de reglas: normaliza texto → detecta medicamento en BD → detecta intención por regex → valida rol → ejecuta consulta SQL parametrizada → arma respuesta. Las consultas SQL viven en un solo módulo (`consultas.py`) que usan tanto los endpoints REST como el chatbot.

**Tech Stack:** Python 3.12, FastAPI, psycopg 3 (SQL parametrizado, sin ORM), PyJWT, bcrypt, pytest, PostgreSQL 16, nginx, HTML/CSS/JS puro, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-29-chatbot-ips-design.md`

## Global Constraints

- Costo $0, todo local; se levanta con `docker compose up --build`.
- Solo datos ficticios; sin datos clínicos ni de pacientes reales.
- SQL siempre parametrizado (`%s`); nunca concatenar entrada del usuario en SQL.
- Contraseñas con hash bcrypt; sesión con JWT; secretos solo en `.env` (nunca en el repo; se entrega `.env.example`).
- Roles exactos en BD y código: `ADMINISTRADOR`, `FARMACIA`, `ALMACENISTA`.
- Tipos de movimiento exactos: `ENTRADA`, `SALIDA`. Estados: `ACTIVO`, `INACTIVO`.
- Ventana de "próximos a vencer": 30 días (constante `DIAS_VENCIMIENTO`).
- Mensaje no entendido (literal): `No pude identificar tu consulta. Puedes preguntarme sobre inventario, medicamentos, movimientos, vencimientos o ubicaciones.`
- Mensaje sin permiso (literal): `Esa consulta no está disponible para tu rol.`
- El menú del frontend solo oculta opciones; la seguridad real está en el backend.
- Backend sin prefijo de ruta (`/medicamentos`, `/chat`…); nginx expone todo bajo `/api/` y FastAPI usa `root_path="/api"`.
- Usuarios de prueba: `admin`, `farmacia`, `almacen`; contraseña de los tres: `demo1234`.
- Sin microservicios, Kubernetes, nube, IA de pago ni sobreingeniería. Comentar solo lo necesario.
- Los mensajes al usuario están en español.

## Review Focus

Casos que el spec implica pero no detalla, ordenados por probabilidad. Cada uno tiene su test en la tarea indicada:

1. **Contraseña de login muy larga o con caracteres no ASCII** (bcrypt limita a 72 bytes): debe dar 401/422, nunca 500. → Tarea 2 (`test_login_password_muy_larga_no_rompe`).
2. **Usuario desactivado después de iniciar sesión** (su token sigue vigente): debe recibir 401. → Tarea 2 (`test_token_de_usuario_desactivado`).
3. **Salida mayor al stock, cantidad 0, negativa o enorme**: 409 o 422, el stock no cambia. → Tarea 3 (`test_movimientos.py`).
4. **Mensaje de chat vacío, solo espacios, de 501 caracteres, con comillas SQL, `%`, emojis**: 422 o "no entendido", nunca 500, tablas intactas. → Tarea 4 (`test_chat.py`).
5. **Pregunta con medicamento inexistente** ("unidades de paracetamol"): mensaje "no entendido", sin inventar cifras. → Tarea 4 (`test_chat.py`).

---

## Mapa de archivos

```
chatbotIps/
├── .gitignore  .env.example  docker-compose.yml  README.md
├── db/init.sql                         # tablas + datos ficticios (idempotente: hace DROP primero)
├── backend/
│   ├── Dockerfile  requirements.txt  requirements-dev.txt  pytest.ini
│   ├── app/
│   │   ├── main.py          # crea la app y registra routers
│   │   ├── config.py        # variables de entorno
│   │   ├── db.py            # get_conn (una conexión por petición)
│   │   ├── roles.py         # constantes de roles
│   │   ├── auth.py          # bcrypt, JWT, usuario_actual, requiere_roles
│   │   ├── consultas.py     # TODO el SQL de lectura/escritura de negocio
│   │   ├── routers/ auth.py usuarios.py medicamentos.py movimientos.py servicios.py chat.py
│   │   └── chatbot/ normalizador.py intenciones.py permisos.py respuestas.py servicio.py
│   └── tests/ conftest.py test_auth.py test_usuarios.py test_medicamentos.py
│              test_movimientos.py test_normalizador.py test_intenciones.py test_chat.py
├── frontend/ Dockerfile nginx.conf index.html css/estilos.css js/{util,api,vistas,chat,app}.js
└── scripts/smoke.py                    # prueba de humo contra http://localhost
```

Comando para correr pruebas (todas las tareas): `docker compose run --rm -T backend pytest -q`.
**Nota:** las pruebas reinician la BD con `db/init.sql` antes de cada test (es la misma BD de la demo; se restaura sola).

---

### Task 1: Estructura del repo y base de datos

**Files:**
- Create: `.gitignore`, `.env.example`, `docker-compose.yml`, `db/init.sql`

**Interfaces:**
- Produces: BD `ips` con tablas `roles(id,nombre)`, `usuarios(id,nombre,usuario,password_hash,rol_id,estado)`, `servicios(id,nombre)`, `medicamentos(id,nombre,principio_activo,presentacion,cantidad_actual,stock_minimo,fecha_vencimiento,ubicacion,estado)`, `movimientos(id,medicamento_id,tipo,cantidad,fecha TIMESTAMP,usuario_id)`. Servicio compose `db` (healthcheck). Ids fijos: roles 1=ADMINISTRADOR,2=FARMACIA,3=ALMACENISTA; usuarios 1=admin,2=farmacia,3=almacen; medicamentos 1..12 en el orden del seed.

- [ ] **Step 1: Crear `.gitignore`**

```
.env
__pycache__/
*.pyc
.pytest_cache/
.superpowers/
```

- [ ] **Step 2: Crear `.env.example` y copiarlo a `.env`**

```
POSTGRES_DB=ips
POSTGRES_USER=ips_user
POSTGRES_PASSWORD=cambia_esta_clave
JWT_SECRET=cambia_este_secreto_largo_y_aleatorio
FRONTEND_PORT=80
```

Run: `cp .env.example .env`

- [ ] **Step 3: Crear `docker-compose.yml` (solo `db` por ahora)**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 3s
      timeout: 3s
      retries: 20

volumes:
  pgdata:
```

- [ ] **Step 4: Crear `db/init.sql`**

El hash es bcrypt de `demo1234`. Los movimientos usan fechas relativas al primer día del mes actual (día 0..13 del mes, o negativos = mes anterior) para que "este mes" siempre tenga datos.

```sql
DROP TABLE IF EXISTS movimientos, medicamentos, servicios, usuarios, roles CASCADE;

CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    usuario VARCHAR(30) NOT NULL UNIQUE,
    password_hash VARCHAR(100) NOT NULL,
    rol_id INT NOT NULL REFERENCES roles(id),
    estado VARCHAR(10) NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'INACTIVO'))
);

CREATE TABLE servicios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE medicamentos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL,
    principio_activo VARCHAR(80) NOT NULL,
    presentacion VARCHAR(60) NOT NULL,
    cantidad_actual INT NOT NULL CHECK (cantidad_actual >= 0),
    stock_minimo INT NOT NULL CHECK (stock_minimo >= 0),
    fecha_vencimiento DATE NOT NULL,
    ubicacion VARCHAR(60) NOT NULL,
    estado VARCHAR(10) NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'INACTIVO'))
);

CREATE TABLE movimientos (
    id SERIAL PRIMARY KEY,
    medicamento_id INT NOT NULL REFERENCES medicamentos(id),
    tipo VARCHAR(7) NOT NULL CHECK (tipo IN ('ENTRADA', 'SALIDA')),
    cantidad INT NOT NULL CHECK (cantidad > 0),
    fecha TIMESTAMP NOT NULL DEFAULT now(),
    usuario_id INT NOT NULL REFERENCES usuarios(id)
);
CREATE INDEX idx_movimientos_medicamento_fecha ON movimientos (medicamento_id, fecha);

INSERT INTO roles (nombre) VALUES ('ADMINISTRADOR'), ('FARMACIA'), ('ALMACENISTA');

INSERT INTO usuarios (nombre, usuario, password_hash, rol_id) VALUES
('Administrador Demo', 'admin', '$2b$10$tqRzyxhni0q4NIKAhMHixuHQqgAvZ8ZdwV4w0aJrJG0VbROymjGk2', 1),
('Responsable de Farmacia Demo', 'farmacia', '$2b$10$tqRzyxhni0q4NIKAhMHixuHQqgAvZ8ZdwV4w0aJrJG0VbROymjGk2', 2),
('Almacenista Demo', 'almacen', '$2b$10$tqRzyxhni0q4NIKAhMHixuHQqgAvZ8ZdwV4w0aJrJG0VbROymjGk2', 3);

INSERT INTO servicios (nombre) VALUES ('Farmacia'), ('Almacén de medicamentos'), ('Administración');

-- 3 bajo el mínimo (1,2,3) y 3 que vencen en menos de 30 días (4,5,6).
INSERT INTO medicamentos (nombre, principio_activo, presentacion, cantidad_actual, stock_minimo, fecha_vencimiento, ubicacion) VALUES
('Acetaminofén', 'Acetaminofén',        'Tabletas 500 mg',    15,  50, CURRENT_DATE + 400, 'Estante A1'),
('Amoxicilina',  'Amoxicilina',         'Cápsulas 500 mg',     8,  40, CURRENT_DATE + 200, 'Estante A2'),
('Losartán',     'Losartán potásico',   'Tabletas 50 mg',     12,  30, CURRENT_DATE + 300, 'Estante B1'),
('Ibuprofeno',   'Ibuprofeno',          'Tabletas 400 mg',   120,  40, CURRENT_DATE + 25,  'Estante A3'),
('Insulina',     'Insulina humana NPH', 'Vial 10 ml',         30,  10, CURRENT_DATE + 20,  'Nevera 1'),
('Omeprazol',    'Omeprazol',           'Cápsulas 20 mg',    200,  50, CURRENT_DATE + 15,  'Estante B2'),
('Metformina',   'Metformina',          'Tabletas 850 mg',   300,  80, CURRENT_DATE + 500, 'Estante B3'),
('Salbutamol',   'Salbutamol',          'Inhalador 100 mcg',  60,  20, CURRENT_DATE + 350, 'Estante C1'),
('Diclofenaco',  'Diclofenaco sódico',  'Ampolla 75 mg',      90,  30, CURRENT_DATE + 600, 'Estante C2'),
('Loratadina',   'Loratadina',          'Tabletas 10 mg',    150,  40, CURRENT_DATE + 250, 'Estante C3'),
('Enalapril',    'Enalapril',           'Tabletas 20 mg',     45,  30, CURRENT_DATE + 180, 'Estante D1'),
('Suero Oral',   'Sales de rehidratación', 'Sobre',          100,  60, CURRENT_DATE + 45,  'Estante D2');

-- (medicamento, tipo, cantidad, día relativo al inicio del mes, usuario)
-- Mes actual: 5 entradas y 7 salidas. Acetaminofén tiene 3 movimientos (el mayor).
-- Mes anterior (día negativo): 2 entradas y 1 salida, que NO deben contarse en "este mes".
INSERT INTO movimientos (medicamento_id, tipo, cantidad, fecha, usuario_id)
SELECT v.med, v.tipo, v.cant,
       (date_trunc('month', CURRENT_DATE)::date + v.dia) + time '09:00', v.usr
FROM (VALUES
    (1, 'ENTRADA', 100,  2, 3),
    (1, 'SALIDA',   85,  5, 2),
    (1, 'SALIDA',   30,  9, 2),
    (2, 'ENTRADA',  50,  3, 3),
    (2, 'SALIDA',   42,  8, 2),
    (3, 'SALIDA',   18,  6, 2),
    (4, 'ENTRADA',  60,  4, 3),
    (4, 'SALIDA',   20, 10, 2),
    (5, 'ENTRADA',  20,  7, 3),
    (5, 'SALIDA',    5, 11, 2),
    (6, 'SALIDA',   40, 12, 2),
    (7, 'ENTRADA', 100, 13, 3),
    (1, 'ENTRADA', 200, -5, 3),
    (1, 'SALIDA',   60, -3, 2),
    (5, 'ENTRADA',  15, -10, 3)
) AS v(med, tipo, cant, dia, usr);
```

- [ ] **Step 5: Levantar la BD y verificar los datos**

Run:
```bash
docker compose up -d db
docker compose exec -T db psql -U ips_user -d ips -c "SELECT (SELECT count(*) FROM medicamentos) AS meds, (SELECT count(*) FROM medicamentos WHERE cantidad_actual < stock_minimo) AS bajo, (SELECT count(*) FROM medicamentos WHERE fecha_vencimiento BETWEEN CURRENT_DATE AND CURRENT_DATE + 30) AS por_vencer, (SELECT count(*) FROM movimientos) AS movs;"
```
Expected: `meds=12, bajo=3, por_vencer=3, movs=15`

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example docker-compose.yml db/init.sql
git commit -m "feat: estructura inicial y base de datos con datos ficticios"
```

---

### Task 2: Backend base, autenticación, roles y usuarios

**Files:**
- Create: `backend/Dockerfile`, `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pytest.ini`
- Create: `backend/app/__init__.py` (vacío), `config.py`, `db.py`, `roles.py`, `auth.py`, `main.py`
- Create: `backend/app/routers/__init__.py` (vacío), `routers/auth.py`, `routers/usuarios.py`
- Create: `backend/tests/conftest.py`, `tests/test_auth.py`, `tests/test_usuarios.py`
- Modify: `docker-compose.yml` (agregar servicio `backend`)

**Interfaces:**
- Consumes: BD de la Tarea 1.
- Produces:
  - `app.db.get_conn()` → generador de dependencia FastAPI que entrega una `psycopg.Connection` con `row_factory=dict_row` (una por petición).
  - `app.roles`: `ADMIN="ADMINISTRADOR"`, `FARMACIA="FARMACIA"`, `ALMACEN="ALMACENISTA"`, `TODOS=(ADMIN, FARMACIA, ALMACEN)`.
  - `app.auth`: `hashear_password(plano:str)->str`, `verificar_password(plano:str, hash_:str)->bool`, `crear_token(usuario_id:int, rol:str)->str`, `usuario_actual` (dependencia → `dict` con `id,nombre,usuario,estado,rol`), `requiere_roles(*roles)` (fábrica de dependencia; 401 sin token/inválido, 403 rol no permitido).
  - Endpoints: `POST /auth/login`, `GET /auth/me`, `GET /usuarios`, `POST /usuarios`.
  - Fixtures de test: `client`, `conn`, `admin`, `farmacia`, `almacen` (cabeceras `{"Authorization": "Bearer …"}`), `fecha_mes(dia)->str "DD/MM/YYYY"`; fixture autouse `bd_limpia`.

- [ ] **Step 1: Archivos de configuración del backend**

`backend/requirements.txt`:
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
psycopg[binary]==3.2.3
pyjwt==2.10.1
bcrypt==4.2.1
```

`backend/requirements-dev.txt`:
```
-r requirements.txt
pytest==8.3.4
httpx==0.28.1
```

`backend/pytest.ini`:
```
[pytest]
pythonpath = .
testpaths = tests
```

`backend/Dockerfile` (se instalan también las dependencias de prueba para mantenerlo simple):
```dockerfile
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY pytest.ini ./
COPY app ./app
COPY tests ./tests
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Agregar el servicio `backend` a `docker-compose.yml`** (dentro de `services:`, después de `db`)

```yaml
  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      JWT_SECRET: ${JWT_SECRET}
    volumes:
      - ./db:/db:ro
      - ./backend/app:/srv/app
      - ./backend/tests:/srv/tests
    depends_on:
      db:
        condition: service_healthy
```

(Los volúmenes de `app` y `tests` evitan reconstruir la imagen mientras se desarrolla.)

- [ ] **Step 3: Escribir `tests/conftest.py`**

```python
import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]
INIT_SQL = Path(os.getenv("INIT_SQL", "/db/init.sql"))


@pytest.fixture(autouse=True)
def bd_limpia():
    """Restaura la BD con los datos ficticios antes de cada prueba."""
    with psycopg.connect(DATABASE_URL, autocommit=True) as c:
        c.execute(INIT_SQL.read_text(encoding="utf-8"))


@pytest.fixture
def conn():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as c:
        yield c


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _cabecera(client, usuario):
    r = client.post("/auth/login", json={"usuario": usuario, "password": "demo1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def admin(client):
    return _cabecera(client, "admin")


@pytest.fixture
def farmacia(client):
    return _cabecera(client, "farmacia")


@pytest.fixture
def almacen(client):
    return _cabecera(client, "almacen")


@pytest.fixture
def fecha_mes(conn):
    """Devuelve 'DD/MM/YYYY' del día `dia` (0 = primer día) del mes actual."""

    def _fecha(dia):
        fila = conn.execute(
            "SELECT to_char(date_trunc('month', CURRENT_DATE)::date + %s::int, 'DD/MM/YYYY') AS f",
            (dia,),
        ).fetchone()
        return fila["f"]

    return _fecha
```

- [ ] **Step 4: Escribir `tests/test_auth.py` (falla al inicio)**

```python
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
```

- [ ] **Step 5: Escribir `tests/test_usuarios.py` (falla al inicio)**

```python
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
```

- [ ] **Step 6: Ejecutar y ver fallar**

Run: `docker compose build backend && docker compose run --rm -T backend pytest -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.main'`).

- [ ] **Step 7: Implementar `config.py`, `db.py`, `roles.py`**

`backend/app/config.py`:
```python
import os

DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_HORAS = int(os.getenv("JWT_HORAS", "8"))
```

`backend/app/db.py`:
```python
import psycopg
from psycopg.rows import dict_row

from .config import DATABASE_URL


def get_conn():
    """Una conexión por petición; se cierra sola al terminar."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn
```

`backend/app/roles.py`:
```python
ADMIN = "ADMINISTRADOR"
FARMACIA = "FARMACIA"
ALMACEN = "ALMACENISTA"
TODOS = (ADMIN, FARMACIA, ALMACEN)
```

- [ ] **Step 8: Implementar `auth.py`**

```python
import datetime as dt

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import JWT_HORAS, JWT_SECRET
from .db import get_conn

_bearer = HTTPBearer(auto_error=False)


def hashear_password(plano: str) -> str:
    return bcrypt.hashpw(plano.encode(), bcrypt.gensalt()).decode()


def verificar_password(plano: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(plano.encode(), hash_.encode())
    except ValueError:
        return False


def crear_token(usuario_id: int, rol: str) -> str:
    vence = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=JWT_HORAS)
    return jwt.encode({"sub": str(usuario_id), "rol": rol, "exp": vence}, JWT_SECRET, algorithm="HS256")


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    conn=Depends(get_conn),
):
    if credenciales is None:
        raise HTTPException(401, "No autenticado")
    try:
        datos = jwt.decode(credenciales.credentials, JWT_SECRET, algorithms=["HS256"])
        usuario_id = int(datos["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Sesión inválida o vencida")
    fila = conn.execute(
        """SELECT u.id, u.nombre, u.usuario, u.estado, r.nombre AS rol
           FROM usuarios u JOIN roles r ON r.id = u.rol_id WHERE u.id = %s""",
        (usuario_id,),
    ).fetchone()
    if fila is None or fila["estado"] != "ACTIVO":
        raise HTTPException(401, "Sesión inválida o vencida")
    return fila


def requiere_roles(*roles: str):
    def dependencia(usuario=Depends(usuario_actual)):
        if usuario["rol"] not in roles:
            raise HTTPException(403, "Tu rol no tiene acceso a este recurso")
        return usuario

    return dependencia
```

- [ ] **Step 9: Implementar routers `auth` y `usuarios`**

`backend/app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import crear_token, usuario_actual, verificar_password
from ..db import get_conn

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginEntrada(BaseModel):
    usuario: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=72)


def _resumen(fila):
    return {"nombre": fila["nombre"], "usuario": fila["usuario"], "rol": fila["rol"]}


@router.post("/login")
def login(datos: LoginEntrada, conn=Depends(get_conn)):
    fila = conn.execute(
        """SELECT u.id, u.nombre, u.usuario, u.password_hash, u.estado, r.nombre AS rol
           FROM usuarios u JOIN roles r ON r.id = u.rol_id WHERE u.usuario = %s""",
        (datos.usuario,),
    ).fetchone()
    if (
        fila is None
        or fila["estado"] != "ACTIVO"
        or not verificar_password(datos.password, fila["password_hash"])
    ):
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    return {"token": crear_token(fila["id"], fila["rol"]), "usuario": _resumen(fila)}


@router.get("/me")
def me(usuario=Depends(usuario_actual)):
    return _resumen(usuario)
```

`backend/app/routers/usuarios.py`:
```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth import hashear_password, requiere_roles
from ..db import get_conn
from ..roles import ADMIN

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


class UsuarioNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    usuario: str = Field(pattern=r"^[a-z0-9_]{3,30}$")
    password: str = Field(min_length=8, max_length=72)
    rol: Literal["ADMINISTRADOR", "FARMACIA", "ALMACENISTA"]

    @field_validator("password")
    @classmethod
    def maximo_72_bytes(cls, valor):
        if len(valor.encode()) > 72:
            raise ValueError("La contraseña es demasiado larga")
        return valor


@router.get("")
def listar(conn=Depends(get_conn), usuario=Depends(requiere_roles(ADMIN))):
    return conn.execute(
        """SELECT u.id, u.nombre, u.usuario, r.nombre AS rol, u.estado
           FROM usuarios u JOIN roles r ON r.id = u.rol_id ORDER BY u.id"""
    ).fetchall()


@router.post("", status_code=201)
def crear(datos: UsuarioNuevo, conn=Depends(get_conn), usuario=Depends(requiere_roles(ADMIN))):
    if conn.execute("SELECT 1 FROM usuarios WHERE usuario = %s", (datos.usuario,)).fetchone():
        raise HTTPException(409, "Ese nombre de usuario ya existe")
    fila = conn.execute(
        """INSERT INTO usuarios (nombre, usuario, password_hash, rol_id)
           VALUES (%s, %s, %s, (SELECT id FROM roles WHERE nombre = %s)) RETURNING id""",
        (datos.nombre, datos.usuario, hashear_password(datos.password), datos.rol),
    ).fetchone()
    conn.commit()
    return {"id": fila["id"]}
```
- [ ] **Step 10: Implementar `main.py`**

```python
from fastapi import FastAPI

from .routers import auth, usuarios

app = FastAPI(title="Chatbot IPS", root_path="/api")

app.include_router(auth.router)
app.include_router(usuarios.router)


@app.get("/salud", tags=["sistema"])
def salud():
    return {"estado": "ok"}
```


- [ ] **Step 11: Ejecutar las pruebas y ver pasar**

Run: `docker compose run --rm -T backend pytest -q`
Expected: `14 passed` (9 de auth + 5 de usuarios)

- [ ] **Step 12: Commit**

```bash
git add backend docker-compose.yml
git commit -m "feat: backend base con login JWT, roles y gestión de usuarios"
```

---

### Task 3: Consultas de negocio y endpoints REST (medicamentos, movimientos, servicios)

**Files:**
- Create: `backend/app/consultas.py`
- Create: `backend/app/routers/medicamentos.py`, `routers/movimientos.py`, `routers/servicios.py`
- Modify: `backend/app/main.py` (registrar routers)
- Test: `backend/tests/test_medicamentos.py`, `tests/test_movimientos.py`

**Interfaces:**
- Consumes: `get_conn`, `requiere_roles`, `roles.*`, fixtures de la Tarea 2.
- Produces (`app.consultas`, todas reciben `conn` primero; las filas son `dict`):
  - `DIAS_VENCIMIENTO = 30`
  - `listar_medicamentos(conn) -> list[dict]` (`id,nombre,principio_activo,presentacion,cantidad_actual,stock_minimo,fecha_vencimiento,ubicacion,estado`; solo ACTIVO, orden por nombre)
  - `obtener_medicamento(conn, med_id:int) -> dict|None`
  - `contar_medicamentos(conn) -> int`
  - `medicamentos_bajo_stock(conn) -> list[dict]` (`cantidad_actual < stock_minimo`, orden por nombre)
  - `medicamentos_proximos_a_vencer(conn, dias:int=DIAS_VENCIMIENTO) -> list[dict]` (agrega `dias_restantes:int`; orden por vencimiento)
  - `listar_movimientos(conn, tipo:str|None=None) -> list[dict]` (`id,medicamento_id,medicamento,tipo,cantidad,fecha,usuario`; más recientes primero)
  - `contar_movimientos_mes(conn) -> dict` (`{"entradas":int,"salidas":int}`)
  - `mayor_movimiento_mes(conn) -> dict|None` (`{"nombre":str,"movimientos":int}`)
  - `unidades_movidas_mes(conn, med_id:int, tipo:str) -> int`
  - `ultimo_movimiento(conn, med_id:int, tipo:str) -> dict|None` (`{"fecha":datetime,"cantidad":int}`)
  - `registrar_movimiento(conn, med_id:int, tipo:str, cantidad:int, usuario_id:int) -> dict` (`{"id":int,"cantidad_actual":int}`; lanza `LookupError` si no existe el medicamento, `ValueError` si la salida deja stock negativo; **no** hace commit)
  - Endpoints: `GET /medicamentos`, `/medicamentos/bajo-stock` (ADMIN, FARMACIA), `/medicamentos/proximos-vencer`, `/medicamentos/{id}`, `/medicamentos/{id}/inventario`; `GET /movimientos`, `/movimientos/entradas`, `/movimientos/salidas`; `POST /movimientos` (FARMACIA, ALMACEN → 201); `GET /servicios`. Los `GET` (salvo bajo-stock) permiten los 3 roles.

- [ ] **Step 1: Escribir `tests/test_medicamentos.py` (falla)**

```python
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
```

- [ ] **Step 2: Escribir `tests/test_movimientos.py` (falla)**

```python
def _stock(client, cab, med_id):
    return client.get(f"/medicamentos/{med_id}/inventario", headers=cab).json()["cantidad_actual"]


def test_lista_movimientos(client, admin):
    todos = client.get("/movimientos", headers=admin).json()
    assert len(todos) == 15
    entradas = client.get("/movimientos/entradas", headers=admin).json()
    salidas = client.get("/movimientos/salidas", headers=admin).json()
    assert len(entradas) == 7 and all(m["tipo"] == "ENTRADA" for m in entradas)
    assert len(salidas) == 8 and all(m["tipo"] == "SALIDA" for m in salidas)


def test_registrar_entrada_actualiza_stock(client, farmacia):
    r = client.post("/movimientos", headers=farmacia,
                    json={"medicamento_id": 1, "tipo": "ENTRADA", "cantidad": 10})
    assert r.status_code == 201
    assert r.json()["cantidad_actual"] == 25
    assert _stock(client, farmacia, 1) == 25


def test_registrar_salida_actualiza_stock_y_almacenista_puede(client, almacen):
    r = client.post("/movimientos", headers=almacen,
                    json={"medicamento_id": 1, "tipo": "SALIDA", "cantidad": 5})
    assert r.status_code == 201
    assert _stock(client, almacen, 1) == 10


def test_salida_mayor_al_stock_da_409_y_no_cambia_nada(client, farmacia):
    r = client.post("/movimientos", headers=farmacia,
                    json={"medicamento_id": 1, "tipo": "SALIDA", "cantidad": 16})
    assert r.status_code == 409
    assert _stock(client, farmacia, 1) == 15
    assert len(client.get("/movimientos", headers=farmacia).json()) == 15


def test_administrador_no_registra_movimientos(client, admin):
    r = client.post("/movimientos", headers=admin,
                    json={"medicamento_id": 1, "tipo": "ENTRADA", "cantidad": 1})
    assert r.status_code == 403


def test_datos_invalidos_dan_422(client, farmacia):
    base = {"medicamento_id": 1, "tipo": "ENTRADA", "cantidad": 1}
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
                    json={"medicamento_id": 9999, "tipo": "ENTRADA", "cantidad": 1})
    assert r.status_code == 404
```

- [ ] **Step 3: Ejecutar y ver fallar**

Run: `docker compose run --rm -T backend pytest tests/test_medicamentos.py tests/test_movimientos.py -q`
Expected: FAIL (404 en las rutas: aún no existen).

- [ ] **Step 4: Implementar `consultas.py`**

```python
DIAS_VENCIMIENTO = 30

_COLUMNAS_MED = """id, nombre, principio_activo, presentacion, cantidad_actual, stock_minimo,
                   fecha_vencimiento, ubicacion, estado"""

# Constante interna (no contiene entrada del usuario).
_EN_EL_MES = """fecha >= date_trunc('month', CURRENT_DATE)::date
                AND fecha < (date_trunc('month', CURRENT_DATE) + interval '1 month')::date"""


def listar_medicamentos(conn):
    return conn.execute(
        f"SELECT {_COLUMNAS_MED} FROM medicamentos WHERE estado = 'ACTIVO' ORDER BY nombre"
    ).fetchall()


def obtener_medicamento(conn, med_id):
    return conn.execute(
        f"SELECT {_COLUMNAS_MED} FROM medicamentos WHERE id = %s AND estado = 'ACTIVO'", (med_id,)
    ).fetchone()


def contar_medicamentos(conn):
    return conn.execute("SELECT count(*) AS n FROM medicamentos WHERE estado = 'ACTIVO'").fetchone()["n"]


def medicamentos_bajo_stock(conn):
    return conn.execute(
        f"""SELECT {_COLUMNAS_MED} FROM medicamentos
            WHERE estado = 'ACTIVO' AND cantidad_actual < stock_minimo ORDER BY nombre"""
    ).fetchall()


def medicamentos_proximos_a_vencer(conn, dias=DIAS_VENCIMIENTO):
    return conn.execute(
        f"""SELECT {_COLUMNAS_MED}, (fecha_vencimiento - CURRENT_DATE) AS dias_restantes
            FROM medicamentos
            WHERE estado = 'ACTIVO'
              AND fecha_vencimiento BETWEEN CURRENT_DATE AND CURRENT_DATE + %s::int
            ORDER BY fecha_vencimiento, nombre""",
        (dias,),
    ).fetchall()


def listar_movimientos(conn, tipo=None):
    return conn.execute(
        """SELECT mv.id, mv.medicamento_id, m.nombre AS medicamento, mv.tipo, mv.cantidad,
                  mv.fecha, u.nombre AS usuario
           FROM movimientos mv
           JOIN medicamentos m ON m.id = mv.medicamento_id
           JOIN usuarios u ON u.id = mv.usuario_id
           WHERE (%s::text IS NULL OR mv.tipo = %s)
           ORDER BY mv.fecha DESC, mv.id DESC""",
        (tipo, tipo),
    ).fetchall()


def contar_movimientos_mes(conn):
    return conn.execute(
        f"""SELECT count(*) FILTER (WHERE tipo = 'ENTRADA') AS entradas,
                   count(*) FILTER (WHERE tipo = 'SALIDA') AS salidas
            FROM movimientos WHERE {_EN_EL_MES}"""
    ).fetchone()


def mayor_movimiento_mes(conn):
    return conn.execute(
        f"""SELECT m.nombre, count(*) AS movimientos
            FROM movimientos mv JOIN medicamentos m ON m.id = mv.medicamento_id
            WHERE {_EN_EL_MES}
            GROUP BY m.id, m.nombre ORDER BY movimientos DESC, m.nombre LIMIT 1"""
    ).fetchone()


def unidades_movidas_mes(conn, med_id, tipo):
    return conn.execute(
        f"""SELECT COALESCE(SUM(cantidad), 0) AS total FROM movimientos
            WHERE medicamento_id = %s AND tipo = %s AND {_EN_EL_MES}""",
        (med_id, tipo),
    ).fetchone()["total"]


def ultimo_movimiento(conn, med_id, tipo):
    return conn.execute(
        """SELECT fecha, cantidad FROM movimientos WHERE medicamento_id = %s AND tipo = %s
           ORDER BY fecha DESC, id DESC LIMIT 1""",
        (med_id, tipo),
    ).fetchone()


def registrar_movimiento(conn, med_id, tipo, cantidad, usuario_id):
    """Registra el movimiento y actualiza el stock. No hace commit."""
    med = conn.execute(
        "SELECT cantidad_actual FROM medicamentos WHERE id = %s AND estado = 'ACTIVO' FOR UPDATE",
        (med_id,),
    ).fetchone()
    if med is None:
        raise LookupError("Medicamento no encontrado")
    cambio = cantidad if tipo == "ENTRADA" else -cantidad
    if med["cantidad_actual"] + cambio < 0:
        raise ValueError("No hay unidades suficientes para registrar la salida")
    nuevo = conn.execute(
        "UPDATE medicamentos SET cantidad_actual = cantidad_actual + %s WHERE id = %s RETURNING cantidad_actual",
        (cambio, med_id),
    ).fetchone()["cantidad_actual"]
    mov = conn.execute(
        """INSERT INTO movimientos (medicamento_id, tipo, cantidad, usuario_id)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (med_id, tipo, cantidad, usuario_id),
    ).fetchone()
    return {"id": mov["id"], "cantidad_actual": nuevo}
```

- [ ] **Step 5: Implementar routers**

`backend/app/routers/medicamentos.py`:
```python
from fastapi import APIRouter, Depends, HTTPException

from .. import consultas
from ..auth import requiere_roles
from ..db import get_conn
from ..roles import ADMIN, FARMACIA, TODOS

router = APIRouter(prefix="/medicamentos", tags=["medicamentos"])


@router.get("")
def listar(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return consultas.listar_medicamentos(conn)


@router.get("/bajo-stock")
def bajo_stock(conn=Depends(get_conn), usuario=Depends(requiere_roles(ADMIN, FARMACIA))):
    return consultas.medicamentos_bajo_stock(conn)


@router.get("/proximos-vencer")
def proximos_vencer(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return consultas.medicamentos_proximos_a_vencer(conn)


def _o_404(conn, med_id):
    med = consultas.obtener_medicamento(conn, med_id)
    if med is None:
        raise HTTPException(404, "Medicamento no encontrado")
    return med


@router.get("/{med_id}")
def detalle(med_id: int, conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return _o_404(conn, med_id)


@router.get("/{med_id}/inventario")
def inventario(med_id: int, conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    med = _o_404(conn, med_id)
    return {
        "medicamento_id": med["id"],
        "nombre": med["nombre"],
        "cantidad_actual": med["cantidad_actual"],
        "stock_minimo": med["stock_minimo"],
        "ubicacion": med["ubicacion"],
        "bajo_minimo": med["cantidad_actual"] < med["stock_minimo"],
    }
```

`backend/app/routers/movimientos.py`:
```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import consultas
from ..auth import requiere_roles
from ..db import get_conn
from ..roles import ALMACEN, FARMACIA, TODOS

router = APIRouter(prefix="/movimientos", tags=["movimientos"])


class MovimientoNuevo(BaseModel):
    medicamento_id: int = Field(gt=0)
    tipo: Literal["ENTRADA", "SALIDA"]
    cantidad: int = Field(gt=0, le=100000)


@router.get("")
def listar(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return consultas.listar_movimientos(conn)


@router.get("/entradas")
def entradas(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return consultas.listar_movimientos(conn, "ENTRADA")


@router.get("/salidas")
def salidas(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return consultas.listar_movimientos(conn, "SALIDA")


@router.post("", status_code=201)
def registrar(
    datos: MovimientoNuevo,
    conn=Depends(get_conn),
    usuario=Depends(requiere_roles(FARMACIA, ALMACEN)),
):
    try:
        resultado = consultas.registrar_movimiento(
            conn, datos.medicamento_id, datos.tipo, datos.cantidad, usuario["id"]
        )
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(409, str(error))
    conn.commit()
    return resultado
```

`backend/app/routers/servicios.py`:
```python
from fastapi import APIRouter, Depends

from ..auth import requiere_roles
from ..db import get_conn
from ..roles import TODOS

router = APIRouter(prefix="/servicios", tags=["servicios"])


@router.get("")
def listar(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return conn.execute("SELECT id, nombre FROM servicios ORDER BY id").fetchall()
```

- [ ] **Step 6: Registrar routers en `main.py`**

Reemplazar el import y los `include_router`:
```python
from .routers import auth, medicamentos, movimientos, servicios, usuarios
...
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(medicamentos.router)
app.include_router(movimientos.router)
app.include_router(servicios.router)
```

- [ ] **Step 7: Ejecutar todas las pruebas**

Run: `docker compose run --rm -T backend pytest -q`
Expected: `30 passed` (14 anteriores + 9 de medicamentos + 7 de movimientos)

- [ ] **Step 8: Commit**

```bash
git add backend
git commit -m "feat: consultas de negocio y endpoints REST de medicamentos, movimientos y servicios"
```

---

### Task 4: Chatbot (intenciones, permisos, respuestas) y `POST /chat`

**Files:**
- Create: `backend/app/chatbot/__init__.py` (vacío), `normalizador.py`, `intenciones.py`, `permisos.py`, `respuestas.py`, `servicio.py`
- Create: `backend/app/routers/chat.py`
- Modify: `backend/app/main.py`, `docs/superpowers/specs/2026-09-29-chatbot-ips-design.md` (agregar fila `REVISION_VENCIMIENTO`)
- Test: `backend/tests/test_normalizador.py`, `tests/test_intenciones.py`, `tests/test_chat.py`

**Interfaces:**
- Consumes: `app.consultas.*` (Tarea 3), `app.roles.*`, `requiere_roles`, `get_conn`.
- Produces:
  - `normalizador.normalizar(texto:str)->str` (minúsculas, sin tildes, solo `[a-z0-9 ]`, espacios colapsados)
  - `intenciones`: constantes `str` `TOTAL_MEDICAMENTOS, BAJO_STOCK, PROXIMOS_A_VENCER, REVISION_VENCIMIENTO, MOVIMIENTOS_DEL_MES, MAYOR_MOVIMIENTO_MES, CONSULTAR_INVENTARIO_MEDICAMENTO, ENTRADAS_MEDICAMENTO_MES, SALIDAS_MEDICAMENTO_MES, UBICACION_MEDICAMENTO, ULTIMA_ENTRADA, ULTIMA_SALIDA` (el valor es el mismo nombre en texto) y `detectar_intencion(texto_normalizado:str, hay_medicamento:bool)->str|None`
  - `permisos.PERMISOS: dict[str, set[str]]`
  - `respuestas.MANEJADORES: dict[str, Callable[[conn, dict|None], str]]`
  - `servicio`: `NO_ENTENDIDO`, `SIN_PERMISO`, `buscar_medicamento(conn, texto_normalizado)->dict|None`, `responder(conn, usuario:dict, mensaje:str)->str`
  - Endpoint `POST /chat` `{"mensaje": str(1..500)}` → `{"respuesta": str}` para los 3 roles.

- [ ] **Step 1: Escribir `tests/test_normalizador.py` y `tests/test_intenciones.py` (fallan)**

`tests/test_normalizador.py`:
```python
from app.chatbot.normalizador import normalizar


def test_quita_tildes_signos_y_mayusculas():
    assert normalizar("¿Cuántas UNIDADES de Acetaminofén hay?!") == "cuantas unidades de acetaminofen hay"


def test_colapsa_espacios_y_maneja_enie_y_simbolos():
    assert normalizar("  año   '; DROP-- %s 😀 ") == "ano drop s"


def test_texto_vacio():
    assert normalizar("   ") == ""
```

`tests/test_intenciones.py`:
```python
import pytest

from app.chatbot import intenciones as i
from app.chatbot import permisos, respuestas
from app.chatbot.normalizador import normalizar


@pytest.mark.parametrize(
    "pregunta, hay_med, esperado",
    [
        ("¿Cuántos medicamentos tenemos registrados actualmente?", False, i.TOTAL_MEDICAMENTOS),
        ("¿Cuáles son los medicamentos que están por debajo del mínimo establecido?", False, i.BAJO_STOCK),
        ("¿Qué medicamentos tienen poco stock?", False, i.BAJO_STOCK),
        ("¿Qué medicamentos están próximos a vencer durante los próximos 30 días?", False, i.PROXIMOS_A_VENCER),
        ("¿Qué medicamentos están próximos a vencer?", False, i.PROXIMOS_A_VENCER),
        ("¿Qué medicamentos debo revisar por vencimiento?", False, i.REVISION_VENCIMIENTO),
        ("¿Cuántas entradas y salidas de medicamentos se registraron durante este mes?", False, i.MOVIMIENTOS_DEL_MES),
        ("¿Qué medicamento tiene mayor movimiento durante este mes?", False, i.MAYOR_MOVIMIENTO_MES),
        ("¿Cuántas unidades hay disponibles de acetaminofén?", True, i.CONSULTAR_INVENTARIO_MEDICAMENTO),
        ("¿Cuánto acetaminofén queda?", True, i.CONSULTAR_INVENTARIO_MEDICAMENTO),
        ("¿Cuántas unidades de acetaminofén hay?", True, i.CONSULTAR_INVENTARIO_MEDICAMENTO),
        ("¿Qué cantidad de acetaminofén tenemos?", True, i.CONSULTAR_INVENTARIO_MEDICAMENTO),
        ("¿Cuántas unidades de acetaminofén ingresaron durante este mes?", True, i.ENTRADAS_MEDICAMENTO_MES),
        ("¿Cuántas unidades de acetaminofén salieron durante este mes?", True, i.SALIDAS_MEDICAMENTO_MES),
        ("¿Dónde está ubicado insulina?", True, i.UBICACION_MEDICAMENTO),
        ("¿Dónde está ubicada la insulina?", True, i.UBICACION_MEDICAMENTO),
        ("¿Cuándo fue registrada la última entrada de acetaminofén?", True, i.ULTIMA_ENTRADA),
        ("¿Cuándo fue registrada la última salida de acetaminofén?", True, i.ULTIMA_SALIDA),
        ("hola", False, None),
        ("¿Cuál es la capital de Francia?", False, None),
        ("¿Dónde está ubicado el paracetamol?", False, None),  # medicamento no encontrado
    ],
)
def test_detectar_intencion(pregunta, hay_med, esperado):
    assert i.detectar_intencion(normalizar(pregunta), hay_med) == esperado


def test_toda_intencion_tiene_permisos_y_manejador():
    todas = {v for k, v in vars(i).items() if k.isupper() and not k.startswith("_") and isinstance(v, str)}
    assert todas == set(permisos.PERMISOS) == set(respuestas.MANEJADORES)
```

- [ ] **Step 2: Escribir `tests/test_chat.py` (falla)**

```python
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
```

- [ ] **Step 3: Ejecutar y ver fallar**

Run: `docker compose run --rm -T backend pytest tests/test_normalizador.py tests/test_intenciones.py tests/test_chat.py -q`
Expected: FAIL (`ModuleNotFoundError: app.chatbot`).

- [ ] **Step 4: Implementar `normalizador.py` e `intenciones.py`**

`backend/app/chatbot/normalizador.py`:
```python
import re
import unicodedata


def normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    solo_letras = re.sub(r"[^a-z0-9\s]", " ", sin_tildes.lower())
    return re.sub(r"\s+", " ", solo_letras).strip()
```

`backend/app/chatbot/intenciones.py`:
```python
import re

TOTAL_MEDICAMENTOS = "TOTAL_MEDICAMENTOS"
BAJO_STOCK = "BAJO_STOCK"
PROXIMOS_A_VENCER = "PROXIMOS_A_VENCER"
REVISION_VENCIMIENTO = "REVISION_VENCIMIENTO"
MOVIMIENTOS_DEL_MES = "MOVIMIENTOS_DEL_MES"
MAYOR_MOVIMIENTO_MES = "MAYOR_MOVIMIENTO_MES"
CONSULTAR_INVENTARIO_MEDICAMENTO = "CONSULTAR_INVENTARIO_MEDICAMENTO"
ENTRADAS_MEDICAMENTO_MES = "ENTRADAS_MEDICAMENTO_MES"
SALIDAS_MEDICAMENTO_MES = "SALIDAS_MEDICAMENTO_MES"
UBICACION_MEDICAMENTO = "UBICACION_MEDICAMENTO"
ULTIMA_ENTRADA = "ULTIMA_ENTRADA"
ULTIMA_SALIDA = "ULTIMA_SALIDA"

_ENTRADA = r"\b(entradas?|entraron|ingres\w*)\b"
_SALIDA = r"\b(salidas?|salio|salieron|egres\w*)\b"


def _hay(patron: str, texto: str) -> bool:
    return re.search(patron, texto) is not None


def detectar_intencion(texto: str, hay_medicamento: bool):
    """Recibe texto ya normalizado. Devuelve el nombre de la intención o None."""
    if hay_medicamento and _hay(r"\bultim[ao]\b", texto):
        if _hay(_ENTRADA, texto):
            return ULTIMA_ENTRADA
        if _hay(_SALIDA, texto):
            return ULTIMA_SALIDA
    if hay_medicamento and _hay(r"\b(donde|ubicacion|ubicad[oa]s?|guardad[oa]s?)\b", texto):
        return UBICACION_MEDICAMENTO
    if _hay(r"\b(mayor|mas)\b.*\bmovimientos?\b", texto):
        return MAYOR_MOVIMIENTO_MES

    entradas, salidas = _hay(_ENTRADA, texto), _hay(_SALIDA, texto)
    if hay_medicamento and entradas and not salidas:
        return ENTRADAS_MEDICAMENTO_MES
    if hay_medicamento and salidas and not entradas:
        return SALIDAS_MEDICAMENTO_MES
    if not hay_medicamento and entradas and salidas:
        return MOVIMIENTOS_DEL_MES

    if _hay(r"\b(vencer|vencen|vencimientos?|vencidos?|caducar|caducan)\b", texto):
        return REVISION_VENCIMIENTO if _hay(r"\brevis\w*\b", texto) else PROXIMOS_A_VENCER
    if _hay(r"\b(minimo|poco stock|bajo stock|stock bajo|inventario bajo|poco inventario|pocas unidades)\b", texto):
        return BAJO_STOCK
    if (
        not hay_medicamento
        and _hay(r"\bmedicamentos\b", texto)
        and _hay(r"\b(cuantos|total)\b", texto)
        and _hay(r"\b(registrados|tenemos|hay|existen)\b", texto)
    ):
        return TOTAL_MEDICAMENTOS
    if hay_medicamento and _hay(
        r"\b(cuant\w*|cantidad|queda\w*|hay|tenemos|disponibles?|unidades|existencias?|stock|inventario)\b", texto
    ):
        return CONSULTAR_INVENTARIO_MEDICAMENTO
    return None
```

- [ ] **Step 5: Implementar `permisos.py`**

```python
from ..roles import ADMIN, ALMACEN, FARMACIA, TODOS
from . import intenciones as i

PERMISOS = {
    i.TOTAL_MEDICAMENTOS: {ADMIN},
    i.MOVIMIENTOS_DEL_MES: {ADMIN},
    i.MAYOR_MOVIMIENTO_MES: {ADMIN},
    i.BAJO_STOCK: {ADMIN, FARMACIA},
    i.PROXIMOS_A_VENCER: set(TODOS),
    i.REVISION_VENCIMIENTO: set(TODOS),
    i.CONSULTAR_INVENTARIO_MEDICAMENTO: set(TODOS),
    i.ENTRADAS_MEDICAMENTO_MES: {FARMACIA},
    i.SALIDAS_MEDICAMENTO_MES: {FARMACIA},
    i.UBICACION_MEDICAMENTO: {ALMACEN},
    i.ULTIMA_ENTRADA: {ALMACEN},
    i.ULTIMA_SALIDA: {ALMACEN},
}
```

- [ ] **Step 6: Implementar `respuestas.py`**

```python
from .. import consultas as c
from . import intenciones as i


def _pl(n, singular, plural):
    return singular if n == 1 else plural


def _fecha(valor):
    return valor.strftime("%d/%m/%Y")


def _lista(filas, formato):
    return "\n".join(f"• {formato(f)}" for f in filas)


def _linea_vencimiento(f):
    d = f["dias_restantes"]
    return f"{f['nombre']} — vence el {_fecha(f['fecha_vencimiento'])} (en {d} {_pl(d, 'día', 'días')})"


def total_medicamentos(conn, med):
    n = c.contar_medicamentos(conn)
    return f"Actualmente hay {n} {_pl(n, 'medicamento registrado', 'medicamentos registrados')} en el sistema."


def bajo_stock(conn, med):
    filas = c.medicamentos_bajo_stock(conn)
    if not filas:
        return "No hay medicamentos por debajo del mínimo establecido."
    n = len(filas)
    return (
        f"Actualmente hay {n} {_pl(n, 'medicamento', 'medicamentos')} por debajo del mínimo establecido:\n\n"
        + _lista(filas, lambda f: f"{f['nombre']} — {f['cantidad_actual']} unidades (mínimo {f['stock_minimo']})")
        + "\n\nTe recomiendo revisar estos medicamentos en el inventario."
    )


def proximos_a_vencer(conn, med):
    filas = c.medicamentos_proximos_a_vencer(conn)
    if not filas:
        return f"No hay medicamentos próximos a vencer durante los próximos {c.DIAS_VENCIMIENTO} días."
    n = len(filas)
    return (
        f"Hay {n} {_pl(n, 'medicamento próximo', 'medicamentos próximos')} a vencer "
        f"durante los próximos {c.DIAS_VENCIMIENTO} días:\n\n"
        + _lista(filas, _linea_vencimiento)
    )


def revision_vencimiento(conn, med):
    filas = c.medicamentos_proximos_a_vencer(conn)
    if not filas:
        return "No hay medicamentos que requieran revisión por vencimiento."
    n = len(filas)
    return (
        f"Hay {n} {_pl(n, 'medicamento que requiere', 'medicamentos que requieren')} "
        "revisión por vencimiento:\n\n" + _lista(filas, _linea_vencimiento)
    )


def movimientos_del_mes(conn, med):
    t = c.contar_movimientos_mes(conn)
    e, s = t["entradas"], t["salidas"]
    return (
        f"Durante este mes se registraron {e} {_pl(e, 'entrada', 'entradas')} "
        f"y {s} {_pl(s, 'salida', 'salidas')} de medicamentos."
    )


def mayor_movimiento_mes(conn, med):
    fila = c.mayor_movimiento_mes(conn)
    if fila is None:
        return "Durante este mes no se han registrado movimientos."
    n = fila["movimientos"]
    return (
        f"El medicamento con mayor movimiento durante este mes ha sido {fila['nombre']}, "
        f"con {n} {_pl(n, 'movimiento registrado', 'movimientos registrados')}."
    )


def inventario_medicamento(conn, med):
    u = med["cantidad_actual"]
    return f"Actualmente hay {u} {_pl(u, 'unidad disponible', 'unidades disponibles')} de {med['nombre']}."


def _unidades_mes(conn, med, tipo, verbo_singular, verbo_plural):
    u = c.unidades_movidas_mes(conn, med["id"], tipo)
    return (
        f"Durante este mes {_pl(u, verbo_singular, verbo_plural)} {u} "
        f"{_pl(u, 'unidad', 'unidades')} de {med['nombre']}."
    )


def entradas_medicamento_mes(conn, med):
    return _unidades_mes(conn, med, "ENTRADA", "ingresó", "ingresaron")


def salidas_medicamento_mes(conn, med):
    return _unidades_mes(conn, med, "SALIDA", "salió", "salieron")


def ubicacion_medicamento(conn, med):
    return f"{med['nombre']} se encuentra en: {med['ubicacion']}."


def _ultimo(conn, med, tipo, palabra):
    fila = c.ultimo_movimiento(conn, med["id"], tipo)
    if fila is None:
        return f"No hay {palabra}s registradas de {med['nombre']}."
    n = fila["cantidad"]
    return (
        f"La última {palabra} de {med['nombre']} fue registrada el {_fecha(fila['fecha'])}, "
        f"con {n} {_pl(n, 'unidad', 'unidades')}."
    )


def ultima_entrada(conn, med):
    return _ultimo(conn, med, "ENTRADA", "entrada")


def ultima_salida(conn, med):
    return _ultimo(conn, med, "SALIDA", "salida")


MANEJADORES = {
    i.TOTAL_MEDICAMENTOS: total_medicamentos,
    i.BAJO_STOCK: bajo_stock,
    i.PROXIMOS_A_VENCER: proximos_a_vencer,
    i.REVISION_VENCIMIENTO: revision_vencimiento,
    i.MOVIMIENTOS_DEL_MES: movimientos_del_mes,
    i.MAYOR_MOVIMIENTO_MES: mayor_movimiento_mes,
    i.CONSULTAR_INVENTARIO_MEDICAMENTO: inventario_medicamento,
    i.ENTRADAS_MEDICAMENTO_MES: entradas_medicamento_mes,
    i.SALIDAS_MEDICAMENTO_MES: salidas_medicamento_mes,
    i.UBICACION_MEDICAMENTO: ubicacion_medicamento,
    i.ULTIMA_ENTRADA: ultima_entrada,
    i.ULTIMA_SALIDA: ultima_salida,
}
```

- [ ] **Step 7: Implementar `servicio.py` y `routers/chat.py`**

`backend/app/chatbot/servicio.py`:
```python
import re

from .. import consultas
from .intenciones import detectar_intencion
from .normalizador import normalizar
from .permisos import PERMISOS
from .respuestas import MANEJADORES

NO_ENTENDIDO = (
    "No pude identificar tu consulta. Puedes preguntarme sobre inventario, "
    "medicamentos, movimientos, vencimientos o ubicaciones."
)
SIN_PERMISO = "Esa consulta no está disponible para tu rol."


def buscar_medicamento(conn, texto):
    """Busca el nombre (o principio activo) de un medicamento dentro del texto normalizado."""
    candidatos = sorted(consultas.listar_medicamentos(conn), key=lambda m: -len(m["nombre"]))
    for med in candidatos:
        for nombre in (med["nombre"], med["principio_activo"]):
            if re.search(rf"\b{re.escape(normalizar(nombre))}\b", texto):
                return med
    return None


def responder(conn, usuario, mensaje):
    texto = normalizar(mensaje)
    med = buscar_medicamento(conn, texto)
    intencion = detectar_intencion(texto, med is not None)
    if intencion is None:
        return NO_ENTENDIDO
    if usuario["rol"] not in PERMISOS[intencion]:
        return SIN_PERMISO
    return MANEJADORES[intencion](conn, med)
```

`backend/app/routers/chat.py`:
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from ..auth import requiere_roles
from ..chatbot.servicio import responder
from ..db import get_conn
from ..roles import TODOS

router = APIRouter(tags=["chat"])


class ChatEntrada(BaseModel):
    mensaje: str = Field(min_length=1, max_length=500)

    @field_validator("mensaje")
    @classmethod
    def no_vacio(cls, valor):
        valor = valor.strip()
        if not valor:
            raise ValueError("El mensaje no puede estar vacío")
        return valor


@router.post("/chat")
def chat(datos: ChatEntrada, conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return {"respuesta": responder(conn, usuario, datos.mensaje)}
```

En `main.py`: importar `chat` en la línea de routers y agregar `app.include_router(chat.router)`.

- [ ] **Step 8: Actualizar el spec (fila nueva en la tabla de intenciones)**

En `docs/superpowers/specs/2026-09-29-chatbot-ips-design.md`, después de la fila `PROXIMOS_A_VENCER`, agregar:
```
| REVISION_VENCIMIENTO ("¿qué debo revisar por vencimiento?") | ✅ | ✅ | ✅ |
```

- [ ] **Step 9: Ejecutar todas las pruebas**

Run: `docker compose run --rm -T backend pytest -q`
Expected: todas en verde, 0 failed. Si una regex de intención falla, ajustar solo `intenciones.py` hasta que pase, sin tocar los tests.

- [ ] **Step 10: Commit**

```bash
git add backend docs
git commit -m "feat: chatbot por reglas con permisos por rol y endpoint POST /chat"
```

---

### Task 5: Frontend (interfaz IPS) y nginx

**Files:**
- Create: `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/index.html`, `frontend/css/estilos.css`
- Create: `frontend/js/util.js`, `api.js`, `vistas.js`, `chat.js`, `app.js`
- Modify: `docker-compose.yml` (servicio `frontend`)

**Interfaces:**
- Consumes: API bajo `/api` (todos los endpoints de las Tareas 2–4).
- Produces (globales del navegador): `el(tag, props, ...hijos)`, `tabla(columnas, filas)`, `fechaCorta(iso)`, `Api.pedir(ruta, opciones)`, `Api.cerrarSesion()`, `Api.hayToken()`, `Api.guardarToken(t)`, funciones de vista `vistaInicio(usuario)`, `vistaChat(usuario)`, `vistaMedicamentos()`, `vistaInventario()`, `vistaMovimientos(usuario)`, `vistaVencimientos()`, `vistaUsuarios()` (cada una devuelve `Promise<HTMLElement>` o `HTMLElement`), `mostrar(idVista)`.

Esta tarea no tiene pruebas automatizadas (es HTML/JS simple); se verifica con `curl` y un recorrido manual.

- [ ] **Step 1: Servicio `frontend` en `docker-compose.yml`** (dentro de `services:`)

```yaml
  frontend:
    build: ./frontend
    ports:
      - "${FRONTEND_PORT:-80}:80"
    depends_on:
      - backend
```

- [ ] **Step 2: `frontend/Dockerfile` y `frontend/nginx.conf`**

```dockerfile
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/
COPY css /usr/share/nginx/html/css
COPY js /usr/share/nginx/html/js
```

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: `frontend/index.html`**

```html
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IPS Centro de Salud — Asistente Virtual</title>
  <link rel="stylesheet" href="css/estilos.css">
</head>
<body>
  <section id="pantalla-login" class="login">
    <form id="form-login" class="tarjeta login-caja">
      <div class="logo">🏥</div>
      <h1>IPS Centro de Salud</h1>
      <p class="subtitulo">Asistente Virtual</p>
      <label>Usuario
        <input id="login-usuario" autocomplete="username" required maxlength="30">
      </label>
      <label>Contraseña
        <input id="login-password" type="password" autocomplete="current-password" required maxlength="72">
      </label>
      <p id="login-error" class="error" role="alert"></p>
      <button type="submit" class="boton">Ingresar</button>
      <p class="ayuda">Demo: admin, farmacia o almacen · clave demo1234</p>
    </form>
  </section>

  <div id="app" hidden>
    <header class="encabezado">
      <div class="marca">
        <span class="logo-chico">🏥</span>
        <div>
          <h1>IPS Centro de Salud</h1>
          <p>Asistente Virtual</p>
        </div>
      </div>
      <div class="sesion">
        <span id="nombre-usuario"></span>
        <span id="rol-usuario" class="etiqueta"></span>
        <button id="btn-salir" class="boton boton-claro" type="button">Salir</button>
      </div>
    </header>
    <div class="cuerpo">
      <nav id="menu" aria-label="Menú principal"></nav>
      <main id="contenido"></main>
    </div>
  </div>

  <script src="js/util.js"></script>
  <script src="js/api.js"></script>
  <script src="js/vistas.js"></script>
  <script src="js/chat.js"></script>
  <script src="js/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: `frontend/css/estilos.css`**

```css
:root {
  --azul: #0b5cad;
  --azul-oscuro: #083d75;
  --verde: #1f9d6b;
  --fondo: #f2f7fb;
  --texto: #1d2b3a;
  --borde: #d5e2ee;
  --alerta: #c0392b;
}
* { box-sizing: border-box; }
body { margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: var(--fondo); color: var(--texto); }
[hidden] { display: none !important; }
h1, h2 { margin: 0; }

.tarjeta { background: #fff; border: 1px solid var(--borde); border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(11, 92, 173, .06); }
.boton { background: var(--azul); color: #fff; border: 0; border-radius: 8px; padding: 10px 18px; font-size: 1rem; cursor: pointer; }
.boton:hover { background: var(--azul-oscuro); }
.boton-claro { background: rgba(255, 255, 255, .18); padding: 6px 12px; }
.error { color: var(--alerta); min-height: 1.2em; margin: 6px 0; }
.aviso { color: var(--verde); min-height: 1.2em; }
input, select { width: 100%; padding: 10px; border: 1px solid var(--borde); border-radius: 8px; font-size: 1rem; }
label { display: block; margin-bottom: 12px; font-weight: 600; font-size: .9rem; }

/* Login */
.login { min-height: 100vh; display: grid; place-items: center; background: linear-gradient(135deg, var(--azul), var(--verde)); padding: 16px; }
.login-caja { width: 100%; max-width: 380px; text-align: center; }
.login-caja label { text-align: left; }
.login-caja .logo { font-size: 3rem; }
.subtitulo { color: var(--verde); font-weight: 600; margin: 4px 0 18px; }
.ayuda { font-size: .8rem; color: #6a7c8e; }

/* Estructura */
.encabezado { background: var(--azul); color: #fff; display: flex; justify-content: space-between; align-items: center; padding: 12px 24px; gap: 12px; flex-wrap: wrap; }
.marca { display: flex; align-items: center; gap: 12px; }
.marca h1 { font-size: 1.25rem; }
.marca p { margin: 0; font-size: .85rem; opacity: .85; }
.logo-chico { font-size: 2rem; }
.sesion { display: flex; align-items: center; gap: 10px; }
.etiqueta { background: var(--verde); border-radius: 999px; padding: 2px 10px; font-size: .78rem; }
.cuerpo { display: grid; grid-template-columns: 220px 1fr; min-height: calc(100vh - 68px); }
#menu { background: #fff; border-right: 1px solid var(--borde); padding: 16px 10px; display: flex; flex-direction: column; gap: 4px; }
#menu button { text-align: left; background: none; border: 0; padding: 10px 12px; border-radius: 8px; font-size: 1rem; cursor: pointer; color: var(--texto); }
#menu button:hover { background: var(--fondo); }
#menu button.activo { background: var(--azul); color: #fff; }
#contenido { padding: 24px; overflow-x: auto; }
#contenido h2 { color: var(--azul-oscuro); margin-bottom: 16px; }

/* Tablas y formularios */
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; }
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--borde); }
th { background: #e6f0fa; color: var(--azul-oscuro); font-size: .85rem; }
.insignia { border-radius: 999px; padding: 2px 10px; font-size: .78rem; font-weight: 600; }
.insignia.ok { background: #dff5ea; color: #157a52; }
.insignia.alerta { background: #fde4e1; color: var(--alerta); }
.formulario-linea { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; align-items: end; margin-bottom: 20px; }
.formulario-linea label { margin: 0; }

/* Chat */
.chat { display: flex; flex-direction: column; height: calc(100vh - 150px); max-width: 820px; }
.mensajes { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding: 12px; background: #fff; border: 1px solid var(--borde); border-radius: 12px; }
.burbuja { max-width: 80%; padding: 10px 14px; border-radius: 14px; }
.burbuja .quien { display: block; font-size: .75rem; font-weight: 700; margin-bottom: 4px; }
.burbuja .texto { white-space: pre-wrap; }
.burbuja.bot { background: #e6f0fa; align-self: flex-start; }
.burbuja.usuario { background: var(--verde); color: #fff; align-self: flex-end; }
.sugerencias { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.sugerencias button { background: #fff; border: 1px solid var(--azul); color: var(--azul); border-radius: 999px; padding: 6px 12px; cursor: pointer; font-size: .85rem; }
.sugerencias button:hover { background: var(--azul); color: #fff; }
.entrada-chat { display: flex; gap: 8px; }

@media (max-width: 800px) {
  .cuerpo { grid-template-columns: 1fr; }
  #menu { flex-direction: row; flex-wrap: wrap; border-right: 0; border-bottom: 1px solid var(--borde); }
  .burbuja { max-width: 95%; }
}
```

- [ ] **Step 5: `frontend/js/util.js` y `frontend/js/api.js`**

`util.js`:
```javascript
// Crea elementos DOM de forma segura (los textos nunca se interpretan como HTML).
function el(tag, props = {}, ...hijos) {
  const nodo = document.createElement(tag);
  for (const [clave, valor] of Object.entries(props)) {
    if (clave === "class") nodo.className = valor;
    else if (clave.startsWith("on")) nodo.addEventListener(clave.slice(2), valor);
    else nodo.setAttribute(clave, valor);
  }
  for (const hijo of hijos.flat()) nodo.append(hijo instanceof Node ? hijo : String(hijo ?? ""));
  return nodo;
}

function fechaCorta(iso) {
  const [anio, mes, dia] = String(iso).slice(0, 10).split("-");
  return `${dia}/${mes}/${anio}`;
}

function insignia(texto, tipo) {
  return el("span", { class: `insignia ${tipo}` }, texto);
}

function tabla(columnas, filas) {
  if (filas.length === 0) return el("p", {}, "No hay datos para mostrar.");
  return el(
    "table",
    {},
    el("thead", {}, el("tr", {}, columnas.map((c) => el("th", {}, c)))),
    el("tbody", {}, filas.map((fila) => el("tr", {}, fila.map((celda) => el("td", {}, celda)))))
  );
}
```

`api.js`:
```javascript
const Api = (() => {
  const guardarToken = (t) => sessionStorage.setItem("token", t);
  const hayToken = () => Boolean(sessionStorage.getItem("token"));
  const cerrarSesion = () => {
    sessionStorage.removeItem("token");
    location.reload();
  };

  function mensajeDeError(datos) {
    if (typeof datos.detail === "string") return datos.detail;
    return "Los datos enviados no son válidos.";
  }

  async function pedir(ruta, opciones = {}) {
    const cabeceras = { "Content-Type": "application/json" };
    const token = sessionStorage.getItem("token");
    if (token) cabeceras.Authorization = `Bearer ${token}`;
    const respuesta = await fetch(`/api${ruta}`, { ...opciones, headers: cabeceras });
    const datos = await respuesta.json().catch(() => ({}));
    if (respuesta.status === 401 && ruta !== "/auth/login") {
      cerrarSesion();
      throw new Error("Tu sesión terminó. Inicia sesión de nuevo.");
    }
    if (!respuesta.ok) throw new Error(mensajeDeError(datos));
    return datos;
  }

  return { pedir, guardarToken, hayToken, cerrarSesion };
})();
```

- [ ] **Step 6: `frontend/js/vistas.js`**

```javascript
const DESCRIPCION_ROL = {
  ADMINISTRADOR: "Puedes consultar información general, reportes de movimientos y administrar usuarios.",
  FARMACIA: "Puedes revisar inventario, vencimientos y controlar entradas y salidas de medicamentos.",
  ALMACENISTA: "Puedes consultar existencias y ubicaciones, y registrar entradas y salidas.",
};

function encabezadoVista(titulo) {
  return el("h2", {}, titulo);
}

function vistaInicio(usuario) {
  return el(
    "div",
    {},
    encabezadoVista(`Hola, ${usuario.nombre}`),
    el(
      "div",
      { class: "tarjeta" },
      el("p", {}, DESCRIPCION_ROL[usuario.rol]),
      el("p", {}, "Usa el menú de la izquierda o pregúntale al asistente virtual."),
      el("button", { class: "boton", type: "button", onclick: () => mostrar("chat") }, "Ir al chat")
    )
  );
}

async function vistaMedicamentos() {
  const meds = await Api.pedir("/medicamentos");
  return el(
    "div",
    {},
    encabezadoVista("Medicamentos"),
    tabla(
      ["Nombre", "Principio activo", "Presentación", "Ubicación"],
      meds.map((m) => [m.nombre, m.principio_activo, m.presentacion, m.ubicacion])
    )
  );
}

async function vistaInventario() {
  const meds = await Api.pedir("/medicamentos");
  return el(
    "div",
    {},
    encabezadoVista("Inventario"),
    tabla(
      ["Medicamento", "Cantidad actual", "Stock mínimo", "Estado"],
      meds.map((m) => [
        m.nombre,
        m.cantidad_actual,
        m.stock_minimo,
        m.cantidad_actual < m.stock_minimo ? insignia("Stock bajo", "alerta") : insignia("Normal", "ok"),
      ])
    )
  );
}

async function vistaVencimientos() {
  const meds = await Api.pedir("/medicamentos/proximos-vencer");
  return el(
    "div",
    {},
    encabezadoVista("Próximos a vencer (30 días)"),
    tabla(
      ["Medicamento", "Vence", "Días restantes", "Cantidad", "Ubicación"],
      meds.map((m) => [m.nombre, fechaCorta(m.fecha_vencimiento), m.dias_restantes, m.cantidad_actual, m.ubicacion])
    )
  );
}

function formularioMovimiento(meds) {
  const medicamento = el("select", { required: "" }, meds.map((m) => el("option", { value: m.id }, m.nombre)));
  const tipo = el("select", {}, el("option", { value: "ENTRADA" }, "Entrada"), el("option", { value: "SALIDA" }, "Salida"));
  const cantidad = el("input", { type: "number", min: "1", max: "100000", required: "", placeholder: "Cantidad" });
  const mensaje = el("p", { class: "error", role: "status" });

  async function enviar(evento) {
    evento.preventDefault();
    try {
      await Api.pedir("/movimientos", {
        method: "POST",
        body: JSON.stringify({ medicamento_id: Number(medicamento.value), tipo: tipo.value, cantidad: Number(cantidad.value) }),
      });
      mostrar("movimientos");
    } catch (error) {
      mensaje.textContent = error.message;
    }
  }

  return el(
    "form",
    { class: "tarjeta formulario-linea", onsubmit: enviar },
    el("label", {}, "Medicamento", medicamento),
    el("label", {}, "Tipo", tipo),
    el("label", {}, "Cantidad", cantidad),
    el("button", { class: "boton", type: "submit" }, "Registrar"),
    mensaje
  );
}

async function vistaMovimientos(usuario) {
  const [movs, meds] = await Promise.all([Api.pedir("/movimientos"), Api.pedir("/medicamentos")]);
  const contenedor = el("div", {}, encabezadoVista("Movimientos"));
  if (usuario.rol !== "ADMINISTRADOR") contenedor.append(formularioMovimiento(meds));
  contenedor.append(
    tabla(
      ["Fecha", "Medicamento", "Tipo", "Cantidad", "Responsable"],
      movs.map((m) => [
        fechaCorta(m.fecha),
        m.medicamento,
        insignia(m.tipo === "ENTRADA" ? "Entrada" : "Salida", m.tipo === "ENTRADA" ? "ok" : "alerta"),
        m.cantidad,
        m.usuario,
      ])
    )
  );
  return contenedor;
}

async function vistaUsuarios() {
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
    tabla(["Nombre", "Usuario", "Rol", "Estado"], usuarios.map((u) => [u.nombre, u.usuario, u.rol, u.estado]))
  );
}
```

- [ ] **Step 7: `frontend/js/chat.js`**

```javascript
const SUGERENCIAS = {
  ADMINISTRADOR: [
    "¿Cuántos medicamentos tenemos registrados actualmente?",
    "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?",
    "¿Qué medicamentos están próximos a vencer durante los próximos 30 días?",
    "¿Cuántas entradas y salidas de medicamentos se registraron durante este mes?",
    "¿Qué medicamento tiene mayor movimiento durante este mes?",
  ],
  FARMACIA: [
    "¿Cuántas unidades hay disponibles de acetaminofén?",
    "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?",
    "¿Qué medicamentos están próximos a vencer?",
    "¿Cuántas unidades de acetaminofén ingresaron durante este mes?",
    "¿Cuántas unidades de acetaminofén salieron durante este mes?",
  ],
  ALMACENISTA: [
    "¿Dónde está ubicada la insulina?",
    "¿Cuántas unidades hay disponibles de insulina?",
    "¿Cuándo fue registrada la última entrada de acetaminofén?",
    "¿Cuándo fue registrada la última salida de acetaminofén?",
    "¿Qué medicamentos debo revisar por vencimiento?",
  ],
};

function vistaChat(usuario) {
  const mensajes = el("div", { class: "mensajes", "aria-live": "polite" });
  const entrada = el("input", { type: "text", placeholder: "Escribe tu pregunta...", maxlength: "500", required: "", autocomplete: "off" });

  function agregar(quien, texto) {
    mensajes.append(
      el(
        "div",
        { class: `burbuja ${quien}` },
        el("span", { class: "quien" }, quien === "bot" ? "🤖 Asistente IPS" : "👤 Tú"),
        el("div", { class: "texto" }, texto)
      )
    );
    mensajes.scrollTop = mensajes.scrollHeight;
  }

  async function enviar(texto) {
    texto = texto.trim();
    if (!texto) return;
    agregar("usuario", texto);
    entrada.value = "";
    try {
      const datos = await Api.pedir("/chat", { method: "POST", body: JSON.stringify({ mensaje: texto }) });
      agregar("bot", datos.respuesta);
    } catch (error) {
      agregar("bot", `No pude completar la consulta: ${error.message}`);
    }
  }

  agregar("bot", "Hola, ¿en qué puedo ayudarte?");

  return el(
    "div",
    { class: "chat" },
    encabezadoVista("Chat"),
    mensajes,
    el(
      "div",
      { class: "sugerencias" },
      SUGERENCIAS[usuario.rol].map((s) => el("button", { type: "button", onclick: () => enviar(s) }, s))
    ),
    el(
      "form",
      { class: "entrada-chat", onsubmit: (evento) => { evento.preventDefault(); enviar(entrada.value); } },
      entrada,
      el("button", { class: "boton", type: "submit" }, "Enviar")
    )
  );
}
```

- [ ] **Step 8: `frontend/js/app.js`**

```javascript
const NOMBRE_ROL = {
  ADMINISTRADOR: "Administrador del sistema",
  FARMACIA: "Responsable de farmacia",
  ALMACENISTA: "Almacenista",
};
const TODOS = ["ADMINISTRADOR", "FARMACIA", "ALMACENISTA"];

// Las opciones del menú dependen del rol (la seguridad real está en el backend).
const MENU = [
  { id: "inicio", texto: "🏠 Inicio", roles: TODOS, vista: vistaInicio },
  { id: "chat", texto: "💬 Chat", roles: TODOS, vista: vistaChat },
  { id: "medicamentos", texto: "💊 Medicamentos", roles: TODOS, vista: vistaMedicamentos },
  { id: "inventario", texto: "📦 Inventario", roles: TODOS, vista: vistaInventario },
  { id: "movimientos", texto: "🔁 Movimientos", roles: TODOS, vista: vistaMovimientos },
  { id: "vencimientos", texto: "⏳ Vencimientos", roles: TODOS, vista: vistaVencimientos },
  { id: "usuarios", texto: "👥 Usuarios", roles: ["ADMINISTRADOR"], vista: vistaUsuarios },
];

let usuarioActual = null;

async function mostrar(id) {
  const item = MENU.find((m) => m.id === id && m.roles.includes(usuarioActual.rol));
  if (!item) return;
  document.querySelectorAll("#menu button").forEach((b) => b.classList.toggle("activo", b.dataset.id === id));
  const contenido = document.getElementById("contenido");
  contenido.replaceChildren(el("p", {}, "Cargando…"));
  try {
    contenido.replaceChildren(await item.vista(usuarioActual));
  } catch (error) {
    contenido.replaceChildren(el("p", { class: "error" }, error.message));
  }
}

function entrar(usuario) {
  usuarioActual = usuario;
  document.getElementById("pantalla-login").hidden = true;
  document.getElementById("app").hidden = false;
  document.getElementById("nombre-usuario").textContent = usuario.nombre;
  document.getElementById("rol-usuario").textContent = NOMBRE_ROL[usuario.rol];
  document.getElementById("menu").replaceChildren(
    ...MENU.filter((m) => m.roles.includes(usuario.rol)).map((m) =>
      el("button", { type: "button", "data-id": m.id, onclick: () => mostrar(m.id) }, m.texto)
    )
  );
  mostrar("inicio");
}

document.getElementById("form-login").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const error = document.getElementById("login-error");
  error.textContent = "";
  try {
    const datos = await Api.pedir("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        usuario: document.getElementById("login-usuario").value.trim(),
        password: document.getElementById("login-password").value,
      }),
    });
    Api.guardarToken(datos.token);
    entrar(datos.usuario);
  } catch (e) {
    error.textContent = e.message;
  }
});

document.getElementById("btn-salir").addEventListener("click", () => Api.cerrarSesion());

(async () => {
  if (!Api.hayToken()) return;
  try {
    entrar(await Api.pedir("/auth/me"));
  } catch (e) {
    /* si la sesión no sirve, se queda en la pantalla de ingreso */
  }
})();
```

- [ ] **Step 9: Verificar sintaxis JS y levantar todo**

Run:
```bash
for f in frontend/js/*.js; do node --check "$f" && echo "OK $f"; done   # solo si node está instalado
docker compose up -d --build
sleep 5
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/
curl -s -X POST http://localhost/api/auth/login -H 'Content-Type: application/json' -d '{"usuario":"admin","password":"demo1234"}'
```
Expected: `200` para `/` y un JSON con `token` y `"rol":"ADMINISTRADOR"` (si `FRONTEND_PORT` no es 80, usar ese puerto).

- [ ] **Step 10: Recorrido manual (anotar cualquier defecto y corregirlo antes de seguir)**

Abrir `http://localhost`. Comprobar:
1. Login con `admin/demo1234` → menú con 7 opciones (incluye Usuarios). Con `farmacia` y `almacen` → 6 opciones (sin Usuarios).
2. Chat: pulsar cada botón de sugerencia → respuesta con datos; escribir "hola" → mensaje de no entendido.
3. Inventario muestra 3 medicamentos con "Stock bajo"; Vencimientos muestra 3 filas.
4. Como `farmacia`: registrar una entrada en Movimientos → aparece en la tabla y el inventario sube.
5. Como `admin`: crear un usuario en Usuarios y verlo en la lista.
6. Reducir el ancho de la ventana: el menú pasa a horizontal y todo se sigue viendo.
7. "Salir" vuelve al login.

- [ ] **Step 11: Commit**

```bash
git add frontend docker-compose.yml
git commit -m "feat: interfaz web de la IPS con menú por rol, chat y vistas de datos"
```

---

### Task 6: Integración de punta a punta y prueba de humo

**Files:**
- Create: `scripts/smoke.py`

**Interfaces:**
- Consumes: la app completa levantada con `docker compose up --build` (frontend en `http://localhost`).
- Produces: `python3 scripts/smoke.py [URL_BASE]` → imprime las 15 preguntas con su respuesta; termina con código 1 si alguna no obtiene una respuesta válida.

- [ ] **Step 1: Crear `scripts/smoke.py`**

```python
"""Prueba de humo: recorre las 15 preguntas del proyecto a través de nginx → FastAPI → PostgreSQL."""
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost"

PREGUNTAS = {
    "admin": [
        "¿Cuántos medicamentos tenemos registrados actualmente?",
        "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?",
        "¿Qué medicamentos están próximos a vencer durante los próximos 30 días?",
        "¿Cuántas entradas y salidas de medicamentos se registraron durante este mes?",
        "¿Qué medicamento tiene mayor movimiento durante este mes?",
    ],
    "farmacia": [
        "¿Cuántas unidades hay disponibles de acetaminofén?",
        "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?",
        "¿Qué medicamentos están próximos a vencer?",
        "¿Cuántas unidades de acetaminofén ingresaron durante este mes?",
        "¿Cuántas unidades de acetaminofén salieron durante este mes?",
    ],
    "almacen": [
        "¿Dónde está ubicada la insulina?",
        "¿Cuántas unidades hay disponibles de insulina?",
        "¿Cuándo fue registrada la última entrada de acetaminofén?",
        "¿Cuándo fue registrada la última salida de acetaminofén?",
        "¿Qué medicamentos debo revisar por vencimiento?",
    ],
}
RECHAZOS = ("No pude identificar tu consulta", "Esa consulta no está disponible")


def post(ruta, cuerpo, token=None):
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(
        f"{BASE}/api{ruta}", data=json.dumps(cuerpo).encode(), headers=cabeceras, method="POST"
    )
    with urllib.request.urlopen(peticion) as respuesta:
        return json.load(respuesta)


fallos = 0
for usuario, preguntas in PREGUNTAS.items():
    token = post("/auth/login", {"usuario": usuario, "password": "demo1234"})["token"]
    print(f"\n=== {usuario} ===")
    for pregunta in preguntas:
        respuesta = post("/chat", {"mensaje": pregunta}, token)["respuesta"]
        valida = not respuesta.startswith(RECHAZOS)
        fallos += not valida
        print(f"{'OK  ' if valida else 'FAIL'} {pregunta}\n     → {respuesta}\n")

print("Resultado:", "TODO BIEN" if fallos == 0 else f"{fallos} preguntas fallaron")
sys.exit(1 if fallos else 0)
```

- [ ] **Step 2: Levantar desde cero y ejecutar la prueba de humo**

Run:
```bash
docker compose down -v
docker compose up -d --build
sleep 8
python3 scripts/smoke.py
```
Expected: 15 líneas `OK` y `Resultado: TODO BIEN`. Confirmar que el primer arranque (`down -v`) crea los datos solo con `init.sql`.

- [ ] **Step 3: Ejecutar la suite completa una última vez**

Run: `docker compose run --rm -T backend pytest -q`
Expected: todas en verde.

- [ ] **Step 4: Commit**

```bash
git add scripts
git commit -m "test: prueba de humo de las 15 preguntas de punta a punta"
```

---

### Task 7: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Escribir `README.md`**

````markdown
# Chatbot IPS — MVP académico

Asistente virtual para una IPS (centro de salud) que responde preguntas sobre medicamentos, inventario, movimientos, vencimientos y ubicaciones, según el rol de quien pregunta. Proyecto universitario de Administración en Salud. **Todos los datos son ficticios.**

## Objetivo

Demostrar el flujo completo: **Usuario → Chatbot → Backend → Base de datos relacional → Respuesta**.

## Arquitectura

```
Navegador ──▶ nginx (frontend, puerto 80) ──/api──▶ FastAPI (backend) ──▶ PostgreSQL
```

Son tres contenedores que se levantan con Docker Compose. nginx sirve la página y reenvía las peticiones `/api` al backend, que consulta la base de datos.

## Tecnologías

| Parte | Tecnología |
|---|---|
| Página web | HTML, CSS y JavaScript (sin frameworks) |
| Backend | Python + FastAPI |
| Base de datos | PostgreSQL |
| Contenedores | Docker + Docker Compose |
| Seguridad | Contraseñas con bcrypt, sesión con token JWT |

Todo es gratuito y corre en su computador.

## Estructura del proyecto

```
db/init.sql        Tablas y datos ficticios
backend/app/       Código del servidor (API, login, chatbot)
backend/tests/     Pruebas automáticas
frontend/          Página web y configuración de nginx
scripts/smoke.py   Prueba rápida con las 15 preguntas
docs/superpowers/  Diseño y plan de implementación
```

## Cómo instalarlo

1. Instale **Docker Desktop** (incluye Docker Compose) y ábralo.
2. Copie el archivo de configuración: `cp .env.example .env` (puede cambiar las claves si quiere).

## Cómo ejecutarlo

```bash
docker compose up --build
```

Abra **http://localhost** en el navegador. La documentación técnica interactiva de la API está en **http://localhost/api/docs**.

Para apagar: `Ctrl+C` y luego `docker compose down`. Para borrar los datos y empezar de cero: `docker compose down -v`.

Si el puerto 80 está ocupado, cambie `FRONTEND_PORT` en `.env` (por ejemplo `8080`) y abra `http://localhost:8080`.

## Usuarios de prueba

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `demo1234` | Administrador del sistema |
| `farmacia` | `demo1234` | Responsable de farmacia |
| `almacen` | `demo1234` | Almacenista |

## Ejemplos de preguntas y respuestas

**Administrador**
- ¿Cuántos medicamentos tenemos registrados actualmente? → *Actualmente hay 12 medicamentos registrados en el sistema.*
- ¿Cuáles son los medicamentos que están por debajo del mínimo establecido? → lista con Acetaminofén, Amoxicilina y Losartán.
- ¿Qué medicamentos están próximos a vencer durante los próximos 30 días?
- ¿Cuántas entradas y salidas de medicamentos se registraron durante este mes?
- ¿Qué medicamento tiene mayor movimiento durante este mes?

**Responsable de farmacia**
- ¿Cuántas unidades hay disponibles de acetaminofén? → *Actualmente hay 15 unidades disponibles de Acetaminofén.*
- ¿Cuántas unidades de acetaminofén ingresaron durante este mes? / ¿…salieron durante este mes?
- ¿Qué medicamentos están próximos a vencer?

**Almacenista**
- ¿Dónde está ubicada la insulina? → *Insulina se encuentra en: Nevera 1.*
- ¿Cuándo fue registrada la última entrada de acetaminofén?
- ¿Qué medicamentos debo revisar por vencimiento?

Si el chatbot no entiende, responde: *"No pude identificar tu consulta. Puedes preguntarme sobre inventario, medicamentos, movimientos, vencimientos o ubicaciones."* y no inventa datos. Si pregunta algo que no corresponde a su rol: *"Esa consulta no está disponible para tu rol."*

Limitación conocida: el chatbot no entiende rangos de fechas libres (por ejemplo "esta semana"); trabaja con "este mes" y "próximos 30 días".

## Cómo funciona la conexión con la base de datos

1. El backend abre una conexión a PostgreSQL en cada petición (datos de conexión en `.env`).
2. Todas las consultas están en `backend/app/consultas.py` y usan parámetros (`%s`), nunca texto pegado, para evitar inyección SQL.
3. El chatbot y los endpoints REST usan las mismas consultas, así que siempre dan los mismos resultados.
4. Al registrar un movimiento, el sistema actualiza el inventario y guarda el movimiento en la misma transacción; no permite dejar el stock en negativo.

Tablas: `roles`, `usuarios`, `medicamentos`, `movimientos` y `servicios`.

## Cómo funciona el chatbot

1. Limpia el texto (minúsculas, sin tildes ni signos).
2. Busca si menciona un medicamento de la base de datos.
3. Detecta la intención con palabras clave (por ejemplo "cuánto / cantidad / queda / hay" + un medicamento = consultar inventario). Distintas formas de preguntar llegan a la misma consulta.
4. Verifica que el rol tenga permiso para esa intención.
5. Consulta la base de datos y redacta la respuesta.

La lógica está separada en `backend/app/chatbot/`, de modo que en el futuro se pueda cambiar por un modelo de IA local sin tocar el resto.

## Cómo funciona el sistema de roles

Al iniciar sesión el backend entrega un token que incluye el rol. En cada petición se revisa el token y se consulta al usuario en la base de datos (si fue desactivado, se rechaza).

| Consulta | Administrador | Farmacia | Almacenista |
|---|---|---|---|
| Total de medicamentos, movimientos del mes, mayor movimiento | ✅ | | |
| Bajo el mínimo | ✅ | ✅ | |
| Próximos a vencer / revisar por vencimiento | ✅ | ✅ | ✅ |
| Unidades disponibles de un medicamento | ✅ | ✅ | ✅ |
| Entradas y salidas del mes de un medicamento | | ✅ | |
| Ubicación, última entrada, última salida | | | ✅ |
| Registrar entradas/salidas (formulario) | | ✅ | ✅ |
| Crear y ver usuarios | ✅ | | |

El menú de la página se adapta al rol, pero la protección real está en el servidor: aunque alguien llame a la API directamente, recibe error 403 si su rol no corresponde.

## Pruebas

```bash
docker compose run --rm backend pytest -q   # pruebas automáticas (restauran los datos de demostración)
python3 scripts/smoke.py                    # las 15 preguntas de punta a punta
```
````

- [ ] **Step 2: Verificar que el README es fiel al comportamiento**

Run: `python3 scripts/smoke.py` y comparar 2 respuestas con los ejemplos del README (`12 medicamentos registrados`, `Nevera 1`).
Expected: coinciden.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README con instalación, ejecución, usuarios, ejemplos y roles"
```

---

## Autorevisión

- **Cobertura del spec:** §3 arquitectura → Tareas 1, 2, 5; §4 estructura → mapa de archivos; §5 BD y datos → Tarea 1; §6 chatbot e intenciones/roles → Tarea 4; §7 API → Tareas 2–4; §8 frontend → Tarea 5; §9 pruebas → Tareas 2–4 y 6; README/documentación del prompt → Tarea 7. La intención adicional `REVISION_VENCIMIENTO` se agrega al spec en la Tarea 4.
- **Consistencia de nombres:** constantes de intención, `PERMISOS`, `MANEJADORES`, funciones de `consultas.py` y fixtures se usan con los mismos nombres en todas las tareas.
- **Sin marcadores pendientes.** Todo el código de cada paso es el definitivo.
- **Riesgos a vigilar al ejecutar:** (1) si `FRONTEND_PORT=80` está ocupado en su equipo, cambiarlo en `.env`; (2) las pruebas reinician la BD de la demo (documentado en el README).
