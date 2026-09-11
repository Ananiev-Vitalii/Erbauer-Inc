document.addEventListener("DOMContentLoaded", () => {
  const backToTop = document.getElementById("backToTop");
  const footer = document.querySelector("footer");

  if (!backToTop || !footer) return;

  function handleBackToTopVisibility() {
    const footerRect = footer.getBoundingClientRect();
    const footerVisible = footerRect.top <= window.innerHeight;

    if (footerVisible) {
      backToTop.classList.add("is-visible");
    } else {
      backToTop.classList.remove("is-visible");
    }
  }

  handleBackToTopVisibility();
  window.addEventListener("scroll", handleBackToTopVisibility);
  window.addEventListener("resize", handleBackToTopVisibility);

  backToTop.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
});