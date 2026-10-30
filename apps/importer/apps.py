from django.apps import AppConfig


class ImporterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.importer'
    verbose_name = '题库导入'
