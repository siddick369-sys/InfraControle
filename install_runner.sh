#!/bin/bash
set -e

echo "=========================================================="
echo "    INFRA-CONTROL: INSTALLATION DU GITHUB RUNNER"
echo "=========================================================="

echo "[*] Création du répertoire actions-runner..."
mkdir -p actions-runner && cd actions-runner

echo "[*] Téléchargement du package runner..."
curl -o actions-runner-linux-x64-2.335.1.tar.gz -L https://github.com/actions/runner/releases/download/v2.335.1/actions-runner-linux-x64-2.335.1.tar.gz

echo "[*] Validation du hash..."
echo "4ef2f25285f0ae4477f1fe1e346db76d2f3ebf03824e2ddd1973a2819bf6c8cf  actions-runner-linux-x64-2.335.1.tar.gz" | shasum -a 256 -c

echo "[*] Extraction de l'installateur..."
tar xzf ./actions-runner-linux-x64-2.335.1.tar.gz

echo "[*] Le token d'enregistrement expire après 1 heure !"
echo "Veuillez aller sur GitHub -> Settings -> Actions -> Runners -> New self-hosted runner"
read -p "[>] Collez votre nouveau TOKEN ici (ex: AB2F5...) : " GITHUB_TOKEN

echo "[*] Configuration de l'agent GitHub..."
./config.sh --url https://github.com/siddick369-sys/InfraControle --token $GITHUB_TOKEN --unattended --replace

echo "[*] Installation du service systemd..."
sudo ./svc.sh install

echo "[*] Démarrage du service GitHub Runner..."
sudo ./svc.sh start

echo "=========================================================="
echo "[SUCCESS] L'agent GitHub tourne désormais en arrière-plan !"
echo "La VM est prête à recevoir les déploiements automatiques."
echo "=========================================================="
