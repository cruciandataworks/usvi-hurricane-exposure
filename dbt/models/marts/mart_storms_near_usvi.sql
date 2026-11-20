-- Every storm whose centre came within {{ var('listed_nmi') }} nmi of any estate, 1851 to the latest
-- HURDAT2 season. "Near" (the headline counts) means within {{ var('near_nmi') }} nmi. Strength is the
-- storm's maximum sustained wind at the hour of closest approach, not the wind measured
-- on land. For 2004 on, the 2020 population and housing inside each wind field is added.
with es as (
    select es.*, e.island, e.estate_name, e.population, e.housing_units
    from {{ ref('int_estate_storm') }} es join {{ ref('stg_estates') }} e using (geoid)
),
per_storm as (
    select
        storm_id,
        min(closest_nmi)                                   as closest_nmi,
        arg_min(closest_utc, closest_nmi)                  as closest_utc,
        arg_min(wind_at_closest_kt, closest_nmi)           as wind_at_closest_kt,
        arg_min(island, closest_nmi)                       as closest_island,
        arg_min(estate_name, closest_nmi)                  as closest_estate,
        min(closest_nmi) filter (where island = 'St. Croix')  as stx_nmi,
        min(closest_nmi) filter (where island = 'St. Thomas') as stt_nmi,
        min(closest_nmi) filter (where island = 'St. John')   as stj_nmi,
        bool_or(has_radii)                                 as has_radii,
        max(max_field_kt)                                  as max_field_kt,
        {% for kt in [34, 50, 64] %}
        case when bool_or(has_radii) then coalesce(sum(population) filter (where max_field_kt >= {{ kt }}), 0) end as pop_in_{{ kt }}kt,
        case when bool_or(has_radii) then coalesce(sum(housing_units) filter (where max_field_kt >= {{ kt }}), 0) end as housing_in_{{ kt }}kt,
        case when bool_or(has_radii) then count(*) filter (where max_field_kt >= {{ kt }}) end as estates_in_{{ kt }}kt,{% endfor %}
        max(hours_in_34kt)                                 as max_hours_in_34kt
    from es group by storm_id
),
peak as (
    select storm_id, max(wind_kt) as peak_wind_kt, min(pressure_mb) as min_pressure_mb
    from {{ ref('stg_track_points') }} group by storm_id
)
select
    s.storm_id, s.storm_name, s.storm_label, s.season,
    floor(s.season / 10) * 10                              as decade,
    p.closest_nmi,
    p.closest_utc,
    cast(p.closest_utc - interval 4 hour as date)          as closest_date_ast,
    p.closest_island, p.closest_estate, p.stx_nmi, p.stt_nmi, p.stj_nmi,
    p.wind_at_closest_kt,
    {{ category('p.wind_at_closest_kt') }}                 as category_at_closest,
    p.closest_nmi <= {{ var('near_nmi') }}                 as is_near,
    p.wind_at_closest_kt >= 34                             as is_ts_plus,
    p.wind_at_closest_kt >= 64                             as is_hurricane,
    p.wind_at_closest_kt >= 96                             as is_major,
    k.peak_wind_kt, {{ category('k.peak_wind_kt') }} as peak_category, k.min_pressure_mb,
    p.has_radii, p.max_field_kt,
    p.pop_in_34kt, p.housing_in_34kt, p.estates_in_34kt,
    p.pop_in_50kt, p.housing_in_50kt, p.estates_in_50kt,
    p.pop_in_64kt, p.housing_in_64kt, p.estates_in_64kt,
    p.max_hours_in_34kt
from per_storm p
join {{ ref('stg_storms') }} s using (storm_id)
join peak k using (storm_id)
where p.closest_nmi <= {{ var('listed_nmi') }}
