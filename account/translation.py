from modeltranslation.translator import TranslationOptions, register

from account.models import Position, Employee, CheatSheet, CheatSheetStep


@register(Position)
class PositionTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Employee)
class EmployeeTranslationOptions(TranslationOptions):
    fields = ("first_name", "last_name")


@register(CheatSheet)
class CheatSheetTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(CheatSheetStep)
class CheatSheetStepTranslationOptions(TranslationOptions):
    fields = ("description",)
