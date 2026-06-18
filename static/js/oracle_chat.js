/**
 * Oracle AI Chat - Frontend Logic (Enhanced for WOW Effect)
 */

document.addEventListener("DOMContentLoaded", () => {
    // ═══════════════════════════════════════════════════════
    // 5. ORACLE IA - WIDGET WIFI SIRENE INCIDENT (PHASE 3)
    // ═══════════════════════════════════════════════════════
    let lastAlertTimestamp = null;
    async function pollWifiSecurity() {
        try {
            const res = await fetch("/wifi/api/stats/");
            if (!res.ok) return;
            const data = await res.json();
            
            // Cherche la dernière alerte de piratage (Critique)
            const hack = data.alerts.find(a => 
                a.type.includes("BRUTE_FORCE") || 
                a.type.includes("DDOS_WIFI") || 
                a.type.includes("ROGUE_AP") || 
                a.type.includes("ARP_POISONING")
            );

            if (hack) {
                // Si l'heure de l'alerte est nouvelle
                if (lastAlertTimestamp !== hack.time) {
                    lastAlertTimestamp = hack.time;
                    console.log("[ORACLE WIFI SHIELD] Threat Detected:", hack.type);
                    
                    // Modifie temporairement la fenêtre en Rouge (Hacker Sévère)
                    const w = document.getElementById("oracle-window");
                    if(w) w.style.boxShadow = "0 8px 32px 0 rgba(220, 38, 38, 0.8)";
                    
                    // Force la voix alarmiste et dicte
                    if (window.speechSynthesis && !speechSynthesis.speaking) {
                        const originalLang = document.currentOracleLang || 'fr-FR';
                        const utterance = new SpeechSynthesisUtterance();
                        utterance.text = "Attention. Système infiltré. Une attaque de type " + hack.type.replace(/_/g, " ") + " a été détectée sur votre réseau local. Je vous conseille vivement d'isoler la cible réseau.";
                        utterance.lang = "fr-FR";
                        utterance.rate = 1.15;
                        utterance.pitch = 1.3;
                        
                        let voices = window.speechSynthesis.getVoices();
                        let targetVoice = voices.find(v => v.lang === 'fr-FR');
                        if (targetVoice) utterance.voice = targetVoice;
                        
                        window.speechSynthesis.speak(utterance);
                        
                        setTimeout(() => { if(w) w.style.boxShadow = ""; }, 10000);
                    }
                }
            }
        } catch(e) {}
    }
    
    // Démarre la vérification toutes les 8 secondes en arrière-plan
    setInterval(pollWifiSecurity, 8000);

    const fab = document.getElementById("oracle-fab");
    const windowEl = document.getElementById("oracle-window");
    const closeBtn = document.getElementById("oracle-close");
    const voiceBtn = document.getElementById("oracle-voice-toggle");
    const matrixBtn = document.getElementById("oracle-matrix-toggle");
    const sendBtn = document.getElementById("oracle-send");
    const input = document.getElementById("oracle-input");
    const messages = document.getElementById("oracle-messages");
    const typing = document.getElementById("oracle-typing");

    let voiceEnabled = false;
    let matrixMode = false;

    // Toggle window & SFX
    function playSFX(type) {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain); gain.connect(ctx.destination);
            if(type === 'open') { 
                osc.type='sine'; 
                osc.frequency.setValueAtTime(800, ctx.currentTime); 
                osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime+0.1); 
                gain.gain.setValueAtTime(0.1, ctx.currentTime); 
                gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime+0.1); 
            } else if (type === 'send') {
                osc.type = "square";
                osc.frequency.setValueAtTime(300, ctx.currentTime);
                osc.frequency.exponentialRampToValueAtTime(100, ctx.currentTime + 0.1);
                gain.gain.setValueAtTime(0.05, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1);
            }
            osc.start(); osc.stop(ctx.currentTime+0.1);
        } catch(e) {}
    }

    // Restore History
    const hist = localStorage.getItem("oracleHistory");
    if(hist) {
        messages.innerHTML = hist;
        messages.appendChild(typing); // Réinsérer l'indicateur de frappe qui a été écrasé
    }

    // Toggle window
    fab.addEventListener("click", () => {
        const isVisible = windowEl.style.display === "flex";
        windowEl.style.display = isVisible ? "none" : "flex";
        if (!isVisible) {
            playSFX('open');
            input.focus();
            scrollToBottom();
        }
    });

    // Split Screen
    const splitBtn = document.getElementById("oracle-split-toggle");
    if(splitBtn) splitBtn.addEventListener("click", () => document.body.classList.toggle("oracle-split-mode"));

    // Microphone Speech Recognition
    const micBtn = document.getElementById("oracle-mic");
    if(micBtn) {
        micBtn.addEventListener("click", () => {
            const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
            if(SpeechRec) {
                const recog = new SpeechRec();
                recog.lang = 'fr-FR';
                recog.start();
                micBtn.innerHTML = "<i class='fas fa-microphone-slash fa-pulse text-danger'></i>";
                recog.onresult = (e) => {
                    input.value = e.results[0][0].transcript;
                    sendMessage();
                };
                recog.onend = () => micBtn.innerHTML = "<i class='fas fa-microphone'></i>";
            } else { addMessage("Mic non supporté.", "oracle"); }
        });
    }

    // Drag & Drop Log Files Handler
    windowEl.addEventListener('dragover', (e) => {
        e.preventDefault();
        windowEl.style.boxShadow = "0 0 30px #0ea5e9 inset";
    });
    windowEl.addEventListener('dragleave', (e) => {
        e.preventDefault();
        windowEl.style.boxShadow = matrixMode ? "0 0 20px rgba(0, 255, 0, 0.4)" : "0 25px 60px rgba(0,0,0,0.8), 0 0 40px rgba(14, 165, 233, 0.2)";
    });
    windowEl.addEventListener('drop', (e) => {
        e.preventDefault();
        windowEl.style.boxShadow = matrixMode ? "0 0 20px rgba(0, 255, 0, 0.4)" : "0 25px 60px rgba(0,0,0,0.8), 0 0 40px rgba(14, 165, 233, 0.2)";
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            const reader = new FileReader();
            reader.onload = function(event) {
                addMessage("✅ Fichier lu avec succès : " + file.name + "\nExtrait transféré au modèle IA pour analyse contextuelle.", "oracle");
                input.value = `[FICHIER LOG JOINT: ${file.name}] \n${event.target.result}\n\n${input.value}`;
            };
            reader.readAsText(file);
        }
    });

    closeBtn.addEventListener("click", () => {
        windowEl.style.display = "none";
        window.speechSynthesis.cancel();
    });

    // Voice Synthesis Toggle
    voiceBtn.addEventListener("click", () => {
        voiceEnabled = !voiceEnabled;
        const icon = voiceBtn.querySelector("i");
        if (voiceEnabled) {
            icon.classList.remove("fa-volume-mute");
            icon.classList.add("fa-volume-up");
            voiceBtn.style.color = "var(--accent-cyan)";
            speakText("Module vocal activé, Commandant.");
        } else {
            icon.classList.remove("fa-volume-up");
            icon.classList.add("fa-volume-mute");
            voiceBtn.style.color = "#FFF";
            window.speechSynthesis.cancel();
        }
    });

    // Matrix Hacker Mode Toggle
    matrixBtn.addEventListener("click", () => {
        matrixMode = !matrixMode;
        if (matrixMode) {
            windowEl.classList.add("hacker-mode");
            matrixBtn.style.textShadow = "0 0 10px #0f0";
            matrixBtn.style.color = "#0f0";
        } else {
            windowEl.classList.remove("hacker-mode");
            matrixBtn.style.textShadow = "none";
            matrixBtn.style.color = "var(--accent-cyan)";
        }
    });

    // Speak Function (Psychological Profiling & Audio Vis)
    function speakText(text) {
        if (!voiceEnabled) return;
        window.speechSynthesis.cancel();
        
        let pitch = 0.9;
        let rate = 1.05;
        if (text.includes("[SEVERITY: CRITICAL]")) {
            pitch = 1.5; // Urgence accrue
            rate = 1.25; // Rythme d'élocution plus rapide
            windowEl.classList.add("critical-alert-glow");
        } else {
            windowEl.classList.remove("critical-alert-glow");
        }

        const cleanText = text.replace(/\[SEVERITY:(.*?)\]/g, "");
        const synth = window.speechSynthesis;
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.lang = "fr-FR";
        utterance.rate = rate;
        utterance.pitch = pitch;
        
        // Forcer la sélection d'une voix française disponible dans le navigateur
        const voices = synth.getVoices();
        const frenchVoice = voices.find(v => v.lang.startsWith('fr') || v.name.toLowerCase().includes('french') || v.name.toLowerCase().includes('français'));
        if (frenchVoice) {
            utterance.voice = frenchVoice;
        }
        
        utterance.onstart = () => {
            const vis = document.getElementById("oracle-visualizer");
            if (vis) vis.style.opacity = "1";
        };
        utterance.onend = () => {
            const vis = document.getElementById("oracle-visualizer");
            if (vis) vis.style.opacity = "0";
            
            // Execute pending navigation after speaking finishes
            if (window.pendingNavigationUrl) {
                const url = window.pendingNavigationUrl;
                window.pendingNavigationUrl = null;
                setTimeout(() => { window.location.href = url; }, 500);
            }
        };

        synth.speak(utterance);
    }

    // Auto-Execute Command Function
    window.executeAICommand = async (cmd, btnEl) => {
        btnEl.disabled = true;
        btnEl.innerHTML = "<i class='fas fa-spinner fa-spin'></i> Exécution...";
        try {
            const response = await fetch("/aiengine/execute_cmd/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken()
                },
                body: JSON.stringify({ command: cmd })
            });
            const data = await response.json();
            if (data.output) {
                btnEl.innerHTML = "<i class='fas fa-check'></i> Exécuté";
                btnEl.classList.replace("btn-epic", "btn-success");
                addMessage("Résultat de l'exécution :\n" + data.output, "oracle");
            } else {
                btnEl.innerHTML = "<i class='fas fa-times'></i> Échec";
                btnEl.classList.replace("btn-epic", "btn-danger");
                addMessage("Erreur d'exécution : " + data.error, "oracle");
            }
        } catch (e) {
            btnEl.innerHTML = "<i class='fas fa-times'></i> Erreur";
            addMessage("Erreur réseau.", "oracle");
        }
    };

    // Send message
    const sendMessage = async () => {
        const text = input.value.trim();
        if (!text) return;

        playSFX('send');
        addMessage(text, "user");
        input.value = "";
        
        typing.style.display = "flex";
        scrollToBottom();

        try {
            const response = await fetch("/aiengine/oracle/chat/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken()
                },
                body: JSON.stringify({ 
                    message: text,
                    page_path: window.location.pathname,
                    page_title: document.title
                })
            });

            const data = await response.json();
            typing.style.display = "none";

            if (data.response) {
                addMessage(data.response, "oracle", data.command);
                speakText(data.response.replace(/```.*?```/gs, "")); // Speak without raw code
            } else {
                addMessage("Erreur : " + (data.error || "Impossible de joindre l'Oracle."), "oracle");
            }
        } catch (error) {
            typing.style.display = "none";
            addMessage("Erreur réseau. Vérifiez votre connexion.", "oracle");
        }
    };

    sendBtn.addEventListener("click", sendMessage);
    input.addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendMessage();
    });

    function addMessage(text, role, commandToRun = null) {
        const div = document.createElement("div");
        div.className = `message ${role}`;
        
        // Markdown & Special Blocks handling
        let parsedText = text;
        
        // 1. Ansible YAML Playbook Downloader
        parsedText = parsedText.replace(/```yaml\n([\s\S]*?)```/g, (match, code) => {
            const base64Code = btoa(unescape(encodeURIComponent(code)));
            return `<pre><code>${code}</code></pre><br><button class="btn btn-sm btn-info mt-2" onclick="downloadYaml('${base64Code}', 'ia_playbook.yml')"><i class="fas fa-download"></i> Télécharger YAML</button>`;
        });

        // 2. ASCII Graphics
        parsedText = parsedText.replace(/```ascii\n([\s\S]*?)```/g, '<pre style="font-family: monospace; line-height: 1.1; letter-spacing: -0.5px; overflow-x: auto; background: rgba(0,0,0,0.5);"><code>$1</code></pre>');

        // 3. Autonomous Navigation / Routing
        parsedText = parsedText.replace(/```navigate\n([\s\S]*?)```/g, (match, url) => {
            const safeUrl = url.trim();
            // L'IA naviguera APRES sa lecture TTS ou s'executera immediatement (si muet)
            if (voiceEnabled) {
                window.pendingNavigationUrl = safeUrl;
            } else {
                setTimeout(() => { window.location.href = safeUrl; }, 1500);
            }
            return `<div class="p-2 my-2" style="background:rgba(14,165,233,0.1); border-radius:8px; border-left:3px solid #0ea5e9;">🚀 Routage Autonome activé : Redirection vers <b>${safeUrl}</b> en cours d'exécution...</div>`;
        });

        // 4. SVG Inline Bar Charts
        parsedText = parsedText.replace(/```svg-chart\n([\s\S]*?)```/g, (match, values) => {
            const vals = values.split(',').map(v=> parseInt(v.trim()) || 0);
            const max = Math.max(...vals, 100);
            let bars = vals.map((v, i) => `<rect x="${i*35}" y="${100 - (v/max)*100}" width="25" height="${(v/max)*100}" fill="#0ea5e9"><title>${v}</title></rect><text x="${i*35 + 12}" y="95" fill="white" font-size="10" text-anchor="middle">${v}</text>`).join('');
            return `<div class="chart-container my-2" style="background:rgba(0,0,0,0.5); padding:10px; border-radius:8px;"><svg viewBox="0 0 ${Math.max(vals.length*35, 100)} 100" width="100%" height="80">${bars}</svg></div>`;
        });

        // 5. Copiable Bash/Shell Blocks
        parsedText = parsedText.replace(/```(?:bash|sh|cmd)\n([\s\S]*?)```/g, (match, code) => {
            const b64 = btoa(unescape(encodeURIComponent(code.trim())));
            return `<div style="position:relative; margin-top: 10px;">
                <button onclick="navigator.clipboard.writeText(decodeURIComponent(escape(atob('${b64}')))); this.innerHTML='<i class=\\'fas fa-check\\'></i>'" class="btn btn-xs btn-outline-info" style="position:absolute; top:5px; right:5px; z-index:10;"><i class="fas fa-copy"></i></button>
                <pre><code>${code}</code></pre>
            </div>`;
        });

        // PDF Export
        if (parsedText.includes("[ACTION: EXPORT_PDF]")) {
            parsedText = parsedText.replace(/\[ACTION: EXPORT_PDF\]/g, "");
            parsedText += `<br><button class="btn btn-sm btn-primary mt-2" onclick="window.print()"><i class="fas fa-file-pdf"></i> Imprimer Rapport d'Intervention</button>`;
        }

        // Clean out internal tags
        parsedText = parsedText.replace(/\[SEVERITY:.*?\]/g, "");

        // Default parsing for remaining code that wasn't bash or yaml
        parsedText = parsedText.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
        parsedText = parsedText.replace(/`([^`]+)`/g, '<code>$1</code>');
        parsedText = parsedText.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        parsedText = parsedText.replace(/\n/g, '<br>');

        div.innerHTML = parsedText;

        if (commandToRun) {
            div.innerHTML += `<br><button class="btn btn-sm btn-epic mt-2" onclick="executeAICommand('${btoa(unescape(encodeURIComponent(commandToRun)))}', this)"><i class="fas fa-play"></i> Exécuter '${commandToRun.substring(0,25)}...'</button>`;
        }

        // Faux Typewriter effect for matrix mode: Apparition progressive (dé-scramble)
        if(matrixMode && role === 'oracle') {
            div.style.opacity = '0';
            setTimeout(() => { div.style.transition='opacity 0.5s'; div.style.opacity='1'; }, 100);
        }

        messages.insertBefore(div, typing);
        scrollToBottom();
        
        // Save to History (sans le typing indicator)
        const cln = messages.cloneNode(true);
        const typTmp = cln.querySelector("#oracle-typing");
        if(typTmp) typTmp.remove();
        localStorage.setItem("oracleHistory", cln.innerHTML);
    }

    window.downloadYaml = (base64Str, filename) => {
        const text = decodeURIComponent(escape(atob(base64Str)));
        const blob = new Blob([text], { type: 'text/yaml' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
    };

    // decode bas64 safe
    window.btoa = window.btoa || function(str) { return str; };
    window.atob = window.atob || function(str) { return str; };
    
    // Override execute function to decode safely
    const originalExecute = window.executeAICommand;
    window.executeAICommand = async (b64Cmd, btnEl) => {
        let actualCmd = decodeURIComponent(escape(atob(b64Cmd)));
        originalExecute(actualCmd, btnEl);
    };

    function scrollToBottom() {
        messages.scrollTop = messages.scrollHeight;
    }

    function getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
});
