-- Estate population and housing units add up exactly to the Census island and territory totals.
with est as (
    select island, sum(population) as population, sum(housing_units) as housing_units
    from {{ ref('stg_estates') }} group by rollup (island)
)
select t.island, t.population, e.population as estate_sum, t.housing_units, e.housing_units as estate_hu
from {{ ref('stg_island_totals') }} t
left join est e on coalesce(e.island, 'Territory') = t.island
where e.population is distinct from t.population or e.housing_units is distinct from t.housing_units
   or (select count(*) from {{ ref('stg_island_totals') }}) <> 4
