"""Synthetic immutable provider + recording RPC. Real SQL semantics tested separately."""
import json
import unittest
from dataclasses import replace
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from hashlib import sha256
from unittest.mock import patch, MagicMock

from worker import sync
from worker.api_client import ApiClient
from worker.db import Db
from worker.paid_sync import SnapshotManifest, SnapshotPage, UnsafeSnapshot, run
from worker.paid_transport import exact_json, rpc
from worker.sources.google_ads import GOOGLE_ADS
from worker.sources.meta import META


def row(**changes):
    return dict(date='2024-10-01',customer_id='account',campaign_id='20814455901',campaign_name='Brand',
                ad_group_id='group',ad_group_name='Group',impressions=10,clicks=2,cost_micros=1000001,
                conversions=Decimal('0.123456789012345678901'),**changes)


class Provider:
    def __init__(self, rows=None):
        self.rows = [row()] if rows is None else rows
        self.manifest_edit = lambda m:m
        self.pages_edit = lambda pages:pages
        self.events = []
    def require_paid_snapshot_support(self, src):
        self.events.append('support')
    def data_through(self):
        self.events.append('health')
        return date(2024,10,2)
    def snapshot_manifest(self, src, window, generation):
        self.events.append('manifest')
        platform={'google_ads':'google_ads','meta':'meta_ads','lsa':'lsa'}[src.name]
        return self.manifest_edit(SnapshotManifest(platform,generation,window.start_date,window.end_date,
            'fixture-current-version',datetime.now(timezone.utc),sha256(exact_json(self.rows).encode()).hexdigest(),True))
    def snapshot_pages(self, src, window, manifest):
        self.events.append('pages')
        yield from self.pages_edit([SnapshotPage(manifest.snapshot_id,None,None,tuple(self.rows))])


class Database:
    def __init__(self):
        self.calls=[];self.fail_on=None;self.lost_ack=None;self.generation=1
        self.previous=None;self.events=[]
    def paid_rpc(self,name,params):
        self.events.append(name);self.calls.append((name,params))
        if self.fail_on==name: raise RuntimeError('synthetic RPC failure')
        if name=='begin_paid_source_run':
            return {'generation':self.generation,'started_at':datetime.now(timezone.utc).isoformat(),'committed_through':self.previous}
        if name=='persist_paid_source_window' and params['p_generation'] != self.generation:
            raise RuntimeError('stale generation')
        if name==self.lost_ack: return None
        if name=='stage_paid_source_window':return len(params['p_raw'])
        if name=='persist_paid_source_window':return len(params['p_facts'])
        return True
    def names(self):return [n for n,_ in self.calls]


