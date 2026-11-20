-- One row per estate: 2020 population and housing units joined to its Census boundary.
-- The Census tables carry names, not codes, so the join is on island + name; a full
-- outer join lets the tests catch any name that fails to match on either side.
with counts as (
    select island, estate, population, housing_units
    from {{ source('raw', 'census_counts') }} where estate is not null
)
select
    s.geoid,
    coalesce(s.island, c.island)                                as island,
    coalesce(s.estate, c.estate)                                as estate,
    regexp_replace(coalesce(s.estate, c.estate), '^Estate ', '') as estate_name,
    c.population,
    c.housing_units,
    s.lat,
    s.lon,
    round(s.land_m2 / 1e6, 3)                                   as land_km2,
    s.rings_json
from {{ source('raw', 'estate_shapes') }} s
full outer join counts c on c.island = s.island and c.estate = s.estate
