from django.conf import settings


def app_config(request):
    return {'app': settings.APP_CONFIG}
