FROM python:3.9
WORKDIR /app
COPY foodgram/requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "foodgram.foodgram.wsgi"]