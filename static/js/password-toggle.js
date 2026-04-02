document.addEventListener('click', function (e) {
  const btn = e.target.closest('.password-toggle');
  if (!btn) return;

  const id = btn.getAttribute('data-target');
  const input = document.getElementById(id);
  if (!input) return;

  const icon = btn.querySelector('i');
  const isShown = input.type === 'text';
  input.type = isShown ? 'password' : 'text';

  if (icon) {
    icon.classList.toggle('fa-eye', isShown);
    icon.classList.toggle('fa-eye-slash', !isShown);
  }
  btn.setAttribute('aria-label', isShown ? 'Show password' : 'Hide password');
});
