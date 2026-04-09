#!/usr/bin/env python3
"""
Telegram Proxy Server - App for Render
Phiên bản đơn giản để deploy trên Render
"""

import os
import socket
import threading
import time
import logging
from flask import Flask, render_template, jsonify
import requests

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class SimpleProxy:
    def __init__(self, host='0.0.0.0', port=None):
        self.host = host
        # Sử dụng port từ environment variable hoặc default
        self.port = port or int(os.environ.get('PROXY_PORT', 10000))
        self.running = False
        self.server_socket = None
        self.connections = []
        self.start_time = 0
        
    def start(self):
        """Khởi động proxy server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(100)
            
            self.running = True
            self.start_time = time.time()
            logger.info(f"Proxy server đang chạy trên {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    logger.info(f"Kết nối mới từ {client_address}")
                    
                    # Tạo thread mới cho mỗi kết nối
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                    self.connections.append(client_socket)
                    
                except Exception as e:
                    if self.running:
                        logger.error(f"Lỗi khi chấp nhận kết nối: {e}")
                        
        except Exception as e:
            logger.error(f"Lỗi khi khởi động proxy server: {e}")
    
    def handle_client(self, client_socket, client_address):
        """Xử lý kết nối từ client"""
        try:
            # Đọc request từ client
            request_data = client_socket.recv(4096)
            if not request_data:
                return
            
            # Parse HTTP request
            request_lines = request_data.decode('utf-8', errors='ignore').split('\n')
            if not request_lines:
                return
            
            first_line = request_lines[0]
            if not first_line.startswith(('GET', 'POST', 'CONNECT')):
                return
            
            method, url, version = first_line.split(' ', 2)
            
            if method == 'CONNECT':
                # HTTPS tunneling
                self.handle_https_tunnel(client_socket, url)
            else:
                # HTTP proxy
                self.handle_http_proxy(client_socket, request_data)
                
        except Exception as e:
            logger.error(f"Lỗi khi xử lý client {client_address}: {e}")
        finally:
            try:
                client_socket.close()
                if client_socket in self.connections:
                    self.connections.remove(client_socket)
            except:
                pass
    
    def handle_https_tunnel(self, client_socket, target):
        """Xử lý HTTPS tunneling"""
        try:
            host, port = target.split(':')
            port = int(port)
            
            # Kết nối đến target server
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.connect((host, port))
            
            # Gửi "Connection established" cho client
            client_socket.send(b'HTTP/1.1 200 Connection established\r\n\r\n')
            
            # Tạo tunnel giữa client và target
            self.create_tunnel(client_socket, target_socket)
            
        except Exception as e:
            logger.error(f"Lỗi HTTPS tunnel: {e}")
            try:
                client_socket.send(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
            except:
                pass
    
    def handle_http_proxy(self, client_socket, request_data):
        """Xử lý HTTP proxy"""
        try:
            # Parse request để lấy target URL
            request_lines = request_data.decode('utf-8', errors='ignore').split('\n')
            first_line = request_lines[0]
            method, url, version = first_line.split(' ', 2)
            
            # Tìm Host header
            host = None
            for line in request_lines:
                if line.lower().startswith('host:'):
                    host = line.split(':', 1)[1].strip()
                    break
            
            if not host:
                client_socket.send(b'HTTP/1.1 400 Bad Request\r\n\r\n')
                return
            
            # Kết nối đến target server
            target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_socket.connect((host, 80))
            
            # Gửi request đến target
            target_socket.send(request_data)
            
            # Nhận response và gửi về client
            while True:
                response_data = target_socket.recv(4096)
                if not response_data:
                    break
                client_socket.send(response_data)
                
        except Exception as e:
            logger.error(f"Lỗi HTTP proxy: {e}")
            try:
                client_socket.send(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
            except:
                pass
    
    def create_tunnel(self, client_socket, target_socket):
        """Tạo tunnel giữa client và target"""
        def forward_data(src, dst):
            try:
                while True:
                    data = src.recv(4096)
                    if not data:
                        break
                    dst.send(data)
            except:
                pass
            finally:
                try:
                    src.close()
                    dst.close()
                except:
                    pass
        
        # Tạo 2 thread để forward data
        t1 = threading.Thread(target=forward_data, args=(client_socket, target_socket))
        t2 = threading.Thread(target=forward_data, args=(target_socket, client_socket))
        
        t1.daemon = True
        t2.daemon = True
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
    
    def stop(self):
        """Dừng proxy server"""
        self.running = False
        
        # Đóng tất cả kết nối
        for conn in self.connections:
            try:
                conn.close()
            except:
                pass
        self.connections.clear()
        
        # Đóng server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        logger.info("Proxy server đã dừng")

# Khởi tạo proxy server
proxy = SimpleProxy()

# Khởi động proxy server trong thread riêng
def start_proxy():
    proxy.start()

proxy_thread = threading.Thread(target=start_proxy)
proxy_thread.daemon = True
proxy_thread.start()

# Flask routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def status():
    return jsonify({
        'status': 'running' if proxy.running else 'stopped',
        'connections': len(proxy.connections),
        'uptime': time.time() - proxy.start_time if proxy.start_time > 0 else 0
    })

@app.route('/test_telegram')
def test_telegram():
    try:
        # Test kết nối đến Telegram
        response = requests.get('https://api.telegram.org/bot123456789:ABCdefGHIjklMNOpqrsTUVwxyz/getMe', 
                             timeout=10)
        return jsonify({
            'success': True,
            'status_code': response.status_code,
            'message': 'Kết nối Telegram thành công'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Không thể kết nối đến Telegram'
        })

if __name__ == '__main__':
    # Lấy port từ environment variable (Render)
    port = int(os.environ.get('PORT', 5000))
    
    # Khởi động Flask app
    app.run(host='0.0.0.0', port=port, debug=False)
    
    # Log thông tin proxy
    logger.info(f"Web interface running on port {port}")
    logger.info(f"Proxy server running on port {proxy.port}")
