import os
import tempfile
import glob
import boto3
from pyspark.sql.functions import *
from datetime import *
import requests
from pyspark.ml.evaluation import RegressionEvaluator

def connect_minio():
    MINIO_ENDPOINT = "http://minio:9000"
    ACCESS_KEY = "admin"
    SECRET_KEY = "admin123"

    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY
    )

    return s3

def set_data_minio(df, bucket, latitude, longitude):
    connect_minio()

    #Vamos a crear el nombre de la carpeta que va a contener nuestro archivo parquet
    city, date = df.select(lower("city"), "local_time").first()
    date = date.date()
    if bucket != "historicalweather":
        folder_name = f"{date}"
    else:
        city = city.replace(" ", "_")
        latitude = str(latitude).replace(".", "_")
        longitude = str(longitude).replace(".", "_").replace("-", "")
        folder_name = f"{city}__{latitude}__{longitude}"
    print("Nombre de la carpeta:", folder_name)

    temp_dir = tempfile.mkdtemp() # Esto lo que te hace es crear un directorio en memoria para no generarlo en local 
    output_path = os.path.join(temp_dir, folder_name)
    df.coalesce(1).write.mode("overwrite").parquet(output_path)

    # Buscamos el archivo Parquet generado 
    parquet_files = glob.glob(os.path.join(output_path, "*.parquet"))
    if not parquet_files:
        raise Exception("No se encontró ningún archivo Parquet en la ruta de salida.")
    parquet_file = parquet_files[0]
    print("Archivo Parquet generado:", parquet_file)

    with open(parquet_file, "rb") as f: #Esta movida te pilla los archivos en memoria
        parquet_content = f.read()

    # Inicializar el cliente de MinIO usando boto3
    s3 = connect_minio()

    object_key = f"{folder_name}/{folder_name}.parquet"
    s3.put_object(Bucket=bucket, Key=object_key, Body=parquet_content)
    print("Archivo subido correctamente a MinIO en:", object_key)

def set_data_postgres(df, table):
    df.write \
        .format("jdbc") \
        .option("url", "jdbc:postgresql://postgres:5432/airflow") \
        .option("dbtable", f"pro_raw_api.{table}") \
        .option("user", "airflow") \
        .option("password", "airflow") \
        .option("driver", "org.postgresql.Driver") \
        .mode("append") \
        .save()

    print("Datos registrados correctamente en la bbdd")

def set_df_last_records(city, spark, latitude, longitude): 
    start_date = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")

    df = df_data(2, spark, city, latitude, longitude, start_date)

    return df

def get_cities_minio():
    s3 = connect_minio()
    bucket_name = 'historicalweather'
    
    # Usamos Delimiter para obtener solo el primer nivel de "carpetas"
    response = s3.list_objects_v2(Bucket=bucket_name, Delimiter='/')
    cities = []
    if 'CommonPrefixes' in response:
        folders = [prefix['Prefix'] for prefix in response['CommonPrefixes']]
        cities = [
            {
                "city": parts[0].replace("_", " "),
                "lat": str(parts[1]).replace("_", "."),
                "long": -float(str(parts[2]).replace("_", ".").replace("/",""))
            }
            for parts in (f.split("__") for f in folders)
        ]

    return cities

def check_city_minio(city):
    cities = get_cities_minio() 
    return city.lower() in (c.get("city", "").lower() for c in cities) 

