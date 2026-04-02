import paramiko
import re
from django.utils import timezone
from monitoring.models import JournalReseau

COMMANDES_INTERDITES = [
    "rm -rf",
    "shutdown",
    "reboot",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",  # fork bomb
]


def nettoyer_ansi(texte: str) -> str:
    """
    Supprime les codes d'échappement ANSI (garbage characters) comme [?9001h
    """
    if not texte:
        return ""
    # Regex standard pour les séquences d'échappement ANSI (VT100, etc)
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    res = ansi_escape.sub('', texte)
    # Supprime aussi les caractères de contrôle spécifiques comme Page Down / Page Up fantômes
    res = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', res)
    return res.strip()


def est_commande_dangereuse(cmd: str) -> bool:
    return any(d in cmd.lower() for d in COMMANDES_INTERDITES)


def executer_commande_core(
    equipement,
    commande,
    utilisateur=None,
    ip_utilisateur="system"
):
    """
    Fonction MÉTIER pure
    → utilisée par vue, celery, planification, rollback
    """

    sortie_complete = ""
    succes_global = True

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=equipement.adresse_ip,
            port=equipement.port_ssh,
            username=equipement.utilisateur_ssh,
            password=equipement.mot_de_passe_ssh,
            timeout=10,
            look_for_keys=False,
            allow_agent=False,
        )

        # 💻 Détermine si on a besoin d'un PTY (essentiel pour sudo Linux, nuisible pour Windows)
        type_eq = str(equipement.type_equipement).lower()
        needs_pty = False if ('win' in type_eq or 'pc' in type_eq) else True

        for ligne in commande.commandes_split():

            # 🔒 Sécurité
            if est_commande_dangereuse(ligne) and (
                not utilisateur or not utilisateur.is_superuser
            ):
                raise PermissionError(
                    f"Commande interdite détectée : {ligne}"
                )

            sortie_complete += f"\n$ {ligne}\n"

            stdin, stdout, stderr = ssh.exec_command(
                ligne,
                get_pty=needs_pty
            )

            # 🔑 Sudo automatique (uniquement si PTY actif)
            if needs_pty and "sudo" in ligne:
                stdin.write(f"{equipement.mot_de_passe_ssh}\n")
                stdin.flush()

            # Lecture et nettoyage
            sortie = nettoyer_ansi(stdout.read().decode(errors="ignore"))
            erreur = nettoyer_ansi(stderr.read().decode(errors="ignore"))

            sortie_complete += sortie

            if erreur:
                sortie_complete += f"\n[ERREUR]\n{erreur}"
                succes_global = False

            sortie_complete += f"\n{'-' * 50}\n"

        ssh.close()

        JournalReseau.objects.create(
            equipement=equipement,
            utilisateur=utilisateur,
            action=f"Exécution commande : {commande.nom}",
            resultat="succès" if succes_global else "partiel",
            sortie_ssh=sortie_complete,
            ip_utilisateur=ip_utilisateur,
            date_action=timezone.now(),
        )

        return {
            "succes": succes_global,
            "sortie": sortie_complete
        }

    except Exception as e:
        ssh.close()

        JournalReseau.objects.create(
            equipement=equipement,
            utilisateur=utilisateur,
            action=f"Échec commande : {commande.nom}",
            resultat="échec",
            sortie_ssh=str(e),
            ip_utilisateur=ip_utilisateur,
            date_action=timezone.now(),
        )

        raise  # on laisse la vue / Celery gérer