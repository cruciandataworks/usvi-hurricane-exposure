-- One row per estate: how many storms have passed near it since 1851, and (since 2004,
-- when NHC records how far each storm's winds reached) how many times it sat inside
-- tropical-storm-force (34 kt) or hurricane-force (64 kt) winds.
with es as (
    select es.*, s.storm_label, s.season, s.storm_name
    from {{ ref('int_estate_storm') }} es join {{ ref('stg_storms') }} s using (storm_id)
)
select
    e.geoid, e.island, e.estate, e.estate_name, e.population, e.housing_units, e.land_km2,
    round(e.lat, 5) as lat, round(e.lon, 5) as lon,
    count(*) filter (where es.closest_nmi <= {{ var('near_nmi') }} and es.wind_at_closest_kt >= 34) as storms_near,
    count(*) filter (where es.closest_nmi <= {{ var('near_nmi') }} and es.wind_at_closest_kt >= 64) as hurricanes_near,
    count(*) filter (where es.closest_nmi <= {{ var('near_nmi') }} and es.wind_at_closest_kt >= 96) as majors_near,
    count(*) filter (where es.closest_nmi <= {{ var('near_nmi') }} and es.wind_at_closest_kt >= 64 and es.season >= 1950) as hurricanes_near_since_1950,
    count(*) filter (where es.max_field_kt >= 34)  as times_in_34kt_since_2004,
    count(*) filter (where es.max_field_kt >= 64)  as times_in_64kt_since_2004,
    sum(es.hours_in_34kt)                          as hours_in_34kt_since_2004,
    arg_min(es.storm_label, es.closest_nmi) filter (where es.wind_at_closest_kt >= 64) as closest_hurricane,
    min(es.closest_nmi) filter (where es.wind_at_closest_kt >= 64)                    as closest_hurricane_nmi,
    arg_max(es.storm_label, es.closest_utc) filter (where es.max_field_kt >= 64)      as last_in_64kt
from {{ ref('stg_estates') }} e
left join es using (geoid)
group by all
