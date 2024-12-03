from django.urls import path,include
from . import views
urlpatterns = [
     path('generate-key/', views.generate_key_view, name='generate_key'),
     path('tryon/', views.try_on, name='virtual-try-on'),
     path('razorpay_order', views.RazorpayPaymentView.as_view(), name='razorpay_order'),
     path('razorpay_callback', views.RazorpayCallback.as_view(), name='razorpay_callback'),
]