from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.views.generic import DetailView, FormView, ListView

from .forms import KeywordUploadForm
from .models import Keyword
from .services import create_keywords_from_list, dispatch_scraping


class KeywordUploadView(LoginRequiredMixin, FormView):
    template_name = 'keywords/upload.html'
    form_class = KeywordUploadForm

    def form_valid(self, form):
        keyword_texts = form.cleaned_data['parsed_keywords']
        file_name = form.cleaned_data['file'].name
        upload_file, keywords = create_keywords_from_list(
            self.request.user, file_name, keyword_texts,
        )
        keyword_ids = [k.id for k in keywords]
        dispatch_scraping(keyword_ids)
        messages.success(
            self.request,
            f'Uploaded {len(keyword_texts)} keywords from {file_name}.',
        )
        return redirect('keyword-list')


class KeywordListView(LoginRequiredMixin, ListView):
    template_name = 'keywords/list.html'
    context_object_name = 'keywords'
    paginate_by = 20

    def get_queryset(self):
        qs = Keyword.objects.filter(
            upload_file__user=self.request.user,
        ).select_related('upload_file', 'search_result')

        status_filter = self.request.GET.get('status')
        if status_filter and status_filter in dict(Keyword.Status.choices):
            qs = qs.filter(status=status_filter)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Keyword.Status.choices
        return context


class KeywordDetailView(LoginRequiredMixin, DetailView):
    template_name = 'keywords/detail.html'
    context_object_name = 'keyword'

    def get_queryset(self):
        return Keyword.objects.filter(
            upload_file__user=self.request.user,
        ).select_related('upload_file', 'search_result')


class KeywordSearchView(LoginRequiredMixin, ListView):
    template_name = 'keywords/search.html'
    context_object_name = 'keywords'
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        if not query:
            return Keyword.objects.none()
        return Keyword.objects.filter(
            upload_file__user=self.request.user,
        ).filter(
            Q(text__icontains=query) | Q(upload_file__file_name__icontains=query)
        ).select_related('upload_file', 'search_result')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        return context
