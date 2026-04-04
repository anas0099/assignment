from django.urls import path

from . import views

urlpatterns = [
    path('signup/', views.SignUpAPIView.as_view(), name='api-signup'),
    path('login/', views.LoginAPIView.as_view(), name='api-login'),
]
