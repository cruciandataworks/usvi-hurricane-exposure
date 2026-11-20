-- Storms passing near the territory (centre within {{ var('near_nmi') }} nmi) by decade and strength.
-- Before weather satellites (the 1960s) storms over open water could be missed entirely,
-- so the early decades are a floor, not a full count.
with decades as (
    select unnest(range(1850, (select max(season) from {{ ref('stg_storms') }}) + 1, 10)) as decade
)
select
    d.decade,
    d.decade || 's'                                                   as label,
    count(s.storm_id) filter (where s.is_ts_plus)                     as storms,
    count(s.storm_id) filter (where s.is_ts_plus and not s.is_hurricane) as tropical_storms,
    count(s.storm_id) filter (where s.is_hurricane and not s.is_major)   as hurricanes_cat12,
    count(s.storm_id) filter (where s.is_major)                       as major_hurricanes,
    least(10, (select max(season) from {{ ref('stg_storms') }}) - d.decade + 1) as years_covered
from decades d
left join {{ ref('mart_storms_near_usvi') }} s on s.decade = d.decade and s.is_near
group by all
order by d.decade
