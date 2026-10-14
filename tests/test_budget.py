import copy
import io
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import budget as b
import connect_mcp as m


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,11,8,tzinfo=timezone.utc)
        self.menu=b.load(Path(__file__).resolve().parents[1]/'assets/synthetic-menu.json')
        self.menu['fetched_at']=b.iso(self.now)
        self.plan=b.make_plan(self.menu,2500,['可乐'],self.now)

    def quote(self,c=None,**changes):
        c=c or self.plan['candidates'][0]
        q=dict(candidate_id=c['id'],plan_id=self.plan['plan_id'],source='synthetic',
               tool='synthetic-price',currency='CNY',store_id=self.plan['store_id'],service='pickup',
               cart_fingerprint=b.digest(c['cart']),quoted_at=b.iso(self.now),status='ok',payable_minor=2000)
        q.update(changes);return q

    def check_rejected(self,**changes):
        result=b.rank(self.plan,{'quotes':[self.quote(**changes)]},self.now)
        self.assertEqual(result['status'],'insufficient_quotes')
        self.assertEqual(result['valid_quotes'],0)
        self.assertEqual(len(result['rejected_quotes']),1)

    def test_no_cola_in_fixed_meals(self):
        self.assertEqual(len(self.plan['candidates']),10)
        self.assertNotIn('可乐',json.dumps(self.plan['candidates'],ensure_ascii=False))
        self.assertEqual(len(self.plan['skipped']),3)

    def test_required_side(self):
        plan=b.make_plan(self.menu,2500,['可乐'],self.now,['薯条'])
        self.assertTrue(plan['candidates'])
        self.assertTrue(all('薯条' in str(c) for c in plan['candidates']))

    def test_unsatisfiable_preferences(self):
        plan=b.make_plan(self.menu,2500,['鸡肉堡'],self.now,['鸡肉堡'])
        result=b.rank(plan,{'quotes':[]},self.now)
        self.assertEqual(result['status'],'no_candidates')

    def test_never_prune_on_reference_price(self):
        plan=b.make_plan(self.menu,100,['可乐'],self.now)
        self.assertEqual(len(plan['candidates']),10)

    def test_light_food_and_drink_without_main(self):
        plan=b.make_plan(self.menu,2500,['可乐'],self.now,['薯条'])
        light=[c for c in plan['candidates'] if
               {x['offer_id'] for x in c['cart']['offers']} == {'demo-side','demo-water'}]
        self.assertEqual(len(light),1)
        self.assertFalse(any({x['offer_id'] for x in c['cart']['offers']} == {'demo-water'}
                             for c in plan['candidates']))

    def test_incomplete_quotes_do_not_claim_no_meal(self):
        result=b.rank(self.plan,{'quotes':[self.quote(payable_minor=3000)]},self.now)
        self.assertEqual(result['status'],'insufficient_quotes')
        self.assertEqual(result['unpriced_candidates'],9)

    def test_all_over_budget(self):
        result=b.rank(self.plan,{'quotes':[self.quote(c,payable_minor=3000) for c in self.plan['candidates']]},self.now)
        self.assertEqual(result['status'],'over_budget')

    def test_exact_budget_and_cent_precision(self):
        result=b.rank(self.plan,{'quotes':[self.quote(payable_minor=2500)]},self.now)
        self.assertEqual(result['results'][0]['remaining_minor'],0)
        self.assertEqual(b.money('0.29'),29)

    def test_different_coupon_same_basket_deduplication(self):
        bare=[c for c in self.plan['candidates'] if len(c['cart']['offers'])==1 and
              c['cart']['offers'][0]['offer_id'].startswith('demo-main')]
        self.assertEqual(len(bare),2)
        result=b.rank(self.plan,{'quotes':[self.quote(bare[0],payable_minor=1800),self.quote(bare[1],payable_minor=1300)]},self.now)
        self.assertEqual(len(result['results']),1)
        self.assertEqual(result['results'][0]['payable_minor'],1300)

    def test_old_quote(self):
        self.check_rejected(quoted_at=b.iso(self.now-timedelta(seconds=301)))

    def test_future_quote(self):
        self.check_rejected(quoted_at=b.iso(self.now+timedelta(seconds=1)))

    def test_wrong_cart_store_source_currency_and_tool(self):
        for values in [{'cart_fingerprint':'changed'}, {'store_id':'another'}, {'source':'mcp'},
                       {'currency':'USD'}, {'tool':'query-meals'}, {'service':'delivery'}, {'plan_id':'old'}]:
            with self.subTest(values=values):self.check_rejected(**values)

    def test_bad_price_and_failed_quote(self):
        for values in [{'payable_minor':True},{'payable_minor':19.99},{'payable_minor':-1},{'status':'error'}]:
            with self.subTest(values=values):self.check_rejected(**values)

    def test_duplicate_quote_is_ambiguous(self):
        with self.assertRaises(b.DataError):b.rank(self.plan,{'quotes':[self.quote(),self.quote()]},self.now)

    def test_stale_menu(self):
        with self.assertRaises(b.DataError):b.rank(self.plan,{'quotes':[]},self.now+timedelta(seconds=1801))

    def test_tampered_plan(self):
        self.plan['budget_minor']=9999
        with self.assertRaises(b.DataError):b.rank(self.plan,{'quotes':[]},self.now)

    def test_money_validation(self):
        for value in ['NaN','Infinity','-2','0','2.001','abc',True,'10001']:
            with self.subTest(value=value),self.assertRaises(b.DataError):b.money(value)

    def test_invalid_menu_data(self):
        for field,value in [('currency','USD'),('service','delivery'),('source','mock-as-live')]:
            menu=copy.deepcopy(self.menu);menu[field]=value
            with self.subTest(field=field),self.assertRaises(b.DataError):b.make_plan(menu,2500,now=self.now)

    def test_synthetic_label(self):
        self.assertIn('均为虚构',b.markdown(b.demo()))
        self.assertEqual(b.demo(100)['status'],'over_budget')


