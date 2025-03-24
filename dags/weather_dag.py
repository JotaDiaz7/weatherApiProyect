from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='daily_weather_etl',
    default_args=default_args,
    description='Ejecuta el script main.py una vez al día',
    schedule_interval='0 9 * * *',  # Ejecutar todos los días a las 9 a.m.
    start_date=datetime(2025, 3, 21),
    catchup=False,
    tags=['weather'],
) as dag:

    run_script = BashOperator(
        task_id='run_weather_script',
        bash_command='python /opt/airflow/dags/main.py',
    )

    run_script_2 = BashOperator(
        task_id='run_bbdd_script',
        bash_command='python /opt/airflow/dags/main_bbdd.py',
    )

    run_script >> run_script_2