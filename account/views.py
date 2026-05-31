from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import generic

from account.forms import EmployeeContactForm, EmployeePositionForm, ProfileAvatarForm


class MyProfileView(LoginRequiredMixin, generic.TemplateView):
    template_name = "account/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        employee = self.request.user.employee

        context["profile"] = employee.profile
        context["employee"] = employee
        context["contact_form"] = EmployeeContactForm(instance=employee)
        context["position_form"] = EmployeePositionForm(instance=employee)
        context["password_form"] = PasswordChangeForm(user=self.request.user)
        context["avatar_form"] = ProfileAvatarForm(instance=employee.profile)

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
        return self.request.user.employee.profile

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
        return self.request.user.employee


class UpdateEmployeePositionView(PartialFormSuccessMixin, generic.UpdateView):
    form_class = EmployeePositionForm
    context_form_name = "position_form"
    template_name = "account/profile.html#employee-position-form"

    def get_object(self, queryset=None):
        return self.request.user.employee


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
