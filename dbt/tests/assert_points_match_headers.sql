-- Every storm has exactly as many track points as its header line says.
select s.storm_id, s.n_points, count(p.seq) as parsed
from {{ ref('stg_storms') }} s left join {{ ref('stg_track_points') }} p using (storm_id)
group by all having count(p.seq) <> s.n_points
