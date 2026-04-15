document.addEventListener("DOMContentLoaded", () => {
  const siteHeader = document.getElementById("siteHeader");
  const menuToggle = document.getElementById("menuToggle");
  const mobileNav = document.getElementById("mobileNav");
  const navLinks = document.querySelectorAll(".main-nav a, .mobile-nav a");
  const sections = document.querySelectorAll("section[id]");

  function handleHeaderState() {
    if (!siteHeader) return;

    if (window.scrollY > 8) {
      siteHeader.classList.add("scrolled");
    } else {
      siteHeader.classList.remove("scrolled");
    }
  }

  function setActiveNavLink() {
    if (!sections.length || !navLinks.length) return;

    let currentId = "";

    sections.forEach((section) => {
      const sectionTop = section.offsetTop - 120;
      const sectionHeight = section.offsetHeight;

      if (
        window.scrollY >= sectionTop &&
        window.scrollY < sectionTop + sectionHeight
      ) {
        currentId = section.getAttribute("id");
      }
    });

    navLinks.forEach((link) => {
      const href = link.getAttribute("href");
      const targetId = href.split("#")[1];
      link.classList.toggle("is-active", targetId === currentId);
    });
  }

  function setupSmoothScroll() {
    document.querySelectorAll('a[href*="#"]').forEach((anchor) => {
      anchor.addEventListener("click", function (e) {
        const href = this.getAttribute("href");
        if (!href.includes("#")) return;

        const [path, id] = href.split("#");

        if (path && path !== window.location.pathname && path !== "") return;

        const target = document.getElementById(id);
        if (!target) return;

        e.preventDefault();

        const headerOffset = siteHeader ? siteHeader.offsetHeight : 80;
        const start = window.scrollY;
        const end =
          target.getBoundingClientRect().top +
          window.scrollY -
          headerOffset;

        const distance = end - start;
        const duration = 500;

        let startTime = null;

        function easeOutQuad(t) {
          return t * (2 - t);
        }

        function animateScroll(timestamp) {
          if (!startTime) startTime = timestamp;

          const elapsed = timestamp - startTime;
          const progress = Math.min(elapsed / duration, 1);
          const eased = easeOutQuad(progress);

          window.scrollTo(0, start + distance * eased);

          if (progress < 1) {
            requestAnimationFrame(animateScroll);
          }
        }

        requestAnimationFrame(animateScroll);
      });
    });
  }

  handleHeaderState();
  setActiveNavLink();
  setupSmoothScroll();

  window.addEventListener("scroll", () => {
    handleHeaderState();
    setActiveNavLink();
  });

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