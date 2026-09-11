document.addEventListener("click", function (e) {
  const btn = e.target.closest(".password-toggle");
  if (!btn) return;

  const inputId = btn.getAttribute("data-target");
  const input = document.getElementById(inputId);
  if (!input) return;

  const isVisible = input.type === "text";
  input.type = isVisible ? "password" : "text";

  btn.classList.toggle("is-active", !isVisible);
  btn.setAttribute("aria-pressed", String(!isVisible));
  btn.setAttribute("aria-label", isVisible ? "Show password" : "Hide password");
});