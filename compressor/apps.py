from django.apps import AppConfig


class CompressorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'compressor'

    def ready(self):
        from pillow_heif import register_heif_opener

        register_heif_opener()
