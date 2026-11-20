select
    source,
    cast(last_attempt as timestamptz) at time zone 'UTC' as last_attempt_utc,
    cast(last_success as timestamptz) at time zone 'UTC' as last_success_utc,
    cast(consecutive_failures as integer)                as consecutive_failures,
    nullif(last_error, '')                               as last_error,
    nullif(detail, '')                                   as detail
from {{ source('raw', 'source_health') }}
