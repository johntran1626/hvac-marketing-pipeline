"""Offline JSON-line bridge to PGlite, invoked only by the SQL test harness."""
import json
import sys
from decimal import Decimal
from worker.paid_sync import run
from worker.paid_transport import exact_json
from worker.tests.test_paid_sync import Provider, row
from worker.sources.google_ads import GOOGLE_ADS
from worker.sources.meta import META
from worker.sources.lsa import LSA


class PipeDatabase:
    def paid_rpc(self, name, params):
        # Encode every parameter separately so JavaScript never parses raw money
        # as binary float before forwarding JSONB to PostgreSQL.
        print(json.dumps({'name':name,'params':{k:exact_json(v) for k,v in params.items()}}), flush=True)
        response=json.loads(sys.stdin.readline(),parse_float=Decimal)
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response['result']


def main():
    db=PipeDatabase()
    run(Provider([row(),{**row(),'customer_id':'second'}]),db,GOOGLE_ADS)
    run(Provider([dict(date_start='2024-10-01',date_stop='2024-10-01',account_id='bridge',campaign_id='120208841937650100',campaign_name='Meta',adset_id='set',adset_name='Set',impressions='10',clicks='2',spend='12345678901234567890.000001',actions=[{'action_type':'lead','value':'0.125'}])]),db,META)
    run(Provider([dict(lead_id='bridge',lead_created_at='2024-10-02T04:59:00Z',category='category',lead_type='PHONE_CALL',charge_status='CHARGED',credited_at=None,cost_usd=Decimal('12.345678901'))]),db,LSA)


if __name__=='__main__':
    main()
