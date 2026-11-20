-- Replays NHC's 11 AM AST 12 Aug 2024 advisory for the storm that became Ernesto, which
-- crossed the Virgin Islands that week. The active-storm logic must rate it a threat.
with t as (
    {{ forecast_threats(ref('fixture_ernesto_forecast'), "timestamp '2024-08-12 15:00:00'") }}
)
select 'Ernesto fixture did not raise a threat' as problem
where not exists (select 1 from t where threat_level in ('direct', 'watch') and closest_nmi <= 60
                  and closest_island = 'St. Croix' and hours_to_closest between 24 and 48)
