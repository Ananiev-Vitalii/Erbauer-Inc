# Алгоритми views додатка User

Маршрути з `user/urls.py` підключені під `/accounts/`. Інформаційні сторінки
використовують GET, форми — GET/POST. Помилки валідації та cooldown зазвичай
повертають HTML зі статусом 200. Очікувана відмова Redis зупиняє захищену операцію
з HTTP 503 через `RateLimitUnavailableMixin`. Для POST діє звичайний CSRF middleware.

## Реєстрація — UserRegistrationView

1. Авторизованого відвідувача перенаправити на головну. Для POST перевірити
   блокування `user_registration` за довіреним IP до форми та Turnstile.
2. Перевірити email, паролі й обов'язкову згоду. Форма знаходить активного
   Employee без User через DB `LOWER(email)` і відхиляє наявних користувачів.
3. Перевірити CAPTCHA. Невалідна форма та невдала CAPTCHA враховуються один раз
   за IP через `form_invalid()`; успішна реєстрація не додає спроби.
4. Підготувати незбережений User через Django creation form. Викликати
   `user.services.registration.register_employee_user()`.
5. Сервіс блокує Employee всередині `atomic()`, повторно перевіряє активність,
   email і прив'язку, потім зберігає неактивний/неверифікований User, зв'язок
   Employee та Profile. Зберігає регістр email Employee й копіює імена працівника.
   PostgreSQL email uniqueness остаточно захищає від конкурентного створення.
6. Очікувані конфлікти стають `RegistrationConflict`, потім помилкою bound-форми.
   Лише відомі User email constraints із SQLSTATE 23505 перетворюються після
   rollback; інші DB-помилки передаються далі.
7. Сервіс реєструє переданий callback через `on_commit()`. Callback view надсилає
   verification email і додає warning при відмові. Redirect на `user:confirm_user`;
   збережені записи не видаляються через помилку email.

Сервіс приймає ID Employee, підготовлений User і callback, а не request, form чи
messages. Зовнішня транзакція відкладає callback; rollback його скасовує.

## Вхід — LoginUser

1. До Turnstile перевірити `user_login` за `ip`, `email`, `captcha_ip`.
2. Перевірити CAPTCHA й повторно прочитати блокування через можливі конкурентні запити.
3. Невдала CAPTCHA додає лише одну спробу `captcha_ip`. Відповідь рендериться
   напряму без `form_invalid()`. Заблоковані/CAPTCHA-failure форми використовують
   `allow_authentication=False`: лінива валідація під час рендерингу не викликає authentication.
4. Після успішної CAPTCHA діє стандартна Django authentication. Невірні credentials
   додають `[ip, email]` один раз. При успіху скинути всі три поля limiter перед
   створенням сесії та стандартним безпечним redirect Django.

Password widgets не повертають введений пароль у HTML. Відмова reset повертає 503
до login. Registration і login навмисно не використовують mixin email-запитів.

## Повторний лист — ConfirmUser

1. Авторизованого відвідувача перенаправити на головну. `RateLimitedTurnstileMixin`
   перевіряє `ip`, `email`, `captcha_ip` у `user_resend_verification` до форми/Turnstile.
2. Перевірити форму, CAPTCHA та знову блокування. Невдала CAPTCHA додає тільки
   `captcha_ip`; успішна — одну бізнес-спробу `[ip, email]`. Запит, який досяг
   порога, до надсилання листа не переходить.
3. Знайти лише неактивного неверифікованого User через DB-lowered email. За
   дозволеного стану викликати email service; повернути однакову нейтральну форму
   успіху для відсутнього/недозволеного User та очікуваної відмови надсилання.

Гілка помилки mixin не додає спроб у `form_invalid()`. Читання блокування не
поновлює cooldown. Окремий CAPTCHA-лічильник не дозволяє витрачати квоту чужого
email неправильною CAPTCHA; користувачі зі спільною IP мають спільне IP-обмеження.
Чинні бізнес-обмеження email залишаються активними.

## Підтвердження — verify_user / InvalidVerify

GET verification залишено свідомо. Усередині `atomic()` декодувати UID і
заблокувати User до перевірки token. Лише `is_active=False, is_verified=False`
переходить до True/True та login. Другий конкурентний запит бачить оновлений стан
і не використовує початковий token повторно. Некоректний/прострочений/використаний
token дає redirect на `invalid_verify`; валідний token для недозволеного стану
не активує User і не виконує login, повертаючи на головну. `InvalidVerify` лише
рендерить сторінку відмови. Статус Employee не змінюється.

## Відновлення пароля — CustomPasswordResetView та стандартні views

Діє той самий алгоритм mixin, що й resend, але у `user_password_reset` із власними
порогами та лічильниками. Після захисних перевірок додати branding компанії та
делегувати token/email Django. `CustomPasswordResetForm.get_users()` вибирає
активних користувачів із usable password через DB-lowered email. Django сам
обробляє й логує помилки доставки; додаткової обгортки винятків немає.
Успішний запит дає redirect на `password-reset-done`. Підтвердження використовує
Django `PasswordResetConfirmView` і `CustomSetPasswordForm`; невалідне посилання
показує стандартний результат відмови, зміна пароля перенаправляє на
`password-reset-complete`. Done/complete views лише рендерять інформацію.

## Logout та email infrastructure

Logout використовує стандартний POST `LogoutView` із redirect на головну;
власний сервіс не потрібний. Anonymous-only обмеження діють на registration,
resend і запит reset; авторизованих користувачів login перенаправляє через Django LoginView.

Verification email використовує host/protocol request та чинний формат token.
`send_verification_email()` логує Anymail API/recipient і requests transport
failures, повертаючи False; programming/configuration errors не приховуються.
Branding береться з єдиного активного CompanyProfile або display name/адреси
`DEFAULT_FROM_EMAIL`. PostgreSQL дозволяє нуль або один активний профіль.
Email ERROR-логи спрямовані в stderr із безпечними місцями traceback і класом
винятку, без payload, chains та locals. Celery/retries не додаються.
Вимоги до IP та Redis описані в [спільному limiter deployment](../core/rate_limiting_deployment.md).
