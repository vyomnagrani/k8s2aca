from flask import Flask, render_template_string
import os
import socket
import psutil
import requests

app = Flask(__name__)

@app.route('/')
def index():
    # Get system memory
    memory = psutil.virtual_memory()
    total_memory = f"{memory.total / (1024 ** 3):.2f} GB"
    used_memory = f"{memory.used / (1024 ** 3):.2f} GB"
    free_memory = f"{memory.available / (1024 ** 3):.2f} GB"

    # Get hostname
    hostname = socket.gethostname()

    # Get public IP
    try:
        public_ip = requests.get('https://api.ipify.org').text
    except requests.RequestException:
        public_ip = "Unable to fetch public IP"

    # HTML template
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>System Info</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 50px;
                background-color: #f4f4f9;
                color: #333;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background: #fff;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            h1 {
                color: #4CAF50;
            }
            .info {
                margin: 20px 0;
                font-size: 1.2em;
            }
            .info span {
                font-weight: bold;
                color: #333;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>System Information</h1>
            <div class="info">Hostname: <span>{{ hostname }}</span></div>
            <div class="info">Public IP: <span>{{ public_ip }}</span></div>
            <div class="info">Memory: <span>{{ used_memory }}</span> used / <span>{{ total_memory }}</span> total</div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, hostname=hostname, public_ip=public_ip, total_memory=total_memory, used_memory=used_memory)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)