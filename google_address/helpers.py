from django.conf import settings


def get_settings(string="GOOGLE_ADDRESS"):
    return getattr(settings, string, {})
