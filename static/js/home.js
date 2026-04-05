document.addEventListener("DOMContentLoaded", () => {
  const backToTop = document.getElementById("backToTop");
  const projectFilters = document.getElementById("projectFilters");
  const projectCards = document.querySelectorAll(".project-card");
  const revealItems = document.querySelectorAll(".reveal");

  if (backToTop) {
    function handleBackToTopVisibility() {
      if (window.scrollY > 280) {
        backToTop.classList.add("is-visible");
      } else {
        backToTop.classList.remove("is-visible");
      }
    }

    handleBackToTopVisibility();
    window.addEventListener("scroll", handleBackToTopVisibility);

    backToTop.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  if (projectFilters) {
    projectFilters.addEventListener("click", (event) => {
      const button = event.target.closest(".filter-btn");
      if (!button) return;

      const filter = button.dataset.filter;

      projectFilters.querySelectorAll(".filter-btn").forEach((btn) => {
        btn.classList.remove("is-active");
      });
      button.classList.add("is-active");

      projectCards.forEach((card) => {
        const category = card.dataset.category;
        const shouldShow = filter === "all" || category === filter;
        card.classList.toggle("hide-project", !shouldShow);
      });
    });
  }

  if (revealItems.length > 0) {
    const observer = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;

          const delay = entry.target.dataset.delay || 0;
          entry.target.style.transitionDelay = `${delay}ms`;
          entry.target.classList.add("is-visible");
          obs.unobserve(entry.target);
        });
      },
      { threshold: 0.16 }
    );

    revealItems.forEach((item) => observer.observe(item));
  }
});