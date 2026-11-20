{# For each storm with a current advisory at `as_of`, where does NHC's forecast bring the
   centre closest to the territory? The forecast points (0, 12, 24 ... 120 hours) are
   joined hour by hour with straight lines, and every hour is measured against every
   estate. Used by mart_active_threats, and by a test that replays Ernesto (Aug 2024). #}
{% macro forecast_threats(forecast, as_of) %}
with latest as (
    select * from {{ forecast }}
    where issued_utc <= {{ as_of }} and issued_utc > {{ as_of }} - interval {{ var('advisory_fresh_h') }} hour
    qualify dense_rank() over (partition by storm_id order by issued_utc desc, advisory desc) = 1
),
legs as (
    select *, lead(valid_utc) over w as valid_next, lead(lat) over w as lat_next,
           lead(lon) over w as lon_next, lead(max_wind_kt) over w as wind_next
    from latest window w as (partition by storm_id order by tau_h)
),
hourly as (
    select l.storm_id, l.storm_name, l.advisory, l.issued_utc,
           l.valid_utc + to_hours(h) as valid_utc,
           l.lat + (l.lat_next - l.lat) * h / n as lat,
           l.lon + (l.lon_next - l.lon) * h / n as lon,
           l.max_wind_kt + (l.wind_next - l.max_wind_kt) * h / n as wind_kt
    from (select *, date_diff('hour', valid_utc, valid_next) as n from legs where valid_next is not null) l,
         unnest(range(0, l.n)) as t(h)
    union all
    select storm_id, storm_name, advisory, issued_utc, valid_utc, lat, lon, max_wind_kt
    from legs where valid_next is null
),
dist as (
    select h.*, e.island, e.estate_name,
           {{ nmi('h.lat', 'h.lon', 'e.lat', 'e.lon') }} as d
    from hourly h cross join {{ ref('stg_estates') }} e
),
closest as (
    select storm_id, any_value(storm_name) as storm_name, any_value(advisory) as advisory,
           any_value(issued_utc) as issued_utc,
           min(d) as closest_nmi, arg_min(valid_utc, d) as closest_utc,
           arg_min(island, d) as closest_island, arg_min(estate_name, d) as closest_estate,
           arg_min(wind_kt, d) as wind_at_closest_kt
    from dist group by storm_id
),
now_pos as (
    select storm_id, lat as now_lat, lon as now_lon, max_wind_kt as now_wind_kt, storm_type as now_type,
           {{ nmi('lat', 'lon', 18.05, -64.83) }} as now_nmi_from_usvi
    from latest where tau_h = 0
)
select c.*, n.now_lat, n.now_lon, n.now_wind_kt, n.now_type, round(n.now_nmi_from_usvi) as now_nmi_from_usvi,
       round(c.closest_nmi) as closest_nmi_rounded,
       round(date_diff('minute', {{ as_of }}, c.closest_utc) / 60.0, 1) as hours_to_closest,
       {{ category('c.wind_at_closest_kt') }} as category_at_closest,
       case when c.closest_utc < {{ as_of }} - interval 6 hour then 'passed'
            when c.closest_nmi <= {{ var('near_nmi') }} then 'direct'
            when c.closest_nmi <= {{ var('threat_nmi') }} then 'watch'
            else 'monitor' end as threat_level,
       {{ as_of }} as as_of_utc
from closest c left join now_pos n using (storm_id)
{% endmacro %}
