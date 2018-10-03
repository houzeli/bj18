from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse

from goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin


class CartAddView(View):
    def post(self, request):
        # 校验用户是否登陆
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '请先登陆'})

        # 接收数据（这个数据是前台ajlx传过来的）
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 校验前台传过来的数据
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 校验传送的数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目不合法,请合法操作'})
        # 检验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '没有该商品，请从新选择商品'})
        # 添加购物车
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 校验sku_id的键cart_key是否存在
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            count += int(cart_count)

        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品数量不足'})
        conn.hset(cart_key, sku_id, count)
        total_count = conn.hlen(cart_key)
        return JsonResponse({'res': 5, 'total_count': total_count, 'message': '商品添加成功'})


class CartInfoView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        cart_dict = conn.hgetall(cart_key)
        skus = []
        total_count = 0
        total_price = 0
        for sku_id, count in cart_dict.items():
            # 根据商品id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的小计
            amount = sku.price * int(count)
            sku.amount = amount
            sku.count = count
            skus.append(sku)
            total_count += int(count)
            total_price += amount
        context = {'total_count': total_count,
                   'total_price': total_price,
                   'skus': skus}

        # 使用模板
        return render(request, 'cart/cart.html', context)
class CartUpdateView(View):
    def post(self,request):
        user=request.user
        #判断用户是否登陆
        if not user.is_authenticated:
            return JsonResponse({'res':0,'errmsg':'亲，请先登陆'})
        #接收前台传送过来的数据
        sku_id=request.POST.get('sku_id')
        count=request.POST.get('count')
        #进行数据校验
        if not all([sku_id,count]):
            return JsonResponse({'res':1,'errmsg':'数据填写不完整'})
        #检验填写的数量
        try:
            count=int(count)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})
        #检验该商品是否存在
        try:
            sku=GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在，请从新选择'})
        #业务处理
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        #检验库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品数目不足'})
        #更新
        conn.hset(cart_key,sku_id,count)
        total_count=0
        vals=conn.hvals(cart_key)
        for val in vals:
            total_count+=int(val)
        return JsonResponse({'res': 5, 'total_count': total_count, 'message': '更新成功'})

class CartDeleteView(View):
    def post(self,request):
        user=request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '亲，请先登陆'})
        sku_id=request.POST.get('sku_id')
        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的商品id'})
        try:
            sku=GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})
        conn=get_redis_connection('default')
        cart_key='cart_%d'%user.id
        conn.hdel(cart_key,sku_id)
        total_count=0
        vals=conn.hvals(cart_key)
        for val in vals:
            total_count+=int(val)
        return JsonResponse({'res': 3, 'total_count': total_count, 'message': '删除成功'})