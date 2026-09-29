# CLAUDE.md

Este archivo orienta a Claude Code (claude.ai/code) cuando trabaja con el código de este repositorio.

## Qué es

MVP académico (Administración en Salud) de un chatbot para una IPS: consulta de medicamentos, inventario, movimientos, vencimientos y ubicaciones según el rol del usuario. **Solo datos ficticios.** Flujo: navegador → nginx → FastAPI → PostgreSQL. La guía para personas está en `docs/MANUAL_USUARIO.md` y `README.md`.

## Comandos

Todo corre en Docker; no hay Python ni Node instalados en el equipo para el proyecto.

```bash
cp .env.example .env                      # solo la primera vez (.env no se versiona)
docker compose up --build -d              # encender (web en http://localhost:${FRONTEND_PORT:-80})
docker compose restart backend            # tras cambiar código del backend (uvicorn no recarga solo)
docker compose run --rm -T backend pytest -q                                   # toda la suite
docker compose run --rm -T backend pytest tests/test_chat.py::test_admin_total_medicamentos -q   # una prueba
python3 scripts/smoke.py http://localhost:8080   # las 15 preguntas de punta a punta (usar el puerto de .env)
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/init.sql     # reiniciar datos de ejemplo
docker run --rm -v "$PWD/frontend/js:/w:ro" node:22-alpine node --check /w/vistas.js            # sintaxis JS (no hay Node local)
```

- No hay linter ni formateador configurados.
- `backend/app` y `backend/tests` están montados como volumen en el contenedor `backend`: no hace falta reconstruir la imagen al editarlos. Reconstruir (`docker compose build backend`) solo si cambian `requirements*.txt`. El frontend sí se copia a la imagen: `docker compose up -d --build frontend` tras editarlo.
- En este equipo el puerto 80 está ocupado; el `.env` local (no versionado) usa `FRONTEND_PORT=8080`.

## Arquitectura (lo que exige leer varios archivos)

**Enrutamiento.** nginx (`frontend/nginx.conf`) sirve la web y reenvía `/api/` al backend quitando el prefijo. El backend define rutas **sin** prefijo (`/chat`, `/medicamentos`…) y usa `FastAPI(root_path="/api")` solo para que `/api/docs` funcione. El JS siempre llama a `/api/...`.

**Un solo lugar para el SQL de negocio.** `backend/app/consultas.py` contiene todas las consultas y escrituras de negocio; las usan tanto los routers REST (`app/routers/`) como el chatbot, para que ambos den siempre el mismo resultado. SQL siempre parametrizado (`%s`, psycopg 3, sin ORM). Una conexión por petición (`db.get_conn`); los endpoints que escriben llaman a `conn.commit()` explícitamente y, si lanzan `HTTPException`, la transacción se revierte.

**Autenticación y roles.** JWT (`auth.py`); en **cada** petición se vuelve a leer el usuario y su rol de la BD (un usuario eliminado o inactivo deja de funcionar aunque su token siga vigente). Roles como constantes en `roles.py` (`ADMINISTRADOR`, `FARMACIA`, `ALMACENISTA`); se protegen endpoints con `requiere_roles(...)`. El menú del frontend solo oculta opciones: la seguridad real está en el backend.

**Chatbot por reglas** (`backend/app/chatbot/`): `normalizador` (minúsculas, sin tildes ni signos) → `servicio.buscar_medicamento` (busca nombre o principio activo del texto en la BD) → `intenciones.detectar_intencion` (regex, el orden de las reglas importa) → `permisos.PERMISOS` (rol permitido por intención) → `respuestas.MANEJADORES` (consulta y redacta). Una intención nueva exige tocar los tres módulos; `test_toda_intencion_tiene_permisos_y_manejador` lo comprueba. Las intenciones que necesitan un medicamento solo se detectan si el texto menciona uno existente; si no, la respuesta es el mensaje literal de "no entendido". Los mensajes literales `NO_ENTENDIDO` y `SIN_PERMISO` están en `chatbot/servicio.py`.

**Base de datos.** `db/init.sql` borra y recrea todas las tablas (idempotente) y carga los datos de ejemplo con **fechas relativas a hoy**; por eso se desactualizan y hay que volver a ejecutarlo (ver comando arriba). No hay migraciones: cualquier cambio de esquema exige reiniciar los datos. Docker solo ejecuta `init.sql` cuando el volumen está vacío. El archivo montado en el contenedor `db` puede quedar obsoleto si git lo reemplaza, por eso el comando de reinicio lo pasa por stdin desde el equipo. La zona horaria de la BD es `America/Bogota` (`CURRENT_DATE` depende de ella).

**Reglas de negocio no obvias.**
- Las entradas se registran solo por `POST /ingresos` (lote + vencimiento + fecha de ingreso; el responsable sale del token). `POST /movimientos` solo acepta `SALIDA`.
- El vencimiento del medicamento es una sola fecha, la más próxima (`LEAST` con el del lote, o el del lote si el actual ya venció). No se lleva la cantidad por lote.
- `movimientos.responsable` guarda el nombre al registrar; `usuario_id` pasa a `NULL` al borrar el usuario (`DELETE /usuarios/{id}` borra la fila y libera el nombre). No se puede eliminar el propio usuario.
- El nombre de medicamento es único sin distinguir mayúsculas (índice único `lower(nombre)`).

**Frontend.** HTML/CSS/JS puro, sin build ni módulos: los scripts se cargan en orden (`util`, `api`, `vistas`, `chat`, `app`) y comparten funciones globales. Los elementos se crean con `el()` (nodos de texto): **no usar `innerHTML` con datos**. `Api.pedir` centraliza el token (sessionStorage), el 401 y los mensajes de error en español. El JS de `frontend/js` se puede ejercitar con jsdom en Docker contra la API real (no hay pruebas de interfaz versionadas).

## Pruebas

`backend/tests/conftest.py` **reinicia la BD real de la demo** con `db/init.sql` antes de cada prueba y otra vez al terminar la sesión; las pruebas usan la BD real (no hay mocks). Fixtures: `client`, `conn`, `admin`/`farmacia`/`almacen` (cabeceras con token), `hoy` (fecha de la BD) y `fecha_mes(dia)`. Ids sembrados: usuarios 1=admin, 2=farmacia, 3=almacen; medicamentos 1..12 (1 = Acetaminofén). Los tests de chat y de movimientos dependen de las cifras exactas del seed (12 medicamentos, 3 bajo mínimo, 3 por vencer, 15 movimientos: 7 entradas y 8 salidas).

## Convenciones del proyecto

- Identificadores, mensajes de usuario y documentación en **español**; sin sobreingeniería (MVP académico, costo $0, todo local).
- Usuarios de prueba: `admin`, `farmacia`, `almacen`; contraseña `demo1234`.
- Git: flujo trunk-based con una sola rama `main`; identidad del repo `sharidmoreno26-lgtm`. **Los commits no llevan `Co-Authored-By` ni mención a IA.** No hacer `git push` sin que se pida (remoto `origin` por SSH).
- `docs/superpowers/specs` y `docs/superpowers/plans` guardan el diseño y el plan de cada funcionalidad; `prompts/` guarda los requerimientos originales.
