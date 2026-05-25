# network/server.py

"""
Serveur réseau pour l’affichage distant.
Le poste juge agit comme serveur TCP.
Envoie les mises à jour de score à chaque changement.
"""

import socket
import threading
import json

class DisplayServer:
    def __init__(self, ip="0.0.0.0", port=5000):
        self.ip = ip
        self.port = port
        self.clients = []
        self.running = True

        thread = threading.Thread(target=self._listen, daemon=True)
        thread.start()

    def _listen(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.ip, self.port))
        server.listen(1)

        while self.running:
            try:
                client, _ = server.accept()
                self.clients.append(client)
            except Exception:
                continue

    def broadcast(self, data: dict):
        """Envoie un dictionnaire JSON à tous les clients connectés."""
        message = (json.dumps(data) + "\n").encode("utf-8")
        for c in self.clients[:]:
            try:
                c.sendall(message)
            except Exception:
                self.clients.remove(c)

    def stop(self):
        self.running = False
