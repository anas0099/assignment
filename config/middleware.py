from django.http import HttpResponsePermanentRedirect


class NonWWWRedirectMiddleware:
    """Permanently redirects www.example.com requests to example.com.

    This keeps the canonical URL consistent and avoids duplicate-content
    issues when the app is accessed via both www and non-www.
    """

    def __init__(self, get_response):
        """Store the next middleware or view in the chain."""
        self.get_response = get_response

    def __call__(self, request):
        """Redirect if the host starts with www., otherwise pass the request through."""
        host = request.get_host().split(':')[0]
        if host.startswith('www.'):
            non_www = host[4:]
            return HttpResponsePermanentRedirect(request.build_absolute_uri().replace(f'://{host}', f'://{non_www}', 1))
        return self.get_response(request)
