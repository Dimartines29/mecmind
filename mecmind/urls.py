from django.urls import path, include
from django.contrib import admin

app_name = 'mecmind_app'

urlpatterns = [
    path('', include('mecmind_app.urls')),
    path('admin/', admin.site.urls),
]
