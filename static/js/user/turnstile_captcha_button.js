function setFormSubmitButtonState(disabled) {
    const submitBtn = document.getElementById("form-submit-btn");
    if (submitBtn) {
        submitBtn.disabled = disabled;
    }
}

function turnstileSuccess(token) {
    setFormSubmitButtonState(false);
}

function turnstileExpired() {
    setFormSubmitButtonState(true);
}

function turnstileError() {
    setFormSubmitButtonState(true);
}

document.addEventListener("DOMContentLoaded", function () {
    setFormSubmitButtonState(true);
});