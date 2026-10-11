"""Supabase over its REST API (PostgREST), with the secret key. Server side only."""
import urllib.parse

from worker.http import send


class Db:
    def __init__(self, url, secret_key):
        self.base = f"{url}/rest/v1"
        self.headers = {"apikey": secret_key, "Authorization": f"Bearer {secret_key}",
                        "Content-Type": "application/json"}

    def paid_rpc(self, name, params):
        from worker.paid_transport import rpc
        return rpc(self.base, self.headers, name, params)

    def upsert(self, table, rows, on_conflict):
        """Insert or update on the natural key, so reruns never duplicate."""
        if table == "fact_marketing_daily":
            raise RuntimeError("Direct fact upserts are disabled; use fenced replacement")
        if rows:
            send(f"{self.base}/{table}?on_conflict={on_conflict}",
                 {**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                 body=rows, method="POST")

    def select(self, table, **filters):
        q = urllib.parse.urlencode({"select": "*", **filters})
        body, _ = send(f"{self.base}/{table}?{q}", self.headers)
        return body
