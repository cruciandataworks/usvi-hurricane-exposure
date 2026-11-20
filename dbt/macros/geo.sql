{# Great-circle distance in nautical miles (NHC's unit), the haversine formula. #}
{% macro nmi(lat1, lon1, lat2, lon2) -%}
    (2 * 3440.065 * asin(sqrt(
        pow(sin(radians(({{ lat2 }}) - ({{ lat1 }})) / 2), 2)
        + cos(radians({{ lat1 }})) * cos(radians({{ lat2 }}))
          * pow(sin(radians(({{ lon2 }}) - ({{ lon1 }})) / 2), 2))))
{%- endmacro %}

{# Compass bearing (0 = north, 90 = east) from point 1 to point 2. Used to tell which
   quadrant of a storm (NE, SE, SW, NW) an estate sits in. #}
{% macro bearing(lat1, lon1, lat2, lon2) -%}
    ((degrees(atan2(
        sin(radians(({{ lon2 }}) - ({{ lon1 }}))) * cos(radians({{ lat2 }})),
        cos(radians({{ lat1 }})) * sin(radians({{ lat2 }}))
        - sin(radians({{ lat1 }})) * cos(radians({{ lat2 }})) * cos(radians(({{ lon2 }}) - ({{ lon1 }})))
    )) + 360) % 360)
{%- endmacro %}

{# Saffir-Simpson category from 1-minute sustained wind in knots. #}
{% macro category(wind) -%}
    case when {{ wind }} >= 137 then 'Category 5' when {{ wind }} >= 113 then 'Category 4'
         when {{ wind }} >= 96 then 'Category 3' when {{ wind }} >= 83 then 'Category 2'
         when {{ wind }} >= 64 then 'Category 1' when {{ wind }} >= 34 then 'Tropical storm'
         when {{ wind }} is not null then 'Depression' end
{%- endmacro %}

{# Pick the wind radius for the quadrant the bearing falls in. #}
{% macro quadrant_radius(bearing, prefix) -%}
    case when {{ bearing }} < 90 then {{ prefix }}_ne when {{ bearing }} < 180 then {{ prefix }}_se
         when {{ bearing }} < 270 then {{ prefix }}_sw else {{ prefix }}_nw end
{%- endmacro %}
