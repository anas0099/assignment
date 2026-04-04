from django.urls import path

from . import views

urlpatterns = [
    path('upload/', views.KeywordUploadView.as_view(), name='keyword-upload'),
    path('', views.KeywordListView.as_view(), name='keyword-list'),
    path('<int:pk>/', views.KeywordDetailView.as_view(), name='keyword-detail'),
    path('search/', views.KeywordSearchView.as_view(), name='keyword-search'),
]
