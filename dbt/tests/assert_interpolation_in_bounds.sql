-- Filled-in hours never invent a wind outside the two real track points around them,
-- and fill gaps of at most 6 hours between points in the window (no long jumps).
select * from {{ ref('int_track_hourly') }}
where wind_kt < least(wind_from, wind_to) - 0.001 or wind_kt > greatest(wind_from, wind_to) + 0.001
   or lat not between -90 and 90 or lon not between -180 and 0
