-- Best-track points are 6 hours apart, and a hurricane moving at 15 knots covers 90
-- nautical miles in that time - enough to skip right past an island. So the track is
-- filled in hour by hour with straight lines between points (wind, pressure and radii too).
-- Only hours within {{ var('track_window_nmi') }} nmi of the territory are kept.
with p as (
    select *, {{ nmi('lat', 'lon', 18.05, -64.83) }} as d_usvi from {{ ref('stg_track_points') }}
),
near_storms as (
    select storm_id from p group by storm_id having min(d_usvi) <= {{ var('track_window_nmi') }} + 200
),
legs as (
    select p.*,
        lead(time_utc) over w as t1, lead(lat) over w as lat1, lead(lon) over w as lon1,
        lead(wind_kt) over w as wind1, lead(pressure_mb) over w as pres1,
        {% for kt in [34, 50, 64] %}{% for q in ['ne', 'se', 'sw', 'nw'] %}lead(r{{ kt }}_{{ q }}) over w as r{{ kt }}_{{ q }}_1,
        {% endfor %}{% endfor %}
        lead(d_usvi) over w as d_usvi1
    from p join near_storms using (storm_id)
    window w as (partition by storm_id order by time_utc, seq)
),
steps as (
    -- each leg is split into whole hours; f runs from 0 (this point) towards 1 (the next)
    select l.*, h, case when t1 is null then 0 else h * 60.0 / date_diff('minute', time_utc, t1) end as f
    from legs l, unnest(range(0, case when t1 is null then 1
                                    else greatest(1, ceil(date_diff('minute', time_utc, t1) / 60.0))::int end)) as t(h)
    where t1 is null or t1 > time_utc
),
interp as (
    select
        storm_id,
        time_utc + to_hours(h::bigint)                       as hour_utc,
        f = 0                                                as is_fix,
        status,
        lat + coalesce(lat1 - lat, 0) * f                    as lat,
        lon + coalesce(lon1 - lon, 0) * f                    as lon,
        wind_kt + coalesce(wind1 - wind_kt, 0) * f           as wind_kt,
        wind_kt as wind_from, coalesce(wind1, wind_kt) as wind_to,
        pressure_mb + coalesce(pres1 - pressure_mb, 0) * f   as pressure_mb,
        {% for kt in [34, 50, 64] %}{% for q in ['ne', 'se', 'sw', 'nw'] %}
        case when t1 is null then r{{ kt }}_{{ q }}
             else r{{ kt }}_{{ q }} + (r{{ kt }}_{{ q }}_1 - r{{ kt }}_{{ q }}) * f end as r{{ kt }}_{{ q }},{% endfor %}{% endfor %}
        least(d_usvi, coalesce(d_usvi1, d_usvi))             as leg_min_d
    from steps
)
select * exclude (leg_min_d), r34_ne is not null as has_radii
from interp
where {{ nmi('lat', 'lon', 18.05, -64.83) }} <= {{ var('track_window_nmi') }}
