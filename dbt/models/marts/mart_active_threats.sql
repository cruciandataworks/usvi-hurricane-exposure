-- Active Atlantic storms with a current NHC advisory, and where the official forecast
-- brings each one closest to the territory in the next 5 days.
{{ forecast_threats(ref('stg_active_forecast'), "cast(now() at time zone 'UTC' as timestamp)") }}
