{{ config(materialized='table') }}

WITH base AS (
    SELECT *
    FROM {{ source('my_source', 'daily_weather') }}
),
min_temp AS (
    SELECT city, MIN(temperature) AS min_temp
    FROM base
    GROUP BY city
)

SELECT b.*
FROM base b
JOIN min_temp m 
    ON b.city = m.city 
    AND b.temperature = m.min_temp