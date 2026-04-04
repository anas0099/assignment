from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import DashboardView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', DashboardView.as_view(), name='dashboard'),
    path('accounts/', include('apps.accounts.urls')),
    path('api/auth/', include('apps.accounts.api.urls')),
]
