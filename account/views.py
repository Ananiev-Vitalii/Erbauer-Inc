import calendar
from datetime import date

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, Subquery
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import generic
from django.views.decorators.cache import never_cache

from account.forms import (
    EmployeeContactForm,
    EmployeeInvoiceForm,
    EmployeePositionForm,
    ProfileAvatarForm,
    SimpleInvoiceForm,
)
from account.models import (
    Employee,
    EmployeeSimpleInvoice,
    Position,
    Profile,
)
from account.services.cache import (
    get_cheat_sheet_steps_cached,
    get_cheat_sheets_cached,
)
from account.services.simple_invoice_period import (
    build_invoice_period,
    get_available_invoice_months,
    get_available_invoice_years,
    get_initial_invoice_period,
    get_invoice_period_hours_total,
    validate_invoice_period_available,
)
from account.services.simple_invoice_processing import (
    expire_stale_simple_invoices_for_employee,
    get_simple_invoice_after_expiration_check,
    is_simple_invoice_processing_expired,
)
from account.services.simple_invoice_submission import (
    submit_simple_invoice,
)
from account.services.work_hours import (
    build_work_hours_calendars,
    get_available_work_months,
    get_employee_month_total,
    parse_work_month,
    save_employee_work_hours,
)
from account.simple_invoice_time import (
    SIMPLE_INVOICE_RETENTION_MONTHS,
    get_simple_invoice_cutoff,
)


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class SimpleInvoiceHistoryView(
    LoginRequiredMixin,
    generic.ListView,
):
    model = EmployeeSimpleInvoice
    template_name = "account/invoice_history.html"
    context_object_name = "invoices"

    PERIOD_MONTHS = {
        "3": 3,
        "6": 6,
        "12": 12,
        "24": 24,
        "36": 36,
    }

    RETENTION_MONTHS = SIMPLE_INVOICE_RETENTION_MONTHS

    def get_retained_invoices(self):
        if hasattr(self, "_retained_invoices"):
            return self._retained_invoices

        retention_start = get_simple_invoice_cutoff(
            months=self.RETENTION_MONTHS,
        )

        invoices = list(
            EmployeeSimpleInvoice.objects.filter(
                employee__user_id=self.request.user.pk,
                created_at__gte=retention_start,
            ).order_by(
                "-created_at",
                "-pk",
            )
        )

        stale_invoice_ids = [
            invoice.pk
            for invoice in invoices
            if is_simple_invoice_processing_expired(invoice)
        ]

        if stale_invoice_ids:
            stale_invoice_ids_set = set(stale_invoice_ids)

            employee_id = next(
                (
                    invoice.employee_id
                    for invoice in invoices
                    if invoice.pk in stale_invoice_ids_set
                ),
                None,
            )

            if employee_id is not None:
                expire_stale_simple_invoices_for_employee(
                    employee=employee_id,
                )

                refreshed_stale_invoices = {
                    row["pk"]: row
                    for row in (
                        EmployeeSimpleInvoice.objects.filter(
                            pk__in=stale_invoice_ids,
                        ).values(
                            "pk",
                            "status",
                            "pdf_file",
                        )
                    )
                }

                for invoice in invoices:
                    refreshed_invoice = refreshed_stale_invoices.get(invoice.pk)

                    if refreshed_invoice is None:
                        continue

                    invoice.status = refreshed_invoice["status"]

                    invoice.pdf_file = refreshed_invoice["pdf_file"] or ""

        self._retained_invoices = invoices

        return self._retained_invoices

    def get_queryset(self):
        invoices = self.get_retained_invoices()

        self.selected_period = "all"
        self.selected_year = None

        year_param = self.request.GET.get("year")
        period_param = self.request.GET.get("period")

        if year_param:
            selected_year = _parse_int(year_param)

            if selected_year is not None:
                self.selected_year = selected_year

                return [
                    invoice
                    for invoice in invoices
                    if (invoice.invoice_year == selected_year)
                ]

        elif period_param in self.PERIOD_MONTHS:
            self.selected_period = period_param

            period_start = get_simple_invoice_cutoff(
                months=self.PERIOD_MONTHS[period_param],
            )

            return [
                invoice for invoice in invoices if (invoice.created_at >= period_start)
            ]

        return invoices

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(**kwargs)

        retained_invoices = self.get_retained_invoices()

        invoice_years = sorted(
            {invoice.invoice_year for invoice in retained_invoices},
            reverse=True,
        )

        available_years = [
            date(
                year,
                1,
                1,
            )
            for year in invoice_years
        ]

        context.update(
            {
                "available_years": available_years,
                "selected_period": self.selected_period,
                "selected_year": self.selected_year,
            }
        )

        return context


