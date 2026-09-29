# Manual de usuario — Chatbot IPS

Guía paso a paso para encender el proyecto, dejar los datos de ejemplo al día y hacer la demostración. No necesita saber programar: solo copiar y pegar los comandos.

> Todos los datos son **ficticios**. No hay pacientes ni información clínica real.

---

## 1. Qué necesita antes de empezar

- **Docker Desktop** instalado y **abierto** (el icono de la ballena debe estar quieto, sin la palabra "starting").
- Una **terminal abierta dentro de la carpeta del proyecto** (`chatbotIps`).
  - En Windows con WSL: abra la terminal de Ubuntu y escriba `cd ~/workspace/chatbotIps`.
- Un navegador (Chrome, Edge o Firefox).

Solo la primera vez, copie el archivo de configuración:

```bash
cp .env.example .env
```

---

## 2. Encender el proyecto

```bash
docker compose up --build
```

- La primera vez tarda unos minutos (descarga e instala todo). Las siguientes veces tarda segundos.
- Cuando la terminal deje de mostrar mensajes nuevos, el sistema está listo. **No cierre esa terminal**: si la cierra, se apaga.
- Para encenderlo **sin ocupar la terminal**, use `docker compose up --build -d` (queda funcionando de fondo).

Abra en el navegador: **http://localhost**

> Si el puerto 80 está ocupado (es común), abra el archivo `.env`, cambie la línea `FRONTEND_PORT=80` por `FRONTEND_PORT=8080`, apague y encienda de nuevo, y entre por **http://localhost:8080**.

**Comprobar que todo está bien:**

```bash
docker compose ps
```
Deben aparecer tres servicios en estado `running` o `Up`: `db`, `backend` y `frontend`.

También puede abrir `http://localhost/api/salud` (o con `:8080`): debe mostrar `{"estado":"ok"}`.

---

## 3. Apagar el proyecto

- Si lo encendió con la terminal ocupada: presione `Ctrl + C` y luego escriba `docker compose down`.
- Si lo encendió con `-d`: escriba `docker compose down`.

Apagar **no borra** los datos: al volver a encender siguen ahí.

---

## 4. Datos de ejemplo (data fake)

### Qué contienen
Los datos están en el archivo `db/init.sql`. Incluyen:

| Dato | Cantidad |
|---|---|
| Usuarios (uno por rol) | 3 |
| Medicamentos | 12 |
| Medicamentos por debajo del mínimo | 3 (Acetaminofén, Amoxicilina y Losartán) |
| Medicamentos que vencen en menos de 30 días | 3 (Omeprazol, Insulina e Ibuprofeno) |
| Movimientos | 15 (7 entradas con lote y vencimiento, 8 salidas) |

### Por qué hay que "actualizarlos"
Las fechas de los datos **se calculan a partir del día en que se cargan** (por ejemplo "vence en 15 días" o "entrada de este mes"). La base de datos guarda esos datos aunque apague el proyecto, así que con el paso de los días quedan viejos: "este mes" puede quedar sin movimientos y los vencimientos dejan de ser cercanos.

**Regla práctica: reinicie los datos el día anterior a la demostración o el mismo día.**

