@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title InfraControl - NOC Control Center
mode con: cols=115 lines=48
color 0B

:: Se placer dans le dossier du script
cd /d "%~dp0"

:: ===================================================================
::  PHASE 0 : DETECTION OS ET PREREQUIS
:: ===================================================================
:DETECT_OS
cls
echo.
echo    ===================================================================================================================
echo                                   INFRACONTROL - VERIFICATION DES PREREQUIS SYSTEME                                   
echo    ===================================================================================================================
echo.

:: --- Etape 1 : Verifier si WSL est installe ---
echo    [*] Verification de WSL [Windows Subsystem for Linux]...
wsl --status >nul 2>&1
if !errorlevel! neq 0 (
    color 0E
    echo    [ATTENTION] WSL n'est pas installe sur ce systeme.
    echo    WSL est necessaire pour faire fonctionner Docker sur Windows.
    echo.
    set /p install_wsl="    Voulez-vous installer WSL maintenant ? [O/N] : "
    if /i "!install_wsl!"=="O" (
        echo.
        echo    [*] Installation de WSL en cours... Cela peut prendre quelques minutes.
        echo    [*] Le PC REDEMARRERA automatiquement apres l'installation.
        echo.
        wsl --install
        echo.
        echo    [*] WSL a ete installe avec succes.
        echo    [*] Veuillez REDEMARRER votre ordinateur, puis relancez ce fichier.
        echo.
        pause
        exit
    ) else (
        echo.
        echo    [ANNULE] WSL n'a pas ete installe. Docker ne pourra pas fonctionner.
        pause
        exit
    )
)
echo    [OK] WSL est installe.

:: --- Etape 2 : Verifier si Docker est installe ---
echo    [*] Verification de Docker...
docker --version >nul 2>&1
if !errorlevel! neq 0 (
    color 0E
    echo    [ATTENTION] Docker n'est pas installe sur ce systeme.
    echo.
    set /p video_docker="    Souhaitez-vous voir une video YouTube sur l'installation de Docker ? [O/N] : "
    if /i "!video_docker!"=="O" (
        echo    [*] Ouverture de YouTube...
        start https://www.youtube.com/results?search_query=installation+de+docker+desktop+windows
        echo.
        echo    [*] Installez Docker Desktop, puis relancez ce fichier.
        pause
        exit
    ) else (
        echo    [*] Tentative de telechargement de Docker Desktop...
        set "DOCKER_URL=https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe"
        set "DOCKER_DL=%USERPROFILE%\Downloads\DockerDesktopInstaller.exe"
        echo    [*] Telechargement en cours vers : !DOCKER_DL!
        powershell -Command "Invoke-WebRequest -Uri '!DOCKER_URL!' -OutFile '!DOCKER_DL!'"
        if exist "!DOCKER_DL!" (
            echo    [SUCCESS] Telechargement termine. Lancement de l'installateur...
            start "" "!DOCKER_DL!"
        ) else (
            echo    [ERREUR] Le telechargement a echoue. Veuillez telecharger Docker manuellement.
            start https://www.docker.com/products/docker-desktop/
        )
        echo.
        echo    [*] Installez Docker Desktop, puis relancez ce fichier.
        pause
        exit
    )
)
echo    [OK] Docker est installe.

:: --- Etape 3 : Verifier si le moteur Docker tourne ---
echo    [*] Verification du moteur Docker...
docker info >nul 2>&1
if !errorlevel! neq 0 (
    color 0C
    echo    [ERREUR] Le moteur Docker n'est pas en cours d'execution.
    echo    Veuillez demarrer Docker Desktop et relancez ce fichier.
    echo.
    pause
    exit
)
echo    [OK] Le moteur Docker est en cours d'execution.
echo.
echo    [SUCCESS] Tous les prerequis sont valides. Chargement du Centre de Controle...
ping 127.0.0.1 -n 2 > nul

