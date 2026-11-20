-- Storms everyone in the territory remembers must show up as hurricanes passing near.
with expected as (
    select * from (values ('AL111989', 'Hugo 1989'), ('AL151995', 'Marilyn 1995'),
                          ('AL112017', 'Irma 2017'), ('AL152017', 'Maria 2017')) t(storm_id, label)
)
select x.*, s.closest_nmi, s.wind_at_closest_kt
from expected x left join {{ ref('mart_storms_near_usvi') }} s using (storm_id)
where s.storm_id is null or not s.is_near or not s.is_hurricane or s.storm_label <> x.label
