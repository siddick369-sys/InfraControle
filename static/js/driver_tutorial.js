document.addEventListener("DOMContentLoaded", function() {
    if (typeof window.driver === 'undefined') {
        console.warn("Driver.js is not loaded.");
        return;
    }

    const driver = window.driver.js.driver;
    const currentPath = window.location.pathname;
    let dynamicSteps = [];
    let pageKey = "general"; // For tracking tutorial status per module

    // Helper: format string matching verbatim
    const progressFormat = 'Etape {{current}} sur {{total}}';

    /* ================================================================
     *  MAPPINGS DES ZONES UI PAR MODULE
     * ================================================================ */
    if (currentPath === '/' || currentPath === '/core/dashboard/' || currentPath.match(/^\/(?:dashboard)?$/i)) {
        pageKey = "core_dashboard";
        dynamicSteps = [
            {
                element: '.navbar-brand',
                popover: { 
                    title: 'Terminal Central', 
                    description: 'Bienvenue dans l\'interface de commande InfraControl. Depuis ce cockpit, vous pilotez l\'intégralité des systèmes sous-jacents : réseaux, serveurs, protocoles sans fil. L\'accès est restreint.', 
                    side: "bottom", align: "start" 
                }
            },
            {
                element: '.navbar-nav.me-auto',
                popover: { 
                    title: 'Console de Navigation', 
                    description: 'Accédez aux modules SRE : [Dashboard] pour l\'état global, [Supervision] pour le monitoring, [WiFi] pour la télémétrie AP, [Remediation] pour l\'automatisation des correctifs, et [Rapports] pour l\'audit.', 
                    side: "bottom" 
                }
            },
            {
                element: '#notif-count',
                popover: { 
                    title: 'Système d\'Alerte (NOC)', 
                    description: 'Unité d\'alerte temps réel. Intercepte les pannes critiques, déviations CPU/RAM, et anomalies de routage. Une notification rouge requiert une attention immédiate du SRE.', 
                    side: "left" 
                }
            },
            {
                element: '.row.g-4.mb-4 > div:nth-child(1) .card',
                popover: {
                    title: 'Statut de l\'Infrastructure',
                    description: 'Indicateurs clés de maturité du réseau : nombre d\'équipements suivis, sessions actives, et alertes non résolues. Conçu pour un diagnostic immédiat.',
                    side: "bottom"
                }
            }
        ];

    } else if (currentPath.startsWith('/monitoring/dashboard')) {
        pageKey = "monitoring_dashboard";
        dynamicSteps = [
            {
                popover: { 
                    title: 'Matrice de Télémétrie', 
                    description: 'Ce tableau de bord centralise le monitoring ICMP/SNMP en temps réel. Mise à jour asynchrone toutes les 10 secondes.', 
                }
            },
            {
                element: '#globalStats',
                popover: { 
                    title: 'KPIs Temps Réel', 
                    description: 'Indicateurs de charge (En ligne, Pannes, Avertissements). Ces seuils sont calculés dynamiquement par le moteur d\'analyse en backend.', 
                    side: "bottom" 
                }
            },
            {
                element: '#equipTable',
                popover: { 
                    title: 'Inventaire Actif', 
                    description: 'Serveurs et Switches mappés. Visualisez l\'allocation CPU/RAM instantanée et le ping en millisecondes. Une latence élevée ici révèle souvent une congestion.', 
                    side: "top" 
                }
            },
            {
                element: '.chart-container, #chartCPU',
                popover: { 
                    title: 'Onde de Performance', 
                    description: 'Graphe historique d\'utilisation CPU (20 derniers cycles de scrutation). Les pics persistants au-delà de 80% nécessitent une investigation ou un scale-up.', 
                    side: "top" 
                }
            }
        ];

    } else if (currentPath.startsWith('/monitoring/equipements')) {
        pageKey = "equipment_inventory";
        dynamicSteps = [
            {
                popover: { 
                    title: 'Registre Matériel', 
                    description: 'Gestion des actifs du SI. Identifiez, modifiez et testez l\'accès distant aux machines supervisées de la Data Room.', 
                }
            },
            {
                element: 'h2 + a, .btn-primary, [data-bs-target="#modalAdd"]',
                popover: { 
                    title: 'Provisionner une Ressource', 
                    description: 'Déclarez une nouvelle entité réseau. InfraControl nécessite une IP, un port SSH et des Credentials sécurisés pour initier la télémétrie.', 
                    side: "bottom" 
                }
            },
            {
                element: '.table-responsive',
                popover: { 
                    title: 'Contrôles Distants', 
                    description: 'Chaque ligne inclut des hooks directs : [Tester] vérifie le handshake SSH, [Modifier] met à jour l\'empreinte, [Corbeille] purgera les logs liés.', 
                    side: "top" 
                }
            }
        ];

    } else if (currentPath.startsWith('/monitoring/network/map')) {
        pageKey = "network_map";
        dynamicSteps = [
            {
                popover: { 
                    title: 'Topology Graph', 
                    description: 'Graphe réseau généré de façon procédurale (D3.js). Les nœuds illustrent l\'architecture physique de votre parc, et les liens la connectivité active.', 
                }
            },
            {
                element: '#network-map, svg, canvas',
                popover: { 
                    title: 'Manipulation Visuelle', 
                    description: 'Le graphe est drag & drop. Isolez les clusters critiques (Databases, Core Switches) pour une meilleure lisibilité. Les positions sont stockées dans le cache applicatif.', 
                    side: "top" 
                }
            }
        ];

    } else if (currentPath.startsWith('/monitoring/incidents')) {
        pageKey = "incident_response";
        dynamicSteps = [
            {
                popover: { 
                    title: 'Centre d\'Incident', 
                    description: 'Le hub de réponse aux incidents (Incident Response). Pannes réseau, overloads mémoire détectés... Trace d\'audit de chaque timeout sur l\'infra.', 
                }
            },
            {
                element: 'form.mb-4, .card-header form',
                popover: { 
                    title: 'Moteur de Recherche', 
                    description: 'Filtrez par sévérité ou par équipement. Fondamental pour isoler les causes racines lors d\'une panne en cascade.', 
                    side: "bottom" 
                }
            },
            {
                element: '.table',
                popover: { 
                    title: 'Diagnostics et IA', 
                    description: 'Cliquez sur l\'œil pour voir la raw stack trace ou sur le Robot pour invoquer le LLM qui analysera l\'erreur et proposera des vecteurs de résolution.', 
                    side: "top" 
                }
            }
        ];

    } else if (currentPath.startsWith('/wifi/ap/')) {
        pageKey = "wifi_ap_detail";
        dynamicSteps = [
            {
                element: '.card-header',
                popover: { 
                    title: 'ID Antenne', 
                    description: 'Metadatas de l\'Access Point (MAC, IP, Firmware). Le canal radio utilisé est contrôlé depuis le WLC.', 
                    side: "bottom" 
                }
            },
            {
                element: '#apHistoryChart',
                popover: { 
                    title: 'Trafic Multibande', 
                    description: 'Split entre les protocoles 2.4 GHz (Longue portée, bruité) et 5 GHz (Courte portée, haut débit). Les courbes illustrent la saturation des canaux.', 
                    side: "top" 
                }
            },
            {
                element: '#ap-clients-table',
                popover: { 
                    title: 'Mac Table Active', 
                    description: 'Registre des sessions 802.11 actives. La force du signal (RSSI) dicte la qualité. Sous -75 dBm, l\'utilisateur vivra un "Drop" de paquets constant.', 
                    side: "top" 
                }
            }
        ];

    } else if (currentPath.startsWith('/wifi')) {
        pageKey = "wifi_dashboard";
        dynamicSteps = [
            {
                popover: { 
                    title: 'Bouclier de Sécurité WiFi', 
                    description: 'Surveillez et protégez votre Box Internet. Ce panneau détecte les pirates, les voisins indésirables ou les attaques sur votre réseau familial.', 
                }
            },
            {
                element: '#stat-security-score',
                popover: { 
                    title: 'Score de Sécurité', 
                    description: 'Si une attaque brute-force ou un appareil inconnu (Hack) tente de pénétrer votre réseau, ce score plongera dans le rouge et déclenchera une alerte.', 
                    side: "bottom" 
                }
            },
            {
                element: '#aps-table-body',
                popover: { 
                    title: 'Radar Anti-Intrusion', 
                    description: 'La liste montre l\'état de la box en direct. Si la box subit une forte charge (attaque), l\'utilisation CPU augmentera de façon suspecte !', 
                    side: "top" 
                }
            }
        ];

    } else if (currentPath.startsWith('/discovery')) {
        pageKey = "network_discovery";
        dynamicSteps = [
            {
                popover: { 
                    title: 'Scan Nmap/ARP', 
                    description: 'Déploiement de sondes actives sur le réseau local pour l\'identification par signature (OS Fingerprinting) et la découverte de Rogue Devices.', 
                }
            },
            {
                element: 'form button[name="scan"]',
                popover: { 
                    title: 'Injection de Trame', 
                    description: 'Lance le balayage ICMP/TCP du sous-réseau. Les appareils répondants verront leur adresse MAC croisée avec la base OUI (Constructeur).', 
                    side: "bottom" 
                }
            },
            {
                element: '.table',
                popover: { 
                    title: 'Classification Automatique', 
                    description: 'Sécurisez votre périmètre. Si une IP inconnue s\'affiche, c\'est peut être un Shadow IT. Enregistrez-la d\'un clic pour démarrer la supervision SNMP.', 
                    side: "top" 
                }
            }
        ];

    } else if (currentPath.startsWith('/remediation')) {
        pageKey = "auto_remediation";
        dynamicSteps = [
            {
                popover: { 
                    title: 'Playbooks Automatiques', 
                    description: 'Self-Healing Network. Ce module utilise SSH pour exécuter de façon autonome des commandes Unix/Windows si un incident est détecté.', 
                }
            },
            {
                element: '[data-bs-target="#addRuleModal"]',
                popover: { 
                    title: 'Création de Règle', 
                    description: 'Définissez le Trigger (ex: `uptime`) et le Payload de résolution (ex: `systemctl restart nginx`). Le moteur Celery évaluera cette règle périodiquement.', 
                    side: "bottom" 
                }
            },
            {
                element: '.row.g-3 .glass-card',
                popover: { 
                    title: 'Déploiements Actifs', 
                    description: 'Vos workers en arrière plan. Le script vert indique le vecteur de correction qui sera injecté via le tunnel crypté.', 
                    side: "top" 
                }
            }
        ];

    } else if (currentPath.startsWith('/reports')) {
        pageKey = "automated_reports";
        dynamicSteps = [
            {
                element: '#btnGenerer',
                popover: { 
                    title: 'Scribe IA', 
                    description: 'Compile un rapport exécutif PDF en 10 secondes. Le réseau neuronal résume lui-même l\'impact métier des pannes des dernières 24 heures pour la DSI.', 
                    side: "bottom" 
                }
            },
            {
                element: '.table',
                popover: { 
                    title: 'Registre Légal', 
                    description: 'Conservez vos preuves d\'infrastructure SLA. Visualisez les compte rendus ou téléchargez le PDF natif mis en page dynamiquement.', 
                    side: "top" 
                }
            }
        ];

    } else if (currentPath.startsWith('/training')) {
        pageKey = "ai_training";
        dynamicSteps = [
            {
                popover: { 
                    title: 'Simulateur d\'Incident', 
                    description: 'Environnement Bac-à-Sable (Sandbox). Mettez au défi vos compétences d\'admin sys sur des incidents virtuels générés par le LLM.', 
                }
            },
            {
                element: 'a[href*="generer_scenario"]',
                popover: { 
                    title: 'Lancer un Test', 
                    description: 'Demandez à l\'Intelligence Artificielle de simuler une base de données corrompue ou un Switch défaillant et tentez de le résoudre virtuellement.', 
                    side: "top" 
                }
            }
        ];

    } else if (currentPath.startsWith('/auth/profile') || currentPath.startsWith('/profile')) {
        pageKey = "user_profile";
        dynamicSteps = [
            {
                element: '.holo-card',
                popover: { 
                    title: 'Passe de Sécurité', 
                    description: 'Vos identifiants d\'authentification InfraControl, votre Token JWT interne, et le statut de votre session administrateur.', 
                    side: "bottom" 
                }
            },
            {
                element: '[data-bs-target="#confirmDeleteModal"]',
                popover: { 
                    title: 'Golden Switch', 
                    description: 'Protocole de terminaison. Invalide l\'utilisateur de l\'annuaire, coupe tous les tokens et place le profil en isolement 7 jours avant purge.', 
                    side: "top" 
                }
            }
        ];

    } else {
        // Fallback générique
        pageKey = "generic_scan";
        dynamicSteps = [
            {
                element: '.navbar-brand',
                popover: { 
                    title: 'Mode Découverte', 
                    description: 'Vous naviguez dans les profondeurs d\'InfraControl. Pour relancer un diagnostic UI, utilisez toujours le bouton [?]', 
                    side: "bottom" 
                }
            },
            {
                element: '#start-tuto',
                popover: { 
                    title: 'Ping d\'Aide', 
                    description: 'L\'assistant Driver.js est branché et écoute sur ce noeud.', 
                    side: "left" 
                }
            }
        ];
    }

    // Configuration de l'Objet Driver avec Thème Premium
    const driverObj = driver({
        showProgress: true,
        progressText: progressFormat,
        allowClose: true,
        overlayColor: 'rgba(5, 10, 16, 0.85)',
        popoverClass: 'driver-theme',
        stagePadding: 10,
        stageRadius: 8,
        animate: true,
        onHighlightStarted: (element) => {
            if (element && element.node) {
                // Forcer une délimitation de la zone via un gros Neon bleu direct sur l'élément DOM
                element.node.style.boxShadow = '0 0 0 4px #0ea5e9, 0 0 30px #0ea5e9';
                element.node.style.outline = '2px solid white';
                element.node.style.outlineOffset = '6px';
                element.node.style.transition = 'box-shadow 0.3s ease';
                element.node.classList.add("driver-highlighted-zone");
            }
        },
        onDeselected: (element) => {
            if (element && element.node) {
                element.node.style.boxShadow = '';
                element.node.style.outline = '';
                element.node.classList.remove("driver-highlighted-zone");
            }
        },
        steps: dynamicSteps,
        onDestroyStarted: () => {
            if (driverObj.hasNextStep() || !driverObj.hasNextStep()) {
                driverObj.destroy();
            }
        }
    });

    /**
     * Logic for Auto-Triggering on first visit using localStorage
     */
    const storageKey = `infracontrol_tutorial_${pageKey}_seen`;
    const tutorialSeen = localStorage.getItem(storageKey);

    // Démarrage manuel toujours disponible
    const startBtn = document.getElementById('start-tuto');
    if (startBtn) {
        startBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (dynamicSteps.length > 0) {
                driverObj.drive();
                localStorage.setItem(storageKey, 'true'); // On le marque comme vu aussi si cliqué
            }
        });
    }

    // Lancement Automatique (1 seule fois par zone)
    if (!tutorialSeen && dynamicSteps.length > 0) {
        // Délai léger pour laisser la page finir ses animations
        setTimeout(() => {
            driverObj.drive();
            localStorage.setItem(storageKey, 'true');
        }, 800);
    }
});
