-- The active-storm logic run on a real past advisory (the storm that became Ernesto,
-- 12 Aug 2024), so the dashboard can show what a threat looks like outside storm season.
{{ forecast_threats(ref('fixture_ernesto_forecast'), "timestamp '2024-08-12 15:00:00'") }}
