from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.window import Window
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import LinearRegression
from datetime import timedelta
from pyspark.ml.linalg import Vectors

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
        
        window_spec = Window.partitionBy("city").orderBy("date") #ventana basada en date
        df = df.withColumn("lag_precip_mm", lag("precip_mm", 1).over(window_spec))
        
        df = df.na.drop(subset=["lag_precip_mm", "precip_mm"])

        fecha_corte = "2023-12-31"  # División para especificar el entrenamiento
        train_df = df.filter(col("date") <= lit(fecha_corte))

        assembler = VectorAssembler(
            inputCols=["lag_precip_mm"],
            outputCol="features"
        )
        
        train_data = assembler.transform(train_df)
        
        lr = LinearRegression(featuresCol="features", labelCol="precip_mm") #Entrenamos el modelo de regresión lineal 
        modelo = lr.fit(train_data)

        cities = [row.city for row in df.select("city").distinct().collect()] #Cogemos todas las ciudades
        n_dias = 7
        all_predictions = []

        for city in cities:
            df_city = df.filter(col("city") == city)
            ultimo_registro = df_city.orderBy("date", ascending=False).first()
            if not ultimo_registro:
                continue
            ultima_fecha = ultimo_registro["date"]
            ultima_precip = ultimo_registro["precip_mm"]

            lag_actual = ultima_precip

            for i in range(1, n_dias + 1):
                nueva_fecha = ultima_fecha + timedelta(days=i) #Generamos la fecha futura
                
                features = Vectors.dense([float(lag_actual)]) #convertimos el lag en vector
                features_df = spark.createDataFrame([(features,)], ["features"])
                
                prediccion = modelo.transform(features_df).collect()[0]["prediction"] #Realizamos la predicción
                
                fecha_str = nueva_fecha.strftime("%Y-%m-%d")
                
                all_predictions.append((city, fecha_str, prediccion))
                
                lag_actual = prediccion

        df_futuro = spark.createDataFrame(all_predictions, ["city", "date", "predicted_precip_mm"])
        df_futuro.show(n_dias * len(cities), truncate=False)
        
    except Exception as e:
        print("Error:", e)
    finally:
        spark.stop()

if __name__ == "__main__":
    main("WeatherApiProject")