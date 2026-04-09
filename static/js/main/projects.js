document.addEventListener("DOMContentLoaded", () => {
  const filtersWrap = document.getElementById("projectFilters");
  const projectCards = Array.from(document.querySelectorAll(".projects__card"));

  if (filtersWrap) {
    const filterButtons = Array.from(
      filtersWrap.querySelectorAll(".projects__filter")
    );

    filtersWrap.addEventListener("click", (event) => {
      const button = event.target.closest(".projects__filter");
      if (!button) return;

      const selectedFilter = button.dataset.filter;

      filterButtons.forEach((btn) => {
        btn.classList.toggle("is-active", btn === button);
      });

      projectCards.forEach((card) => {
        const cardCategory = card.dataset.category;
        const shouldShow =
          selectedFilter === "all" || cardCategory === selectedFilter;

        card.classList.toggle("hide-project", !shouldShow);
      });
    });
  }

  const lightbox = document.getElementById("projectsLightbox");
  const lightboxImage = document.getElementById("projectsLightboxImage");
  const lightboxClose = document.getElementById("projectsLightboxClose");
  const imageButtons = Array.from(
    document.querySelectorAll(".projects__image-icon")
  );

  const openLightbox = (imageSrc, imageAlt = "") => {
    if (!lightbox || !lightboxImage || !imageSrc) return;

    lightboxImage.src = imageSrc;
    lightboxImage.alt = imageAlt;
    lightbox.classList.add("is-open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("lightbox-open");
  };

  const closeLightbox = () => {
    if (!lightbox || !lightboxImage) return;

    lightbox.classList.remove("is-open");
    lightbox.setAttribute("aria-hidden", "true");
    lightboxImage.src = "";
    lightboxImage.alt = "";
    document.body.classList.remove("lightbox-open");
  };

  imageButtons.forEach((button) => {
    button.addEventListener("click", () => {
      openLightbox(button.dataset.image, button.dataset.alt || "");
    });
  });

  if (lightbox) {
    lightbox.addEventListener("click", (event) => {
      if (event.target.hasAttribute("data-lightbox-close")) {
        closeLightbox();
      }
    });
  }

  if (lightboxClose) {
    lightboxClose.addEventListener("click", closeLightbox);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && lightbox?.classList.contains("is-open")) {
      closeLightbox();
    }
  });
});