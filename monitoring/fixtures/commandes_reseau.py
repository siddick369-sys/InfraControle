from monitoring.models import CommandeAutomatique
from django.contrib.auth.models import User

# Facultatif : associe à l’admin s’il existe
admin = User.objects.filter(is_superuser=True).first()

commandes = [
    # === Configuration réseau de base ===
    ("Configurer adresse IP statique", "Définit une adresse IP fixe sur Ubuntu", """
sudo bash -c 'echo "network:
  version: 2
  renderer: networkd
  ethernets:
    ens33:
      dhcp4: no
      addresses: [192.168.1.10/24]
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]" > /etc/netplan/01-netcfg.yaml'
sudo netplan apply
"""),

    ("Activer DHCP", "Installe et active le serveur DHCP", """
sudo apt install isc-dhcp-server -y
sudo systemctl enable isc-dhcp-server
sudo systemctl restart isc-dhcp-server
"""),

    ("Configurer DHCP", "Configure les baux IP DHCP", """
sudo bash -c 'echo "
subnet 192.168.1.0 netmask 255.255.255.0 {
  range 192.168.1.100 192.168.1.200;
  option routers 192.168.1.1;
  option domain-name-servers 8.8.8.8;
}" > /etc/dhcp/dhcpd.conf'
sudo systemctl restart isc-dhcp-server
"""),

    ("Installer et activer OpenVPN serveur", "Configure un serveur VPN basique", """
sudo apt install openvpn easy-rsa -y
make-cadir ~/openvpn-ca
cd ~/openvpn-ca
./easyrsa init-pki
./easyrsa build-ca nopass
"""),

    ("Configurer NAT (partage Internet)", "Active le routage et le NAT", """
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
sudo apt install iptables-persistent -y
"""),

    # === Sécurité et pare-feu ===
    ("Installer UFW", "Installe le pare-feu UFW", """
sudo apt install ufw -y
sudo ufw enable
sudo ufw allow OpenSSH
"""),

    ("Autoriser HTTP/HTTPS", "Ouvre les ports web", """
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
"""),

    ("Bloquer tout trafic entrant sauf SSH", "Renforce la sécurité", """
sudo ufw default deny incoming
sudo ufw allow 22/tcp
sudo ufw reload
"""),

    ("Afficher règles pare-feu", "Liste toutes les règles UFW", "sudo ufw status verbose"),

    ("Installer Fail2Ban", "Protège contre les tentatives SSH abusives", """
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
"""),

    # === Supervision & outils réseau ===
    ("Installer Netdata", "Outil de monitoring complet", """
bash <(curl -Ss https://my-netdata.io/kickstart.sh)
"""),

    ("Installer Nmon", "Surveillance CPU/RAM/Disque", "sudo apt install nmon -y"),

    ("Installer IPerf3", "Test de performance réseau", "sudo apt install iperf3 -y"),

    ("Installer Htop", "Visualisation des processus", "sudo apt install htop -y"),

    ("Installer et activer SNMP", "Supervision via SNMP", """
sudo apt install snmpd -y
sudo systemctl enable snmpd
sudo systemctl start snmpd
"""),

    ("Configurer SNMP v2", "Ajoute la communauté publique SNMP", """
sudo bash -c 'echo "rocommunity public" >> /etc/snmp/snmpd.conf'
sudo systemctl restart snmpd
"""),

    ("Vérifier connectivité Internet", "Ping Google DNS", "ping -c 4 8.8.8.8"),

    ("Tracer la route réseau", "Affiche le chemin réseau vers 8.8.8.8", "traceroute 8.8.8.8"),

    # === Services & DNS ===
    ("Installer Bind9", "Installe un serveur DNS interne", """
sudo apt install bind9 bind9utils -y
sudo systemctl enable bind9
sudo systemctl start bind9
"""),

    ("Redémarrer le serveur DNS", "Redémarre Bind9", "sudo systemctl restart bind9"),

    ("Vérifier résolveur DNS", "Test du DNS avec dig", "dig google.com"),

    # === Serveurs applicatifs ===
    ("Installer Apache2", "Serveur web HTTP", """
sudo apt install apache2 -y
sudo systemctl enable apache2
sudo systemctl start apache2
"""),

    ("Installer Nginx", "Serveur web alternatif", """
sudo apt install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
"""),

    ("Installer MariaDB", "Base de données MySQL", """
sudo apt install mariadb-server -y
sudo systemctl enable mariadb
sudo systemctl start mariadb
"""),

    ("Installer PHP", "Support PHP pour Apache/Nginx", "sudo apt install php php-mysql libapache2-mod-php -y"),

    ("Installer Git", "Contrôle de version", "sudo apt install git -y"),

    ("Installer Docker", "Conteneurisation des services", """
sudo apt install apt-transport-https ca-certificates curl gnupg-agent software-properties-common -y
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io -y
"""),

    ("Installer Kubernetes (kubectl + minikube)", "Cluster de conteneurs local", """
sudo apt install curl apt-transport-https -y
curl -LO "https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64"
sudo install minikube-linux-amd64 /usr/local/bin/minikube
curl -LO "https://dl.k8s.io/release/v1.28.0/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/
"""),

    # === Supervision système ===
    ("Afficher charge CPU", "Affiche la charge moyenne du CPU", "uptime"),

    ("Afficher utilisation mémoire", "Montre la mémoire utilisée", "free -h"),

    ("Afficher espace disque", "Montre les partitions", "df -h"),

    ("Lister interfaces réseau", "Affiche toutes les interfaces actives", "ip link show"),

    ("Redémarrer serveur", "Redémarre la machine proprement", "sudo reboot"),

    ("Arrêter serveur", "Éteint la machine", "sudo shutdown now"),

    ("Mettre à jour le système", "Met à jour tous les paquets", """
sudo apt update
sudo apt upgrade -y
"""),

    ("Supprimer paquets inutiles", "Nettoyage du système", "sudo apt autoremove -y"),

    ("Afficher services actifs", "Liste les services actifs", "systemctl list-units --type=service --state=running"),

    ("Lister utilisateurs système", "Affiche la liste des utilisateurs Linux", "cut -d: -f1 /etc/passwd"),

    ("Ajouter un nouvel utilisateur", "Ajoute un compte utilisateur", "sudo adduser <nom_utilisateur>"),

    ("Modifier le mot de passe utilisateur", "Change le mot de passe d’un utilisateur", "sudo passwd <nom_utilisateur>"),

    ("Supprimer un utilisateur", "Supprime un utilisateur Linux", "sudo deluser <nom_utilisateur>"),

    ("Installer Samba", "Partage de fichiers Windows/Linux", """
sudo apt install samba -y
sudo systemctl enable smbd
sudo systemctl start smbd
"""),

    ("Installer FTP (vsftpd)", "Serveur FTP standard", """
sudo apt install vsftpd -y
sudo systemctl enable vsftpd
sudo systemctl start vsftpd
"""),

    ("Configurer FTP anonyme", "Active les connexions FTP anonymes", """
sudo sed -i 's/anonymous_enable=NO/anonymous_enable=YES/' /etc/vsftpd.conf
sudo systemctl restart vsftpd
"""),

    ("Installer OpenSSH", "Installe et démarre SSH", """
sudo apt install openssh-server -y
sudo systemctl enable ssh
sudo systemctl start ssh
"""),

    ("Afficher IP publique", "Récupère l’adresse IP externe", "curl ifconfig.me"),

    ("Scanner ports ouverts", "Analyse rapide avec netstat", "sudo netstat -tuln"),

    ("Installer Nmap", "Scanner réseau puissant", "sudo apt install nmap -y"),

    ("Scanner un hôte local", "Exemple de scan d’un hôte", "nmap 192.168.1.1"),
]

for nom, desc, contenu in commandes:
    CommandeAutomatique.objects.get_or_create(
        nom=nom,
        defaults={
            'description': desc,
            'contenu': contenu,
            'cree_par': admin
        }
    )

print("✅ 50 commandes réseau ajoutées avec succès !")



# python manage.py shell < monitoring/fixtures/commandes_reseau.py