
  
    

  create  table "airflow"."pro_raw_api"."max_temp_summer__dbt_tmp"
  
  
    as
  
  (
    

WITH base AS (
    SELECT
        city,
        CAST(local_time AS DATE) AS date,
        CAST(local_time AS TIMESTAMP) AS ts,
        temperature
    FROM "airflow"."pro_raw_api"."daily_weather"
    WHERE EXTRACT(MONTH FROM CAST(local_time AS TIMESTAMP)) IN (6, 7, 8)
),

ranked AS (
    SELECT
        city,
        date,
        temperature,
        EXTRACT(YEAR FROM ts) AS year,
        ROW_NUMBER() OVER (
            PARTITION BY city, EXTRACT(YEAR FROM ts)
            ORDER BY temperature DESC
        ) AS rn
    FROM base
)

SELECT
    city,
    date,
    temperature
FROM ranked
WHERE rn = 1
ORDER BY city, date
  );
  