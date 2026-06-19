#!/bin/bash
# ===================================================================
#  InfraControl - Lanceur Linux (Serveur / Desktop)
#  Compatible Ubuntu, Debian, CentOS, Rocky Linux
# ===================================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Se placer dans le dossier du script
cd "$(dirname "$0")"

# Detection d'interface graphique
HAS_GUI=false
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    HAS_GUI=true
fi

# ===================================================================
#  PHASE 0 : VERIFICATION DES PREREQUIS
# ===================================================================
check_prerequisites() {
    echo ""
    echo -e "${CYAN}   ===================================================${NC}"
    echo -e "${CYAN}     INFRACONTROL - VERIFICATION DES PREREQUIS${NC}"
    echo -e "${CYAN}   ===================================================${NC}"
    echo ""

    # Verifier Docker
    echo -e "   [*] Verification de Docker..."
    if ! command -v docker &> /dev/null; then
        echo -e "   ${YELLOW}[ATTENTION] Docker n'est pas installe.${NC}"
        echo ""

        if [ "$HAS_GUI" = true ]; then
            read -p "   Voulez-vous voir une video YouTube sur l'installation ? [O/N] : " video_choice
            if [[ "$video_choice" =~ ^[Oo]$ ]]; then
                xdg-open "https://www.youtube.com/results?search_query=installation+docker+linux+ubuntu" 2>/dev/null
                echo -e "   ${GREEN}[*] Installez Docker, puis relancez ce script.${NC}"
                exit 0
            fi
        fi

        echo -e "   ${BLUE}[*] Installation automatique de Docker...${NC}"
        if command -v apt-get &> /dev/null; then
            echo -e "   ${BLUE}[*] Installation via script securise Docker...${NC}"
            echo "   [+] Mise à jour des paquets..."
            sudo apt-update
            
            echo "   [+] Installation des dépendances..."
            sudo apt install -y ca-certificates curl gnupg
            
            echo "   [+] Création du dossier des clés..."
            sudo install -m 0755 -d /etc/apt/keyrings
            
            echo "   [+] Téléchargement de la clé Docker..."
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc > /dev/null
            sudo chmod a+r /etc/apt/keyrings/docker.asc
            
            echo "   [+] Ajout du dépôt Docker..."
            echo \
              "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
              $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
              sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
              
            echo "   [+] Installation de Docker..."
            sudo apt update
            sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            
            echo "   [+] Activation du service Docker..."
            sudo systemctl enable docker
            sudo systemctl start docker
            
            echo "   [+] Ajout de l'utilisateur courant au groupe docker..."
            sudo usermod -aG docker "$USER"
            
            echo "   [+] Vérification :"
            docker --version || true
            
            echo -e "   ${GREEN}[SUCCESS] Docker installé. Reconnectez-vous pour appliquer les permissions.${NC}"
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y docker docker-compose
            sudo systemctl enable docker
            sudo systemctl start docker
            sudo usermod -aG docker "$USER"
            echo -e "   ${GREEN}[SUCCESS] Docker installe.${NC}"
        else
            echo -e "   ${RED}[ERREUR] Gestionnaire de paquets non supporte.${NC}"
            echo "   Installez Docker manuellement : https://docs.docker.com/engine/install/"
            exit 1
        fi
    fi
    echo -e "   ${GREEN}[OK] Docker est installe.${NC}"

    # Verifier que le daemon Docker tourne
    echo -e "   [*] Verification du moteur Docker..."
    if ! docker info &> /dev/null; then
        echo -e "   ${RED}[ERREUR] Le moteur Docker n'est pas en cours d'execution.${NC}"
        echo -e "   Essayez : ${BOLD}sudo systemctl start docker${NC}"
        exit 1
    fi
    echo -e "   ${GREEN}[OK] Le moteur Docker est en cours d'execution.${NC}"
    echo ""
}

