from django.conf.urls import url


from users import views
from users.views import RegisterView,ActiveView,LoginView,UserInfoView,UserOrderView,AddressView,LogoutView

urlpatterns = [
    #url(r'^register$',views.register),
    #url(r'^register_hander$',views.register_hander),
    url(r'^register$', RegisterView.as_view(), name='register'),
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),
    url(r'^login$',LoginView.as_view(),name='login'),
    url(r'^$', UserInfoView.as_view(), name='users'),
    url(r'^order/(?P<page>\d+)$', UserOrderView.as_view(), name='order'),
    url(r'^address$', AddressView.as_view(), name='address'),
    url(r'^logout$', LogoutView.as_view(), name='logout'), # 注销登录


]
