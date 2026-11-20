-- Every estate against every storm hour near the territory: how close did the centre come,
-- how strong was the storm then, and (2004 on, when NHC records wind radii) did winds of
-- 34, 50 or 64 knots reach the estate? The estate is placed in the storm's NE/SE/SW/NW
-- quadrant by compass bearing from the centre, and compared with that quadrant's radius.
with pairs as (
    select
        e.geoid, h.storm_id, h.hour_utc, h.wind_kt, h.has_radii,
        {{ nmi('h.lat', 'h.lon', 'e.lat', 'e.lon') }}     as d,
        {{ bearing('h.lat', 'h.lon', 'e.lat', 'e.lon') }} as b,
        h.r34_ne, h.r34_se, h.r34_sw, h.r34_nw, h.r50_ne, h.r50_se, h.r50_sw, h.r50_nw,
        h.r64_ne, h.r64_se, h.r64_sw, h.r64_nw
    from {{ ref('int_track_hourly') }} h cross join {{ ref('stg_estates') }} e
),
fields as (
    select *,
        case when not has_radii then null
             when d <= {{ quadrant_radius('b', 'r64') }} then 64
             when d <= {{ quadrant_radius('b', 'r50') }} then 50
             when d <= {{ quadrant_radius('b', 'r34') }} then 34
             else 0 end as field_kt
    from pairs
)
select
    geoid,
    storm_id,
    round(min(d), 1)                  as closest_nmi,
    arg_min(hour_utc, d)              as closest_utc,
    round(arg_min(wind_kt, d))        as wind_at_closest_kt,
    bool_or(has_radii)                as has_radii,
    max(field_kt)                     as max_field_kt,
    count(*) filter (where field_kt >= 34) as hours_in_34kt,
    count(*) filter (where field_kt >= 64) as hours_in_64kt
from fields
group by geoid, storm_id
