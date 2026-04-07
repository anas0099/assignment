from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class NonWWWRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]
        if host.startswith('www.'):
            non_www = host[4:]
            return HttpResponsePermanentRedirect(
                request.build_absolute_uri().replace(f'://{host}', f'://{non_www}', 1)
            )
        return self.get_response(request)
