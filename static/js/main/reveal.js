document.addEventListener("DOMContentLoaded", () => {
  const revealItems = document.querySelectorAll(".reveal:not(.hero-stats)");
  if (!revealItems.length) return;

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
    { threshold: 0.05 }
  );

  revealItems.forEach((item) => observer.observe(item));
});