-- How often? For three strength levels and three periods: how many storms passed near,
-- in how many separate years, and what that implies per year. "Return period" is the
-- average number of years between such storms (years / storms). The chance per year is
-- the share of years with at least one.
with periods as (
    select * from (values ('Since 1851', 1851), ('Since 1950', 1950), ('Since 2004', 2004)) t(period, first_season)
),
levels as (
    select * from (values (1, 'Tropical storm or stronger', 34), (2, 'Hurricane', 64), (3, 'Major hurricane (Cat 3+)', 96)) t(level_order, level, min_kt)
),
last_season as (select max(season) as y from {{ ref('stg_storms') }}),
agg as (
    select
        p.period, p.first_season, l.level_order, l.level, l.min_kt,
        max(ls.y) - p.first_season + 1         as years,
        count(s.storm_id)                      as storms,
        count(distinct s.season)               as years_with_one,
        arg_max(s.storm_label, s.closest_utc)  as most_recent
    from periods p cross join levels l cross join last_season ls
    left join {{ ref('mart_storms_near_usvi') }} s
        on s.is_near and s.season >= p.first_season and s.wind_at_closest_kt >= l.min_kt
    group by p.period, p.first_season, l.level_order, l.level, l.min_kt
)
select *,
    round(years / nullif(storms, 0), 1)        as return_period_years,
    round(100.0 * years_with_one / years, 1)   as pct_years_with_one
from agg
order by first_season, level_order
