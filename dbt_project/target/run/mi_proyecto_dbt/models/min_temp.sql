
  
    

  create  table "airflow"."pro_raw_api"."min_temp__dbt_tmp"
  
  
    as
  
  (
    

WITH base AS (
    SELECT *
    FROM "airflow"."pro_raw_api"."daily_weather"
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
  );
  