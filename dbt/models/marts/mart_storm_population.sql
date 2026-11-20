-- 2004 on: for each storm whose 34-knot winds reached any estate, the 2020 population and
-- housing units inside each wind field, island by island. Today's population is used for
-- every storm, so this reads as "if this storm came again, who would be in its winds".
select
    s.storm_id, s.storm_label, s.season, e.island,
    {% for kt in [34, 50, 64] %}
    coalesce(sum(e.population) filter (where es.max_field_kt >= {{ kt }}), 0)    as pop_in_{{ kt }}kt,
    coalesce(sum(e.housing_units) filter (where es.max_field_kt >= {{ kt }}), 0) as housing_in_{{ kt }}kt,{% endfor %}
    sum(e.population)                                                         as island_population
from {{ ref('int_estate_storm') }} es
join {{ ref('stg_estates') }} e using (geoid)
join {{ ref('stg_storms') }} s using (storm_id)
where es.has_radii
group by all
having coalesce(sum(e.population) filter (where es.max_field_kt >= 34), 0) > 0
    or count(*) filter (where es.max_field_kt >= 34) > 0
