

WITH base AS (
    SELECT *
    FROM "airflow"."pro_raw_api"."daily_weather"
    WHERE EXTRACT(MONTH FROM CAST(date AS timestamp)) IN (6, 7, 8)
),
max_temp AS (
    SELECT 
        city,
        EXTRACT(YEAR FROM CAST(date AS timestamp)) AS year,
        MAX(temperature) AS max_temp
    FROM base
    GROUP BY city, EXTRACT(YEAR FROM CAST(date AS timestamp))
)

SELECT b.*
FROM base b
JOIN max_temp m 
    ON b.city = m.city 
    AND EXTRACT(YEAR FROM CAST(b.date AS timestamp)) = m.year
    AND b.temperature = m.max_temp