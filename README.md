# Chatbot IPS — MVP académico

Asistente virtual para una IPS (centro de salud) que responde preguntas sobre medicamentos, inventario, movimientos, vencimientos y ubicaciones, según el rol de quien pregunta. Proyecto universitario de Administración en Salud. **Todos los datos son ficticios.**

> Guía paso a paso para encender el proyecto, actualizar los datos de ejemplo y hacer la demostración: **[docs/MANUAL_USUARIO.md](docs/MANUAL_USUARIO.md)**.

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
docs/              Manual de usuario, diseños y planes de implementación
prompts/           Prompts originales con los requerimientos del proyecto
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
| Ingreso de medicamentos (formulario con lote y vencimiento) | | ✅ | ✅ |
| Registrar salidas (formulario) | | ✅ | ✅ |
| Crear, ver y eliminar usuarios | ✅ | | |

El menú de la página se adapta al rol, pero la protección real está en el servidor: aunque alguien llame a la API directamente, recibe error 403 si su rol no corresponde.

## Ingreso de medicamentos y eliminación de usuarios

**Ingreso de medicamentos** (farmacia y almacenista, en *Movimientos → Ingreso de medicamentos*): se registra el medicamento (existente o nuevo), la cantidad, el número de lote, la fecha de vencimiento, la fecha de ingreso y el responsable, que es siempre quien tiene la sesión iniciada. Al guardar, el sistema suma la cantidad al inventario y deja el movimiento con su lote para poder rastrearlo. No se aceptan lotes ya vencidos, fechas de ingreso futuras ni datos incompletos.

El medicamento conserva **una sola fecha de vencimiento: la más próxima** entre lo que ya tenía y el lote que ingresa. Límite conocido: el sistema no lleva la cantidad de cada lote por separado; las salidas no descuentan de un lote en particular.

**Eliminar usuarios** (administrador, en *Usuarios*): antes de eliminar se pide confirmación. El usuario se borra de la base de datos: ya no puede entrar y su nombre de usuario queda libre para registrarlo de nuevo. Los movimientos que hizo se conservan y siguen mostrando su nombre como responsable. No se puede eliminar el propio usuario.

Endpoints nuevos: `POST /ingresos` y `DELETE /usuarios/{id}`. `POST /movimientos` ahora solo registra salidas.

## Pruebas

```bash
docker compose run --rm backend pytest -q   # pruebas automáticas (restauran los datos de demostración)
python3 scripts/smoke.py                    # las 15 preguntas de punta a punta
```

Si cambiaste `FRONTEND_PORT`, el script necesita la URL, por ejemplo: `python3 scripts/smoke.py http://localhost:8080`.

## Antes de la demo: reiniciar los datos

**Después de actualizar el código** (por ejemplo, con `git pull`) reinicie también los datos: el esquema de la base cambia y la base guardada del equipo no se actualiza sola. Sin esto, la pantalla *Movimientos* muestra "Error del servidor".

Las fechas de los datos de ejemplo son relativas al día en que se ejecuta `init.sql`, y el volumen de la base de datos persiste. Con el tiempo los datos de demostración quedan desactualizados. Para reiniciarlos:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/init.sql
```

(`init.sql` borra y vuelve a crear las tablas). Alternativa: `docker compose down -v` y luego `docker compose up --build`. Ejecutar las pruebas con pytest también restaura los datos.
