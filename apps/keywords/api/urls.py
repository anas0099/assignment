from django.urls import path

from . import views

urlpatterns = [
    path('upload/', views.KeywordUploadAPIView.as_view(), name='api-keyword-upload'),
    path('', views.KeywordListAPIView.as_view(), name='api-keyword-list'),
    path('<int:pk>/', views.KeywordDetailAPIView.as_view(), name='api-keyword-detail'),
]
