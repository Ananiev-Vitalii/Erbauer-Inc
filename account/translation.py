from modeltranslation.translator import TranslationOptions, register

from account.models import Position, Employee


@register(Position)
class PositionTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Employee)
class EmployeeTranslationOptions(TranslationOptions):
    fields = ("first_name", "last_name")
