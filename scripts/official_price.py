"""Validate a McDonald's pickup price response against an exact internal candidate.

The host supplies tool request/response JSON. This module does not call the MCP
server and cannot independently authenticate a host-provided transcript.
"""
from collections import Counter

from budget import DataError, digest, iso, minor, require, stamp, text


def expected_items(candidate):
    """Map the confirmed pickup selection shape to calculate-price items."""
    require(not candidate['cart']['coupon_ids'], '本适配器只处理未使用优惠券的试算')
    items = []
    for offer in candidate['cart']['offers']:
        for selection in offer['selections']:
            options = selection['options']
            require(set(options) <= {'roundList'}, '未识别的餐品选配字段')
            item = {'productCode': selection['item_code'],
                    'quantity': selection['quantity']}
            if 'roundList' in options:
                item['roundList'] = options['roundList']
            items.append(item)
    return items


def to_quote(plan, candidate, request, response, quoted_at):
    """Accept a successful exact-basket pickup quote; otherwise raise DataError.

    quoted_at must be the actual tool invocation time with a timezone. Never
    assign the current time to an old response to keep it fresh.
    """
    require(plan['source'] == 'mcp', '只接受真实来源的plan')
    require(candidate['id'] in {c['id'] for c in plan['candidates']}, '不是本轮候选')
    require(isinstance(request, dict) and isinstance(response, dict), '工具入参与返回须为对象')
    require(request.get('storeCode') == plan['store_id'], '算价门店不一致')
    require(type(request.get('orderType')) is int and request['orderType'] == 1, '取餐类型不一致')
    require(type(request.get('beType')) is int and request['beType'] == 1, '场景类型不一致')
    require('beCode' not in request and 'couponId' not in request and 'couponCode' not in request,
            '本适配器不接受企业场景或用券试算')
    require(request.get('items') == expected_items(candidate), '算价购物篮或选配不一致')
    require(response.get('success') is True and type(response.get('code')) is int
            and response['code'] == 200, '官方算价未成功')
    data = response.get('data')
    require(isinstance(data, dict), '算价缺少data')
    payable = minor(data.get('price'), 'data.price')
    discount = minor(data.get('discount'), 'data.discount')
    original = minor(data.get('originalPrice'), 'data.originalPrice')
    require(discount == 0 and original == payable, '未用券价格与原价或优惠不一致')
    products = data.get('productList')
    require(isinstance(products, list), '算价缺少productList')
    actual = Counter()
    for product in products:
        require(isinstance(product, dict), 'productList项无效')
        code = text(product.get('productCode'), 'productCode')
        quantity = product.get('quantity')
        require(type(quantity) is int and quantity > 0, '商品数量无效')
        minor(product.get('subtotal'), 'subtotal')
        actual[code] += quantity
    expected = Counter()
    for item in request['items']:
        expected[item['productCode']] += item['quantity']
    require(actual == expected, '算价返回的商品与请求不一致')
    require(sum(p['subtotal'] for p in products) == payable, '商品小计与应付价不一致')
    dt = stamp(quoted_at)
    # The WorkBuddy response datetime is a local wall-clock string without a
    # timezone. The caller must supply the actual timezone explicitly.
    if response.get('datetime') is not None:
        require(response['datetime'] == quoted_at[:19].replace('T', ' '),
                '算价时间与返回记录不一致')
    return {'plan_id': plan['plan_id'], 'candidate_id': candidate['id'],
            'cart_fingerprint': digest(candidate['cart']), 'source': 'mcp',
            'tool': 'calculate-price', 'currency': 'CNY', 'store_id': plan['store_id'],
            'service': 'pickup', 'quoted_at': iso(dt), 'status': 'ok',
            'payable_minor': payable}