class MyProfileView(
    LoginRequiredMixin,
    generic.TemplateView,
):
    template_name = "account/profile.html"

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        employee = Employee.objects.select_related(
            "profile",
            "position",
        ).get(user_id=user.pk)

        profile = employee.profile

        context["profile"] = profile
        context["employee"] = employee

        context["positions"] = Position.objects.order_by("name")

        context["contact_form"] = EmployeeContactForm(instance=employee)

        context["position_form"] = EmployeePositionForm(instance=employee)

        context["password_form"] = PasswordChangeForm(user=self.request.user)

        return context


class PartialFormSuccessMixin(LoginRequiredMixin):
    http_method_names = ["post"]
    context_form_name = None

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(**kwargs)

        if self.context_form_name:
            context[self.context_form_name] = kwargs.get(
                "form",
                context.get("form"),
            )

        return context

    def get_success_form(self):
        return self.get_form_class()(instance=self.object)

    def form_valid(
        self,
        form,
    ):
        self.object = form.save()

        success_form = self.get_success_form()

        success_form.is_success = True

        return self.render_to_response(self.get_context_data(form=success_form))

    def form_invalid(
        self,
        form,
    ):
        if hasattr(
            self,
            "get_object",
        ):
            self.object = self.get_object()

        return self.render_to_response(self.get_context_data(form=form))


class UpdateAvatarView(
    LoginRequiredMixin,
    generic.UpdateView,
):
    form_class = ProfileAvatarForm
    http_method_names = ["post"]

    def get_object(
        self,
        queryset=None,
    ):
        return Profile.objects.select_related(
            "employee",
            "employee__user",
        ).get(employee__user=self.request.user)

    def form_valid(
        self,
        form,
    ):
        self.object = form.save()

        return JsonResponse(
            {
                "success": True,
                "avatar_url": self.object.avatar.url,
            }
        )

    def form_invalid(
        self,
        form,
    ):
        return JsonResponse(
            {
                "success": False,
                "errors": form.errors,
            },
            status=400,
        )


class UpdateContactDetailsView(
    PartialFormSuccessMixin,
    generic.UpdateView,
):
    form_class = EmployeeContactForm
    context_form_name = "contact_form"
    template_name = "account/profile.html" "#contact-form"

    def get_object(
        self,
        queryset=None,
    ):
        return Employee.objects.select_related("user").get(user=self.request.user)


class UpdateEmployeePositionView(
    PartialFormSuccessMixin,
    generic.UpdateView,
):
    form_class = EmployeePositionForm
    context_form_name = "position_form"
    template_name = "account/profile.html" "#employee-position-form"

    def get_object(
        self,
        queryset=None,
    ):
        return Employee.objects.select_related("position").get(user=self.request.user)

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(**kwargs)

        context["employee"] = self.object

        context["positions"] = Position.objects.order_by("name")

        return context


class UpdatePasswordView(
    PartialFormSuccessMixin,
    generic.FormView,
):
    form_class = PasswordChangeForm
    context_form_name = "password_form"
    template_name = "account/profile.html" "#password-form"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        kwargs["user"] = self.request.user

        return kwargs

    def get_success_form(self):
        return self.get_form_class()(user=self.request.user)

    def form_valid(
        self,
        form,
    ):
        user = form.save()

        update_session_auth_hash(
            self.request,
            user,
        )

        success_form = self.get_success_form()

        success_form.is_success = True

        return self.render_to_response(self.get_context_data(form=success_form))


