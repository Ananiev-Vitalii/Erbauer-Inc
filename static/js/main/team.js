document.addEventListener('DOMContentLoaded', () => {
  const teamSection = document.querySelector('.team');
  if (!teamSection) return;

  const INITIAL_VISIBLE_COUNT = 4;
  const STEP_COUNT = 4;

  const cards = Array.from(teamSection.querySelectorAll('[data-team-card]'));
  const showMoreButton = teamSection.querySelector('[data-team-show-more]');
  const showLessButton = teamSection.querySelector('[data-team-show-less]');
  const actions = teamSection.querySelector('[data-team-actions]');

  const textItems = [
    teamSection.querySelector('.team__kicker'),
    teamSection.querySelector('.team__title'),
    teamSection.querySelector('.team__lead')
  ].filter(Boolean);

  let visibleCount = Math.min(INITIAL_VISIBLE_COUNT, cards.length);
  let hasAnimated = false;
  const timers = [];

  const addTimer = (fn, delay) => {
    const id = window.setTimeout(fn, delay);
    timers.push(id);
  };

  const clearAllTimers = () => {
    timers.forEach(window.clearTimeout);
    timers.length = 0;
  };

  const getVisibleCards = () => {
    return cards.filter((card) => !card.classList.contains('team__card--collapsed'));
  };

  const updateButtons = () => {
    if (showLessButton) {
      showLessButton.hidden = visibleCount <= INITIAL_VISIBLE_COUNT;
    }

    if (showMoreButton) {
      showMoreButton.hidden = visibleCount >= cards.length;
    }
  };

  const getPreviousVisibleCount = () => {
    if (visibleCount <= INITIAL_VISIBLE_COUNT) {
      return INITIAL_VISIBLE_COUNT;
    }

    const extraCount = visibleCount - INITIAL_VISIBLE_COUNT;
    const remainder = extraCount % STEP_COUNT;

    if (remainder > 0) {
      return visibleCount - remainder;
    }

    return Math.max(
      visibleCount - STEP_COUNT,
      INITIAL_VISIBLE_COUNT
    );
  };

  const preserveActionsPosition = (callback) => {
    if (!actions) {
      callback();
      return;
    }

    const topBefore = actions.getBoundingClientRect().top;

    callback();

    window.requestAnimationFrame(() => {
      const topAfter = actions.getBoundingClientRect().top;
      const offset = topAfter - topBefore;

      if (offset !== 0) {
        window.scrollBy(0, offset);
      }
    });
  };

  const revealNewCards = (previousVisibleCount, nextVisibleCount) => {
    const newCards = cards.slice(previousVisibleCount, nextVisibleCount);

    newCards.forEach((card, index) => {
      card.classList.remove('team__card--collapsed');

      if (!hasAnimated) return;

      card.classList.remove('is-visible');
      card.classList.remove('team__anim--settle');

      const baseDelay = index * 120;

      addTimer(() => {
        card.classList.add('team__anim--settle');
      }, baseDelay);

      addTimer(() => {
        card.classList.add('is-visible');
      }, baseDelay + 180);

      addTimer(() => {
        card.classList.remove('team__anim--settle');
      }, baseDelay + 420);
    });
  };

  const updateCards = (previousVisibleCount = visibleCount) => {
    cards.forEach((card, index) => {
      if (index < visibleCount) {
        card.classList.remove('team__card--collapsed');

        if (hasAnimated) {
          card.classList.add('is-visible');
        }
      } else {
        card.classList.add('team__card--collapsed');
        card.classList.remove('team__anim--settle');
      }
    });

    if (visibleCount > previousVisibleCount) {
      revealNewCards(previousVisibleCount, visibleCount);
    }

    updateButtons();
  };

  const showMore = () => {
    const previousVisibleCount = visibleCount;

    visibleCount = Math.min(
      visibleCount + STEP_COUNT,
      cards.length
    );

    updateCards(previousVisibleCount);
  };

  const showLess = () => {
    const previousVisibleCount = visibleCount;

    preserveActionsPosition(() => {
      visibleCount = getPreviousVisibleCount();
      updateCards(previousVisibleCount);
    });
  };

  const animateTextSequence = () => {
    const stepDelay = 260;

    textItems.forEach((item, index) => {
      addTimer(() => {
        item.classList.add('is-visible');
      }, index * stepDelay);
    });
  };

  const animateCardSequence = () => {
    const stepDelay = 190;
    const settleDelay = 430;
    const finalDelay = 620;

    getVisibleCards().forEach((card, index) => {
      const baseDelay = index * stepDelay;

      addTimer(() => {
        card.classList.add('team__anim--settle');
      }, baseDelay);

      addTimer(() => {
        card.classList.add('is-visible');
      }, baseDelay + settleDelay);

      addTimer(() => {
        card.classList.remove('team__anim--settle');
      }, baseDelay + finalDelay);
    });
  };

  if (showMoreButton) {
    showMoreButton.addEventListener('click', showMore);
  }

  if (showLessButton) {
    showLessButton.addEventListener('click', showLess);
  }

  updateCards();

  const observer = new IntersectionObserver(
    (entries, obs) => {
      const entry = entries[0];
      if (!entry.isIntersecting || hasAnimated) return;

      hasAnimated = true;

      animateTextSequence();
      animateCardSequence();

      obs.unobserve(teamSection);
    },
    {
      threshold: 0.05,
    }
  );

  observer.observe(teamSection);

  window.addEventListener(
    'beforeunload',
    () => {
      clearAllTimers();
      observer.disconnect();
    },
    { once: true }
  );
});