class Response(io.BytesIO):
    def __init__(self,body=b'',content_type='application/json',status=200,headers=None):
        super().__init__(body);self.status=status
        self.headers={'Content-Type':content_type,**(headers or {})}


class FakeOpener:
    def __init__(self):self.requests=[]
    def open(self,req,timeout):
        self.requests.append(req)
        if req.method=='DELETE':return Response(status=204)
        body=json.loads(req.data);method=body['method']
        if method=='notifications/initialized':return Response(status=202)
        if method=='initialize':
            result={'protocolVersion':'2025-06-18','capabilities':{'tools':{}}}
            headers={'Mcp-Session-Id':'TEST_SESSION'}
        elif method=='tools/list':
            result={'tools':[{'name':t,'inputSchema':{'type':'object'}} for t in sorted(m.READ_TOOLS|{'create-order'})]}
            headers={}
        else:raise AssertionError('Unexpected business call')
        return Response(json.dumps({'jsonrpc':'2.0','id':body['id'],'result':result}).encode(),headers=headers)


class ConnectionTests(unittest.TestCase):
    def test_json_and_sse(self):
        obj={'jsonrpc':'2.0','id':2,'result':{'tools':[]}}
        self.assertEqual(m.parse_response(Response(json.dumps(obj).encode()),2),obj['result'])
        sse=b': heartbeat\n\ndata: '+json.dumps(obj).encode()+b'\n\n'
        self.assertEqual(m.parse_response(Response(sse,'text/event-stream'),2),obj['result'])

    def test_reject_wrong_id_and_rpc_error(self):
        for obj in [{'jsonrpc':'2.0','id':99,'result':{}},{'jsonrpc':'2.0','id':2,'error':{'message':'SECRET'}}]:
            with self.assertRaises(m.ConnectionErrorSafe) as err:m.parse_response(Response(json.dumps(obj).encode()),2)
            self.assertNotIn('SECRET',str(err.exception))

    def test_discover_handshake_and_read_only(self):
        opener=FakeOpener();client=m.DiscoveryClient('FAKE_TEST_TOKEN',opener)
        manifest=client.discover();client.close()
        self.assertEqual(manifest['missing_core_tools'],[])
        self.assertNotIn('create-order',[t['name'] for t in manifest['tools']])
        self.assertEqual(manifest['business_calls_performed'],0)
        self.assertEqual(opener.requests[1].get_header('Mcp-session-id'),'TEST_SESSION')
        self.assertEqual(opener.requests[2].get_header('Mcp-protocol-version'),'2025-06-18')
        self.assertEqual(opener.requests[-1].method,'DELETE')
        self.assertNotIn('FAKE_TEST_TOKEN',json.dumps(manifest))

    def test_no_redirect(self):
        with self.assertRaises(m.ConnectionErrorSafe):m.NoRedirect().redirect_request(None,None,302,'',{},'https://example.org')

    def test_no_credential_or_bad_characters(self):
        for token in ('','bad\nheader'):
            with self.assertRaises(m.ConnectionErrorSafe):m.DiscoveryClient(token)


if __name__=='__main__':unittest.main()
