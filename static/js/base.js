document.addEventListener("DOMContentLoaded", () => {
  const siteHeader = document.getElementById("siteHeader");
  const menuToggle = document.getElementById("menuToggle");
  const mobileNav = document.getElementById("mobileNav");
  const profileToggle = document.getElementById("profileToggle");
  const profileDropdown = document.getElementById("profileDropdown");
  const navLinks = document.querySelectorAll(".main-nav a, .mobile-nav a");
  const sections = document.querySelectorAll("section[id]");

  const currentPath = normalizePath(window.location.pathname);
  const homePath = normalizePath("/");

  function normalizePath(path) {
    return (path || "").replace(/\/+$/, "") || "/";
  }

  function closeMobileNav() {
    if (!mobileNav) return;

    mobileNav.classList.remove("is-open");

    if (menuToggle) {
      menuToggle.setAttribute("aria-expanded", "false");
    }
  }

  function closeProfileDropdown() {
    if (!profileDropdown) return;

    profileDropdown.classList.remove("is-open");

    if (profileToggle) {
      profileToggle.setAttribute("aria-expanded", "false");
    }
  }

  function closeAllDropdowns() {
    closeMobileNav();
    closeProfileDropdown();
  }

  function handleHeaderState() {
    if (!siteHeader) return;

    if (window.scrollY > 8) {
      siteHeader.classList.add("scrolled");
    } else {
      siteHeader.classList.remove("scrolled");
    }
  }

  function clearActiveNavLinks() {
    navLinks.forEach((link) => link.classList.remove("is-active"));
  }

  function setActiveNavLink() {
    if (!navLinks.length) return;

    const isHomePage = currentPath === homePath;

    clearActiveNavLinks();

    if (isHomePage && sections.length) {
      let currentId = "";

      sections.forEach((section) => {
        const sectionTop = section.offsetTop - 120;
        const sectionHeight = section.offsetHeight;

        if (
          window.scrollY >= sectionTop &&
          window.scrollY < sectionTop + sectionHeight
        ) {
          currentId = section.getAttribute("id") || "";
        }
      });

      if (currentId) {
        navLinks.forEach((link) => {
          const href = link.getAttribute("href") || "";
          const hashIndex = href.indexOf("#");
          const targetId = hashIndex >= 0 ? href.slice(hashIndex + 1) : "";

          if (targetId === currentId) {
            link.classList.add("is-active");
          }
        });
      }

      return;
    }

    navLinks.forEach((link) => {
      const href = link.getAttribute("href") || "";

      if (href.includes("#")) return;

      const linkPath = normalizePath(href);

      if (linkPath === currentPath) {
        link.classList.add("is-active");
      }
    });
  }

  function setupSmoothScroll() {
    document.querySelectorAll('a[href*="#"]').forEach((anchor) => {
      anchor.addEventListener("click", function (e) {
        const href = this.getAttribute("href") || "";
        const hashIndex = href.indexOf("#");

        if (hashIndex === -1) return;

        const rawPath = href.slice(0, hashIndex);
        const path = normalizePath(rawPath);
        const id = href.slice(hashIndex + 1);

        if (!id) return;

        const isSamePage = rawPath === "" || path === currentPath;

        if (!isSamePage) return;

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
        closeAllDropdowns();
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
    menuToggle.addEventListener("click", (e) => {
      e.stopPropagation();

      closeProfileDropdown();

      const isOpen = mobileNav.classList.toggle("is-open");
      menuToggle.setAttribute("aria-expanded", String(isOpen));
    });

    mobileNav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", closeMobileNav);
    });

    mobileNav.addEventListener("click", (e) => {
      e.stopPropagation();
    });
  }

  if (profileToggle && profileDropdown) {
    profileToggle.addEventListener("click", (e) => {
      e.stopPropagation();

      closeMobileNav();

      const isOpen = profileDropdown.classList.toggle("is-open");
      profileToggle.setAttribute("aria-expanded", String(isOpen));
    });

    profileDropdown.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", closeProfileDropdown);
    });

    profileDropdown.addEventListener("click", (e) => {
      e.stopPropagation();
    });
  }

  document.addEventListener("click", closeAllDropdowns);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllDropdowns();
    }
  });
});