


WITH base AS (
    SELECT
        *
    FROM "airflow"."pro_raw_api"."daily_weather"  
)

SELECT
    *
FROM base
WHERE precip_mm > 0