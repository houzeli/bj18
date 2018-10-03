import re
from django.http import HttpResponse
from django.conf import settings
from goods.models import GoodsSKU
from django.shortcuts import render, redirect
from django_redis import get_redis_connection

from utils.mixin import LoginRequiredMixin

from django.views import View
from django.core.paginator import Paginator

from users.models import User, Address

from order.models import OrderInfo,OrderGoods
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from celery_tasks.tasks import send
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout


def register(request):
    return render(request, 'users/register.html')


def register_hander(request):
    username = request.POST.get('user_name')
    password = request.POST.get('pwd')
    email = request.POST.get('email')
    allow = request.POST.get('allow')
    if not all([username, password, email]):
        errmsg = '请完整填写信息'
        return render(request, 'users/register.html', {'errmsg': errmsg})
    if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
        errmsg = '邮箱格式错误'
        return render(request, 'users/register.html', {'errmsg': errmsg})
    if allow != 'on':
        errmsg = '亲！请先同意协议'
        return render(request, 'users/register.html', {'errmsg': errmsg})

    try:
        user = User.objects.get(username=username)
    except Exception:
        user = None

    if user:
        errmsg = '用户名已存在'
        return render(request, 'users/register.html', {'errmsg': errmsg})

    user = User.objects.create_user(username, email, password)
    user.is_active = 0
    user.save()
    return redirect('/index')


class RegisterView(View):
    def get(self, request):
        return render(request, 'users/register.html')

    def post(self, request):
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        if not all([username, password, email]):
            errmsg = '请完整填写信息'
            return render(request, 'users/register.html', {'errmsg': errmsg})
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            errmsg = '邮箱格式错误'
            return render(request, 'users/register.html', {'errmsg': errmsg})
        if allow != 'on':
            errmsg = '亲！请先同意协议'
            return render(request, 'users/register.html', {'errmsg': errmsg})

        try:
            user = User.objects.get(username=username)
        except Exception:
            user = None

        if user:
            errmsg = '用户名已存在'
            return render(request, 'users/register.html', {'errmsg': errmsg})

        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode()
        send.delay(email, username, token)

        return redirect('/index')


class ActiveView(View):
    def get(self, request, token):
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            user_id = info['confirm']
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            return redirect('users/login')
        except SignatureExpired as e:
            return HttpResponse('链接已失效')


class LoginView(View):
    def get(self, request):
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''

        return render(request, 'users/login.html', {'username': username, 'checked': checked})

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        remember = request.POST.get('remember')

        if not all([username, password]):
            errmsg = '信息填写不完整'
            return render(request, 'users/login.html', {'errmsg': errmsg})
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active == 1:
                login(request, user)
                next_url = request.GET.get('next', reverse('goods:index'))

                response = redirect(next_url)
                if remember == 'on':
                    response.set_cookie('username', username, max_age=24 * 3600 * 7)
                else:
                    response.delete_cookie('username')
                return response
            else:
                errmsg = '用户未激活'
                return render(request, 'users/login.html', {'errmsg': errmsg})

        else:
            errmsg = '请正确填写用户名或密码'
            return render(request, 'users/login.html', {'errmsg': errmsg})


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect(reverse('goods:index'))


class UserInfoView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        address = Address.objects.get_default_address(user)
        con = get_redis_connection('default')
        history_key = 'history_%d' % user.id
        sku_ids = con.lrange(history_key, 0, 4)
        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)
        context = {'page': 'user',
                   'address': address,
                   'goods_li': goods_li}

        return render(request, 'users/user_center_info.html', context)





class UserOrderView(LoginRequiredMixin, View):
    '''用户订单'''

    def get(self, request, page):
        '''显示'''
        # 获取用户的订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')

        # 遍历获取订单商品的信息
        for order in orders:
            # 根据order_id查询订单商品信息
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.count * order_sku.price
                # 动态给order_sku增加属性amount,保存订单商品的小计
                order_sku.amount = amount

            # 动态给order增加属性，保存订单状态标题
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态给order增加属性，保存订单商品的信息
            order.order_skus = order_skus

        # 分页
        paginator = Paginator(orders, 1)

        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)



        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 组织上下文
        context = {'order_page': order_page,
                   'pages': pages,
                   'page': 'order'}

        # 使用模板
        return render(request, 'users/user_center_order.html', context)

class AddressView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        address = Address.objects.get_default_address(user)
        return render(request, 'users/user_center_site.html', {'page': 'address', 'address': address})

    def post(self, request):
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        if not all([receiver, addr, phone]):
            errmsg = '请完整填写数据，我们才能更好找到您'
            return render(request, 'users/user_center_site.html', {'errmsg': errmsg})
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            errmsg = '请正确填写手机号，方便我们联系'
            return render(request, 'users/user_center_site.html', {'errmsg': errmsg})
        user = request.user
        address = Address.objects.get_default_address(user)
        if address:
            is_default = False
        else:
            is_default = True
        Address.objects.create(user=user,
                               receiver=receiver,
                               zip_code=zip_code,
                               addr=addr,
                               phone=phone,
                               is_default=is_default)

        return redirect(reverse('users:address'))
