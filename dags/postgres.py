from pyspark.sql import SparkSession
from pyspark.sql.functions import *
import os
import tempfile
from utils import connect_minio, set_data_postgres

def main(name):
    spark = SparkSession.builder.appName(name)\
        .config("spark.jars", "/opt/spark/jars/postgresql-42.2.27.jar")\
        .config("spark.driver.extraClassPath", "/opt/spark/jars/postgresql-42.2.27.jar")\
        .config("spark.executor.extraClassPath", "/opt/spark/jars/postgresql-42.2.27.jar")\
        .getOrCreate()
        
    try:
        bucket = 'dailyweather'

        #Vamos a comprobar si la ciudad ya existe en nuestro MinIO
        s3 = connect_minio()
        #Listamos las carpetas que haya 
        response = s3.list_objects_v2(Bucket=bucket, Delimiter="/")
        #Recorremos y obtenemos las carpetas con prefijos en común, si no me da una lista vacía
        folders = [obj['Prefix'].rstrip('/') for obj in response.get('CommonPrefixes', [])]
        if not folders:#Lanzamos excepción
            raise Exception('No hay carpetas disponibles')
        
        #Vamos a coger archivos de la primera
        folder = folders[len(folders)-1]

        response = s3.list_objects_v2(Bucket=bucket, Prefix=folder + "/")
        files = [obj['Key'] for obj in response.get('Contents', [])]
        if not files:
            raise Exception("No hay archivos en la carpeta")
        
        #Creamos un directorio temporal para descargarnos los archivos
        temp_dir = tempfile.mkdtemp()
        #Introducimos todos los archivos en el directorio
        for file in files:
            filename = os.path.basename(file)
            local_path = os.path.join(temp_dir, filename)
            s3.download_file(bucket, file, local_path)

        # Leer parquet con Spark
        df = spark.read.parquet(temp_dir)
        df.show()

        set_data_postgres(df, "daily_weather")

    except Exception as e:
        print("Error:", e)
    finally:
        spark.stop()

if __name__ == "__main__":
    main("WeatherApiProject")