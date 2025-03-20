FROM python:3.9

# Instalar Java 17 correctamente
RUN apt-get update && apt-get install -y openjdk-17-jdk curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Configurar JAVA_HOME correctamente
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Instalar dependencias Python
RUN pip install databricks-cli boto3 pyspark jupyter requests

# Instalar MinIO Client (mc)
RUN curl -O https://dl.min.io/client/mc/release/linux-amd64/mc && \
    chmod +x mc && mv mc /usr/local/bin/mc

# Exponer puerto Jupyter Notebook
EXPOSE 8888

# Carpeta de trabajo
WORKDIR /workspace

# Comando para ejecutar Jupyter Notebook
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]

