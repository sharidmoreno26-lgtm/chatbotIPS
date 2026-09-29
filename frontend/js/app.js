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
