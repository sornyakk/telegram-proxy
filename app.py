import os
import requests
from flask import Flask, request, Response

app = Flask(__name__)

@app.route('/')
def home():
    return 'Proxy is running'

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD'])
def proxy(path):
    try:
        url = request.url
        
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        response = requests.request(
            method=request.method,
            url=url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=60
        )
        
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(name, value) for name, value in response.raw.headers.items()
                           if name.lower() not in excluded_headers]
        
        return Response(response.content, response.status_code, response_headers)
    
    except Exception as e:
        return f"Proxy error: {e}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
