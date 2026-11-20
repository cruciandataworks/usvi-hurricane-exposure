-- One row per storm. Storms before 1950 had no names; HURDAT2 calls them UNNAMED.
select
    storm_id,
    substr(storm_id, 1, 2)                                       as basin,
    cast(substr(storm_id, 3, 2) as integer)                      as storm_number,
    season,
    case when name = 'UNNAMED' then null else (upper(name[1]) || lower(name[2:])) end  as storm_name,
    case when name = 'UNNAMED' then 'Unnamed ' || season || ' #' || cast(substr(storm_id, 3, 2) as integer)
         else (upper(name[1]) || lower(name[2:])) || ' ' || season end                 as storm_label,
    n_points,
    source_file
from {{ source('raw', 'hurdat_storms') }}
