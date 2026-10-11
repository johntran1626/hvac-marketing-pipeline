-- Retired: unfenced raw-table upserts cannot certify authoritative snapshots.
-- Use the fenced worker paid-source protocol after its completeness blocker is resolved.
do $$ begin raise exception 'Legacy LSA fact writer disabled: use fenced replacement protocol'; end $$;
