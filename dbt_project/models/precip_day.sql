{{ config(materialized='table') }}


WITH base AS (
    SELECT
        *
    FROM {{ source('my_source', 'daily_weather') }}  
)

SELECT
    *
FROM base
WHERE precip_mm > 0