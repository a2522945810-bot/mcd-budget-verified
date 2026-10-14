#!/usr/bin/env python3
"""Replay a redacted historical WorkBuddy transcript. No network or live price."""

import json
import re
from datetime import timedelta, timezone
from pathlib import Path

from budget import make_plan, rank, stamp, utcnow
from official_price import to_quote


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'workbuddy.md'


def replay(now=None):
    blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', RECORD.read_text(encoding='utf-8'))
    if len(blocks) != 2:
        raise ValueError('workbuddy.md 应包含请求与响应两个 JSON 块')
    request, response = map(json.loads, blocks)
    # The response records price-call time, but not a precise menu-fetch time.
    # This reconstructed plan time is ONLY for replay, not a claim about the MCP log.
    quoted_at = response['datetime'].replace(' ', 'T') + '+08:00'
    call_time = stamp(quoted_at)
    options = request['items'][0]['roundList']
    menu = {
        'source': 'mcp', 'currency': 'CNY', 'service': 'pickup',
        'store_id': request['storeCode'], 'fetched_at': quoted_at,
        'offers': [{
            'id': 'workbuddy-historical-c', 'name': '大堡口福三件套', 'kind': 'meal',
            'available': True, 'components_known': True,
            'components': ['Hold不住鸡排堡（椒盐风味）', '中薯条', '阳光柠檬红茶中杯'],
            'selections': [{
                'item_code': request['items'][0]['productCode'], 'quantity': 1,
                'options': {'roundList': options},
            }],
            'coupon_ids': [], 'reference_minor': None,
        }],
    }
    plan = make_plan(menu, 2500, ['可乐'], call_time, ['薯条'])
    quote = to_quote(plan, plan['candidates'][0], request, response, quoted_at)
    result = rank(plan, {'quotes': [quote]}, call_time)
    now = now or utcnow()
    return result, (now - call_time).total_seconds() > 300


def main():
    result, expired = replay()
    item = result['results'][0]
    print('历史记录复核｜来自 workbuddy.md 的脱敏 WorkBuddy 回述')
    print('不联网、不读取 Token；菜单抓取时刻在历史记录中缺失，'
          '重建时间仅供本地复核，不代表原始菜单调用时间。')
    beijing = stamp(item['quoted_at']).astimezone(timezone(timedelta(hours=8)))
    print(f"记录时间：{beijing.strftime('%Y-%m-%d %H:%M:%S')} 北京时间；门店：{result['store_id']}")
    print('选择：鸡排堡＋中薯条＋阳光柠檬红茶（未用券）')
    print(f"历史应付：¥{item['payable_minor']/100:.2f}；"
          f"相对 ¥{result['budget_minor']/100:.2f} 预算余 ¥{item['remaining_minor']/100:.2f}")
    print('当前状态：已超过本项目 5 分钟报价窗口，不是实时价格。' if expired
          else '当前状态：历史复核成功，仍需重新查询才能作为当前报价。')


if __name__ == '__main__':
    main()
