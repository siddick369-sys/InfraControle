import sys

with open('monitoring/ssh_utils.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False

for line in lines:
    if line.startswith('def collecter_performance_ssh(equipement):'):
        skip = True
        
        new_code = '''def get_os_type(client):
    """Detects if the remote OS is Windows or Linux"""
    out = exec_cmd(client, "uname")
    if "Linux" in out or "Darwin" in out:
        return "linux"
    
    out_win = exec_cmd(client, "cmd.exe /c ver")
    if "Windows" in out_win:
        return "windows"
        
    return "unknown"

def collecter_performance_windows_ssh(client, equipement, metrics):
    """Collecte les métriques de performance sur Windows via PowerShell"""
    try:
        out_cpu = exec_cmd(client, 'powershell -Command "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"')
        if out_cpu and out_cpu.isdigit():
            metrics['cpu_usage'] = float(out_cpu)
            metrics['cpu_load_1m'] = float(out_cpu) / 100.0

        out_ram = exec_cmd(client, 'powershell -Command "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory | ConvertTo-Json"')
        import json
        if out_ram and "{" in out_ram:
            try:
                ram_data = json.loads(out_ram)
                total_kb = float(ram_data.get("TotalVisibleMemorySize", 0))
                free_kb = float(ram_data.get("FreePhysicalMemory", 0))
                if total_kb > 0:
                    used_kb = total_kb - free_kb
                    metrics['ram_total_mb'] = total_kb / 1024
                    metrics['ram_used_mb'] = used_kb / 1024
                    metrics['ram_usage'] = round((used_kb / total_kb) * 100, 1)
            except Exception as e:
                logger.error(f"[SSH Windows] Erreur lecture RAM: {e}")

        out_disk = exec_cmd(client, 'powershell -Command "Get-CimInstance Win32_LogicalDisk -Filter \\"DeviceID=\'C:\'\\" | Select-Object Size, FreeSpace | ConvertTo-Json"')
        if out_disk and "{" in out_disk:
            try:
                disk_data = json.loads(out_disk)
                total_b = float(disk_data.get("Size", 0))
                free_b = float(disk_data.get("FreeSpace", 0))
                if total_b > 0:
                    used_b = total_b - free_b
                    metrics['disk_usage'] = round((used_b / total_b) * 100, 1)
            except Exception as e:
                logger.error(f"[SSH Windows] Erreur lecture Disque: {e}")

        out_uptime = exec_cmd(client, 'powershell -Command "(New-TimeSpan -Start (Get-CimInstance Win32_OperatingSystem).LastBootUpTime -End (Get-Date)).TotalSeconds"')
        if out_uptime:
            try:
                metrics['uptime_seconds'] = int(float(out_uptime.replace(',', '.')))
            except:
                pass

        equipement.statut = 'en ligne'
        equipement.derniere_verification = timezone.now()
        equipement.cpu_usage = metrics['cpu_usage']
        equipement.ram_usage = metrics['ram_usage']
        equipement.save()
        
        logger.info(f"[SSH Windows] Succes {equipement.adresse_ip}")
        return metrics

    except Exception as e:
        logger.error(f"[SSH Windows] Echec {equipement.adresse_ip}: {e}")
        return metrics

def collecter_performance_linux_ssh(client, equipement, metrics):
    """Collecte TOUTES les métriques Linux pour StatReseau"""
    try:
        out = exec_cmd(client, "cat /proc/loadavg")
        if out:
            parts = out.split()
            metrics['cpu_load_1m'] = float(parts[0])
            metrics['cpu_load_5m'] = float(parts[1])
            
        out = exec_cmd(client, "grep 'cpu ' /proc/stat")
        if out:
            metrics['cpu_usage'] = metrics.get('cpu_load_1m', 0) * 10
            
        out = exec_cmd(client, "free -m")
        if out:
            for line in out.splitlines():
                if "Mem:" in line:
                    p = line.split()
                    total, used = int(p[1]), int(p[2])
                    metrics['ram_total_mb'] = total
                    metrics['ram_used_mb'] = used
                    metrics['ram_usage'] = round((used/total)*100, 1)

        out = exec_cmd(client, "df -P / | tail -1")
        if out:
            p = out.split()
            for x in p:
                if "%" in x: metrics['disk_usage'] = float(x.replace("%",""))
        
        out = exec_cmd(client, "df -Pi / | tail -1")
        if out:
            p = out.split()
            for x in p:
                if "%" in x: metrics['inode_usage'] = float(x.replace("%",""))

        cmd_disk = "cat /proc/diskstats | grep -E 'sd|vd|nvme' | head -1"
        cmd_net = "cat /proc/net/dev | grep -v Lo | sort -k2 -nr | head -1"
        
        t1 = time.time()
        d1_io = exec_cmd(client, cmd_disk).split()
        d1_net = exec_cmd(client, cmd_net).replace(":", " ").split()
        
        time.sleep(2)
        
        t2 = time.time()
        d2_io = exec_cmd(client, cmd_disk).split()
        d2_net = exec_cmd(client, cmd_net).replace(":", " ").split()
        
        delta_t = t2 - t1
        
        if d1_io and d2_io and len(d1_io)>10 and len(d2_io)>10:
            r1, w1 = int(d1_io[5]), int(d1_io[9])
            r2, w2 = int(d2_io[5]), int(d2_io[9])
            metrics['disk_read_mb'] = round(((r2-r1)*512/1048576)/delta_t, 2)
            metrics['disk_write_mb'] = round(((w2-w1)*512/1048576)/delta_t, 2)

        if d1_net and d2_net and len(d1_net)>10:
            rx1, tx1 = int(d1_net[1]), int(d1_net[9])
            rx2, tx2 = int(d2_net[1]), int(d2_net[9])
            
            metrics['bandwidth_in_mbps'] = round(((rx2-rx1)*8/1000000)/delta_t, 2)
            metrics['bandwidth_out_mbps'] = round(((tx2-tx1)*8/1000000)/delta_t, 2)
            
            metrics['errors_in'] = int(d2_net[3])
            metrics['drops_in'] = int(d2_net[4])
            metrics['errors_out'] = int(d2_net[11])
            metrics['drops_out'] = int(d2_net[12])

        out = exec_cmd(client, "cat /proc/uptime")
        if out: metrics['uptime_seconds'] = int(float(out.split()[0]))

        equipement.statut = 'en ligne'
        equipement.derniere_verification = timezone.now()
        equipement.cpu_usage = metrics['cpu_usage']
        equipement.ram_usage = metrics['ram_usage']
        equipement.save()
        
        logger.info(f"[SSH Linux] Succes {equipement.adresse_ip}")
        return metrics

    except Exception as e:
        logger.error(f"[SSH Linux] Echec global {equipement.adresse_ip}: {e}")
        return metrics

def collecter_performance_ssh(equipement):
    """Fonction principale de collecte de performance cross-platform"""
    metrics = {
        "cpu_usage": None, "cpu_load_1m": None, "cpu_load_5m": None,
        "ram_usage": None, "ram_total_mb": None, "ram_used_mb": None,
        "disk_usage": None, "inode_usage": None,
        "disk_read_mb": 0.0, "disk_write_mb": 0.0,
        "bandwidth_in_mbps": 0.0, "bandwidth_out_mbps": 0.0,
        "drops_in": 0, "drops_out": 0,
        "errors_in": 0, "errors_out": 0,
        "uptime_seconds": 0
    }
    
    client = None
    try:
        client = get_ssh_client(equipement)
        os_type = get_os_type(client)
        
        if os_type == "windows":
            return collecter_performance_windows_ssh(client, equipement, metrics)
        elif os_type == "linux":
            return collecter_performance_linux_ssh(client, equipement, metrics)
        else:
            logger.warning(f"[SSH] OS inconnu pour {equipement.adresse_ip}. Fallback sur Linux.")
            return collecter_performance_linux_ssh(client, equipement, metrics)

    except Exception as e:
        logger.error(f"[SSH] Echec connexion/collecte {equipement.adresse_ip}: {e}")
        return metrics
    finally:
        if client: client.close()

'''
        new_lines.append(new_code)
        continue
        
    if skip and line.startswith('def ssh_connect(equipement):'):
        skip = False

    if not skip:
        new_lines.append(line)

with open('monitoring/ssh_utils.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
