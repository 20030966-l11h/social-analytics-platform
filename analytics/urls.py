from django.urls import path
from . import views

urlpatterns = [
    # login and signup
    path('', views.login_page, name='login'),
    path('signup/', views.signup_page, name='signup'),
    path('logout/', views.logout_view, name='logout'),

    # main pages
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload_page, name='upload'),
    path('sentiment/', views.sentiment_page, name='sentiment'),
    path('trends/', views.trends_page, name='trends'),
    path('reports/', views.reports_page, name='reports'),
    path('topics/', views.topics_page, name='topics'),
    path('audience/', views.audience_page, name='audience'),
    path('platforms/', views.platforms_page, name='platforms'),
    path('reports/download/', views.download_csv, name='download_csv'),
]
