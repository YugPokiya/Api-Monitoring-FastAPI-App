from flask import Flask
from prometheus_client import start_http_server, Counter

app = Flask(__name__)
request_counter = Counter('app_request_total', 'Total requests to the app')

@app.route('/')
def home():
    request_counter.inc()
    return "Hello Prometheus!"

if __name__ == "__main__":
    start_http_server(8000)
    app.run(port=5000)