# monitoring/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

from channels.generic.websocket import WebsocketConsumer
import paramiko
import threading

from monitoring.models import EquipementReseau

class SSHConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()

        equipement_id = self.scope["url_route"]["kwargs"]["equipement_id"]
        equipement = EquipementReseau.objects.get(id=equipement_id)

        try:
            if not equipement.utilisateur_ssh or not equipement.mot_de_passe_ssh:
                self.send(text_data="❌ Erreur : Identifiants SSH manquants pour cet équipement.\r\n")
                self.close()
                return

            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(
                hostname=equipement.adresse_ip,
                username=equipement.utilisateur_ssh,
                password=equipement.mot_de_passe_ssh,
                port=equipement.port_ssh,
                timeout=10
            )

            # 🔥 PSEUDO TERMINAL
            self.channel = self.ssh.invoke_shell(term="xterm")
            
            # Thread lecture SSH → navigateur
            threading.Thread(target=self.read_ssh, daemon=True).start()
            
        except Exception as e:
            self.send(text_data=f"❌ Échec de la connexion SSH : {str(e)}\r\n")
            self.close()

    def receive(self, text_data):
        self.channel.send(text_data)

    def read_ssh(self):
        while True:
            data = self.channel.recv(1024)
            if not data:
                break
            self.send(text_data=data.decode(errors="ignore"))

    def disconnect(self, close_code):
        try:
            self.channel.close()
            self.ssh.close()
        except:
            pass