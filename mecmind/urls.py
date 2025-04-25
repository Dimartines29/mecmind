from django.urls import path, include

app_name = 'mecmind_app'

urlpatterns = [
    path('', include('mecmind_app.urls')),
]