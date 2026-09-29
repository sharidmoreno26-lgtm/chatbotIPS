Quiero que implementes las siguientes funcionalidades dentro del sistema de gestión para una **IPS de salud**, respetando la arquitectura, diseño visual y estructura general del sistema existente.

### 1. Rol Administrador – Gestión de usuarios

Dentro del rol **Administrador**, debe existir un apartado llamado **“Usuarios”** que permita gestionar los usuarios de la plataforma.

El Administrador debe poder:

- **Crear nuevos usuarios**, registrando la información solicitada por el sistema.
- **Asignar un rol** al usuario de acuerdo con las funciones que desempeñará dentro de la plataforma.
- **Visualizar el listado de usuarios registrados**, mostrando su información básica y el rol asignado.
- **Eliminar usuarios existentes**.

Al seleccionar la opción de eliminar un usuario, el sistema debe mostrar primero un mensaje de confirmación:

**“¿Está seguro de que desea eliminar este usuario?”**

El usuario solo debe ser eliminado cuando el Administrador confirme la acción.

La gestión de usuarios debe permitir mantener un control organizado de las personas que tienen acceso al sistema y de los roles asignados a cada una.

---

### 2. Rol Almacén y Farmacia – Ingreso de medicamentos

Dentro del rol **Almacén y Farmacia**, debe existir en la pantalla de inicio la sección **“Movimientos”**.

Dentro de esta sección debe estar disponible la opción **“Ingreso de medicamentos”**, permitiendo registrar de manera sencilla los medicamentos que ingresan al almacén o farmacia.

Al seleccionar **“Ingreso de medicamentos”**, el sistema debe mostrar un formulario para registrar la información correspondiente a cada medicamento.

El formulario debe incluir como mínimo:

- **Nombre del medicamento.**
- **Cantidad ingresada.**
- **Número de lote.**
- **Fecha de vencimiento.**
- **Fecha de ingreso.**
- **Responsable del ingreso.**

Una vez diligenciada la información, el sistema debe permitir **guardar el ingreso del medicamento**.

Al guardar correctamente el registro, el sistema debe:

- Incorporar el medicamento al inventario.
- Actualizar automáticamente la cantidad disponible.
- Registrar el lote correspondiente.
- Registrar la fecha de vencimiento.
- Registrar la fecha de ingreso.
- Identificar al responsable que realizó el ingreso.
- Mantener la trazabilidad del movimiento realizado.

### 3. Validaciones

Para ambas funcionalidades, el sistema debe validar que la información obligatoria esté completa antes de permitir guardar o ejecutar una acción.

En el caso del ingreso de medicamentos, se debe evitar registrar información incompleta o inconsistente.

En el caso de eliminación de usuarios, siempre debe solicitarse confirmación antes de ejecutar la eliminación.

### 4. Consideraciones de implementación

Integra estas funcionalidades dentro de la interfaz actual sin modificar innecesariamente las demás funciones existentes.

Mantén una interfaz **clara, sencilla, intuitiva y acorde con una plataforma de gestión de una IPS de salud**.

No me hagas preguntas técnicas sobre cómo implementar estas funciones. **Toma las decisiones técnicas necesarias por tu cuenta**, respetando la arquitectura existente y procurando que las nuevas funcionalidades queden correctamente conectadas con el sistema actual.
