from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('data/', views.data_view, name='data'),
    path('map/', views.map_view, name='map'),

]
