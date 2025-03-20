import os
import tempfile
import glob
import requests
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lower, date_format
import boto3

def main(name):
    # Inicializar Spark
    spark = SparkSession.builder.appName(name).getOrCreate()

    # Configuración de la API y de MinIO
    API_KEY = "0184ac7ffd35494ca93123514251703"
    city = "Elche"
    url = f"http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={city}&aqi=no"

    MINIO_ENDPOINT = "http://minio:9000"
    ACCESS_KEY = "admin"
    SECRET_KEY = "admin123"
    BUCKET_NAME = "test"

    try:
        # Llamada a la API y parseo del JSON
        response = requests.get(url)
        data = response.json()

        # Crear DataFrames de PySpark a partir del JSON
        df_location = spark.createDataFrame([data["location"]])
        df_current = spark.createDataFrame([data["current"]])
        df_condition = spark.createDataFrame([data["current"]["condition"]])

        # Seleccionar y renombrar columnas
        df_location = df_location.select(
            lower(col("name")).alias("city"),
            date_format(col("localtime"), "yyyy-MM-dd HH:mm").alias("localtime")
        )
        df_current = df_current.select(
            col("temp_c").alias("temperature"),
            col("wind_kph").alias("wind_kph"),
            col("humidity").alias("humidity"),
            col("feelslike_c").alias("feelslike"),
            col("precip_mm").alias("precip_mm")
        )
        df_condition = df_condition.select(
            col("text").alias("text"),
            col("icon").alias("icon")
        )

        # Unir los DataFrames (cross join, ya que cada uno tiene una única fila)
        data_df = df_location.crossJoin(df_current).crossJoin(df_condition)
        data_df.show(truncate=False)

        #Vamos a crear el nombre de la carpeta que va a contener nuestro archivo parquet
        city, localtime = df_location.select(lower("city"), "localtime").first()
        localtime = localtime.replace(":", "-").replace(" ", "_")
        folder_name = f"{city}_{localtime}"
        print("Nombre de la carpeta:", folder_name)

        temp_dir = tempfile.mkdtemp() # Esto lo que te hace es crear un directorio en memoria para no generarlo en local 
        output_path = os.path.join(temp_dir, folder_name)
        data_df.coalesce(1).write.mode("overwrite").parquet(output_path)

        # Buscamos el archivo Parquet generado 
        parquet_files = glob.glob(os.path.join(output_path, "*.parquet"))
        if not parquet_files:
            raise Exception("No se encontró ningún archivo Parquet en la ruta de salida.")
        parquet_file = parquet_files[0]
        print("Archivo Parquet generado:", parquet_file)

        with open(parquet_file, "rb") as f: #Esta movida te pilla los archivos en memoria
            parquet_content = f.read()

        # Inicializar el cliente de MinIO usando boto3
        s3_client = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY
        )

        object_key = f"{folder_name}/{folder_name}.parquet"
        s3_client.put_object(Bucket=BUCKET_NAME, Key=object_key, Body=parquet_content)
        print("Archivo subido correctamente a MinIO en:", object_key)

    except Exception as e:
        print("Error:", e)
    finally:
        spark.stop()

if __name__ == "__main__":
    main("WeatherApiProject")