"""
URL маршруты для compressor app
"""

from django.urls import path
from . import views

app_name = 'compressor'

urlpatterns = [
    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Main pages
    path('', views.index, name='index'),
    path('profile/', views.profile, name='profile'),
    
    # API
    path('api/upload/', views.upload_files, name='upload'),
    path('api/compress/<str:session_id>/', views.compress_images, name='compress'),
    path('api/status/<str:session_id>/', views.get_status, name='status'),
    path('api/download/<str:session_id>/', views.download_archive, name='download'),
    path('api/summary/<str:session_id>/', views.get_summary, name='summary'),
]