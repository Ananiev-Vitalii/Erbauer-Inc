document.addEventListener("DOMContentLoaded", () => {
  const heroStatsSection = document.querySelector(".hero-stats");
  const heroStatValues = document.querySelectorAll(".hero-stat-value");

  const heroTextPanel = document.querySelector("[data-hero-text-panel]");
  const heroTitle = document.querySelector("[data-hero-title]");

  let heroFitFrame = null;

  function syncSiteHeaderHeight() {
    const siteHeader = document.getElementById("siteHeader");
    if (!siteHeader) return;

    const headerHeight = siteHeader.getBoundingClientRect().height;

    document.documentElement.style.setProperty(
      "--site-header-height",
      `${Math.round(headerHeight)}px`
    );
  }

  function getCssNumberVariable(element, variableName, fallback) {
    const value = window
      .getComputedStyle(element)
      .getPropertyValue(variableName)
      .trim();

    const parsed = parseFloat(value);

    return Number.isNaN(parsed) ? fallback : parsed;
  }

  function getHeroTitleMaxSize() {
    if (!heroTitle) return 84;

    const hero = document.querySelector(".hero");
    if (!hero) return 84;

    return getCssNumberVariable(hero, "--hero-title-max", 84);
  }

  function getHeroTitleMinSize() {
    if (!heroTitle) return 24;

    const hero = document.querySelector(".hero");
    if (!hero) return 24;

    return getCssNumberVariable(hero, "--hero-title-min", 24);
  }

  function fitHeroTitleNow() {
    if (!heroTextPanel || !heroTitle) return;

    const maxSize = getHeroTitleMaxSize();
    const minSize = getHeroTitleMinSize();

    heroTitle.style.fontSize = `${maxSize}px`;

    let low = minSize;
    let high = maxSize;
    let best = minSize;

    while (low <= high) {
      const middle = Math.floor((low + high) / 2);

      heroTitle.style.fontSize = `${middle}px`;

      const isFitting =
        heroTextPanel.scrollHeight <= heroTextPanel.clientHeight;

      if (isFitting) {
        best = middle;
        low = middle + 1;
      } else {
        high = middle - 1;
      }
    }

    heroTitle.style.fontSize = `${best}px`;

    /*
      Финальная страховочная проверка.
      Иногда браузер после изменения размера шрифта пересчитывает переносы не мгновенно.
    */
    let safetySize = best;

    while (
      heroTextPanel.scrollHeight > heroTextPanel.clientHeight &&
      safetySize > minSize
    ) {
      safetySize -= 1;
      heroTitle.style.fontSize = `${safetySize}px`;
    }
  }

  function fitHeroTitle() {
    if (heroFitFrame) {
      cancelAnimationFrame(heroFitFrame);
    }

    heroFitFrame = requestAnimationFrame(() => {
      fitHeroTitleNow();

      requestAnimationFrame(() => {
        fitHeroTitleNow();
      });
    });
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

  initStatsRevealAndCounter();

  syncSiteHeaderHeight();
  fitHeroTitle();

  window.addEventListener("resize", () => {
    syncSiteHeaderHeight();
    fitHeroTitle();
  });

  window.addEventListener("load", () => {
    syncSiteHeaderHeight();
    fitHeroTitle();
  });

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => {
      syncSiteHeaderHeight();
      fitHeroTitle();
    });
  }
});