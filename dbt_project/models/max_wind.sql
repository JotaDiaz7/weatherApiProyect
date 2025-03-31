{{ config(materialized='table') }}

WITH base AS (
    SELECT *
    FROM {{ source('my_source', 'daily_weather') }}
),
max_wind AS (
    SELECT city, MAX(wind_kph) AS max_wind
    FROM base
    GROUP BY city
)

SELECT b.*
FROM base b
JOIN max_wind m 
    ON b.city = m.city 
    AND b.wind_kph = m.max_wind