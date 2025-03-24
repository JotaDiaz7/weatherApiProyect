import os
import tempfile
from pyspark.sql import SparkSession
import boto3

def main(name):
    spark = SparkSession.builder.appName(name)\
        .config("spark.jars", "/opt/spark/jars/postgresql-42.2.27.jar") \
        .getOrCreate()

    MINIO_ENDPOINT = "http://minio:9000"
    ACCESS_KEY = "admin"
    SECRET_KEY = "admin123"
    BUCKET_NAME = "test"
    CITY = 'elche_'
    
    try:
        #Me conecto a MinIO
        s3 = boto3.client('s3',
                          endpoint_url=MINIO_ENDPOINT,
                          aws_access_key_id=ACCESS_KEY,
                          aws_secret_access_key=SECRET_KEY)
        #Listamos las carpetas que haya 
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=CITY, Delimiter="/")
        #Recorremos y obtenemos las carpetas con prefijos en común, si no me da una lista vacía
        folders = [obj['Prefix'].rstrip('/') for obj in response.get('CommonPrefixes', [])]
        if not folders:#Lanzamos excepción
            raise Exception('No hay carpetas disponibles')

        #Vamos a coger archivos de la primera
        folder = folders[len(folders)-1]
        
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder + "/")
        files = [obj['Key'] for obj in response.get('Contents', [])]
        if not files:
            raise Exception("No hay archivos en la carpeta")
        
        #Creamos un directorio temporal para descargarnos los archivos
        temp_dir = tempfile.mkdtemp()
        #Introducimos todos los archivos en el directorio
        for file in files:
            filename = os.path.basename(file)
            local_path = os.path.join(temp_dir, filename)
            s3.download_file(BUCKET_NAME, file, local_path)

        # Leer parquet con Spark
        df = spark.read.parquet(temp_dir)
        df.show()

        #Vamos a registrar el df en postgres
        df.write \
          .format("jdbc") \
          .option("url", "jdbc:postgresql://postgres:5432/airflow") \
          .option("dbtable", 'daily_weather') \
          .option("user", "airflow") \
          .option("password", "airflow") \
          .option("driver", "org.postgresql.Driver") \
          .mode("append") \
          .save()

        print("Datos registrados correctamente en la bbdd")

    except Exception as e:
        print("Error:", e)
    finally:
        spark.stop()

if __name__ == "__main__":
    main("WeatherApiBBDD")