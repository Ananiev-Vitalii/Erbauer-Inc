from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.db import transaction
from django.views import generic
from threading import Thread

from account.forms import (
    EmployeeContactForm,
    EmployeePositionForm,
    ProfileAvatarForm,
    SimpleInvoiceForm,
    EmployeeInvoiceForm,
)
from account.models import EmployeeSimpleInvoice, Employee, Position, Profile
from account.services.simple_invoice_service import process_simple_invoice_in_background


class MyProfileView(LoginRequiredMixin, generic.TemplateView):
    template_name = "account/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        employee = Employee.objects.select_related("profile", "position").get(
            user_id=user.pk
        )

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.context_form_name:
            context[self.context_form_name] = kwargs.get("form", context.get("form"))

        return context

    def get_success_form(self):
        return self.get_form_class()(instance=self.object)

    def form_valid(self, form):
        self.object = form.save()

        success_form = self.get_success_form()
        success_form.is_success = True

        return self.render_to_response(self.get_context_data(form=success_form))

    def form_invalid(self, form):
        if hasattr(self, "get_object"):
            self.object = self.get_object()

        return self.render_to_response(self.get_context_data(form=form))


class UpdateAvatarView(LoginRequiredMixin, generic.UpdateView):
    form_class = ProfileAvatarForm
    http_method_names = ["post"]

    def get_object(self, queryset=None):
        return Profile.objects.select_related("employee", "employee__user").get(
            employee__user=self.request.user
        )

    def form_valid(self, form):
        self.object = form.save()

        return JsonResponse(
            {
                "success": True,
                "avatar_url": self.object.avatar.url,
            }
        )

    def form_invalid(self, form):
        return JsonResponse(
            {
                "success": False,
                "errors": form.errors,
            },
            status=400,
        )


class UpdateContactDetailsView(PartialFormSuccessMixin, generic.UpdateView):
    form_class = EmployeeContactForm
    context_form_name = "contact_form"
    template_name = "account/profile.html#contact-form"

    def get_object(self, queryset=None):
        return Employee.objects.select_related("user").get(user=self.request.user)


class UpdateEmployeePositionView(PartialFormSuccessMixin, generic.UpdateView):
    form_class = EmployeePositionForm
    context_form_name = "position_form"
    template_name = "account/profile.html#employee-position-form"

    def get_object(self, queryset=None):
        return Employee.objects.select_related("position").get(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["employee"] = self.object
        context["positions"] = Position.objects.order_by("name")
        return context


class UpdatePasswordView(PartialFormSuccessMixin, generic.FormView):
    form_class = PasswordChangeForm
    context_form_name = "password_form"
    template_name = "account/profile.html#password-form"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_form(self):
        return self.get_form_class()(user=self.request.user)

    def form_valid(self, form):
        user = form.save()
        update_session_auth_hash(self.request, user)

        success_form = self.get_success_form()
        success_form.is_success = True

        return self.render_to_response(self.get_context_data(form=success_form))


class SimpleInvoiceCreateView(LoginRequiredMixin, generic.View):
    template_name = "account/invoice.html"
    partial_template_name = "account/invoice.html#simple-invoice-form"

    def get_employee_form(self, employee, data=None):
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

    def get_invoice_form(self, employee, data=None):
        if data is not None:
            return SimpleInvoiceForm(data)

        today = timezone.localdate()
        invoice_initial = {
            "end_day": today.day,
        }

        last_invoice = (
            EmployeeSimpleInvoice.objects.filter(employee=employee)
            .order_by("-id")
            .first()
        )

        if last_invoice:
            invoice_initial.update(
                {
                    "invoice_number": last_invoice.invoice_number + 1,
                    "rate": str(last_invoice.rate),
                }
            )

        return SimpleInvoiceForm(initial=invoice_initial)

    def get_context(self, employee, employee_form=None, invoice_form=None):
        return {
            "employee_form": employee_form or self.get_employee_form(employee),
            "invoice_form": invoice_form or self.get_invoice_form(employee),
        }

    def get(self, request, *args, **kwargs):
        employee = request.user.employee
        context = self.get_context(employee)

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        employee = request.user.employee

        employee_form = self.get_employee_form(employee, data=request.POST)
        invoice_form = self.get_invoice_form(employee, data=request.POST)

        if employee_form.is_valid() and invoice_form.is_valid():
            employee_data = employee_form.cleaned_data.copy()

            with transaction.atomic():
                invoice = invoice_form.save(commit=False)
                invoice.employee = employee
                invoice.save()

                EmployeeSimpleInvoice.objects.filter(
                    employee=employee,
                ).exclude(
                    id=invoice.id,
                ).delete()

                transaction.on_commit(
                    lambda: Thread(
                        target=process_simple_invoice_in_background,
                        kwargs={
                            "invoice_id": invoice.id,
                            "employee_data": employee_data,
                        },
                        daemon=True,
                        name=f"simple-invoice-{invoice.id}",
                    ).start()
                )

            employee_form = self.get_employee_form(employee)
            invoice_form = self.get_invoice_form(employee)
            invoice_form.is_success = True

            context = self.get_context(
                employee,
                employee_form=employee_form,
                invoice_form=invoice_form,
            )

            return render(request, self.partial_template_name, context)

        context = self.get_context(
            employee,
            employee_form=employee_form,
            invoice_form=invoice_form,
        )

        return render(request, self.partial_template_name, context)
