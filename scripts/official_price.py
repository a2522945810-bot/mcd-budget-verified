"""Validate a McDonald's pickup price response against an exact internal candidate.

The host supplies tool request/response JSON. This module does not call the MCP
server and cannot independently authenticate a host-provided transcript.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from budget import DataError, digest, iso, load, minor, require, stamp, text, utcnow


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
                rounds = options['roundList']
                require(isinstance(rounds, list) and rounds, 'roundList须为非空列表')
                ids = set()
                for part in rounds:
                    require(isinstance(part, dict), '套餐轮次须为对象')
                    round_id = part.get('round')
                    # This adapter only supports the numeric IDs observed in
                    # the successful WorkBuddy price request ("1", "2", "3").
                    # A display title such as "选择主食" is not an ID.
                    require(isinstance(round_id, str) and round_id.isascii()
                            and round_id.isdecimal() and round_id not in ids,
                            '本适配器仅支持已核验的数字轮次编码，不能传展示名称或重复轮次')
                    ids.add(round_id)
                    choices = part.get('comboItemList')
                    require(isinstance(choices, list) and choices, '套餐轮次缺少选中商品')
                    for choice in choices:
                        require(isinstance(choice, dict) and set(choice)=={'code','quantity'},
                                '本适配器不支持套餐特制或额外选项；不可擅自附加modification')
                        text(choice['code'], 'comboItemList.code')
                        require(type(choice['quantity']) is int and choice['quantity'] > 0,
                                '套餐选项数量无效')
                item['roundList'] = rounds
            items.append(item)
    return items


def prepare_requests(plan, now=None, limit=8):
    """Prepare up to eight minimal, locally checked price requests; never call MCP."""
    now = now or utcnow()
    require(digest({k: v for k, v in plan.items() if k != 'plan_id'}) == plan.get('plan_id'),
            'plan内容被修改，请重新生成')
    require(plan.get('source') == 'mcp' and plan.get('service') == 'pickup',
            '只支持真实到店取餐plan')
    require(0 <= (now-stamp(plan['fetched_at'])).total_seconds() <= 1800,
            '菜单已超过30分钟，请重新查询')
    require(type(limit) is int and 1 <= limit <= 8, '本轮最多预检8个候选')
    ready, blocked = [], []
    for candidate in plan['candidates'][:limit]:
        try:
            items = expected_items(candidate)
            ready.append({'candidate_id': candidate['id'], 'request': {
                'storeCode': plan['store_id'], 'orderType': 1, 'beType': 1,
                'items': items,
            }})
        except DataError as exc:
            blocked.append({'candidate_id': candidate['id'], 'reason': str(exc)})
    return {'plan_id': plan['plan_id'], 'selected': min(limit, len(plan['candidates'])),
            'ready': ready, 'blocked': blocked,
            'notice': '本地预检，不联网；需按实时工具schema核对后才可逐项调用calculate-price'}


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


def main(argv=None):
    parser = argparse.ArgumentParser(description='离线预检最多8个套餐算价请求，不调用MCP')
    parser.add_argument('--plan', required=True)
    parser.add_argument('--limit', type=int, default=8)
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        result = prepare_requests(load(args.plan), limit=args.limit)
        content = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            Path(args.output).write_text(content, encoding='utf-8')
        else:
            print(content, end='')
        return 0
    except (DataError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        parser.exit(2, f'预检失败：{exc}\n')


if __name__ == '__main__':
    main()
