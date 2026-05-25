# network/client.py

"""
Client réseau pour l’affichage distant.
Se connecte automatiquement au serveur juge.
Reçoit les mises à jour de score en temps réel.
"""

import socket
import threading
import json
import time

class DisplayClient:
    def __init__(self, ip: str, port: int, on_update_callback):
        self.ip = ip
        self.port = port
        self.on_update = on_update_callback
        self.running = True

        thread = threading.Thread(target=self._connect_loop, daemon=True)
        thread.start()

    def _connect_loop(self):
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((self.ip, self.port))
                self._listen(sock)
            except Exception:
                time.sleep(1)

    def _listen(self, sock):
        buffer = ""
        while self.running:
            try:
                data = sock.recv(1024).decode("utf-8")
                if not data:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    payload = json.loads(line)
                    self.on_update(payload)
            except Exception:
                break

    def stop(self):
        self.running = False