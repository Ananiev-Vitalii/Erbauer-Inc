document.addEventListener("DOMContentLoaded", () => {
  const heroStatsSection = document.querySelector(".hero-stats");
  const heroStatValues = document.querySelectorAll(".hero-stat-value");

  function syncSiteHeaderHeight() {
    const siteHeader = document.getElementById("siteHeader");
    if (!siteHeader) return;

    const headerHeight = siteHeader.getBoundingClientRect().height;
    document.documentElement.style.setProperty(
      "--site-header-height",
      `${Math.round(headerHeight)}px`
    );
  }

  function syncHeroImageToTitle() {
    if (window.innerWidth <= 980) {
      const heroMedia = document.querySelector(".hero-media");
      const heroImageFrame = document.querySelector(".hero-media .image-frame");

      if (heroMedia) {
        heroMedia.style.removeProperty("--hero-media-offset");
      }

      if (heroImageFrame) {
        heroImageFrame.style.removeProperty("--hero-image-height");
      }

      return;
    }

    const heroCopy = document.querySelector(".hero-copy");
    const heroTitle = document.querySelector(".hero-copy h1");
    const heroMedia = document.querySelector(".hero-media");
    const heroImageFrame = document.querySelector(".hero-media .image-frame");

    if (!heroCopy || !heroTitle || !heroMedia || !heroImageFrame) return;

    const copyRect = heroCopy.getBoundingClientRect();
    const titleRect = heroTitle.getBoundingClientRect();

    const titleOffsetTop = titleRect.top - copyRect.top;
    const titleHeight = titleRect.height;

    heroMedia.style.setProperty(
      "--hero-media-offset",
      `${Math.max(titleOffsetTop, 0)}px`
    );

    heroImageFrame.style.setProperty(
      "--hero-image-height",
      `${Math.max(titleHeight, 220)}px`
    );
  }

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function formatCounterValue(value) {
    return Math.round(value).toString();
  }

  function animateCounter(element, options = {}) {
    const { duration = 1800, startDelay = 0 } = options;

    const rawText = element.textContent.trim();
    const hasPlus = rawText.includes("+");
    const target = parseInt(rawText.replace(/[^\d]/g, ""), 10);

    if (Number.isNaN(target)) return;
    if (element.dataset.counterAnimated === "true") return;

    element.dataset.counterAnimated = "true";

    const startAnimation = () => {
      element.textContent = hasPlus ? "0+" : "0";

      const startTime = performance.now();

      function updateCounter(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeOutCubic(progress);

        let currentValue;

        if (target <= 100) {
          currentValue = Math.round(target * eased);
        } else if (target <= 500) {
          currentValue = Math.round((target * eased) / 2) * 2;
        } else {
          currentValue = Math.round((target * eased) / 5) * 5;
        }

        currentValue = Math.min(currentValue, target);

        element.textContent = hasPlus
          ? `${formatCounterValue(currentValue)}+`
          : formatCounterValue(currentValue);

        if (progress < 1) {
          requestAnimationFrame(updateCounter);
        } else {
          element.textContent = hasPlus
            ? `${formatCounterValue(target)}+`
            : formatCounterValue(target);
        }
      }

      requestAnimationFrame(updateCounter);
    };

    if (startDelay > 0) {
      window.setTimeout(startAnimation, startDelay);
    } else {
      startAnimation();
    }
  }

  function initStatsRevealAndCounter() {
    if (!heroStatsSection || heroStatValues.length === 0) return;

    const statsObserver = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;

          heroStatsSection.classList.add("is-visible");

          heroStatValues.forEach((item, index) => {
            animateCounter(item, {
              duration: 1700 + index * 120,
              startDelay: index * 140,
            });
          });

          observer.unobserve(entry.target);
        });
      },
      {
        threshold: 0.85,
        rootMargin: "0px",
      }
    );

    statsObserver.observe(heroStatsSection);
  }

  function bindHeroImageEvents() {
    const heroImage = document.querySelector(".hero-media .image-frame img");
    if (!heroImage) return;

    if (heroImage.complete) {
      syncHeroImageToTitle();
    } else {
      heroImage.addEventListener("load", syncHeroImageToTitle);
    }
  }

  initStatsRevealAndCounter();

  syncSiteHeaderHeight();
  syncHeroImageToTitle();

  window.addEventListener("resize", () => {
    syncSiteHeaderHeight();
    syncHeroImageToTitle();
  });

  bindHeroImageEvents();

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => {
      syncSiteHeaderHeight();
      syncHeroImageToTitle();
    });
  }
});