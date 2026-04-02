document.addEventListener("DOMContentLoaded", function () {
    const input =
        document.getElementById("id_password1") ||
        document.getElementById("id_new_password1");

    const bar = document.getElementById("password-strength-bar");
    const wrapper = document.getElementById("password-strength-wrapper");

    if (!input || !bar || !wrapper) return;

    function resetStrength() {
        wrapper.classList.add("password-strength-hidden");
        bar.style.width = "0%";
        bar.className = "progress-bar";
    }

    function updateStrength(value) {
        let score = 0;

        if (value.length >= 8) score++;
        if (value.length >= 12) score++;
        if (/[A-Z]/.test(value)) score++;
        if (/[a-z]/.test(value)) score++;
        if (/[0-9]/.test(value)) score++;
        if (/[^A-Za-z0-9]/.test(value)) score++;

        bar.className = "progress-bar";

        if (value.length < 8) {
            bar.style.width = "33%";
            bar.classList.add("bg-danger");
        } else if (score < 4) {
            bar.style.width = "66%";
            bar.classList.add("bg-warning");
        } else {
            bar.style.width = "100%";
            bar.classList.add("bg-success");
        }
    }

    resetStrength();

    input.addEventListener("input", function () {
        const value = input.value;

        if (!value) {
            resetStrength();
            return;
        }

        wrapper.classList.remove("password-strength-hidden");
        updateStrength(value);
    });
});