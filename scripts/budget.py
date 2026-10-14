#!/usr/bin/env python3
"""Deterministic candidates and quote checks. Python 3.10+, standard library.
Internal JSON is NOT McDonald's MCP schema. Host must obtain actual live quotes.
"""
import argparse
import hashlib
import itertools
import json
import sys
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

SOURCE = {'synthetic', 'mcp'}
MAX_OFFERS = 12
MAX_CANDIDATES = 150
MAX_MENU_AGE = 1800
MAX_QUOTE_AGE = 300


class DataError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DataError(message)


def text(value, field):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 500, f'{field} 必须为非空文本')
    return value.strip()


def money(value):
    try:
        d = Decimal(str(value))
        require(d.is_finite() and 0 < d <= 10000 and d.as_tuple().exponent >= -2,
                '预算须为0至10000元之间、最多两位小数的正数')
        return int(d * 100)
    except (InvalidOperation, ValueError, TypeError) as e:
        raise DataError('预算格式错误') from e


def minor(value, field):
    require(type(value) is int and 0 <= value <= 1000000, f'{field} 必须为整数分')
    return value


def stamp(value):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(dt.tzinfo is not None, '时间必须带时区')
        return dt.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError) as e:
        raise DataError('时间须为带时区的ISO8601格式') from e


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def normalized(value):
    return unicodedata.normalize('NFKC', value).casefold().replace(' ', '')


def load(path):
    with open(path, encoding='utf-8') as f:
        obj = json.load(f)
    require(isinstance(obj, dict), '输入须为JSON对象')
    return obj


def make_plan(menu, budget, excludes=(), now=None, includes=()):
    now = now or utcnow()
    require(menu.get('source') in SOURCE, 'source须为synthetic或mcp')
    require(menu.get('currency') == 'CNY', '只支持CNY')
    require(menu.get('service') == 'pickup', '第一版只支持到店取餐')
    store = text(menu.get('store_id'), 'store_id')
    fetched = stamp(menu.get('fetched_at'))
    require(0 <= (now-fetched).total_seconds() <= MAX_MENU_AGE, '菜单时间在未来或已超过30分钟，请刷新')
    require(type(budget) is int and 0 < budget <= 1000000, '预算必须为正整数分')
    excluded = [text(v, 'exclude') for v in excludes]
    included = [text(v, 'include') for v in includes]
    offers = menu.get('offers')
    require(isinstance(offers, list) and len(offers) <= MAX_OFFERS, '请提供至多12个原子餐品/套餐项')
    valid = []; skipped = []; seen = set()
    for offer in offers:
        require(isinstance(offer, dict), 'offer须为对象')
        oid = text(offer.get('id'), 'offer.id')
        require(oid not in seen, 'offer.id重复'); seen.add(oid)
        name = text(offer.get('name'), 'offer.name')
        require(type(offer.get('available')) is bool, 'available须为布尔值')
        require(type(offer.get('components_known')) is bool, 'components_known须为布尔值')
        if not offer['available']:
            skipped.append({'id': oid, 'reason': '当前不可售'}); continue
        if not offer['components_known']:
            skipped.append({'id': oid, 'reason': '组成不明，需先查询详情'}); continue
        parts = offer.get('components')
        require(isinstance(parts, list) and len(parts) > 0, '已知组成必须列出components')
        parts = [text(v, 'component') for v in parts]
        labels = [normalized(v) for v in [name]+parts]
        if any(normalized(x) in label for x in excluded for label in labels):
            skipped.append({'id': oid, 'reason': '包含被排除的餐品'}); continue
        kind = offer.get('kind')
        require(kind in ('main', 'side', 'drink', 'meal'), 'kind须为main/side/drink/meal')
        selections = offer.get('selections')
        require(isinstance(selections, list) and len(selections) > 0, '必须有精确selections')
        clean = []
        for selection in selections:
            require(isinstance(selection, dict), 'selection须为对象')
            code = text(selection.get('item_code'), 'item_code')
            qty = selection.get('quantity')
            require(type(qty) is int and 1 <= qty <= 10, 'quantity须为1至10的整数')
            options = selection.get('options')
            require(isinstance(options, dict), 'options须为对象，空配置用{}')
            clean.append({'item_code': code, 'quantity': qty, 'options': options})
        coupons = offer.get('coupon_ids', [])
        require(isinstance(coupons, list), 'coupon_ids须为列表')
        coupons = [text(c, 'coupon_id') for c in coupons]
        require(len(coupons)==len(set(coupons)), '单项优惠券重复')
        hint = offer.get('reference_minor')
        if hint is not None: minor(hint, 'reference_minor')
        valid.append(dict(id=oid, name=name, kind=kind, components=parts,
                          selections=clean, coupon_ids=coupons, reference_minor=hint))
    scope = dict(source=menu['source'], currency='CNY', service='pickup', store_id=store,
                 fetched_at=iso(fetched), budget_minor=budget, excludes=excluded, includes=included)
    candidates = []
    for n in range(1, min(3, len(valid))+1):
        for group in itertools.combinations(valid, n):
            labels = [normalized(v) for x in group for v in [x['name']]+x['components']]
            if not all(any(normalized(w) in label for label in labels) for w in included):
                continue
            kinds = [x['kind'] for x in group]
            mains = sum(k in ('main', 'meal') for k in kinds)
            # A side and drink can be a useful light choice under a tight budget.
            # Keep at least one food item; drinks alone are outside this Skill.
            if (mains > 1 or kinds.count('side') > 1 or kinds.count('drink') > 1
                    or (mains == 0 and kinds.count('side') != 1)):
                continue
            coupons = [c for x in group for c in x['coupon_ids']]
            if len(set(coupons)) != len(coupons): continue
            cart = {'offers': [{'offer_id': x['id'], 'name': x['name'],
                               'components': x['components'], 'selections': x['selections']} for x in group],
                    'coupon_ids': sorted(coupons)}
            cid = digest({'scope': scope, 'cart': cart})
            hint = sum(x['reference_minor'] for x in group) if all(x['reference_minor'] is not None for x in group) else None
            candidates.append({'id': cid, 'cart': cart, 'reference_minor': hint})
    require(len(candidates)<=MAX_CANDIDATES, '候选超过150个，请缩小餐品范围')
    candidates.sort(key=lambda c: (c['reference_minor'] is None, c['reference_minor'] or 0, c['id']))
    plan = {**scope, 'candidates': candidates, 'skipped': skipped,
            'scope_note': '最多12个已核对组成的原子项；主餐/套餐可加一份小食和一份饮料，也可只选小食或小食加饮料；不覆盖全菜单或全部替换方式'}
    plan['plan_id'] = digest(plan)
    return plan


