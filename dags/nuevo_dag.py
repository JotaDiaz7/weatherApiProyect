from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
from pyspark.sql import SparkSession

def test_spark():
    spark = SparkSession.builder.appName("AirflowSparkTest").getOrCreate()
    df = spark.createDataFrame([("Hola",), ("desde",), ("Airflow",)], ["palabra"])
    df.show()
    spark.stop()

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 1, 1),
    'retries': 0,
}

with DAG(
    dag_id='test_pyspark_dag',
    default_args=default_args,
    schedule_interval=None,  # solo manual
    catchup=False,
    tags=['test'],
) as dag:
    
    run_spark = PythonOperator(
        task_id='run_spark_task',
        python_callable=test_spark,
    )