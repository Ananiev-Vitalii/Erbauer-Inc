document.addEventListener("DOMContentLoaded", () => {
  const siteHeader = document.getElementById("siteHeader");
  const menuToggle = document.getElementById("menuToggle");
  const mobileNav = document.getElementById("mobileNav");

  function handleHeaderState() {
    if (!siteHeader) return;

    if (window.scrollY > 8) {
      siteHeader.classList.add("scrolled");
    } else {
      siteHeader.classList.remove("scrolled");
    }
  }

  handleHeaderState();
  window.addEventListener("scroll", handleHeaderState);

  if (menuToggle && mobileNav) {
    menuToggle.addEventListener("click", () => {
      const isOpen = mobileNav.classList.toggle("is-open");
      menuToggle.setAttribute("aria-expanded", String(isOpen));
    });

    mobileNav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        mobileNav.classList.remove("is-open");
        menuToggle.setAttribute("aria-expanded", "false");
      });
    });
  }
});