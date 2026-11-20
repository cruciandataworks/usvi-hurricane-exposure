-- One row per best-track point. Winds are 1-minute sustained, in knots; radii are the
-- furthest extent (nautical miles) of 34-, 50- and 64-knot winds in each quadrant,
-- recorded from 2004 on. A radius of 0 means no winds that strong in that quadrant.
select
    storm_id,
    seq,
    time_utc,
    record_id,
    case record_id when 'L' then 'Landfall' when 'I' then 'Peak intensity' when 'P' then 'Minimum pressure'
                   when 'C' then 'Closest approach' when 'W' then 'Peak wind' end as record_label,
    status,
    case status when 'HU' then 'Hurricane' when 'TS' then 'Tropical storm' when 'TD' then 'Tropical depression'
                when 'EX' then 'Extratropical' when 'SD' then 'Subtropical depression'
                when 'SS' then 'Subtropical storm' when 'LO' then 'Low' when 'WV' then 'Tropical wave'
                when 'DB' then 'Disturbance' end                                  as status_label,
    lat,
    lon,
    cast(wind_kt as integer)      as wind_kt,
    cast(pressure_mb as integer)  as pressure_mb,
    {% for kt in [34, 50, 64] %}{% for q in ['ne', 'se', 'sw', 'nw'] %}
    cast(r{{ kt }}_{{ q }} as integer) as r{{ kt }}_{{ q }},{% endfor %}{% endfor %}
    r34_ne is not null            as has_radii,
    cast(rmw_nmi as integer)      as rmw_nmi
from {{ source('raw', 'hurdat_points') }}
