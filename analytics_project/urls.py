from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
import os
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    # all our app urls
    path('', include('analytics.urls')),

    # serve css, js and assets folders directly so href="css/style.css" works
    re_path(r'^css/(?P<path>.*)$', serve, {'document_root': os.path.join(settings.BASE_DIR, 'css')}),
    re_path(r'^js/(?P<path>.*)$', serve, {'document_root': os.path.join(settings.BASE_DIR, 'js')}),
    re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': os.path.join(settings.BASE_DIR, 'assets')}),
]
