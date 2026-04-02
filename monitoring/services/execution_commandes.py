# monitoring/services/execution_commandes.py

from monitoring.ssh_utils import ssh_connect
from monitoring.models import ExecutionCommande
import logging

logger = logging.getLogger("monitoring.exec")


def executer_commande_automatique(equipement, commande_auto, utilisateur):
    """
    Exécute une CommandeAutomatique sur un équipement
    (ligne par ligne si nécessaire)
    """
    ssh = ssh_connect(equipement)

    sortie_complete = []
    erreur_complete = []
    succes_global = True

    for ligne in commande_auto.commandes_split():
        try:
            logger.info(
                f"[EXEC] {equipement.nom} → {ligne}"
            )

            stdin, stdout, stderr = ssh.exec_command(
                ligne,
                get_pty=True
            )

            # sudo implicite
            stdin.write(equipement.mot_de_passe_ssh + "\n")
            stdin.flush()

            out = stdout.read().decode()
            err = stderr.read().decode()

            sortie_complete.append(out)

            if err:
                erreur_complete.append(err)
                succes_global = False

        except Exception as e:
            erreur_complete.append(str(e))
            succes_global = False

    ssh.close()

    # 🧾 AUDIT
    ExecutionCommande.objects.create(
        equipement=equipement,
        utilisateur=utilisateur,
        commande=commande_auto.contenu,
        succes=succes_global,
        sortie="\n".join(sortie_complete),
        erreur="\n".join(erreur_complete)
    )

    return succes_global