# ===================================================================
#  AUTHENTIFICATION DJANGO
# ===================================================================
django_auth() {
    echo ""
    echo -e "${CYAN}   ===================================================${NC}"
    echo -e "${CYAN}     VERROU DE SECURITE ADMINISTRATEUR${NC}"
    echo -e "${CYAN}   ===================================================${NC}"
    echo ""

    # Verifier que le conteneur django tourne
    if ! docker-compose ps --services --filter "status=running" 2>/dev/null | grep -q "django"; then
        echo -e "   ${RED}[ERREUR] Le serveur Web est eteint. Demarrez-le d'abord [Option 1].${NC}"
        return 1
    fi

    read -p "   Nom d'utilisateur : " batch_usr
    read -sp "   Mot de passe      : " batch_pwd
    echo ""
    echo ""

    echo -e "   [*] Validation des credentials..."
    if docker-compose exec -T -e BATCH_USER="$batch_usr" -e BATCH_PASS="$batch_pwd" django python -c \
        "import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','InfraContol.settings');django.setup();from django.contrib.auth import authenticate;u=authenticate(username=os.environ.get('BATCH_USER'),password=os.environ.get('BATCH_PASS'));import sys;sys.exit(0) if getattr(u,'is_staff',False) else sys.exit(1)" 2>/dev/null; then
        echo -e "   ${GREEN}[ACCES AUTORISE] Bienvenue, Administrateur $batch_usr.${NC}"
        echo ""
        return 0
    else
        echo -e "   ${RED}[ACCES REFUSE] Identifiants incorrects ou droits insuffisants.${NC}"
        echo ""
        return 1
    fi
}

# ===================================================================
#  MENU PRINCIPAL
# ===================================================================
show_menu() {
    clear
    echo ""
    echo -e "${BLUE}   ██╗███╗   ██╗███████╗██████╗  █████╗  ██████╗ ██████╗ ███╗   ██╗████████╗██████╗  ██████╗ ██╗${NC}"
    echo -e "${BLUE}   ██║████╗  ██║██╔════╝██╔══██╗██╔══██╗██╔════╝ ██╔══██╗████╗  ██║╚══██╔══╝██╔══██╗██╔═══██╗██║${NC}"
    echo -e "${BLUE}   ██║██╔██╗ ██║█████╗  ██████╔╝███████║██║      ██████╔╝██╔██╗ ██║   ██║   ██████╔╝██║   ██║██║${NC}"
    echo -e "${BLUE}   ██║██║╚██╗██║██╔══╝  ██╔══██╗██╔══██║██║      ██╔══██╗██║╚██╗██║   ██║   ██╔══██╗██║   ██║██║${NC}"
    echo -e "${BLUE}   ██║██║ ╚████║██║     ██║  ██║██║  ██║╚██████╗ ██║  ██║██║ ╚████║   ██║   ██║  ██║╚██████╔╝███████╗${NC}"
    echo -e "${BLUE}   ╚═╝╚═╝  ╚═══╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝${NC}"
    echo ""
    echo -e "${CYAN}   =============================================================================================${NC}"
    echo -e "${BOLD}                          CENTRE DE CONTROLE NOC [SECURISE] - LINUX${NC}"
    echo -e "${CYAN}   =============================================================================================${NC}"
    echo ""
    echo "     --- OPERATIONS INFRASTRUCTURE ---"
    echo "     [1] Demarrer + ouvrir Dashboard              [4] Etat de la grappe de serveurs"
    echo "     [2] Arreter l'infrastructure [*]             [5] Logs systeme en direct"
    echo "     [3] Redemarrer l'infrastructure [*]          [6] Statistiques CPU/RAM/Net"
    echo ""
    echo "     --- SUPERVISION ANALYTIQUE ---"
    echo "     [7] Grafana (Metriques)                      [8] Prometheus (Alertes)"
    echo "     [9] Dozzle (Logs web)"
    echo ""
    echo "     --- DIAGNOSTIC RESEAU ---"
    echo "     [10] Ping                                    [11] Traceroute"
    echo "     [12] Ports ouverts (netstat/ss)              [13] DNS (nslookup/dig)"
    echo ""
    echo "     --- MAINTENANCE ET SECURITE ---"
    echo "     [14] Sauvegarde BDD [*]                      [15] Console PostgreSQL [*]"
    echo "     [16] Console Bash Django [*]                 [17] Reconstruire les images [*]"
    echo "     [18] Nettoyer Docker [*]                     [19] FORMATAGE D'URGENCE [*]"
    echo ""
    echo "     [*] = Action critique (authentification requise)"
    echo "     [0] Quitter"
    echo ""
    echo -e "${CYAN}   =============================================================================================${NC}"
}

# ===================================================================
#  EXECUTION DES ACTIONS
# ===================================================================
check_prerequisites

