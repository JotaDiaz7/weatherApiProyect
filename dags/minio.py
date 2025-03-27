from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from utils import get_cities_minio, set_df_last_records, set_data_minio

def main(name):
    spark = SparkSession.builder.appName(name).getOrCreate()
    
    try:
        #Vamos a comprobar si la ciudad ya existe en nuestro MinIO
        cities = get_cities_minio()
        bucket = 'dailyweather'

        df = None
        for city in cities:
            df_city = set_df_last_records(city, spark)
            if df is None:
                df = df_city
            else:
                df = df.union(df_city)

        df.show()

        set_data_minio(df, bucket)

    except Exception as e:
        print("Error:", e)
    finally:
        spark.stop()

if __name__ == "__main__":
    main("WeatherApiProject")