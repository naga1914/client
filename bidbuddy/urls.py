from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('success/', views.success, name='success'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('bidbuddy-trial/', views.bidbuddy_trial, name='bidbuddy_trial'),
    path('pro-version/', views.pro_version, name='pro_version'),
    path('pay/', views.pay, name='pay'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('upload/', views.upload_file, name='upload_file'),
    path('check_summary/<str:job_id>/', views.check_summary, name='check_summary'),
]