select storm_id, storm_name, advisory, issued_utc, tau_h, valid_utc, lat, lon,
       max_wind_kt, gust_kt, storm_type, development, fetched_utc
from {{ source('raw', 'active_forecast') }}
