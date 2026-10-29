from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts and permissions"

    def ready(self):
        from django.db.models.signals import post_migrate

        from .supabase import harden_after_migrate

        post_migrate.connect(harden_after_migrate, dispatch_uid="accounts_supabase_harden")
