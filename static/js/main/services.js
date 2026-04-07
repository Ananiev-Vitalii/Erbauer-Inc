document.addEventListener("DOMContentLoaded", () => {
  function initServicesSlider() {
    const dotsContainer = document.getElementById("servicesDots");
    const pages = document.querySelectorAll(".services__page");

    if (!dotsContainer || !pages.length) return;

    const dots = dotsContainer.querySelectorAll(".services__dot");
    if (!dots.length) return;

    function setActivePage(index) {
      pages.forEach((page, pageIndex) => {
        page.classList.toggle("is-active", pageIndex === index);
      });

      dots.forEach((dot, dotIndex) => {
        dot.classList.toggle("is-active", dotIndex === index);
      });
    }

    dotsContainer.addEventListener("click", (event) => {
      const button = event.target.closest(".services__dot");
      if (!button) return;

      const index = Number(button.dataset.index);
      if (Number.isNaN(index)) return;

      setActivePage(index);
    });

    const initialIndex = Array.from(dots).findIndex((dot) =>
      dot.classList.contains("is-active")
    );

    setActivePage(initialIndex >= 0 ? initialIndex : 0);
  }

  initServicesSlider();
});