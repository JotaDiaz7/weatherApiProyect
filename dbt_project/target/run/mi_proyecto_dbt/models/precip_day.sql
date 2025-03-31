
  
    

  create  table "airflow"."pro_raw_api"."precip_day__dbt_tmp"
  
  
    as
  
  (
    


WITH base AS (
    SELECT
        *
    FROM "airflow"."pro_raw_api"."daily_weather"  
)

SELECT
    *
FROM base
WHERE precip_mm > 0
  );
  