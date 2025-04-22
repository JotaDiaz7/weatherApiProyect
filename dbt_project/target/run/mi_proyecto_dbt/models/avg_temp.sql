
  
    

  create  table "airflow"."pro_raw_api"."avg_temp__dbt_tmp"
  
  
    as
  
  (
    


WITH base AS (
    SELECT
        city,
        CAST(local_time AS DATE) AS date_day,
        CAST(temperature AS FLOAT) AS temperature
    FROM "airflow"."pro_raw_api"."daily_weather" 
)

SELECT
    city,
    date_day AS date,
    AVG(temperature) AS avg_temperature
FROM base
GROUP BY
    city,
    date_day
  );
  