def rank(plan, quote_bundle, now=None):
    now = now or utcnow()
    require(digest({k: v for k, v in plan.items() if k != 'plan_id'}) == plan.get('plan_id'), 'plan内容被修改，请重新生成')
    require(plan.get('source') in SOURCE and plan.get('currency')=='CNY' and plan.get('service')=='pickup', '不支持的plan')
    require(0 <= (now-stamp(plan['fetched_at'])).total_seconds() <= MAX_MENU_AGE, '菜单已过期，请重新查询')
    require(isinstance(quote_bundle.get('quotes'), list), 'quotes须为列表')
    quotes = quote_bundle['quotes']; require(len(quotes)<=MAX_CANDIDATES, '报价数量超过上限')
    candidates = {x['id']: x for x in plan['candidates']}
    seen = set(); accepted = []; rejected = []; priced = 0; over_budget = 0
    for q in quotes:
        require(isinstance(q, dict), 'quote须为对象')
        cid = q.get('candidate_id')
        require(isinstance(cid, str) and cid not in seen, '报价缺少candidate_id或存在重复，请只保留最新一次结果')
        seen.add(cid)
        try:
            require(cid in candidates, '不是本轮候选')
            require(q.get('plan_id')==plan['plan_id'], '报价不属于本轮plan')
            require(q.get('source')==plan['source'], '模拟与真实来源不能混用')
            require(q.get('tool')==('calculate-price' if plan['source']=='mcp' else 'synthetic-price'), '报价工具不匹配')
            require(q.get('currency')=='CNY' and q.get('store_id')==plan['store_id'] and q.get('service')=='pickup', '币种、门店或取餐方式不匹配')
            require(q.get('cart_fingerprint')==digest(candidates[cid]['cart']), '报价餐品、选项或优惠与候选不匹配')
            require(q.get('status')=='ok', '官方报价失败或无法核对购物篮')
            dt = stamp(q.get('quoted_at')); age=(now-dt).total_seconds()
            require(0 <= age <= MAX_QUOTE_AGE and dt >= stamp(plan['fetched_at']), '报价时间在未来、早于菜单或超过5分钟')
            amount=minor(q.get('payable_minor'), 'payable_minor'); priced+=1
            if amount>plan['budget_minor']:
                over_budget+=1; continue
            accepted.append({'candidate_id': cid, 'cart': candidates[cid]['cart'],
                             'payable_minor': amount, 'remaining_minor': plan['budget_minor']-amount,
                             'quoted_at': iso(dt)})
        except DataError as e:
            rejected.append({'candidate_id': cid, 'reason': str(e)})
    accepted.sort(key=lambda x: (x['payable_minor'], x['candidate_id']))
    # Different coupon routes to the same precise basket occupy one recommendation.
    distinct = []; basket_seen = set()
    for candidate in accepted:
        selections = [s for offer in candidate['cart']['offers'] for s in offer['selections']]
        key = digest(sorted(selections, key=lambda s: json.dumps(s, sort_keys=True)))
        if key not in basket_seen:
            basket_seen.add(key); distinct.append(candidate)
    unpriced=len(candidates)-priced
    status='found' if accepted else ('no_candidates' if not candidates else ('insufficient_quotes' if unpriced else 'over_budget'))
    return {'source': plan['source'], 'status': status, 'store_id': plan['store_id'],
            'budget_minor': plan['budget_minor'], 'generated_candidates': len(candidates),
            'valid_quotes': priced, 'unpriced_candidates': unpriced, 'over_budget_candidates': over_budget,
            'results': distinct[:3], 'rejected_quotes': rejected, 'scope_note': plan['scope_note']}


