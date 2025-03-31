
  
    

  create  table "airflow"."pro_raw_api"."avg_hum__dbt_tmp"
  
  
    as
  
  (
    


WITH base AS (
    SELECT
        city,
        CAST(date AS DATE) AS date_day,
        CAST(humidity AS INT) AS humidity
    FROM "airflow"."pro_raw_api"."daily_weather"  -- Usa la fuente declarada
)

SELECT
    city,
    date_day AS date,
    AVG(humidity) AS humidity
FROM base
GROUP BY
    city,
    date_day
  );
  