:: ===================================================================
::  MENU PRINCIPAL
:: ===================================================================
:MENU
cls
echo.
echo    ██╗███╗   ██╗███████╗██████╗  █████╗  ██████╗ ██████╗ ███╗   ██╗████████╗██████╗  ██████╗ ██╗     
echo    ██║████╗  ██║██╔════╝██╔══██╗██╔══██╗██╔════╝ ██╔══██╗████╗  ██║╚══██╔══╝██╔══██╗██╔═══██╗██║     
echo    ██║██╔██╗ ██║█████╗  ██████╔╝███████║██║      ██████╔╝██╔██╗ ██║   ██║   ██████╔╝██║   ██║██║     
echo    ██║██║╚██╗██║██╔══╝  ██╔══██╗██╔══██║██║      ██╔══██╗██║╚██╗██║   ██║   ██╔══██╗██║   ██║██║     
echo    ██║██║ ╚████║██║     ██║  ██║██║  ██║╚██████╗ ██║  ██║██║ ╚████║   ██║   ██║  ██║╚██████╔╝███████╗
echo    ╚═╝╚═╝  ╚═══╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
echo.
echo    ===================================================================================================================
echo                                CENTRE DE CONTROLE NOC ET ADMINISTRATION RESEAU [SECURISE]                             
echo    ===================================================================================================================
echo.
echo      --- OPERATIONS INFRASTRUCTURE [DOCKER] ---
echo      [1] Demarrer l'infrastructure et ouvrir Dashboard         [4] Afficher l'etat de la grappe de serveurs
echo      [2] Arreter l'infrastructure proprement [*]               [5] Visionner les logs globaux du systeme
echo      [3] Redemarrer l'infrastructure complete [*]              [6] Statistiques d'utilisation CPU/RAM/Net
echo.
echo      --- OUTILS NOC ET SUPERVISION ANALYTIQUE ---
echo      [7] Ouvrir le tableau de bord Grafana                     [8] Ouvrir le moteur d'alerte Prometheus
echo      [9] Ouvrir le visionneur centralise de logs Dozzle
echo.
echo      --- DIAGNOSTIC RESEAU INTERACTIF ---
echo      [10] Lancer un Ping interactif                            [11] Lancer un Traceroute
echo      [12] Verifier les ports reseaux ouverts                   [13] Resolution DNS d'une IP/Domaine
echo.
echo      --- MAINTENANCE ET SECURITE ---
echo      [14] Sauvegarde complete de la Base de Donnees [*]        [15] Console SQL PostgreSQL [*]
echo      [16] Console Bash Serveur Web Django [*]                  [17] Mettre a jour l'infrastructure [*]
echo      [18] Liberer l'espace disque du systeme [*]               [19] FORMATAGE D'URGENCE [*]
echo.
echo      [*] = Action critique necessitant une authentification Administrateur Web.
echo      [0] Quitter le Centre de Controle
echo.
echo    ===================================================================================================================
set /p choix="    Selectionnez une action [0-19] : "

if "%choix%"=="1" goto START
if "%choix%"=="2" goto STOP
if "%choix%"=="3" goto RESTART
if "%choix%"=="4" goto PS
if "%choix%"=="5" goto LOGS
if "%choix%"=="6" goto STATS
if "%choix%"=="7" goto GRAFANA
if "%choix%"=="8" goto PROMETHEUS
if "%choix%"=="9" goto DOZZLE
if "%choix%"=="10" goto PING
if "%choix%"=="11" goto TRACERT
if "%choix%"=="12" goto NETSTAT
if "%choix%"=="13" goto NSLOOKUP
if "%choix%"=="14" goto BACKUP
if "%choix%"=="15" goto BASH_DB
if "%choix%"=="16" goto BASH_WEB
if "%choix%"=="17" goto BUILD
if "%choix%"=="18" goto PRUNE
if "%choix%"=="19" goto RESET
if "%choix%"=="0" exit

goto MENU

:: ===================================================================
::  MOTEUR DE SECURITE [DJANGO AUTH]
:: ===================================================================
:DJANGO_AUTH
echo.
echo    ===================================================================================================================
echo                                        VERROU DE SECURITE ADMINISTRATEUR                                              
echo    ===================================================================================================================
echo.
echo    [SECURITE] Une action critique a ete demandee.
echo    Vous devez vous authentifier avec votre compte Web InfraControl.
echo.

:: Verifier que le conteneur django tourne
docker compose ps --services --filter "status=running" 2>nul | findstr /i "django" >nul 2>&1
if !errorlevel! neq 0 (
    color 0C
    echo    [ERREUR] Le serveur Web est eteint.
    echo    Veuillez le demarrer avec l'option [1] avant d'effectuer cette action.
    color 0B
    exit /b 1
)