def markdown(result):
    label = '模拟演示｜商品、优惠和价格均为虚构，不可用于真实消费' if result['source']=='synthetic' else '实时调用结果整理｜来源由调用方提供，本地脚本未独立认证；不构成保价'
    lines=[f'# 预算配餐结果\n\n{label}\n', f"门店：{result['store_id']}；预算：{result['budget_minor']/100:.2f}元。",
           f"本轮生成{result['generated_candidates']}个候选，有效报价{result['valid_quotes']}个，未核价{result['unpriced_candidates']}个。"]
    if result['results']:
        for i,r in enumerate(result['results'],1):
            names='＋'.join(x['name'] for x in r['cart']['offers'])
            lines.append(f"\n{i}. {names}\n   应付{r['payable_minor']/100:.2f}元；预算剩余{r['remaining_minor']/100:.2f}元；报价时间{r['quoted_at']}。")
    else:
        lines.append({'no_candidates':'没有符合本轮餐品组成与偏好规则的候选。',
                      'insufficient_quotes':'没有得到可推荐的预算内报价；仍有未核价或失效结果，不能判定不存在合适组合。',
                      'over_budget':'本轮候选已全部核价，均超出预算。'}[result['status']])
    lines.append('\n搜索范围：'+result['scope_note']+'。未宣称全局最低价。')
    if result['rejected_quotes']: lines.append(f"已拒绝{len(result['rejected_quotes'])}条失效或不匹配报价。")
    return '\n'.join(lines)+'\n'


def demo(budget=2500, excludes=('可乐',), includes=()):
    menu=load(Path(__file__).resolve().parent.parent/'assets'/'synthetic-menu.json')
    now=utcnow(); menu['fetched_at']=iso(now)
    plan=make_plan(menu,budget,excludes,now,includes); quotes=[]
    for c in plan['candidates']:
        payable=c['reference_minor']-(500 if 'DEMO_COUPON_5' in c['cart']['coupon_ids'] else 0)
        quotes.append(dict(plan_id=plan['plan_id'],candidate_id=c['id'],cart_fingerprint=digest(c['cart']),
                           source='synthetic',tool='synthetic-price',currency='CNY',store_id=plan['store_id'],
                           service='pickup',status='ok',quoted_at=iso(now),payable_minor=payable))
    return rank(plan,{'quotes':quotes},now)


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__); sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan');p.add_argument('--input',required=True);p.add_argument('--budget',required=True)
    p.add_argument('--exclude',action='append',default=[]);p.add_argument('--include',action='append',default=[]);p.add_argument('--output')
    p=sub.add_parser('rank');p.add_argument('--plan',required=True);p.add_argument('--quotes',required=True)
    p.add_argument('--format',choices=['json','markdown'],default='markdown');p.add_argument('--output')
    p=sub.add_parser('demo');p.add_argument('--budget',default='25');p.add_argument('--exclude',action='append')
    p.add_argument('--include',action='append',default=[])
    p.add_argument('--format',choices=['json','markdown'],default='markdown');p.add_argument('--output')
    a=ap.parse_args(argv)
    try:
        if a.command=='plan':result=make_plan(load(a.input),money(a.budget),a.exclude,includes=a.include)
        elif a.command=='rank':result=rank(load(a.plan),load(a.quotes))
        else:result=demo(money(a.budget),a.exclude if a.exclude is not None else ['可乐'],a.include)
        out=json.dumps(result,ensure_ascii=False,indent=2) if a.command=='plan' or a.format=='json' else markdown(result)
        if a.output:Path(a.output).write_text(out+'\n',encoding='utf-8')
        else:print(out)
        return 0
    except (DataError, OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        print(f'输入或文件错误：{e}',file=sys.stderr);return 2


if __name__=='__main__':
    sys.exit(main())
