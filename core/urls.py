from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('giris/', views.login_view, name='login'),
    path('cikis/', views.logout_view, name='logout'),

    # Musaitlik
    path('musaitlik/', views.availability_view, name='availability'),
    path('musaitlik/ozet/', views.availability_summary, name='availability_summary'),

    # Musaitlik Istekleri (yonetici)
    path('musaitlik/istek/', views.availability_request_list, name='availability_request_list'),
    path('musaitlik/istek/yeni/', views.availability_request_create, name='availability_request_create'),
    path('musaitlik/istek/<int:pk>/', views.availability_request_detail, name='availability_request_detail'),

    # Kullanici listesi
    path('kullanicilar/', views.user_list, name='user_list'),

    # Gorevlerim
    path('gorevlerim/', views.my_assignments, name='my_assignments'),

    # Atama
    path('atama/', views.assignment_sheet, name='assignment_sheet'),
    path('atama/kaydet/', views.assignment_save, name='assignment_save'),

    # API endpoints
    path('api/musait-kisiler/', views.api_available_people, name='api_available_people'),
    path('api/hafta-maclari/', views.api_week_matches, name='api_week_matches'),

    # PDF export
    path('atama/pdf/', views.assignment_pdf_view, name='assignment_pdf'),
]
