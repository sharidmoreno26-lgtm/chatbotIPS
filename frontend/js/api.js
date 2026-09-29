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
