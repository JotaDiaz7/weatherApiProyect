{{ config(materialized='table') }}


WITH base AS (
    SELECT
        city,
        CAST(date AS DATE) AS date_day,
        CAST(temperature AS FLOAT) AS temperature
    FROM {{ source('my_source', 'daily_weather') }} 
)

SELECT
    city,
    date_day AS date,
    AVG(temperature) AS avg_temperature
FROM base
GROUP BY
    city,
    date_day