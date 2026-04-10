document.addEventListener('DOMContentLoaded', () => {
  const teamSection = document.querySelector('.team');
  if (!teamSection) return;

  const textItems = [
    teamSection.querySelector('.team__kicker'),
    teamSection.querySelector('.team__title'),
    teamSection.querySelector('.team__lead')
  ].filter(Boolean);

  const cardItems = Array.from(teamSection.querySelectorAll('.team__card'));

  let hasAnimated = false;
  const timers = [];

  const addTimer = (fn, delay) => {
    const id = window.setTimeout(fn, delay);
    timers.push(id);
  };

  const clearAllTimers = () => {
    timers.forEach(window.clearTimeout);
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

    cardItems.forEach((card, index) => {
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
      threshold: 0.3,
      rootMargin: '0px 0px -10% 0px'
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