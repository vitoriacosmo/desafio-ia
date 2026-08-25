FROM python:3.11-slim

WORKDIR /app

# Otimizacoes para execucao Python em container
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalacao das dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia do codigo do projeto
COPY . .

# Comando padrao de execucao da esteira
CMD ["python", "nivel_1/analise_dados.py"]
