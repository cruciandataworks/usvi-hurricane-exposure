-- The Census's own island and territory totals, used to check the estate rows add up.
select coalesce(island, 'Territory') as island, population, housing_units
from {{ source('raw', 'census_counts') }}
where estate is null and (is_island_total or island is null)
  and (island is null or island in ('St. Croix', 'St. John', 'St. Thomas'))
