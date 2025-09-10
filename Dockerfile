FROM python:3.11.6-bullseye

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /sanic

COPY requirements.txt requirements.txt

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

RUN python -m spacy download en_core_web_sm

COPY . .

CMD ["python3", "start.py"]

