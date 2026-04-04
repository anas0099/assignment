from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views import View
from django.views.generic import FormView, TemplateView

from .forms import LoginForm, SignUpForm


class SignUpView(FormView):
    template_name = 'accounts/signup.html'
    form_class = SignUpForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect('dashboard')


class LoginView(FormView):
    template_name = 'accounts/login.html'
    form_class = LoginForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = authenticate(
            self.request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if user is None:
            form.add_error(None, 'Invalid username or password.')
            return self.form_invalid(form)
        login(self.request, user)
        next_url = self.request.GET.get('next', 'dashboard')
        return redirect(next_url)


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('login')

    def post(self, request):
        logout(request)
        return redirect('login')


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.keywords.models import Keyword
        user_keywords = Keyword.objects.filter(upload_file__user=self.request.user)
        context['total_keywords'] = user_keywords.count()
        context['completed_keywords'] = user_keywords.filter(status='completed').count()
        context['pending_keywords'] = user_keywords.exclude(status='completed').count()
        return context
