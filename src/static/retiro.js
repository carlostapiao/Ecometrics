(() => {
 const boton = document.getElementById("agregar-origen");
 const total = document.getElementById("id_origenes-TOTAL_FORMS");
 if (!boton || !total) return;
 boton.addEventListener("click", () => {
   const indice = Number(total.value);
   if (indice >= 20) return;
   const plantilla = document.getElementById("origen-vacio").innerHTML.replaceAll("__prefix__", String(indice));
   document.getElementById("origenes").insertAdjacentHTML("beforeend", plantilla);
   total.value = String(indice + 1);
   boton.disabled = indice + 1 >= 20;
 });
})();