class PaidSyncTests(unittest.TestCase):
    def test_shipped_api_fails_closed_before_network_or_state(self):
        db=Database()
        with patch('urllib.request.urlopen') as network, self.assertRaisesRegex(UnsafeSnapshot,'immutable'):
            sync.run(ApiClient('synthetic-unused-key'),db,GOOGLE_ADS)
        network.assert_not_called();self.assertEqual(db.calls,[])

    def test_legacy_paid_window_and_direct_fact_upserts_are_disabled(self):
        with self.assertRaisesRegex(RuntimeError,'fenced'):
            sync.load_window(None,None,GOOGLE_ADS,date(2024,10,1),date(2024,10,2))
        with self.assertRaisesRegex(RuntimeError,'Direct fact'):
            Db('https://unused.invalid','unused').upsert('fact_marketing_daily',[{}],'x')

    def test_full_window_exact_decimal_and_success_order(self):
        db=Database();api=Provider();events=[];db.events=events;api.events=events
        run(api,db,GOOGLE_ADS)
        self.assertLess(events.index('begin_paid_source_run'),events.index('manifest'))
        self.assertLess(events.index('stage_paid_source_window'),events.index('persist_paid_source_window'))
        self.assertEqual(events[-1],'finish_paid_source_run')
        payload=next(p for n,p in db.calls if n=='persist_paid_source_window')
        self.assertEqual(payload['p_facts'][0]['reported_leads'],'0.123456789012345678901')
        self.assertEqual(payload['p_facts'][0]['spend_usd'],'1.000001')

    def test_incomplete_pagination_never_stages_or_writes(self):
        api=Provider();api.pages_edit=lambda pages:[replace(pages[0],next_cursor='missing')]
        db=Database()
        with self.assertRaisesRegex(UnsafeSnapshot,'Incomplete'):run(api,db,GOOGLE_ADS)
        self.assertNotIn('stage_paid_source_window',db.names());self.assertNotIn('finish_paid_source_run',db.names())

    def test_terminal_page_does_not_prove_completeness_when_manifest_differs(self):
        api=Provider();api.pages_edit=lambda pages:[replace(pages[0],rows=())];db=Database()
        with self.assertRaisesRegex(UnsafeSnapshot,'manifest'):run(api,db,GOOGLE_ADS)
        self.assertNotIn('stage_paid_source_window',db.names())

    def test_equal_row_counts_do_not_certify_a_different_snapshot(self):
        api=Provider();api.pages_edit=lambda pages:[replace(pages[0],rows=({**row(),'customer_id':'other'},))];db=Database()
        with self.assertRaisesRegex(UnsafeSnapshot,'manifest'):run(api,db,GOOGLE_ADS)
        self.assertNotIn('stage_paid_source_window',db.names())

    def test_disappeared_record_is_not_reintroduced_from_old_raw_tables(self):
        db=Database();db.select=lambda *args,**kwargs: self.fail('must never reread raw upsert leftovers')
        run(Provider([]),db,GOOGLE_ADS)
        payload=next(p for n,p in db.calls if n=='persist_paid_source_window')
        self.assertEqual(payload['p_raw'],[])

    def test_cursor_cycles_and_snapshot_drift_are_not_silently_dropped(self):
        for edit in [lambda p:[replace(p[0],next_cursor='x'),replace(p[0],request_cursor='x',next_cursor='x'),replace(p[0],request_cursor='x')],lambda p:[replace(p[0],snapshot_id='other')],lambda p:p+p]:
            api=Provider();api.pages_edit=edit;db=Database()
            with self.subTest(edit=edit),self.assertRaises(UnsafeSnapshot):run(api,db,GOOGLE_ADS)
            self.assertNotIn('stage_paid_source_window',db.names())

    def test_stale_snapshot_and_wrong_generation_or_account_subset_fail(self):
        for change in [{'acquired_at':datetime.now(timezone.utc)-timedelta(days=1)},{'generation':999},{'all_accounts':False}]:
            api=Provider();api.manifest_edit=lambda m:replace(m,**change);db=Database()
            with self.subTest(change=change),self.assertRaises(UnsafeSnapshot):run(api,db,GOOGLE_ADS)
            self.assertNotIn('persist_paid_source_window',db.names())

    def test_unknown_brand_duplicate_key_and_invalid_record_fail_without_facts(self):
        for rows in [[{**row(),'campaign_id':'unresolved'}],[row(),row()],[{**row(),'cost_micros':-1}]]:
            db=Database()
            with self.subTest(rows=rows),self.assertRaises(ValueError):run(Provider(rows),db,GOOGLE_ADS)
            self.assertNotIn('persist_paid_source_window',db.names());self.assertNotIn('finish_paid_source_run',db.names())

    def test_failed_rpc_and_lost_ack_never_publish_success(self):
        for rpc_name in ['stage_paid_source_window','persist_paid_source_window']:
            for failure in ['fail_on','lost_ack']:
                db=Database();setattr(db,failure,rpc_name)
                with self.subTest(rpc=rpc_name,failure=failure),self.assertRaises((RuntimeError,ValueError)):run(Provider(),db,GOOGLE_ADS)
                self.assertNotIn('finish_paid_source_run',db.names())

    def test_out_of_order_worker_cannot_finish(self):
        api=Provider();db=Database();original=db.paid_rpc
        def rpc_call(name,params):
            if name=='persist_paid_source_window':db.generation+=1
            return original(name,params)
        db.paid_rpc=rpc_call
        with self.assertRaisesRegex(RuntimeError,'stale'):run(api,db,GOOGLE_ADS)
        self.assertNotIn('finish_paid_source_run',db.names())

    def test_empty_authoritative_snapshot_is_an_explicit_replacement(self):
        db=Database();run(Provider([]),db,GOOGLE_ADS)
        p=next(p for n,p in db.calls if n=='persist_paid_source_window')
        self.assertEqual(p['p_raw'],[]);self.assertEqual(p['p_facts'],[])

    def test_worker_meta_name_maps_to_meta_ads(self):
        raw=dict(date_start='2024-10-01',date_stop='2024-10-01',account_id='account',campaign_id='120208841937650100',campaign_name='Meta',adset_id='set',adset_name='Set',impressions='10',clicks='2',spend='1.000001',actions=[{'action_type':'lead','value':'0.125'}])
        db=Database();run(Provider([raw]),db,META)
        self.assertTrue(all(p['p_source']=='meta_ads' for _,p in db.calls))

    def test_paid_transport_preserves_decimal_and_does_not_retry_lost_ack(self):
        amount=Decimal('12345678901234567890.000001')
        self.assertEqual(json.loads(exact_json({'amount':amount}),parse_float=Decimal)['amount'],amount)
        with self.assertRaises(ValueError):exact_json({'amount':0.1})
        with patch('urllib.request.urlopen',side_effect=TimeoutError('private detail')) as send:
            with self.assertRaisesRegex(RuntimeError,'acknowledgement lost') as error:
                rpc('https://unused.invalid/rest/v1',{},'begin_paid_source_run',{'p_source':'google_ads'})
            self.assertNotIn('private detail',str(error.exception));send.assert_called_once()

    def test_rollback_acknowledgement_is_not_success(self):
        response=MagicMock();response.__enter__.return_value=response
        response.headers={'Preference-Applied':'tx=rollback'};response.read.return_value=b'true'
        with patch('urllib.request.urlopen',return_value=response),self.assertRaises(RuntimeError):
            rpc('https://unused.invalid/rest/v1',{},'finish_paid_source_run',{})

    def test_late_window_failure_does_not_finish_source(self):
        api=Provider([]);api.data_through=lambda:date(2024,11,2);db=Database();original=db.paid_rpc
        def call(name,params):
            if name=='persist_paid_source_window' and params['p_start']=='2024-11-01':raise RuntimeError('late failure')
            return original(name,params)
        db.paid_rpc=call
        with self.assertRaises(RuntimeError):run(api,db,GOOGLE_ADS)
        self.assertEqual(db.names().count('persist_paid_source_window'),1)
        self.assertNotIn('finish_paid_source_run',db.names())
