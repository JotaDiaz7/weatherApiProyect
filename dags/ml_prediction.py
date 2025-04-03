from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.window import Window
from pyspark.ml.feature import VectorAssembler,StandardScaler
from pyspark.ml.regression import LinearRegression
from datetime import timedelta, date, time as dt_time
from utils import set_data_minio, set_data_postgres
import math
from pyspark.ml import Pipeline

def main(name):
    spark = SparkSession.builder.appName(name)\
        .config("spark.jars", "/opt/spark/jars/postgresql-42.2.27.jar")\
        .config("spark.driver.extraClassPath", "/opt/spark/jars/postgresql-42.2.27.jar")\
        .config("spark.executor.extraClassPath", "/opt/spark/jars/postgresql-42.2.27.jar")\
        .getOrCreate()
        
    try:
        df = spark.read  \
            .format("jdbc") \
            .option("url", "jdbc:postgresql://postgres:5432/airflow") \
            .option("dbtable", 'pro_raw_api.daily_weather') \
            .option("user", "airflow") \
            .option("password", "airflow") \
            .load()

        df = df.withColumn("date", to_timestamp(col("date"), "yyyy-MM-dd"))

        columns = ["temperature", "wind_kph", "humidity", "precip_mm"]
        
        window_spec = Window.partitionBy("city").orderBy("date", "time") #ventana basada en city 

        for column in columns:
            df = df.withColumn("lag_" + column, lag(column, 1).over(window_spec))    

        #Representamos la hora de forma cíclica
        df = df.withColumn("hour", hour(col("time")))
        df = df.withColumn("sin_hour", sin(col("hour") * (2 * math.pi / 24)))
        df = df.withColumn("cos_hour", cos(col("hour") * (2 * math.pi / 24)))
        
        # Eliminar filas con valores nulos en las columnas necesarias
        for column in columns:
            df = df.na.drop(subset=["lag_" + column, column, "sin_hour", "cos_hour"])

        fecha_corte = "2023-12-31"  # División para especificar el entrenamiento

        cities = [row.city for row in df.select("city").distinct().collect()] #Cogemos todas las ciudades
        hours = [row.time for row in df.select("time").distinct().collect()]
        n_dias = 1
        all_predictions = []
        ultima_fecha = date.today()

        for column in columns:
            lag_col = "lag_"+column
            #Filtramos los datos para el entrenamiento
            train = df.filter(col("date") <= lit(fecha_corte))
            
            vector = VectorAssembler(#Combina los datos de las columnas en un vector
                inputCols=[lag_col, "sin_hour", "cos_hour"], 
                outputCol="features_unscaled"
            )
            # Escalar las características para que tengan una media cero y varianza uno
            scaler = StandardScaler(inputCol="features_unscaled", outputCol="features")
            
            lr = LinearRegression(featuresCol="features", labelCol=column)#Predice los datos finales mediante los vectores escalados
            pipeline = Pipeline(stages=[vector, scaler, lr])#Encadena todas las etapas
            model = pipeline.fit(train)#Entrena al modelo

            for city in cities:
                df_city = df.filter(col("city") == city)
                last_data = df_city.orderBy("date", ascending=False).first()
                if not last_data:
                    continue
                lag_actual = last_data[column]

                for i in range(1, n_dias + 1):
                    nueva_fecha = date.today() + timedelta(days=i) 
                    fecha_str = nueva_fecha.strftime("%Y-%m-%d")

                    for fh in hours:
                        hour_int = int(fh.split(":")[0])
                        sin_hour_val = math.sin(hour_int * (2 * math.pi / 24))
                        cos_hour_val = math.cos(hour_int * (2 * math.pi / 24))
                                                
                        features_df = spark.createDataFrame(
                            [(float(lag_actual), sin_hour_val, cos_hour_val)], 
                            [lag_col, "sin_hour", "cos_hour"]
                        )
                        
                        prediction = model.transform(features_df).collect()[0]["prediction"]
                        
                        time_str = dt_time(hour=hour_int).strftime("%H:%M:%S")
                        
                        all_predictions.append((city, fecha_str, time_str, column, prediction))
                        
                        lag_actual = prediction

        df_futuro = spark.createDataFrame(all_predictions, ["city", "date", "time", "target", "prediction"])
        df_futuro = df_futuro.groupBy("city", "date", "time").pivot("target").agg({"prediction": "first"}).orderBy("city","time")
        df_futuro.show(truncate=False)

        set_data_minio(df_futuro, 'forecast', '', '')
        set_data_postgres(df_futuro, 'forecast')

    except Exception as e:
        print("Error:", e)
    finally:
        spark.stop()

if __name__ == "__main__":
    main("WeatherApiProject")