class WorkHoursView(
    LoginRequiredMixin,
    generic.TemplateView,
):
    template_name = "account/work_hours.html"
    partial_template_name = "account/work_hours.html" "#work-hours-content"

    def is_partial_request(self):
        return self.request.GET.get("partial") == "1"

    def get_template_names(self):
        if self.is_partial_request():
            return [self.partial_template_name]

        return [self.template_name]

    def get_employee_queryset(self):
        return (
            Employee.objects.filter(
                is_active=True,
                user__is_active=True,
                user__is_verified=True,
            )
            .select_related(
                "user",
                "profile",
                "position",
            )
            .order_by(
                "first_name",
                "last_name",
                "pk",
            )
        )

    def get_selected_month(self):
        today = timezone.localdate()

        month_value = self.request.GET.get("month")

        if not month_value:
            return today.replace(day=1)

        try:
            return parse_work_month(
                month_value,
                reference_date=today,
            )

        except ValueError:
            return today.replace(day=1)

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(**kwargs)

        today = timezone.localdate()

        employees = list(self.get_employee_queryset())

        current_employee = next(
            (
                employee
                for employee in employees
                if (employee.user_id == self.request.user.pk)
            ),
            None,
        )

        if current_employee is None:
            raise Http404

        other_employees = [
            employee for employee in employees if employee.pk != current_employee.pk
        ]

        employees_by_id = {employee.pk: employee for employee in other_employees}

        selected_month = self.get_selected_month()

        employee_value = self.request.GET.get("employee") or "mine"

        show_my_hours = False
        show_all_employees = False
        selected_employee_id = None

        if employee_value == "all":
            show_all_employees = True

            selected_employees = [
                current_employee,
                *other_employees,
            ]

        else:
            requested_employee_id = _parse_int(employee_value)

            selected_employee = (
                employees_by_id.get(requested_employee_id)
                if requested_employee_id is not None
                else None
            )

            if selected_employee is None:
                show_my_hours = True

                selected_employees = [current_employee]

            else:
                selected_employee_id = selected_employee.pk

                selected_employees = [selected_employee]

        calendars = build_work_hours_calendars(
            employees=selected_employees,
            year=selected_month.year,
            month=selected_month.month,
            current_employee=current_employee,
            reference_date=today,
        )

        context.update(
            {
                "other_employees": other_employees,
                "available_work_months": get_available_work_months(
                    reference_date=today,
                ),
                "selected_work_month": selected_month,
                "selected_work_month_value": selected_month.strftime("%Y-%m"),
                "show_my_hours": show_my_hours,
                "show_all_employees": show_all_employees,
                "selected_employee_id": selected_employee_id,
                "work_hours_calendars": calendars,
                "current_employee": current_employee,
            }
        )

        return context


@method_decorator(
    never_cache,
    name="dispatch",
)
class WorkHoursUpdateView(
    LoginRequiredMixin,
    generic.View,
):
    http_method_names = ["post"]

    def post(
        self,
        request,
        *args,
        **kwargs,
    ):
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            raise Http404

        work_date_value = request.POST.get("work_date")

        raw_hours = request.POST.get("hours")

        try:
            work_date = date.fromisoformat(work_date_value)

        except (
            TypeError,
            ValueError,
        ):
            return JsonResponse(
                {
                    "success": False,
                    "message": _("Invalid work date."),
                },
                status=400,
            )

        employee = request.user.employee

        try:
            entry = save_employee_work_hours(
                employee=employee,
                work_date=work_date,
                raw_hours=raw_hours,
            )

        except ValidationError as exc:
            return JsonResponse(
                {
                    "success": False,
                    "message": (exc.messages[0] if exc.messages else str(exc)),
                },
                status=400,
            )

        month_total = get_employee_month_total(
            employee=employee,
            year=work_date.year,
            month=work_date.month,
        )

        return JsonResponse(
            {
                "success": True,
                "work_date": work_date.isoformat(),
                "hours": (
                    format(
                        entry.hours,
                        ".2f",
                    )
                    if entry
                    else ""
                ),
                "has_hours": entry is not None,
                "deleted": entry is None,
                "month_total": format(
                    month_total,
                    ".2f",
                ),
            }
        )


