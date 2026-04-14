from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import FormView, TemplateView

from .forms import LoginForm, SignUpForm


class SignUpView(FormView):
    """Handles the user registration page.

    Redirects already-authenticated users straight to the dashboard so they
    cannot accidentally create a second account.
    """

    template_name = 'accounts/signup.html'
    form_class = SignUpForm

    def dispatch(self, request, *args, **kwargs):
        """Redirect logged-in users away from the sign-up page."""
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Save the new user, log them in, and send them to the dashboard."""
        user = form.save()
        login(self.request, user)
        return redirect('dashboard')


class LoginView(FormView):
    """Handles the login page.

    Supports a ?next= query param so users land back on the page they were
    trying to reach before being redirected to login.
    """

    template_name = 'accounts/login.html'
    form_class = LoginForm

    def dispatch(self, request, *args, **kwargs):
        """Redirect logged-in users away from the login page."""
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Authenticate the user and redirect, or add a form error on bad credentials."""
        user = authenticate(
            self.request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if user is None:
            form.add_error(None, 'Invalid username or password.')
            return self.form_invalid(form)
        login(self.request, user)
        next_url = self.request.GET.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return redirect(next_url)
        return redirect('dashboard')


class LogoutView(View):
    """Logs the user out and redirects to the login page.

    Accepts both GET and POST so a simple link and a form button both work.
    """

    def get(self, request):
        """Log out on a GET request (e.g. clicking a logout link)."""
        logout(request)
        return redirect('login')

    def post(self, request):
        """Log out on a POST request (e.g. submitting a logout form)."""
        logout(request)
        return redirect('login')


class DashboardView(LoginRequiredMixin, TemplateView):
    """Landing page after login showing a summary of the user's scraping activity."""

    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        """Add keyword counts to the template context for the summary cards."""
        context = super().get_context_data(**kwargs)
        from apps.keywords.models import Keyword

        user_keywords = Keyword.objects.filter(upload_file__user=self.request.user)
        context['total_keywords'] = user_keywords.count()
        context['completed_keywords'] = user_keywords.filter(status='completed').count()
        context['pending_keywords'] = user_keywords.exclude(status='completed').count()
        return context
