const avatarForm = document.querySelector("[data-avatar-form]");
const avatarInput = document.querySelector("[data-avatar-input]");
const avatarImage = document.getElementById("profile-avatar-image");
const avatarActions = document.querySelector("[data-avatar-actions]");
const avatarFileName = document.querySelector("[data-avatar-file-name]");
const avatarError = document.querySelector("[data-avatar-error]");

avatarInput?.addEventListener("change", () => {
  const file = avatarInput.files?.[0];

  if (!file) {
    return;
  }

  if (avatarFileName) {
    avatarFileName.textContent = file.name;
  }

  if (avatarActions) {
    avatarActions.hidden = false;
  }

  if (avatarError) {
    avatarError.hidden = true;
    avatarError.textContent = "";
  }
});

avatarForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = avatarInput?.files?.[0];

  if (!file) {
    return;
  }

  const submitButton = avatarForm.querySelector('button[type="submit"]');
  const originalButtonText = submitButton ? submitButton.textContent : null;
  const loadingButtonText = submitButton?.dataset.loadingText || "Uploading...";

  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = loadingButtonText;
  }

  if (avatarError) {
    avatarError.hidden = true;
    avatarError.textContent = "";
  }

  try {
    const response = await fetch(avatarForm.action, {
      method: avatarForm.method,
      body: new FormData(avatarForm),
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      const errors = data.errors?.avatar;

      if (avatarError) {
        avatarError.textContent = errors ? errors.join(" ") : "Could not upload avatar.";
        avatarError.hidden = false;
      }

      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
      }

      return;
    }

    if (avatarImage) {
      avatarImage.src = `${data.avatar_url}?v=${Date.now()}`;
    }

    avatarInput.value = "";

    if (avatarActions) {
      avatarActions.hidden = true;
    }

    if (avatarFileName) {
      avatarFileName.textContent = "";
    }

    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
    }
  } catch (error) {
    console.error("Avatar upload failed:", error);

    if (avatarError) {
      avatarError.textContent = "Upload failed. Please try again.";
      avatarError.hidden = false;
    }

    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = originalButtonText;
    }
  }
});