@method_decorator(
    never_cache,
    name="dispatch",
)
class SimpleInvoicePeriodPreviewView(
    LoginRequiredMixin,
    generic.View,
):
    http_method_names = ["get"]

    def get(
        self,
        request,
        *args,
        **kwargs,
    ):
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            raise Http404

        today = timezone.localdate()

        available_years = get_available_invoice_years(
            reference_date=today,
        )

        selected_year = _parse_int(request.GET.get("year"))

        if selected_year not in available_years:
            return JsonResponse(
                {
                    "success": False,
                    "message": _("The selected invoice " "year is not available."),
                },
                status=400,
            )

        available_months = get_available_invoice_months(
            year=selected_year,
            reference_date=today,
        )

        if not available_months:
            return JsonResponse(
                {
                    "success": False,
                    "message": _(
                        "No invoice months are " "available for the " "selected year."
                    ),
                },
                status=400,
            )

        requested_month = _parse_int(request.GET.get("month"))

        if requested_month in available_months:
            selected_month = requested_month

        else:
            selected_month = max(available_months)

        max_day = calendar.monthrange(
            selected_year,
            selected_month,
        )[1]

        if selected_year == today.year and selected_month == today.month:
            max_day = min(
                max_day,
                today.day,
            )

        start_day = _parse_int(request.GET.get("start_day"))

        end_day = _parse_int(request.GET.get("end_day"))

        if start_day is None:
            start_day = 1

        if end_day is None:
            end_day = max_day

        start_day = max(
            1,
            min(
                start_day,
                max_day,
            ),
        )

        end_day = max(
            1,
            min(
                end_day,
                max_day,
            ),
        )

        month_labels = dict(EmployeeSimpleInvoice.Month.choices)

        response_data = {
            "success": True,
            "selected_year": selected_year,
            "selected_month": selected_month,
            "selected_start_day": start_day,
            "selected_end_day": end_day,
            "months": [
                {
                    "value": month,
                    "label": str(month_labels[month]),
                }
                for month in available_months
            ],
            "days": [
                {
                    "value": day,
                    "label": str(day),
                }
                for day in range(
                    1,
                    max_day + 1,
                )
            ],
            "hours": "0.00",
            "can_submit": False,
            "message": "",
        }

        if start_day > end_day:
            response_data["message"] = _("End day cannot be earlier " "than start day.")

            return JsonResponse(response_data)

        try:
            (
                start_date,
                end_date,
            ) = build_invoice_period(
                year=selected_year,
                month=selected_month,
                start_day=start_day,
                end_day=end_day,
            )

            validate_invoice_period_available(
                employee_user_id=request.user.pk,
                start_date=start_date,
                end_date=end_date,
                cleanup_stale=False,
            )

        except ValidationError as exc:
            response_data["message"] = exc.messages[0] if exc.messages else str(exc)

            return JsonResponse(response_data)

        hours = get_invoice_period_hours_total(
            employee_user_id=request.user.pk,
            start_date=start_date,
            end_date=end_date,
        )

        response_data["hours"] = format(
            hours,
            ".2f",
        )

        response_data["can_submit"] = True

        return JsonResponse(response_data)


class SimpleInvoiceCreateView(
    LoginRequiredMixin,
    generic.View,
):
    template_name = "account/invoice.html"
    partial_template_name = "account/invoice.html" "#simple-invoice-form"

    def get_employee(self):
        last_invoice = EmployeeSimpleInvoice.objects.filter(
            employee_id=OuterRef("pk"),
        ).order_by("-pk")

        return Employee.objects.annotate(
            last_simple_invoice_number=Subquery(
                last_invoice.values("invoice_number")[:1]
            ),
            last_simple_invoice_rate=Subquery(last_invoice.values("rate")[:1]),
            last_simple_invoice_gst_account_number=Subquery(
                last_invoice.values("gst_account_number")[:1]
            ),
            last_simple_invoice_gst=Subquery(last_invoice.values("gst")[:1]),
            last_simple_invoice_wsbc=Subquery(last_invoice.values("wsbc")[:1]),
        ).get(
            user_id=self.request.user.pk,
        )

    def get_employee_form(
        self,
        employee,
        data=None,
    ):
        if data is not None:
            return EmployeeInvoiceForm(data)

        return EmployeeInvoiceForm(
            initial={
                "street_address": employee.street_address,
                "city": employee.city,
                "province": employee.province,
                "postal_code": employee.postal_code,
            }
        )

    def get_invoice_form(
        self,
        employee,
        data=None,
        last_invoice=None,
    ):
        if data is not None:
            return SimpleInvoiceForm(
                data,
                employee=employee,
            )

        period_initial = get_initial_invoice_period(
            employee=employee,
        )

        invoice_initial = {
            "invoice_year": period_initial["year"],
            "invoice_month": period_initial["month"],
            "start_day": period_initial["start_day"],
            "end_day": period_initial["end_day"],
            "hours": period_initial["hours"],
        }

        if last_invoice is not None:
            last_invoice_number = last_invoice.invoice_number

            last_rate = last_invoice.rate

            last_gst_account_number = last_invoice.gst_account_number

            last_gst = last_invoice.gst

            last_wsbc = last_invoice.wsbc

        else:
            last_invoice_number = getattr(
                employee,
                "last_simple_invoice_number",
                None,
            )

            last_rate = getattr(
                employee,
                "last_simple_invoice_rate",
                None,
            )

            last_gst_account_number = getattr(
                employee,
                "last_simple_invoice_gst_account_number",
                "",
            )

            last_gst = getattr(
                employee,
                "last_simple_invoice_gst",
                None,
            )

            last_wsbc = getattr(
                employee,
                "last_simple_invoice_wsbc",
                None,
            )

        if last_invoice_number is not None:
            if last_invoice_number < 99:
                invoice_initial["invoice_number"] = last_invoice_number + 1

            invoice_initial.update(
                {
                    "rate": (str(last_rate) if last_rate is not None else ""),
                    "gst_account_number": (last_gst_account_number or ""),
                    "gst": (str(last_gst) if last_gst is not None else ""),
                    "wsbc": (str(last_wsbc) if last_wsbc is not None else ""),
                }
            )

        else:
            invoice_initial["invoice_number"] = 1

        return SimpleInvoiceForm(
            initial=invoice_initial,
            employee=employee,
        )

    def get_context(
        self,
        employee,
        employee_form=None,
        invoice_form=None,
    ):
        return {
            "employee_form": (employee_form or self.get_employee_form(employee)),
            "invoice_form": (invoice_form or self.get_invoice_form(employee)),
        }

    def get(
        self,
        request,
        *args,
        **kwargs,
    ):
        employee = self.get_employee()

        context = self.get_context(employee)

        return render(
            request,
            self.template_name,
            context,
        )

    def post(
        self,
        request,
        *args,
        **kwargs,
    ):
        employee = self.get_employee()

        employee_form = self.get_employee_form(
            employee,
            data=request.POST,
        )

        invoice_form = self.get_invoice_form(
            employee,
            data=request.POST,
        )

        if employee_form.is_valid() and invoice_form.is_valid():
            try:
                invoice = submit_simple_invoice(
                    employee=employee,
                    invoice_data=invoice_form.cleaned_data,
                    employee_data=employee_form.cleaned_data,
                )

            except ValidationError as exc:
                invoice_form.add_error(
                    None,
                    exc,
                )

            else:
                employee_form = self.get_employee_form(employee)

                invoice_form = self.get_invoice_form(
                    employee,
                    last_invoice=invoice,
                )

                invoice_form.is_success = True

                context = self.get_context(
                    employee,
                    employee_form=employee_form,
                    invoice_form=invoice_form,
                )

                context["invoice_id"] = invoice.pk

                return render(
                    request,
                    self.partial_template_name,
                    context,
                )

        context = self.get_context(
            employee,
            employee_form=employee_form,
            invoice_form=invoice_form,
        )

        return render(
            request,
            self.partial_template_name,
            context,
        )


