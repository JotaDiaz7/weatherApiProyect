import os
import tempfile
import glob
import boto3
from pyspark.sql.functions import *
from datetime import *
import requests
from config import API_KEY

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

def set_data_minio(df, bucket):
    connect_minio()

    #Vamos a crear el nombre de la carpeta que va a contener nuestro archivo parquet
    city, localtime = df.select(lower("city"), "local_time").first()
    if bucket == "dailyweather":
        localtime = localtime.replace("04:00", "")
        folder_name = f"{localtime}"
    else:
        city = city.replace(" ", "_")
        folder_name = f"{city}_last_2_years"
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

def set_data_postgres(df):
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

def set_df_last_records(city, spark): 
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    url = "http://api.weatherapi.com/v1/history.json"

    params = {
        "key": API_KEY,
        "q": city,
        "dt": yesterday
    }

    response = requests.get(url, params=params)
    data = response.json()

    # Definir las horas deseadas
    desired_hours = ["04:00", "09:00", "15:00", "22:00"]

    # Filtramos la lista para obtener sólo los registros cuya hora final coincide con alguna de las deseadas
    hourly = [
        record
        for forecast_day in data["forecast"]["forecastday"]
        for record in forecast_day["hour"]
        if any(record["time"].endswith(hour) for hour in desired_hours)
    ]

    df = spark.createDataFrame(hourly)

    df = df.select(
        date_format(col("time"), "yyyy-MM-dd HH:mm").alias("local_time"),
        col("temp_c").alias("temperature"),
        col("wind_kph"),
        col("humidity"),
        col("feelslike_c").alias("feelslike"),
        col("precip_mm"),
        col("condition.text").alias("text"),
        col("condition.icon").alias("icon")
    )

    # Crear un DataFrame para la información de ubicación (por ejemplo, la ciudad)
    df_location = spark.createDataFrame([data["location"]]).select(
        lower(col("name")).alias("city")
    )

    # Realizar un cross join para añadir la ciudad a cada registro horario
    df = df_location.crossJoin(df)

    return df

def get_cities_minio():
    s3 = connect_minio()
    bucket_name = 'historicalweather'
    
    # Usamos Delimiter para obtener solo el primer nivel de "carpetas"
    response = s3.list_objects_v2(Bucket=bucket_name, Delimiter='/')
    cities = []
    if 'CommonPrefixes' in response:
        folders = [prefix['Prefix'] for prefix in response['CommonPrefixes']]
        cities = [folder.replace("_last_2_years/", "").replace("_", " ") for folder in folders]

    return cities

def check_city_minio(city):
    cities = get_cities_minio() 
    return city.lower() in cities

def create_historical(spark, city, latitude, longitude):
    bucket = 'historicalweather'
    url = "https://archive-api.open-meteo.com/v1/archive"
    current_date = (date.today() - timedelta(days=2)).strftime("%Y-%m-%d")
    params = {
        "latitude": latitude,            
        "longitude": longitude,           
        "start_date": "2021-01-01",     
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
            "icon": icon
        }
        for t, temp, rhum, wspd, precip, icon in zip(
            hourly["time"],
            hourly["temperature_2m"],
            hourly["relativehumidity_2m"],
            hourly["windspeed_10m"],
            hourly["precipitation"],
            hourly["weathercode"],
        )
    ]
    
    # Crear el DataFrame a partir de la lista de registros
    df = spark.createDataFrame(records)
    
    icon_mapping = {
        0: {"icon": "113", "description": "Sunny"},
        1: {"icon": "116", "description": "Mostly Clear"},
        2: {"icon": "116", "description": "Partly Cloudy"},
        3: {"icon": "119", "description": "Cloudy"},
        45: {"icon": "143", "description": "Fog"},
        48: {"icon": "143", "description": "Freezing Fog"},
        51: {"icon": "176", "description": "Light Drizzle"},
        53: {"icon": "176", "description": "Moderate Drizzle"},
        55: {"icon": "176", "description": "Dense Drizzle"},
        56: {"icon": "176", "description": "Freezing Drizzle"},
        57: {"icon": "176", "description": "Freezing Drizzle"},
        61: {"icon": "293", "description": "Light Rain"},
        63: {"icon": "296", "description": "Moderate Rain"},
        65: {"icon": "299", "description": "Heavy Rain"},
        66: {"icon": "308", "description": "Freezing Rain"},
        67: {"icon": "308", "description": "Freezing Rain"},
        71: {"icon": "320", "description": "Light Snow"},
        73: {"icon": "323", "description": "Moderate Snow"},
        75: {"icon": "326", "description": "Heavy Snow"},
        77: {"icon": "326", "description": "Snow Grains"},
        80: {"icon": "308", "description": "Rain Showers"},
        81: {"icon": "308", "description": "Moderate Rain Showers"},
        82: {"icon": "308", "description": "Violent Rain Showers"},
        85: {"icon": "320", "description": "Snow Showers"},
        86: {"icon": "320", "description": "Heavy Snow Showers"},
        95: {"icon": "200", "description": "Thunderstorm"},
        96: {"icon": "200", "description": "Thunderstorm with Hail"},
        99: {"icon": "200", "description": "Thunderstorm with Hail"}
    }
    
    # Función para mapear el weathercode a la URL del icono de WeatherAPI
    def map_to_icon_url(weathercode):
        return f"//cdn.weatherapi.com/weather/64x64/day/{icon_mapping[weathercode]['icon']}.png"
        
    def map_to_description(weathercode):
        return icon_mapping[weathercode]['description']
    
    # Registrar la UDF
    map_to_icon_url_udf = udf(map_to_icon_url, StringType())
    map_to_description = udf(map_to_description, StringType())
    
    df = df.filter(
            col("local_time").endswith("04:00") |
            col("local_time").endswith("09:00") |
            col("local_time").endswith("15:00") |
            col("local_time").endswith("22:00")
        ) \
        .withColumn("city", lit(city)) \
        .withColumn("feelslike", col("temperature")) \
        .withColumn("text", map_to_description(col("icon"))) \
        .withColumn("icon", map_to_icon_url_udf(col("icon"))) \
        .select(
            col("city"),
            regexp_replace(col("local_time"), "T", " ").alias("local_time"),
            col("temperature"),
            col("wind_kph"),
            col("humidity"),
            col("feelslike"),
            col("precip_mm"),
            col("text"),
            col("icon")
        ).orderBy("local_time")
    
    # Mostrar el DataFrame
    df.show(truncate=False)

    # last_reports = set_df_last_records(city, spark)

    # df = data.union(last_reports)

    set_data_minio(df, bucket)
    set_data_postgres(df)
