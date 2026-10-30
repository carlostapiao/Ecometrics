(() => {
  const campo = document.getElementById("token");
  const fragmento = window.location.hash.slice(1);
  if (/^[A-Za-z0-9_-]{43}$/.test(fragmento)) campo.value = fragmento;
  if (window.location.hash) history.replaceState(null, "", window.location.pathname + window.location.search);
  if (!campo.value) document.getElementById("aviso-enlace").textContent = "Abre el enlace completo que te compartió el gerente para activar la cuenta.";
})();