set "batch_usr="
set "batch_pwd="
set /p batch_usr="    Nom d'utilisateur : "
echo|set /p="    Mot de passe      : "
for /f "delims=" %%p in ('powershell -Command "$p=Read-Host -AsSecureString;$b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($p);[Runtime.InteropServices.Marshal]::PtrToStringAuto($b)"') do set "batch_pwd=%%p"
echo.
echo.

echo    [*] Validation des credentials via le serveur Web...
docker compose exec -T -e BATCH_USER="!batch_usr!" -e BATCH_PASS="!batch_pwd!" django python -c "import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','InfraContol.settings');django.setup();from django.contrib.auth import authenticate;u=authenticate(username=os.environ.get('BATCH_USER'),password=os.environ.get('BATCH_PASS'));import sys;sys.exit(0) if getattr(u,'is_staff',False) else sys.exit(1)"

if !errorlevel! neq 0 (
    color 0C
    echo.
    echo    [ACCES REFUSE] Identifiants incorrects ou droits administrateur manquants.
    echo.
    color 0B
    exit /b 1
)
color 0A
echo    [ACCES AUTORISE] Bienvenue, Administrateur !batch_usr!.
echo.
color 0B
exit /b 0

:: ===================================================================
::  VERIFICATION DOCKER
:: ===================================================================
:CHECK_DOCKER
docker info >nul 2>&1
if !errorlevel! neq 0 (
    color 0C
    echo.
    echo    [ERREUR CRITIQUE] Le service Docker n'est pas en cours d'execution.
    echo    Veuillez demarrer Docker Desktop et reessayer.
    echo.
    pause
    color 0B
    goto MENU
)
exit /b 0

:: ===================================================================
::  OPERATIONS INFRASTRUCTURE
:: ===================================================================
:START
call :CHECK_DOCKER
echo.
echo    [*] Deploiement automatise des services InfraControl...

if not exist "docker compose.yml" (
    echo    [*] Telechargement du depot Github...
    git clone https://github.com/siddick369-sys/InfraControle.git .
)

docker compose up -d --remove-orphans

echo.
echo    [*] Application des mises a jour BDD et configurations initiales...
docker compose exec -T django python manage.py migrate --noinput
docker compose exec -T django python manage.py collectstatic --noinput

echo    [*] Execution des commandes de gestion avancees...
docker compose exec -T django python manage.py fix_crypto
docker compose exec -T django python manage.py generate_demo_data
docker compose exec -T django python manage.py commande_reseau
docker compose exec -T django python manage.py smart_monitoring
docker compose exec -T django python manage.py run_wifi_master_sim
docker compose exec -T django python manage.py add_remediations
echo    [SUCCESS] Toutes les configurations appliquees.

echo.
echo    [*] En attente de la disponibilite du Dashboard...
set MAX_RETRIES=30
set RETRY=0
:WAIT_LOOP
powershell -Command "try{$r=Invoke-WebRequest -Uri 'http://localhost:8010/monitoring/dashboard/' -UseBasicParsing -TimeoutSec 1;if($r.StatusCode){exit 0}}catch{exit 1}" >nul 2>&1
if !errorlevel! equ 0 goto READY
set /a RETRY+=1
if !RETRY! equ !MAX_RETRIES! (
    echo    [ATTENTION] Ouverture forcee du navigateur.
    goto READY
)
ping 127.0.0.1 -n 2 > nul
goto WAIT_LOOP
:READY
start http://localhost:8010/monitoring/dashboard/
goto MENU

:STOP
call :CHECK_DOCKER
call :DJANGO_AUTH
if !errorlevel! neq 0 (
    pause
    goto MENU
)
echo    [*] Arret progressif de la grappe de serveurs...
docker compose down
echo    [SUCCESS] Services arretes.
pause
goto MENU

:RESTART
call :CHECK_DOCKER
call :DJANGO_AUTH
if !errorlevel! neq 0 (
    pause
    goto MENU
)
echo    [*] Redemarrage de l'infrastructure...
docker compose restart
echo    [SUCCESS] Services redemarres.
pause
goto MENU

:PS
call :CHECK_DOCKER
echo.
echo    [*] Etat des Services :
echo    --------------------------------------------------
docker compose ps
echo    --------------------------------------------------
pause
goto MENU

