{{ config(materialized='table') }}


WITH base AS (
    SELECT
        city,
        CAST(local_time AS DATE) AS date_day,
        CAST(humidity AS INT) AS humidity
    FROM {{ source('my_source', 'daily_weather') }}  
)

SELECT
    city,
    date_day AS date,
    AVG(humidity) AS humidity
FROM base
GROUP BY
    city,
    date_day