import copy
import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import budget as b
import official_price as p


class WorkBuddyPriceShapeTests(unittest.TestCase):
    def setUp(self):
        self.quoted_at = '2026-10-13T16:41:54+08:00'
        self.when = b.stamp(self.quoted_at)
        self.request = {
            'storeCode': '3350005', 'orderType': 1, 'beType': 1,
            'items': [{'productCode': '9900015602', 'quantity': 1,
                       'roundList': [
                           {'round': '1', 'comboItemList': [{'code': '521147', 'quantity': 1}]},
                           {'round': '2', 'comboItemList': [{'code': '4810', 'quantity': 1}]},
                           {'round': '3', 'comboItemList': [{'code': '515281', 'quantity': 1}]},
                       ]}],
        }
        self.response = {
            'success': True, 'code': 200, 'datetime': '2026-10-13 16:41:54',
            'data': {'originalPrice': 2290, 'discount': 0, 'price': 2290,
                     'productList': [{'productCode': '9900015602', 'quantity': 1,
                                      'subtotal': 2290}]},
        }
        menu = {'source': 'mcp', 'currency': 'CNY', 'service': 'pickup',
                'store_id': '3350005',
                'fetched_at': '2026-10-13T16:40:00+08:00',
                'offers': [{'id': 'meal-c', 'name': '大堡口福三件套', 'kind': 'meal',
                            'available': True, 'components_known': True,
                            'components': ['Hold不住鸡排堡（椒盐风味）', '中薯条', '阳光柠檬红茶中杯'],
                            'selections': [{'item_code': '9900015602', 'quantity': 1,
                                            'options': {'roundList': self.request['items'][0]['roundList']}}],
                            'coupon_ids': [], 'reference_minor': 2290}]}
        self.plan = b.make_plan(menu, 2500, ['可乐'], self.when, ['薯条'])
        self.candidate = self.plan['candidates'][0]

    def test_matches_exact_basket_and_price(self):
        q = p.to_quote(self.plan, self.candidate, self.request, self.response, self.quoted_at)
        ranked = b.rank(self.plan, {'quotes': [q]}, self.when)
        self.assertEqual(ranked['status'], 'found')
        self.assertEqual(ranked['results'][0]['payable_minor'], 2290)
        self.assertEqual(ranked['results'][0]['remaining_minor'], 210)
        stale = b.rank(self.plan, {'quotes': [q]}, self.when + timedelta(seconds=301))
        self.assertEqual(stale['status'], 'insufficient_quotes')
        self.assertEqual(stale['valid_quotes'], 0)

    def test_rejects_different_selection_or_product(self):
        req = copy.deepcopy(self.request)
        req['items'][0]['roundList'][2]['comboItemList'][0]['code'] = '3050'
        with self.assertRaises(b.DataError):
            p.to_quote(self.plan, self.candidate, req, self.response, self.quoted_at)
        response = copy.deepcopy(self.response)
        response['data']['productList'][0]['productCode'] = 'other'
        with self.assertRaises(b.DataError):
            p.to_quote(self.plan, self.candidate, self.request, response, self.quoted_at)

    def test_rejects_bad_amount_or_extra_coupon(self):
        response = copy.deepcopy(self.response)
        response['data']['price'] = 13.9
        with self.assertRaises(b.DataError):
            p.to_quote(self.plan, self.candidate, self.request, response, self.quoted_at)
        req = {**self.request, 'couponId': 'not-for-this-path'}
        with self.assertRaises(b.DataError):
            p.to_quote(self.plan, self.candidate, req, self.response, self.quoted_at)


if __name__ == '__main__':
    unittest.main()