### Cómo actualizarlos (recomendado)
Con el proyecto encendido, en la terminal, dentro de la carpeta del proyecto:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/init.sql
```

Borra las tablas y las vuelve a crear con fechas de **hoy**. Tarda un par de segundos. Los usuarios que haya creado y los ingresos que haya registrado **se pierden** (vuelve a quedar el estado original).

### Otra forma (empezar de cero)
```bash
docker compose down -v
docker compose up --build
```
La `-v` borra la base de datos guardada; al encender se crea de nuevo con los datos de hoy.

### Cuándo es obligatorio reiniciarlos
- Antes de una demostración.
- **Cada vez que actualice el código** (por ejemplo con `git pull`): el esquema de la base puede cambiar. Si no lo hace, la pantalla *Movimientos* muestra "Error del servidor".
- Después de correr las pruebas automáticas (las dejan restauradas, pero conviene comprobarlo).

---

## 5. Entrar al sistema

Abra **http://localhost** (o `:8080`) e ingrese con:

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `demo1234` | Administrador del sistema |
| `farmacia` | `demo1234` | Responsable de farmacia |
| `almacen` | `demo1234` | Almacenista |

El menú de la izquierda cambia según el rol. Para cambiar de rol, presione **Salir** (arriba a la derecha) y entre con otro usuario.

---

## 6. Recorrido de la demostración

### Administrador (`admin`)
1. **Chat:** pruebe los botones de sugerencia o escriba, por ejemplo:
   - ¿Cuántos medicamentos tenemos registrados actualmente?
   - ¿Cuáles son los medicamentos que están por debajo del mínimo establecido?
   - ¿Qué medicamentos están próximos a vencer durante los próximos 30 días?
   - ¿Cuántas entradas y salidas de medicamentos se registraron durante este mes?
   - ¿Qué medicamento tiene mayor movimiento durante este mes?
2. **Usuarios:** cree un usuario (nombre, usuario en minúsculas, contraseña de 8 o más caracteres y rol). Luego elimínelo con el botón **Eliminar**: aparece la pregunta *"¿Está seguro de que desea eliminar este usuario?"* y solo se borra si acepta. Puede volver a registrar el mismo nombre de usuario. No puede eliminar su propio usuario.
3. **Movimientos, Inventario, Vencimientos, Medicamentos:** consulta de tablas (el administrador solo consulta, no registra).

### Responsable de farmacia (`farmacia`)
- **Chat:** ¿Cuántas unidades hay disponibles de acetaminofén? · ¿Qué medicamentos están próximos a vencer? · ¿Cuántas unidades de acetaminofén ingresaron / salieron durante este mes?
- **Movimientos → Ingreso de medicamentos:** elija el medicamento (o *Nuevo medicamento*), cantidad, número de lote, fecha de vencimiento y fecha de ingreso. El responsable se llena solo con su usuario. Al guardar, aparece el mensaje de éxito y la cantidad disponible sube; el ingreso queda en la tabla con su lote y fecha de vencimiento.
- **Movimientos → Registrar salida:** medicamento y cantidad. No permite sacar más de lo que hay.

### Almacenista (`almacen`)
- **Chat:** ¿Dónde está ubicada la insulina? · ¿Cuándo fue registrada la última entrada de acetaminofén? · ¿Qué medicamentos debo revisar por vencimiento?
- **Movimientos:** igual que farmacia (ingreso y salida).

### Cosas que el chatbot NO hace (dígalo en la demo si preguntan)
- Si la pregunta no la entiende, responde: *"No pude identificar tu consulta…"* y no inventa datos.
- Si un rol pregunta algo que no le corresponde: *"Esa consulta no está disponible para tu rol."*
- No entiende rangos libres como "esta semana"; trabaja con "este mes" y "próximos 30 días".
- El sistema no lleva la cantidad de cada lote por separado: cada medicamento conserva una sola fecha de vencimiento (la más próxima).

---

## 7. Lista de comprobación antes de la demostración

1. Docker Desktop abierto.
2. `docker compose up --build -d` y `docker compose ps` con los tres servicios activos.
3. **Reiniciar los datos** (sección 4).
4. Entrar con los tres usuarios y probar un par de preguntas en cada uno.
5. (Opcional) Prueba automática de las 15 preguntas:
   ```bash
   python3 scripts/smoke.py http://localhost
   ```
   (con `:8080` si cambió el puerto). Debe terminar con **TODO BIEN**.
6. Volver a reiniciar los datos si registró ingresos o usuarios de prueba.

---

## 8. Si algo falla

| Síntoma | Qué hacer |
|---|---|
| `Cannot connect to the Docker daemon` o el comando `docker` no funciona | Abra Docker Desktop y espere a que termine de iniciar. |
| `port is already allocated` / el puerto 80 está ocupado | Cambie `FRONTEND_PORT` a `8080` en `.env`, apague (`docker compose down`), encienda de nuevo y use `http://localhost:8080`. |
| La página no carga | Ejecute `docker compose ps`. Si falta algún servicio, `docker compose up --build -d` de nuevo. Revise los mensajes con `docker compose logs backend`. |
| *Movimientos* muestra "Error del servidor" | Reinicie los datos (sección 4): la base guardada es de una versión anterior. |
| El chat dice que no hay movimientos "este mes" o los vencimientos no cuadran | Los datos están viejos: reinícielos (sección 4). |
| "Usuario o contraseña incorrectos" con `admin`/`farmacia`/`almacen` | Reinicie los datos (sección 4): puede haber eliminado ese usuario. La clave es `demo1234`. |
| "Tu sesión terminó" | Vuelva a iniciar sesión. |
| No sé si algo se dañó | `docker compose down -v` y `docker compose up --build`: vuelve todo al estado original. |

---

## 9. Pruebas automáticas (opcional)

```bash
docker compose run --rm backend pytest -q
```
Corre todas las pruebas (unas 144). Al terminar dejan los datos de ejemplo restaurados.

---

## 10. Resumen de comandos

| Para… | Comando |
|---|---|
| Encender | `docker compose up --build` (o con `-d` para no ocupar la terminal) |
| Ver el estado | `docker compose ps` |
| Apagar | `docker compose down` |
| Actualizar los datos de ejemplo | `docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/init.sql` |
| Empezar de cero | `docker compose down -v` y luego `docker compose up --build` |
| Probar las 15 preguntas | `python3 scripts/smoke.py http://localhost` |
| Ver mensajes del servidor | `docker compose logs backend` |
