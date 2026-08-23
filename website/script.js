document.querySelectorAll("[data-icon]").forEach((el) => {
  const name = el.getAttribute("data-icon");
  const size = Number(el.getAttribute("data-size") || 16);
  el.insertAdjacentHTML("afterbegin", window.Lucide.svg(name, size));
});