:LOGS
call :CHECK_DOCKER
echo.
echo    [*] Logs de l'infrastructure. Appuyez sur Ctrl+C pour quitter.
echo    --------------------------------------------------
docker compose logs -f --tail=30
pause
goto MENU

:STATS
call :CHECK_DOCKER
echo.
echo    [*] Stats Materielles. Appuyez sur Ctrl+C pour quitter.
echo    --------------------------------------------------
docker stats
pause
goto MENU

:: ===================================================================
::  SUPERVISION ANALYTIQUE
:: ===================================================================
:GRAFANA
start http://localhost:3010
goto MENU

:PROMETHEUS
start http://localhost:9010
goto MENU

:DOZZLE
start http://localhost:8088
goto MENU

:: ===================================================================
::  DIAGNOSTIC RESEAU
:: ===================================================================
:PING
echo.
set /p target="    Entrez l'IP ou le Domaine a pinguer : "
echo.
ping %target%
pause
goto MENU

:TRACERT
echo.
set /p target="    Entrez l'IP ou le Domaine pour le traceroute : "
echo.
tracert %target%
pause
goto MENU

:NETSTAT
echo.
echo    [*] Analyse des connexions et ports ouverts...
echo    --------------------------------------------------
netstat -ano | findstr /i "listening established"
echo    --------------------------------------------------
pause
goto MENU

:NSLOOKUP
echo.
set /p target="    Entrez l'IP ou le Nom de Domaine pour la resolution DNS : "
echo.
nslookup %target%
pause
goto MENU

:: ===================================================================
::  MAINTENANCE ET SECURITE
:: ===================================================================
:BACKUP
call :CHECK_DOCKER
call :DJANGO_AUTH
if !errorlevel! neq 0 (
    pause
    goto MENU
)
echo.
echo    [*] Creation du Backup de la base de donnees...
set BACKUP_NAME=backup_infracontrol_%date:~-4,4%%date:~-7,2%%date:~-10,2%.sql
docker compose exec -T postgres pg_dump -U infrauser -d infracontrol -F c > "%~dp0%BACKUP_NAME%"
echo.
echo    [SUCCESS] Fichier de sauvegarde cree : %~dp0%BACKUP_NAME%
pause
goto MENU

:BASH_DB
call :CHECK_DOCKER
call :DJANGO_AUTH
if !errorlevel! neq 0 (
    pause
    goto MENU
)
echo.
echo    [*] Console PostgreSQL. Tapez \q pour quitter.
echo    --------------------------------------------------
docker compose exec postgres psql -U infrauser -d infracontrol
echo    --------------------------------------------------
goto MENU

:BASH_WEB
call :CHECK_DOCKER
call :DJANGO_AUTH
if !errorlevel! neq 0 (
    pause
    goto MENU
)
echo.
echo    [*] Console Bash Django. Tapez exit pour quitter.
echo    --------------------------------------------------
docker compose exec django bash
echo    --------------------------------------------------
goto MENU

:BUILD
call :CHECK_DOCKER
call :DJANGO_AUTH
if !errorlevel! neq 0 (
    pause
    goto MENU
)
echo.
echo    [*] Reconstruction de l'infrastructure reseau...
docker compose build --no-cache
echo    [SUCCESS] Images reconstruites. Relancez avec l'option [1].
pause
goto MENU

:PRUNE
call :CHECK_DOCKER
call :DJANGO_AUTH
if !errorlevel! neq 0 (
    pause
    goto MENU
)
echo.
echo    [*] Nettoyage systeme Docker...
docker system prune -f
echo    [SUCCESS] Nettoyage termine.
pause
goto MENU

:RESET
call :CHECK_DOCKER
call :DJANGO_AUTH
if !errorlevel! neq 0 (
    pause
    goto MENU
)
color 0C
echo.
echo    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo    !!! ATTENTION : RISQUE DE PERTE DE DONNEES CRITIQUE !!!!
echo    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo.
set /p confirm="    Tapez OUI pour confirmer la destruction de la BDD : "
if /i "%confirm%"=="OUI" (
    docker compose down -v
    echo    [SUCCESS] Environnement efface.
) else (
    echo    [ANNULE] Aucun fichier efface.
)
pause
color 0B
goto MENU
