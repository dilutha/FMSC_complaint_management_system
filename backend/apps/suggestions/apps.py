from django.apps import AppConfig


class SuggestionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.suggestions"
    label = "suggestions"
    verbose_name = "Suggestion evaluation"

    def ready(self):
        from . import receivers

        receivers.connect()