def df_data(days, spark, city, latitude, longitude, start_date):
    url = "https://archive-api.open-meteo.com/v1/archive"
    current_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    params = {
        "latitude": latitude,            
        "longitude": longitude,           
        "start_date": start_date,     
        "end_date": current_date,       
        "hourly": "temperature_2m,relativehumidity_2m,windspeed_10m,precipitation,weathercode",
        "timezone": "Europe/Madrid"  
    }

    response = requests.get(url, params=params)
    data = response.json()
    
    hourly = data["hourly"]
    
    # Construir una lista de diccionarios, cada uno representando un registro
    records = [
        {
            "local_time": t,            
            "temperature": temp,
            "humidity": rhum,
            "wind_kph": wspd,
            "precip_mm": precip,
            "text": text
        }
        for t, temp, rhum, wspd, precip, text in zip(
            hourly["time"],
            hourly["temperature_2m"],
            hourly["relativehumidity_2m"],
            hourly["windspeed_10m"],
            hourly["precipitation"],
            hourly["weathercode"]
        )
    ]
    
    # Crear el DataFrame a partir de la lista de registros
    df = spark.createDataFrame(records)
    
    icon_mapping = {
        0: "Sunny",
        1: "Mostly Clear",
        2: "Partly Cloudy",
        3: "Cloudy",
        45: "Fog",
        48: "Freezing Fog",
        51: "Light Drizzle",
        53: "Moderate Drizzle",
        55: "Dense Drizzle",
        56: "Freezing Drizzle",
        57: "Freezing Drizzle",
        61: "Light Rain",
        63: "Moderate Rain",
        65: "Heavy Rain",
        66: "Freezing Rain",
        67: "Freezing Rain",
        71: "Light Snow",
        73: "Moderate Snow",
        75: "Heavy Snow",
        77: "Snow Grains",
        80: "Rain Showers",
        81: "Moderate Rain Showers",
        82: "Violent Rain Showers",
        85: "Snow Showers",
        86: "Heavy Snow Showers",
        95: "Thunderstorm",
        96: "Thunderstorm with Hail",
        99: "Thunderstorm with Hail"
    }
        
    def map_to_description(weathercode):
        return icon_mapping[weathercode]
    
    # Registrar la UDF
    map_to_description = udf(map_to_description, StringType())
    
    df = df.filter(col("local_time").endswith("04:00")
                    | col("local_time").endswith("09:00") | col("local_time").endswith("15:00") 
                    | col("local_time").endswith("22:00")) \
        .withColumn("city", lit(city)) \
        .withColumn("feelslike", col("temperature")) \
        .withColumn("text", map_to_description(col("text"))) \
        .select(
            col("city"),
            to_timestamp(regexp_replace(col("local_time"), "T", " "), "yyyy-MM-dd HH:mm").alias("local_time"),
            col("temperature"),
            col("wind_kph"),
            col("humidity"),
            col("feelslike"),
            col("precip_mm"),
            col("text")
        ).orderBy("local_time")
    
    # Mostrar el DataFrame
    df.show(truncate=False)

    return df

def create_historical(spark, city, latitude, longitude):
    bucket = 'historicalweather'
    start_date = '2021-01-01'

    df = df_data(3, spark, city, latitude, longitude, start_date)

    set_data_minio(df, bucket, latitude, longitude)
    set_data_postgres(df, "daily_weather")

#Función para calcular los parámetros de fiabilidad de nuestro modelo
def param_reliability(model, train, column):
    try:
        # ---------------------------
        # Cálculo de parámetros de fiabilidad
        # ---------------------------
        # Evaluación sobre el conjunto de entrenamiento (puedes sustituir o complementar con un conjunto de validación)
        train_predictions = model.transform(train)
        evaluator_rmse = RegressionEvaluator(labelCol=column, predictionCol="prediction", metricName="rmse")
        evaluator_mae = RegressionEvaluator(labelCol=column, predictionCol="prediction", metricName="mae")
        rmse = evaluator_rmse.evaluate(train_predictions)
        mae = evaluator_mae.evaluate(train_predictions)
        print(f"Prarámetros de fiabilidad de {column}: RMSE = {rmse}, MAE = {mae}")
        
        # Calcular el valor máximo de la variable en el conjunto de entrenamiento
        max_value = train.agg({column: "max"}).first()[0]
        
        if max_value != 0:
            rmse_error_margin = (rmse / max_value) * 100
            mae_error_margin = (mae / max_value) * 100
            rmse_accuracy = 100 - rmse_error_margin
            mae_accuracy = 100 - mae_error_margin
            print(f"  Margen de error (RMSE): {rmse_error_margin:.2f} %")
            print(f"  Acierto (100 - RMSE error margin): {rmse_accuracy:.2f} %")
            print(f"  Margen de error (MAE): {mae_error_margin:.2f} %")
            print(f"  Acierto (100 - MAE error margin): {mae_accuracy:.2f} %")
        else:
            print(f"El valor máximo de {column} es 0, lo que impide calcular el margen de error porcentual.")
    except Exception as e:
        print(f"  No se pudo extraer el resumen del modelo para {column}: {e}")
