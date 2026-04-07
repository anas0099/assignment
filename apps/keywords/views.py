from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.views.generic import DetailView, FormView, ListView

from .cache import (
    get_keyword_list,
    get_search_result,
    invalidate_user_keyword_cache,
    set_keyword_list,
    set_search_result,
)
from .dedup import (
    file_hash,
    is_duplicate,
    is_upload_rate_limited,
    mark_uploaded,
    record_upload_attempt,
    upload_rate_limit_status,
)
from .forms import KeywordUploadForm
from .models import Keyword
from .services import create_keywords_from_list, dispatch_scraping


class KeywordUploadView(LoginRequiredMixin, FormView):
    template_name = 'keywords/upload.html'
    form_class = KeywordUploadForm

    def form_valid(self, form):
        from django.conf import settings

        uploaded_file = form.cleaned_data['file']
        keyword_texts = form.cleaned_data['parsed_keywords']
        file_name = uploaded_file.name
        user_id = self.request.user.id

        if is_upload_rate_limited(user_id):
            _, _, reset_in = upload_rate_limit_status(user_id)
            minutes = max(1, reset_in // 60)
            messages.warning(
                self.request,
                f'Upload limit reached (10 uploads per hour). Try again in ~{minutes} minute{"s" if minutes != 1 else ""}.',
            )
            return self.form_invalid(form)

        hash_value = file_hash(uploaded_file)

        if is_duplicate(self.request.user.id, hash_value):
            messages.warning(
                self.request,
                f'"{file_name}" was already uploaded in the last 5 minutes. Please wait before re-uploading the same file.',
            )
            return self.form_invalid(form)

        mark_uploaded(user_id, hash_value)
        record_upload_attempt(user_id)
        upload_file, keywords = create_keywords_from_list(
            self.request.user, file_name, keyword_texts, file_hash=hash_value,
        )
        keyword_ids = [k.id for k in keywords]
        dispatch_scraping(keyword_ids)
        invalidate_user_keyword_cache(self.request.user.id)

        if settings.SCRAPING_MODE == 'async':
            msg = f'Uploaded {len(keyword_texts)} keywords from {file_name}. Scraping enqueued — results will appear shortly.'
        else:
            msg = f'Uploaded {len(keyword_texts)} keywords from {file_name}.'
        messages.success(self.request, msg)
        return redirect('keyword-list')


class KeywordListView(LoginRequiredMixin, ListView):
    template_name = 'keywords/list.html'
    context_object_name = 'keywords'
    paginate_by = 20

    def get_queryset(self):
        page = self.request.GET.get('page', 1)
        status_filter = self.request.GET.get('status', '')
        user_id = self.request.user.id

        cached = get_keyword_list(user_id, page, status_filter)
        if cached is not None:
            return cached

        qs = Keyword.objects.filter(
            upload_file__user=self.request.user,
        ).select_related('upload_file', 'search_result')

        if status_filter and status_filter in dict(Keyword.Status.choices):
            qs = qs.filter(status=status_filter)

        result = list(qs)
        set_keyword_list(user_id, page, result, status_filter)
        return result

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

    def get_object(self, queryset=None):
        keyword_id = self.kwargs['pk']

        cached = get_search_result(keyword_id)
        if cached is not None:
            return cached

        obj = super().get_object(queryset)
        if obj.status == Keyword.Status.COMPLETED:
            set_search_result(keyword_id, obj)
        return obj


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
