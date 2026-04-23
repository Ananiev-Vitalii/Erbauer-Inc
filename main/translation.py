from modeltranslation.translator import TranslationOptions, register

from .models import CompanyProfile, TeamMember, Service, Project


@register(CompanyProfile)
class CompanyProfileTranslationOptions(TranslationOptions):
    fields = (
        "working_hours",
        "about_description",
        "hero_badge",
        "hero_title",
        "hero_description",
        "services_description",
        "footer_description",
    )


@register(TeamMember)
class TeamMemberTranslationOptions(TranslationOptions):
    fields = ("description",)


@register(Service)
class ServiceTranslationOptions(TranslationOptions):
    fields = (
        "title",
        "description",
    )


@register(Project)
class ProjectTranslationOptions(TranslationOptions):
    fields = ("short_description",)
