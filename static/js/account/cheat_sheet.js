document.addEventListener("DOMContentLoaded", () => {
  const dropdown = document.querySelector("[data-cheat-sheet-dropdown]");
  const target = document.querySelector("[data-cheat-sheet-detail-container]");
  const lightbox = document.querySelector("[data-lightbox]");
  const lightboxImage = document.querySelector("[data-lightbox-img]");
  const lightboxClose = document.querySelector("[data-lightbox-close]");

  if (!dropdown || !target) {
    return;
  }

  const toggle = dropdown.querySelector("[data-cheat-sheet-dropdown-toggle]");
  const label = dropdown.querySelector("[data-cheat-sheet-dropdown-label]");
  const options = dropdown.querySelectorAll("[data-cheat-sheet-option]");
  const url = dropdown.dataset.url;

  if (!toggle || !label || !url) {
    return;
  }

  let selectedCheatSheetId = null;
  let isLoading = false;

  let lightboxScale = 1;
  let lightboxTranslateX = 0;
  let lightboxTranslateY = 0;
  let isDraggingImage = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragStartTranslateX = 0;
  let dragStartTranslateY = 0;

  const minScale = 1;
  const maxScale = 4;
  const zoomStep = 0.18;

  const closeDropdown = () => {
    dropdown.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
  };

  const toggleDropdown = () => {
    const isOpen = dropdown.classList.contains("is-open");

    if (isOpen) {
      closeDropdown();
      return;
    }

    dropdown.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
  };

  const setSelectedOption = (selectedOption) => {
    options.forEach((option) => {
      option.classList.remove("is-selected");
    });

    selectedOption.classList.add("is-selected");
    label.textContent = selectedOption.textContent.trim();
  };

  const renderError = () => {
    target.innerHTML = `
      <div class="cheat-sheet-empty">
        <h3>Could not load cheat sheet</h3>
        <p>Please try again.</p>
      </div>
    `;
  };

  const loadCheatSheet = async (cheatSheetId) => {
    if (!cheatSheetId || isLoading || cheatSheetId === selectedCheatSheetId) {
      return;
    }

    isLoading = true;
    selectedCheatSheetId = cheatSheetId;

    target.classList.add("is-loading");
    toggle.disabled = true;

    try {
      const requestUrl = new URL(url, window.location.origin);

      requestUrl.searchParams.set("cheat_sheet_id", cheatSheetId);
      requestUrl.searchParams.set("partial", "1");

      const response = await fetch(requestUrl, {
        method: "GET",
      });

      if (!response.ok) {
        throw new Error("Failed to load cheat sheet.");
      }

      target.innerHTML = await response.text();
    } catch (error) {
      selectedCheatSheetId = null;
      renderError();
    } finally {
      isLoading = false;
      target.classList.remove("is-loading");
      toggle.disabled = false;
    }
  };

  const applyLightboxTransform = () => {
    if (!lightboxImage) {
      return;
    }

    lightboxImage.style.transform = `translate3d(${lightboxTranslateX}px, ${lightboxTranslateY}px, 0) scale(${lightboxScale})`;

    if (lightboxScale > 1) {
      lightbox.classList.add("is-zoomed");
    } else {
      lightbox.classList.remove("is-zoomed");
    }
  };

  const resetLightboxZoom = () => {
    lightboxScale = 1;
    lightboxTranslateX = 0;
    lightboxTranslateY = 0;
    isDraggingImage = false;
    applyLightboxTransform();
  };

  const openLightbox = (imageUrl, imageAlt) => {
    if (!lightbox || !lightboxImage || !imageUrl) {
      return;
    }

    resetLightboxZoom();

    lightboxImage.src = imageUrl;
    lightboxImage.alt = imageAlt || "";

    lightbox.classList.add("is-open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("cheat-sheet-lightbox-open");
  };

  const closeLightbox = () => {
    if (!lightbox || !lightboxImage) {
      return;
    }

    lightbox.classList.remove("is-open", "is-zoomed", "is-dragging");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("cheat-sheet-lightbox-open");

    lightboxImage.src = "";
    lightboxImage.alt = "";

    resetLightboxZoom();
  };

  const handleLightboxWheel = (event) => {
    if (!lightbox || !lightbox.classList.contains("is-open")) {
      return;
    }

    event.preventDefault();

    const zoomDirection = event.deltaY < 0 ? 1 : -1;
    const nextScale = Math.min(
      maxScale,
      Math.max(minScale, lightboxScale + zoomDirection * zoomStep)
    );

    if (nextScale === lightboxScale) {
      return;
    }

    lightboxScale = nextScale;

    if (lightboxScale === 1) {
      lightboxTranslateX = 0;
      lightboxTranslateY = 0;
    }

    applyLightboxTransform();
  };

  const handleLightboxPointerDown = (event) => {
    if (
      !lightbox ||
      !lightboxImage ||
      !lightbox.classList.contains("is-open") ||
      lightboxScale <= 1 ||
      event.pointerType !== "mouse"
    ) {
      return;
    }

    isDraggingImage = true;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    dragStartTranslateX = lightboxTranslateX;
    dragStartTranslateY = lightboxTranslateY;

    lightbox.classList.add("is-dragging");
    lightboxImage.setPointerCapture(event.pointerId);
  };

  const handleLightboxPointerMove = (event) => {
    if (!isDraggingImage) {
      return;
    }

    const deltaX = event.clientX - dragStartX;
    const deltaY = event.clientY - dragStartY;

    lightboxTranslateX = dragStartTranslateX + deltaX;
    lightboxTranslateY = dragStartTranslateY + deltaY;

    applyLightboxTransform();
  };

  const handleLightboxPointerUp = (event) => {
    if (!isDraggingImage || !lightboxImage) {
      return;
    }

    isDraggingImage = false;

    lightbox.classList.remove("is-dragging");

    if (lightboxImage.hasPointerCapture(event.pointerId)) {
      lightboxImage.releasePointerCapture(event.pointerId);
    }
  };

  toggle.addEventListener("click", toggleDropdown);

  options.forEach((option) => {
    option.addEventListener("click", () => {
      const cheatSheetId = option.dataset.cheatSheetId;

      setSelectedOption(option);
      closeDropdown();
      loadCheatSheet(cheatSheetId);
    });
  });

  target.addEventListener("click", (event) => {
    const imageButton = event.target.closest("[data-lightbox-image]");

    if (!imageButton) {
      return;
    }

    openLightbox(imageButton.dataset.imageUrl, imageButton.dataset.imageAlt);
  });

  document.addEventListener("click", (event) => {
    if (!dropdown.contains(event.target)) {
      closeDropdown();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDropdown();
      closeLightbox();
    }
  });

  if (lightbox) {
    lightbox.addEventListener("click", (event) => {
      if (event.target === lightbox) {
        closeLightbox();
      }
    });

    lightbox.addEventListener("wheel", handleLightboxWheel, {
      passive: false,
    });
  }

  if (lightboxImage) {
    lightboxImage.addEventListener("pointerdown", handleLightboxPointerDown);
    lightboxImage.addEventListener("pointermove", handleLightboxPointerMove);
    lightboxImage.addEventListener("pointerup", handleLightboxPointerUp);
    lightboxImage.addEventListener("pointercancel", handleLightboxPointerUp);
  }

  if (lightboxClose) {
    lightboxClose.addEventListener("click", closeLightbox);
  }
});