while true; do
    show_menu
    read -p "    Selectionnez une action [0-19] : " choix

    case $choix in
        1)
            echo -e "   ${BLUE}[*] Deploiement des services...${NC}"
            
            # Clonage du depot Github (s'il n'est pas deja la)
            if [ ! -f "docker-compose.yml" ]; then
                echo -e "   ${YELLOW}[*] Telechargement d'InfraControl depuis Github...${NC}"
                git clone https://github.com/siddick369-sys/InfraControle.git . || echo -e "   ${RED}Erreur Git clone${NC}"
            fi

            docker-compose up -d --remove-orphans
            
            echo -e "   ${BLUE}[*] Execution des commandes de gestion Django...${NC}"
            docker-compose exec -T django python manage.py migrate --noinput || true
            docker-compose exec -T django python manage.py collectstatic --noinput || true
            docker-compose exec -T django python manage.py fix_crypto || true
            docker-compose exec -T django python manage.py generate_demo_data || true
            docker-compose exec -T django python manage.py commande_reseau || true
            docker-compose exec -T django python manage.py smart_monitoring || true
            docker-compose exec -T django python manage.py run_wifi_master_sim || true
            docker-compose exec -T django python manage.py add_remediations || true

            echo -e "   ${GREEN}[SUCCESS] Services demarres et configures.${NC}"
            if [ "$HAS_GUI" = true ]; then
                xdg-open "http://localhost:8010/monitoring/dashboard/" 2>/dev/null &
            else
                echo -e "   Dashboard accessible sur : ${BOLD}http://<IP_SERVEUR>:8010/monitoring/dashboard/${NC}"
            fi
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        2)
            if django_auth; then
                echo -e "   ${BLUE}[*] Arret des services...${NC}"
                docker-compose down
                echo -e "   ${GREEN}[SUCCESS] Services arretes.${NC}"
            fi
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        3)
            if django_auth; then
                echo -e "   ${BLUE}[*] Redemarrage...${NC}"
                docker-compose restart
                echo -e "   ${GREEN}[SUCCESS] Services redemarres.${NC}"
            fi
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        4)
            docker-compose ps
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        5)
            docker-compose logs -f --tail=30
            ;;
        6)
            docker stats
            ;;
        7)
            if [ "$HAS_GUI" = true ]; then xdg-open "http://localhost:3010" 2>/dev/null &
            else echo "   URL Grafana : http://<IP>:3010"; fi
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        8)
            if [ "$HAS_GUI" = true ]; then xdg-open "http://localhost:9010" 2>/dev/null &
            else echo "   URL Prometheus : http://<IP>:9010"; fi
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        9)
            if [ "$HAS_GUI" = true ]; then xdg-open "http://localhost:8088" 2>/dev/null &
            else echo "   URL Dozzle : http://<IP>:8088"; fi
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        10)
            read -p "   IP ou domaine : " target
            ping -c 10 "$target"
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        11)
            read -p "   IP ou domaine : " target
            traceroute "$target" 2>/dev/null || tracepath "$target"
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        12)
            ss -tulnp 2>/dev/null || netstat -tulnp
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        13)
            read -p "   IP ou domaine : " target
            dig "$target" 2>/dev/null || nslookup "$target"
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        14)
            if django_auth; then
                BACKUP="backup_infracontrol_$(date +%Y%m%d_%H%M%S).sql"
                docker-compose exec -T postgres pg_dump -U infrauser -d infracontrol -F c > "$BACKUP"
                echo -e "   ${GREEN}[SUCCESS] Sauvegarde : $BACKUP${NC}"
            fi
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        15)
            if django_auth; then
                docker-compose exec postgres psql -U infrauser -d infracontrol
            fi
            ;;
        16)
            if django_auth; then
                docker-compose exec django bash
            fi
            ;;
        17)
            if django_auth; then
                docker-compose build --no-cache
                echo -e "   ${GREEN}[SUCCESS] Images reconstruites.${NC}"
            fi
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        18)
            if django_auth; then
                docker system prune -f
                echo -e "   ${GREEN}[SUCCESS] Nettoyage termine.${NC}"
            fi
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        19)
            if django_auth; then
                echo -e "   ${RED}!!! DESTRUCTION DE TOUTES LES DONNEES !!!${NC}"
                read -p "   Tapez OUI pour confirmer : " confirm
                if [ "$confirm" = "OUI" ]; then
                    docker-compose down -v
                    echo -e "   ${GREEN}[SUCCESS] Environnement efface.${NC}"
                else
                    echo -e "   ${YELLOW}[ANNULE] Aucun fichier efface.${NC}"
                fi
            fi
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
        0)
            echo -e "   ${GREEN}Au revoir !${NC}"
            exit 0
            ;;
        *)
            echo -e "   ${RED}Option invalide.${NC}"
            read -p "   Appuyez sur Entree pour continuer..." _
            ;;
    esac
done