@method_decorator(
    never_cache,
    name="dispatch",
)
class SimpleInvoiceStatusView(
    LoginRequiredMixin,
    generic.View,
):
    http_method_names = ["get"]

    def get(
        self,
        request,
        invoice_id,
        *args,
        **kwargs,
    ):
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            raise Http404

        invoice = get_simple_invoice_after_expiration_check(
            invoice_id=invoice_id,
            employee_user_id=request.user.pk,
        )

        if invoice is None:
            raise Http404

        can_download = invoice.status == EmployeeSimpleInvoice.Status.SENT and bool(
            invoice.pdf_file
        )

        return JsonResponse(
            {
                "status": invoice.status,
                "can_download": can_download,
            }
        )


@method_decorator(
    never_cache,
    name="dispatch",
)
class SimpleInvoiceDownloadView(
    LoginRequiredMixin,
    generic.View,
):
    def get(
        self,
        request,
        invoice_id,
        *args,
        **kwargs,
    ):
        invoice = get_simple_invoice_after_expiration_check(
            invoice_id=invoice_id,
            employee_user_id=request.user.pk,
        )

        if invoice is None:
            raise Http404

        if invoice.status != EmployeeSimpleInvoice.Status.SENT or not invoice.pdf_file:
            return HttpResponse(
                "Invoice PDF is not ready.",
                status=409,
            )

        return redirect(invoice.pdf_file.url)


class CheatSheetView(
    LoginRequiredMixin,
    generic.TemplateView,
):
    template_name = "account/cheat_sheet.html"
    partial_template_name = "account/cheat_sheet.html" "#cheat-sheet-detail"

    def is_partial_request(self):
        return self.request.GET.get("partial") == "1"

    def get_cheat_sheet_id(self):
        cheat_sheet_id = self.request.GET.get("cheat_sheet_id")

        if not cheat_sheet_id:
            return None

        try:
            return int(cheat_sheet_id)

        except (
            TypeError,
            ValueError,
        ):
            return None

    def get_template_names(self):
        if self.is_partial_request():
            return [self.partial_template_name]

        return [self.template_name]

    def get_context_data(
        self,
        **kwargs,
    ):
        context = super().get_context_data(**kwargs)

        cheat_sheet_id = self.get_cheat_sheet_id()

        if self.is_partial_request():
            context["cheat_sheet_steps"] = []

            if cheat_sheet_id:
                context["cheat_sheet_steps"] = get_cheat_sheet_steps_cached(
                    cheat_sheet_id=cheat_sheet_id,
                )

            return context

        context["cheat_sheets"] = get_cheat_sheets_cached()

        return context
