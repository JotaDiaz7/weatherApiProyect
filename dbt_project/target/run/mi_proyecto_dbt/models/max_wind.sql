
  
    

  create  table "airflow"."pro_raw_api"."max_wind__dbt_tmp"
  
  
    as
  
  (
    

WITH base AS (
    SELECT *
    FROM "airflow"."pro_raw_api"."daily_weather"
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
  );
  