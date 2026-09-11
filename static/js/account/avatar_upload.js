async function initAvatarUploader() {
  const avatarForm = document.querySelector("[data-avatar-form]");

  if (!avatarForm) {
    return;
  }

  const avatarImage = document.getElementById("profile-avatar-image");
  const avatarOpenButton = document.querySelector("[data-avatar-editor-open]");
  const avatarError = document.querySelector("[data-avatar-error]");
  const csrfInput = avatarForm.querySelector('input[name="csrfmiddlewaretoken"]');

  const uppyBundleUrl = avatarForm.dataset.uppyBundleUrl;
  const uploadErrorText = avatarForm.dataset.uploadErrorText || "Could not upload avatar.";
  const networkErrorText = avatarForm.dataset.networkErrorText || "Upload failed. Please try again.";
  const editorTitle = avatarForm.dataset.editorTitle || "Update profile photo";
  const openEditorText = avatarForm.dataset.openEditorText || "Choose photo";
  const uploadButtonText = avatarForm.dataset.uploadButtonText || "Save avatar";
  const dropHintText = avatarForm.dataset.dropHintText || "Drop your photo here or";
  const cancelText = avatarForm.dataset.cancelText || "Cancel";
  const saveText = avatarForm.dataset.saveText || "Save";
  const saveChangesText = avatarForm.dataset.saveChangesText || "Save changes";
  const cancelChangesText = avatarForm.dataset.cancelChangesText || cancelText;

  if (!uppyBundleUrl) {
    showAvatarError("Uppy bundle URL is missing.");
    return;
  }

  const { Uppy, Dashboard, ImageEditor } = await import(uppyBundleUrl);

  const uppy = new Uppy({
    autoProceed: false,
    restrictions: {
      maxNumberOfFiles: 1,
      maxFileSize: 5 * 1024 * 1024,
      allowedFileTypes: ["image/jpeg", "image/png", "image/webp"],
    },
  });

  uppy.use(Dashboard, {
    trigger: avatarOpenButton,
    closeModalOnClickOutside: true,
    closeAfterFinish: false,
    proudlyDisplayPoweredByUppy: false,
    showProgressDetails: true,
    note: "JPG, PNG, WEBP · max 5 MB",
    locale: {
      strings: {
        browseFiles: openEditorText,
        dropPasteFiles: `${dropHintText} %{browseFiles}`,
        uploadXFiles: uploadButtonText,
        uploadXNewFiles: uploadButtonText,
        xFilesSelected: {
          0: "%{smart_count} file selected",
          1: "%{smart_count} files selected",
        },
      },
    },
  });

  uppy.use(ImageEditor, {
    target: Dashboard,
    quality: 0.92,
    cropperOptions: {
      aspectRatio: 1,
      initialAspectRatio: 1,
      viewMode: 1,
      autoCropArea: 1,
      background: false,
      responsive: true,
      croppedCanvasOptions: {
        width: 512,
        height: 512,
        imageSmoothingEnabled: true,
        imageSmoothingQuality: "high",
      },
    },
    actions: {
      revert: true,
      rotate: true,
      granularRotate: false,
      flip: true,
      zoomIn: true,
      zoomOut: true,
      cropSquare: true,
      cropWidescreen: false,
      cropWidescreenVertical: false,
    },
    locale: {
      strings: {
        cancel: cancelText,
        save: saveText,
        revert: "Reset",
        rotate: "Rotate",
        zoomIn: "Zoom in",
        zoomOut: "Zoom out",
        flipHorizontal: "Flip horizontal",
        aspectRatioSquare: "Avatar square",
      },
    },
  });

  uppy.on("dashboard:modal-open", () => {
    hideAvatarError();
    scheduleUppyTextUpdates();
  });

  uppy.on("file-added", (file) => {
    hideAvatarError();

    const isImage = file.type && file.type.startsWith("image/");

    if (!isImage) {
      uppy.removeFile(file.id);
      showAvatarError(uploadErrorText);
      return;
    }

    uppy.getFiles().forEach((existingFile) => {
      if (existingFile.id !== file.id) {
        uppy.removeFile(existingFile.id);
      }
    });

    scheduleUppyTextUpdates();
  });

  uppy.on("file-editor:start", () => {
    scheduleUppyTextUpdates();
  });

  uppy.on("file-editor:complete", () => {
    scheduleUppyTextUpdates();
  });

  uppy.on("upload", async () => {
    hideAvatarError();

    const file = uppy.getFiles()[0];

    if (!file) {
      showAvatarError(uploadErrorText);
      return;
    }

    try {
      uppy.setFileState(file.id, {
        progress: {
          uploadStarted: Date.now(),
          uploadComplete: false,
          percentage: 25,
          bytesUploaded: 0,
          bytesTotal: file.size || 0,
        },
      });

      const formData = new FormData();
      formData.append("avatar", file.data, file.name || "avatar.webp");

      if (csrfInput) {
        formData.append("csrfmiddlewaretoken", csrfInput.value);
      }

      const response = await fetch(avatarForm.action, {
        method: avatarForm.method || "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      const data = await response.json();

      if (!response.ok || !data.success || !data.avatar_url) {
        showAvatarError(uploadErrorText);

        uppy.setFileState(file.id, {
          progress: {
            uploadStarted: null,
            uploadComplete: false,
            percentage: 0,
            bytesUploaded: 0,
            bytesTotal: file.size || 0,
          },
        });

        return;
      }

      uppy.setFileState(file.id, {
        progress: {
          uploadStarted: Date.now(),
          uploadComplete: true,
          percentage: 100,
          bytesUploaded: file.size || 0,
          bytesTotal: file.size || 0,
        },
      });

      if (avatarImage) {
        avatarImage.src = `${data.avatar_url}?v=${Date.now()}`;
      }

      hideAvatarError();
      uppy.cancelAll();

      const dashboard = uppy.getPlugin("Dashboard");

      if (dashboard) {
        dashboard.closeModal();
      }
    } catch (error) {
      console.error("Avatar upload failed:", error);

      showAvatarError(networkErrorText);

      uppy.setFileState(file.id, {
        progress: {
          uploadStarted: null,
          uploadComplete: false,
          percentage: 0,
          bytesUploaded: 0,
          bytesTotal: file.size || 0,
        },
      });
    }
  });

  uppy.on("restriction-failed", (file, error) => {
    showAvatarError(error?.message || uploadErrorText);
  });

  function scheduleUppyTextUpdates() {
    updateUppyText();

    [50, 150, 300, 600, 1000].forEach((delay) => {
      setTimeout(updateUppyText, delay);
    });
  }

  function updateUppyText() {
    const dashboardTitle = document.querySelector(".uppy-DashboardContent-title");

    if (dashboardTitle && !dashboardTitle.querySelector(".uppy-DashboardContent-titleFile")) {
      dashboardTitle.textContent = editorTitle;
    }

    document.querySelectorAll(".uppy-DashboardContent-back").forEach((button) => {
      if (button.textContent !== cancelText) {
        button.textContent = cancelText;
      }
    });

    document.querySelectorAll(".uppy-DashboardContent-save").forEach((button) => {
      if (button.textContent !== saveText) {
        button.textContent = saveText;
      }
    });

    document
      .querySelectorAll(
        ".uppy-Dashboard-FileCard-actions .uppy-c-btn-primary.uppy-Dashboard-FileCard-actionsBtn"
      )
      .forEach((button) => {
        if (button.textContent !== saveChangesText) {
          button.textContent = saveChangesText;
        }
      });

    document
      .querySelectorAll(
        ".uppy-Dashboard-FileCard-actions .uppy-c-btn-link.uppy-Dashboard-FileCard-actionsBtn"
      )
      .forEach((button) => {
        if (button.textContent !== cancelChangesText) {
          button.textContent = cancelChangesText;
        }
      });
  }

  function showAvatarError(message) {
    if (!avatarError) {
      return;
    }

    avatarError.textContent = message;
    avatarError.hidden = false;
  }

  function hideAvatarError() {
    if (!avatarError) {
      return;
    }

    avatarError.textContent = "";
    avatarError.hidden = true;
  }
}

initAvatarUploader();