from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from utils import create_historical, check_city_minio
from config import CITIES

def main(name):
    # Inicializar Spark
    spark = SparkSession.builder.appName(name)\
        .config("spark.jars", "/opt/spark/jars/postgresql-42.2.27.jar")\
        .config("spark.driver.extraClassPath", "/opt/spark/jars/postgresql-42.2.27.jar")\
        .config("spark.executor.extraClassPath", "/opt/spark/jars/postgresql-42.2.27.jar")\
        .getOrCreate()
    
    try:
        print("Ciudades registradas: ")
        for city in CITIES:
            #Vamos a comprobar si la ciudad ya existe en nuestro MinIO
            exist = check_city_minio(city.get('city'))
            
            if not exist and city.get('city', '').strip() and city.get('lat') is not None and city.get('long') is not None:
                print(f"Vamos a crear un histórico de {city['city']}")
                create_historical(spark, city['city'], city['lat'], city['long'])

    except Exception as e:
        print("Error:", e)
    finally:
        spark.stop()

if __name__ == "__main__":
    main("WeatherApiProject")