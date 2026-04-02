from django.core.management.base import BaseCommand
from monitoring.models import CommandeAutomatique
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Charge automatiquement 60 commandes réseau préconfigurées et vérifiées."

    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write(self.style.WARNING("⚠️ Aucun superutilisateur trouvé. Les commandes seront ajoutées sans créateur."))

        commandes = [
            # === Configuration réseau de base ===
            ("Configurer adresse IP statique", "Définit une adresse IP fixe sur Ubuntu", """
sudo bash -c 'cat > /etc/netplan/01-netcfg.yaml <<EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    ens33:
      dhcp4: no
      addresses: [192.168.1.10/24]
      gateway4: 192.168.1.1
      nameservers:
        addresses: [8.8.8.8, 1.1.1.1]
EOF'
sudo netplan apply
"""),

            ("Activer DHCP", "Installe et active le serveur DHCP", """
sudo apt update -y
sudo apt install isc-dhcp-server -y
sudo systemctl enable isc-dhcp-server
sudo systemctl restart isc-dhcp-server
"""),

            ("Configurer DHCP", "Configure les baux IP DHCP", """
sudo bash -c 'cat > /etc/dhcp/dhcpd.conf <<EOF
subnet 192.168.1.0 netmask 255.255.255.0 {
  range 192.168.1.100 192.168.1.200;
  option routers 192.168.1.1;
  option domain-name-servers 8.8.8.8;
}
EOF'
sudo systemctl restart isc-dhcp-server
"""),


            ("Installer et activer OpenVPN serveur", "Configure un serveur VPN OpenVPN", """
sudo apt update -y
sudo apt install openvpn easy-rsa -y
make-cadir ~/openvpn-ca
cd ~/openvpn-ca
./easyrsa init-pki
./easyrsa build-ca nopass
"""),

            # === Sécurité réseau ===
            ("Installer UFW", "Installe et active le pare-feu UFW", """
sudo apt install ufw -y
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
"""),

            ("Autoriser HTTP/HTTPS", "Ouvre les ports web", """
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
"""),

            ("Bloquer tout trafic entrant sauf SSH", "Renforce la sécurité SSH uniquement", """
sudo ufw default deny incoming
sudo ufw allow 22/tcp
sudo ufw reload
"""),

            ("Afficher règles pare-feu", "Liste les règles UFW en détail", "sudo ufw status verbose"),

            ("Installer Fail2Ban", "Protège contre les attaques SSH", """
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
"""),

            # === Supervision & outils réseau ===
            ("Installer Netdata", "Monitoring complet en temps réel", """
bash <(curl -Ss https://my-netdata.io/kickstart.sh)
"""),

            ("Installer Nmon", "Surveillance CPU/RAM/Disque", "sudo apt install nmon -y"),
            ("Installer IPerf3", "Test de performance réseau", "sudo apt install iperf3 -y"),
            ("Installer Htop", "Visualisation interactive CPU/mémoire", "sudo apt install htop -y"),

            ("Installer et activer SNMP", "Supervision SNMP", """
sudo apt install snmpd -y
sudo systemctl enable snmpd
sudo systemctl start snmpd
"""),
            # CORRECTION SNMP : Évite d'écrire la ligne 50 fois
            ("Configurer SNMP v2", "Ajoute la communauté publique SNMP sans doublon", """
grep -qF "rocommunity public" /etc/snmp/snmpd.conf || sudo bash -c "echo 'rocommunity public' >> /etc/snmp/snmpd.conf"
sudo systemctl restart snmpd
"""),
            # CORRECTION NAT : Ajout de l'installation du paquet manquant
            ("Configurer NAT", "Installe les outils et active le NAT", """
sudo apt install iptables-persistent -y
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
sudo netfilter-persistent save
"""),

            ("Vérifier connectivité Internet", "Ping Google DNS", "ping -c 4 8.8.8.8"),
            ("Tracer la route réseau", "Affiche le chemin réseau vers 8.8.8.8", "traceroute 8.8.8.8"),

            # === Services DNS & Web ===
            ("Installer Bind9", "Installe un serveur DNS interne", """
sudo apt install bind9 bind9utils -y
sudo systemctl enable bind9
sudo systemctl start bind9
"""),

            ("Redémarrer le serveur DNS", "Redémarre Bind9 proprement", "sudo systemctl restart bind9"),
            ("Vérifier résolveur DNS", "Teste la résolution DNS", "dig google.com"),

            ("Installer Apache2", "Serveur web Apache2", """
sudo apt install apache2 -y
sudo systemctl enable apache2
sudo systemctl start apache2
"""),

            ("Installer Nginx", "Serveur web Nginx", """
sudo apt install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
"""),

            ("Installer MariaDB", "Base de données MySQL", """
sudo apt install mariadb-server -y
sudo systemctl enable mariadb
sudo systemctl start mariadb
"""),

            ("Installer PHP", "Support PHP", "sudo apt install php php-mysql libapache2-mod-php -y"),
            ("Installer Git", "Contrôle de version Git", "sudo apt install git -y"),

            # === Conteneurisation ===
            ("Installer Docker", "Installe Docker CE", """
sudo apt install apt-transport-https ca-certificates curl gnupg-agent software-properties-common -y
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io -y
"""),

            ("Installer Kubernetes (minikube + kubectl)", "Cluster local Kubernetes", """
sudo apt install curl apt-transport-https -y
curl -LO "https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64"
sudo install minikube-linux-amd64 /usr/local/bin/minikube
curl -LO "https://dl.k8s.io/release/v1.28.0/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/
"""),

            # === Maintenance système ===
            ("Afficher charge CPU", "Affiche la charge CPU", "uptime"),
            ("Afficher utilisation mémoire", "Affiche la RAM utilisée", "free -h"),
            ("Afficher espace disque", "Affiche la place disque", "df -h"),
            ("Lister interfaces réseau", "Interfaces réseau disponibles", "ip -br a"),
            ("Redémarrer serveur", "Reboot immédiat", "sudo reboot"),
            ("Arrêter serveur", "Shutdown immédiat", "sudo shutdown now"),
            ("Mettre à jour le système", "Met à jour tous les paquets", """
sudo apt update && sudo apt upgrade -y
"""),
            ("Nettoyer le système", "Supprime les paquets obsolètes", "sudo apt autoremove -y"),
            ("Afficher services actifs", "Liste des services systemd", "systemctl list-units --type=service --state=running"),
            ("Lister utilisateurs système", "Liste les utilisateurs Linux", "cut -d: -f1 /etc/passwd"),

            # === Fichiers & Partage ===
            ("Installer Samba", "Partage de fichiers SMB", """
sudo apt install samba -y
sudo systemctl enable smbd
sudo systemctl start smbd
"""),

            ("Installer FTP (vsftpd)", "Serveur FTP", """
sudo apt install vsftpd -y
sudo systemctl enable vsftpd
sudo systemctl start vsftpd
"""),

            ("Configurer FTP anonyme", "Active les connexions FTP anonymes", """
sudo sed -i 's/anonymous_enable=NO/anonymous_enable=YES/' /etc/vsftpd.conf
sudo systemctl restart vsftpd
"""),

            # === Commandes supplémentaires (admin réseau avancé) ===
            ("Afficher IP publique", "Récupère l’adresse IP externe", "curl ifconfig.me"),
            ("Scanner ports ouverts", "Analyse avec ss", "sudo ss -tuln"),
            ("Installer Nmap", "Scanner réseau puissant", "sudo apt install nmap -y"),
            ("Scanner un hôte local", "Scan rapide de 192.168.1.1", "nmap -sS 192.168.1.1"),
            ("Afficher la table ARP", "Voir les voisins réseau", "ip neigh show"),
            ("Afficher la table de routage", "Route du trafic réseau", "ip route show"),
            ("Vérifier DNS local", "Affiche les serveurs DNS configurés", "systemd-resolve --status | grep 'DNS Servers'"),
            ("Tester débit réseau", "Test upload/download local", "iperf3 -s & sleep 1 && iperf3 -c 127.0.0.1"),
            ("Afficher connexions actives", "Liste des connexions TCP/UDP", "sudo lsof -i -P -n | grep ESTABLISHED"),
            ("Surveiller la bande passante", "Surveillance réseau en direct", "sudo apt install -y iftop && sudo iftop"),
        ]
        nouvelles_commandes = [
            # === Diagnostic Réseau Avancé ===
            ("Capturer paquets (tcpdump)", "Capture les 50 premiers paquets sur port 80", 
             "sudo tcpdump -i any port 80 -c 50 -nn"),
            
            ("Diagnostic complet MTR", "Trace la route avec perte de paquets (Google)", 
             "sudo apt install mtr -y && mtr -r -c 10 8.8.8.8"),
            
            ("Scanner réseau local (ARP)", "Liste tous les équipements sur le LAN", 
             "sudo apt install arp-scan -y && sudo arp-scan --localnet"),
            
            ("Tester port distant (Netcat)", "Vérifie si un port est ouvert sur une IP", 
             "nc -zv 192.168.1.1 22 80 443"),
            
            ("Analyser sockets détaillés", "Affiche processus et ports (remplace netstat)", 
             "sudo ss -lntuop"),
            
            ("Infos matériel carte réseau", "Affiche vitesse, duplex et driver", 
             "sudo apt install ethtool -y && sudo ethtool eth0"), # Attention à l'interface
            
            ("Vérifier résolution DNS complète", "Trace le cheminement de la résolution DNS", 
             "dig +trace google.com"),
            
            # === Sécurité & SSL ===
            ("Vérifier certificat SSL distant", "Affiche la date d'expiration d'un certificat", 
             "echo | openssl s_client -servername google.com -connect google.com:443 2>/dev/null | openssl x509 -noout -dates"),
            
            ("Générer clé SSH (RSA)", "Crée une paire de clés SSH sans passphrase", 
             "ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ''"),
            
            ("Bannir une IP (Manuellement)", "Ajoute une règle UFW pour bloquer une IP", 
             "sudo ufw deny from 203.0.113.42 to any"),

            # === Gestion IP & Routage ===
            ("Renouveler bail DHCP", "Force le renouvellement de l'IP client", 
             "sudo dhclient -r && sudo dhclient -v"),
            
            ("Ajouter route statique", "Ajoute une route temporaire vers un réseau", 
             "sudo ip route add 10.10.10.0/24 via 192.168.1.1 dev eth0"),
            
            ("Désactiver IPv6 temporairement", "Désactive IPv6 via sysctl", 
             "sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1"),
            
            ("Changer nom d'hôte (Hostname)", "Change le nom du serveur", 
             "sudo hostnamectl set-hostname mon-nouveau-serveur"),

            # === Performance & Logs ===
            ("Tester vitesse Internet (CLI)", "Speedtest en ligne de commande", 
             "sudo apt install speedtest-cli -y && speedtest-cli --simple"),
            
            ("Logs réseau (Kernel)", "Affiche les logs noyaux liés au réseau", 
             "dmesg | grep -i 'eth\|net\|wifi'"),
            
            ("Logs tentatives SSH échouées", "Affiche les dernières tentatives de hack", 
             "grep 'Failed password' /var/log/auth.log | tail -n 20"),

            # === Transfert & Outils ===
            ("Télécharger site web (Miroir)", "Clone un site complet en local", 
             "wget --mirror --convert-links --adjust-extension --page-requisites --no-parent http://example.com"),
            
            ("Synchro fichiers (Rsync)", "Copie locale optimisée", 
             "rsync -avh --progress /source/ /destination/"),
            
            ("Vérifier MTU", "Teste la taille max des paquets sans fragmentation", 
             "ping -M do -s 1472 -c 4 8.8.8.8"),
        ]
        
        windows_commandes = [
            # === Windows : Diagnostic Réseau Avancé ===
            ("Vérifier connectivité Internet (Windows)", "Ping Google DNS (Windows)", "ping -n 4 8.8.8.8", "windows"),
            ("Tracer la route réseau (Windows)", "Affiche le chemin réseau vers 8.8.8.8 (Windows)", "tracert 8.8.8.8", "windows"),
            ("Afficher IP et DNS (Windows)", "Affiche la configuration IP détaillée", "ipconfig /all", "windows"),
            ("Scanner ports ouverts (Windows)", "Liste les connexions actives et ports en écoute", "netstat -ano", "windows"),
            ("Afficher la table ARP (Windows)", "Voir les voisins réseau (Windows)", "arp -a", "windows"),
            ("Afficher la table de routage (Windows)", "Route du trafic réseau (Windows)", "route print", "windows"),
            ("Vérifier résolution DNS (Windows)", "Teste la résolution DNS (Windows)", "nslookup google.com", "windows"),
            ("Vider le cache DNS (Windows)", "Nettoie le cache de résolution DNS", "ipconfig /flushdns", "windows"),
            ("Informations interfaces réseau (Windows)", "Affiche l'état des cartes réseau physiques", "powershell -Command \"Get-NetAdapter | Format-Table -AutoSize\"", "windows"),
            ("Lister statistiques TCP (Windows)", "Statistiques du protocole TCP", "netstat -s -p tcp", "windows"),
            ("Afficher connexions PowerShell (Windows)", "Connexions réseau via Get-NetTCPConnection", "powershell -Command \"Get-NetTCPConnection | Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, State | Set-Printable (ou Format-Table)\"", "windows"),
            ("Vérifier route vers passerelle (Windows)", "Test de saut vers la gateway", "pathping 8.8.8.8", "windows"),
            ("Tester port spécifique (Windows)", "Vérifie si le port 80 est ouvert sur Google via PS", "powershell -Command \"Test-NetConnection -ComputerName google.com -Port 80\"", "windows"),
            
            # === Windows : Hardware, BIOS & Inventaire ===
            ("Modèle et Marque du PC (Windows)", "Récupère le modèle matériel", "powershell -Command \"Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model\"", "windows"),
            ("Numéro de série / BIOS (Windows)", "Récupère le Serial Number", "powershell -Command \"Get-CimInstance Win32_BIOS | Select-Object SerialNumber, Version\"", "windows"),
            ("Détails CPU (Windows)", "Nom, Cœurs et Fréquence", "powershell -Command \"Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, MaxClockSpeed\"", "windows"),
            ("Inventaire RAM (Windows)", "Détails sur les barrettes de RAM", "powershell -Command \"Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, Speed, MemoryType\"", "windows"),
            ("État disques Physiques (Windows)", "Vérifie l'état SMART simplifié", "powershell -Command \"Get-PhysicalDisk | Select-Object FriendlyName, Size, HealthStatus, OperationalStatus\"", "windows"),
            ("Liste des lecteurs logiques (Windows)", "Lettres de lecteur et systèmes de fichiers", "powershell -Command \"Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID, VolumeName, FileSystem\"", "windows"),
            ("Version Windows précise (Windows)", "Build et Version de l'OS", "powershell -Command \"Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture\"", "windows"),
            ("Vérifier TPM (Windows)", "État de la puce de sécurité TPM", "powershell -Command \"Get-Tpm\"", "windows"),
            ("Lister Pilotes (Windows)", "Liste les pilotes installés", "driverquery /V", "windows"),
            
            # === Windows : Processus, Services & Performance ===
            ("Afficher charge CPU (Windows)", "Affiche la charge CPU actuelle", "powershell -Command \"(Get-WmiObject Win32_Processor).LoadPercentage\"", "windows"),
            ("Afficher utilisation mémoire (Windows)", "Affiche la RAM libre", "powershell -Command \"Get-WmiObject Win32_OperatingSystem | Select-Object FreePhysicalMemory\"", "windows"),
            ("Afficher espace disque (Windows)", "Affiche la place disque sur C:", "powershell -Command \"Get-WmiObject Win32_LogicalDisk -Filter \\\"DeviceID='C:'\\\" | Select-Object Size, FreeSpace\"", "windows"),
            ("Afficher processus gourmands CPU (Windows)", "Top 10 CPU", "powershell -Command \"Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 -Property Name, CPU, Id\"", "windows"),
            ("Afficher processus gourmands RAM (Windows)", "Top 10 RAM", "powershell -Command \"Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 -Property Name, @{Name='Mem(MB)';Expression={[math]::round($_.WorkingSet64/1MB,2)}} , Id\"", "windows"),
            ("Lister tous les services (Windows)", "État de tous les services", "powershell -Command \"Get-Service | Select-Object Name, DisplayName, Status\"", "windows"),
            ("Lister services en erreur (Windows)", "Services censés être démarrés mais arrêtés", "powershell -Command \"Get-Service | Where-Object {$_.StartType -eq 'Automatic' -and $_.Status -eq 'Stopped'}\"", "windows"),
            ("Processus associés à un réseau (Windows)", "Liste processus avec ports ouverts", "netstat -abno", "windows"),
            ("Vérifier Uptime (Windows)", "Depuis quand le PC tourne", "powershell -Command \"(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime\"", "windows"),
            ("Afficher temps de boot (Windows)", "Date exacte du dernier démarrage", "powershell -Command \"(Get-CimInstance Win32_OperatingSystem).LastBootUpTime\"", "windows"),
            
            # === Windows : Sécurité & Audit ===
            ("Afficher sessions actives (Windows)", "Utilisateurs connectés au système", "query user", "windows"),
            ("Lister partages réseau (Windows)", "Dossiers partagés par cette machine", "net share", "windows"),
            ("Afficher règles pare-feu (Windows)", "Configuration du Firewall", "netsh advfirewall show allprofiles", "windows"),
            ("Vérifier authentification NTLM (Windows)", "Audit de sécurité NTLM", "powershell -Command \"Get-WinEvent -LogName Security -MaxEvents 50 | Where-Object {$_.Id -eq 4624}\"", "windows"),
            ("Rechercher tentatives Login échec (Windows)", "50 derniers échecs de login", "powershell -Command \"Get-WinEvent -FilterHashtable @{LogName='Security';ID=4625} -MaxEvents 50\"", "windows"),
            ("Vérifier Anti-Virus (Windows)", "État de Windows Defender", "powershell -Command \"Get-MpComputerStatus\"", "windows"),
            ("Derniers correctifs Windows Update (Windows)", "Liste les derniers KBs installés", "powershell -Command \"Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 20\"", "windows"),
            ("Utilisateurs locaux (Windows)", "Liste les comptes utilisateurs du PC", "net user", "windows"),
            ("Membres groupe Admin (Windows)", "Liste des administrateurs système", "net localgroup Administrators", "windows"),
            
            # === Windows : Maintenance & Système ===
            ("Vérifier fichiers système (Windows)", "Vérification d'intégrité (Lent)", "sfc /verifyonly", "windows"),
            ("Vérifier intégrité Image (Windows)", "Check santé OS via DISM", "dism /online /cleanup-image /checkhealth", "windows"),
            ("Redémarrer PC (Windows)", "Reboot immédiat (Attention)", "shutdown /r /t 0", "windows"),
            ("Arrêter PC (Windows)", "Shutdown immédiat (Attention)", "shutdown /s /t 0", "windows"),
            ("Vider Corbeille (Windows)", "Nettoyage rapide", "powershell -Command \"Clear-RecycleBin -Confirm:$false\"", "windows"),
            ("Afficher variables environnement (Windows)", "Variables système et utilisateur", "set", "windows"),
            ("Détail configuration système (Windows)", "Information globale complète", "systeminfo", "windows"),
            
            # === Windows : Monitoring Avancé (Rarement utilisé) ===
            ("Lister Certificats expirés (Windows)", "Audit de sécurité SSL local", "powershell -Command \"Get-ChildItem -Path Cert:\\LocalMachine\\My | Where-Object {$_.NotAfter -lt (Get-Date)}\"", "windows"),
            ("Vérifier Latence Disque (Windows)", "Latence moyenne en ms", "powershell -Command \"(Get-Counter '\\PhysicalDisk(_Total)\\Avg. Disk sec/Read').CounterSamples.CookedValue * 1000\"", "windows"),
            ("Afficher fichiers ouverts (Windows)", "Outil Openfiles (nécessite activation)", "openfiles /query", "windows"),
            ("Récupérer Erreurs Disque (Log) (Windows)", "Events NTFS/Disk dans le log système", "powershell -Command \"Get-WinEvent -LogName System | Where-Object {$_.ProviderName -eq 'Disk' -or $_.ProviderName -eq 'ntfs'} -MaxEvents 20\"", "windows"),
            ("Afficher consommation réseau par process (Windows)", "Stats réseau via Get-NetTCPConnection", "powershell -Command \"Get-NetTCPConnection | Group-Object -Property OwningProcess | Select-Object Count, Name\"", "windows"),
            ("Afficher logs d'erreurs critiques (Windows)", "Top 10 erreurs système", "powershell -Command \"Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2} -MaxEvents 10\"", "windows"),
            ("Vérifier état de la batterie (Windows)", "Si applicable (Laptops)", "powershell -Command \"Get-CimInstance -ClassName Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus\"", "windows"),
            ("Lister Points de Restauration (Windows)", "Sauvegardes système", "powershell -Command \"Get-ComputerRestorePoint\"", "windows"),
            ("Lister applications installées (Windows)", "Logiciels via registry", "powershell -Command \"Get-ItemProperty HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Select-Object DisplayName, DisplayVersion\"", "windows"),
        ]
        
        # Ajoute ceci à ta liste principale
        commandes.extend(nouvelles_commandes)
        commandes.extend(windows_commandes)

        ajoutés, existants = 0, 0
        for item in commandes:
            if len(item) == 3:
                nom, desc, contenu = item
                os_cible = 'linux'
            elif len(item) == 4:
                nom, desc, contenu, os_cible = item

            obj, created = CommandeAutomatique.objects.get_or_create(
                nom=nom,
                defaults={"description": desc, "contenu": contenu, "cree_par": admin, "os_cible": os_cible},
            )
            if created:
                ajoutés += 1
            else:
                # Update OS si nécessaire sur les commandes existantes
                if obj.os_cible != os_cible:
                    obj.os_cible = os_cible
                    obj.save()
                existants += 1

        self.stdout.write(self.style.SUCCESS(f"[OK] {ajoutés} commandes ajoutées, {existants} déjà existantes. (Windows & Linux intégrés)"))