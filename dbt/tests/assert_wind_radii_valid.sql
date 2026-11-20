{{ config(severity='warn') }}
-- Where radii are recorded, 64-knot winds never reach further than 50-knot winds, which
-- never reach further than 34-knot winds, and no radius is negative.
select storm_id, seq from {{ ref('stg_track_points') }}
where has_radii and (
    {% for q in ['ne', 'se', 'sw', 'nw'] %}r64_{{ q }} > r50_{{ q }} or r50_{{ q }} > r34_{{ q }} or r64_{{ q }} < 0 or {% endfor %} false)
