-- Conditions that need attention now. Step 6 keeps one GitHub issue open per key and
-- closes it when the condition clears.
with threat as (
    select
        'storm:' || storm_id                                        as alert_key,
        'storm'                                                     as category,
        case threat_level when 'direct' then 'high' else 'medium' end as severity,
        storm_name || ' forecast within ' || cast(closest_nmi_rounded as integer) || ' nmi of the USVI' as title,
        'NHC advisory ' || advisory || ' (' || strftime(issued_utc - interval 4 hour, '%-d %b %H:%M') || ' AST) '
            || 'forecasts the centre of ' || storm_name || ' to pass ' || cast(closest_nmi_rounded as integer)
            || ' nautical miles from ' || closest_estate || ', ' || closest_island || ' around '
            || strftime(closest_utc - interval 4 hour, '%a %-d %b %H:%M') || ' AST, with maximum winds near '
            || cast(round(wind_at_closest_kt / 5) * 5 as integer) || ' knots (' || category_at_closest || '). '
            || 'Follow the National Hurricane Center and VITEMA for official watches and warnings.' as message,
        issued_utc                                                  as observed_at
    from {{ ref('mart_active_threats') }}
    where threat_level in ('direct', 'watch')
),
collector as (
    select 'collector:' || source, 'data', 'medium',
           'Collector failing: ' || source,
           'The last ' || consecutive_failures || ' runs failed for ' || source || '. Last error: '
               || coalesce(last_error, 'none recorded') || '. Last success: '
               || coalesce(strftime(last_success_utc, '%Y-%m-%d %H:%M UTC'), 'never') || '.',
           last_attempt_utc
    from {{ ref('stg_source_health') }}
    where consecutive_failures >= {{ var('max_consecutive_failures') }}
),
new_release as (
    select 'release:hurdat2', 'data', 'low',
           'New HURDAT2 release: ' || any_value(source_file),
           'NHC published ' || any_value(source_file) || '. The pipeline has already rebuilt everything from it; '
               || 'review the README figures (written from {{ var("hurdat_reviewed") }}) and update the '
               || 'hurdat_reviewed variable in dbt_project.yml to close this notice.',
           cast(now() at time zone 'UTC' as timestamp)
    from {{ ref('stg_storms') }}
    having any_value(source_file) <> '{{ var("hurdat_reviewed") }}'
)
select * from threat
union all select * from collector
union all select * from new_release
