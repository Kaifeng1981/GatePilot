import sys
import os
import json
import time
import ctypes
import subprocess
import psutil
import re
import ipaddress
import winreg
import logging
import urllib.request
import datetime
import csv
import io

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QListWidget, QGroupBox, QSystemTrayIcon, QMenu,
                             QMessageBox, QRadioButton, QComboBox, QCheckBox, 
                             QGridLayout, QAbstractItemView, QListWidgetItem,
                             QDialog, QSizePolicy, QFileDialog, QStyle, QTabWidget, QTextBrowser)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor

# ================= [ Infra ] 基础环境与全局配置 =================
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

def get_res_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(APP_DIR, relative_path)

CREATE_NO_WINDOW = 0x08000000
TASK_NAME = "GatePilot_AutoStart"
SETTINGS_FILE = os.path.join(APP_DIR, "gatepilot_settings.json")
RULES_FILE = os.path.join(APP_DIR, "gatepilot_rules.json")
LOG_FILE = os.path.join(APP_DIR, "gatepilot.log")

# ================= [ Infra ] 专业日志系统 (防无窗模式闪退装甲) =================
log_handlers = [logging.FileHandler(LOG_FILE, encoding='utf-8')]
if sys.stdout is not None:
    log_handlers.append(logging.StreamHandler(sys.stdout))
elif sys.stderr is not None:
    log_handlers.append(logging.StreamHandler(sys.stderr))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger("GatePilot")

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def is_valid_ip(ip_str):
    if not ip_str: return False
    try: ipaddress.ip_address(ip_str.strip()); return True
    except: return False

def decode_cmd(raw_bytes):
    try: return raw_bytes.decode('gbk')
    except UnicodeDecodeError: return raw_bytes.decode('utf-8', errors='ignore')

def is_time_in_range(time_str):
    if not time_str or "-" not in time_str: return True
    try:
        start_str, end_str = time_str.split('-')
        now = datetime.datetime.now().time()
        start = datetime.datetime.strptime(start_str.strip(), "%H:%M").time()
        end = datetime.datetime.strptime(end_str.strip(), "%H:%M").time()
        if start <= end: return start <= now <= end
        else: return start <= now or now <= end
    except: return True

# ================= [ Core ] 国际化系统 =================
CURRENT_LANG = "zh"
EN_DICT = {
    "GatePilot V1.0": "GatePilot V1.0",
    "日志": "Log", "帮助": "Help", "使用帮助": "User Guide",
    "状态：自动引擎已关闭，等待手动操作": "Status: Auto Engine OFF, standing by.",
    "状态：自动引擎 [运行中]，多网卡同步监控中...": "Status: Auto Engine [ON], Multi-Adapter monitoring...",
    "网络规则 (选中后应用 / 双击修改)": "Network Rules (Select/Double-click)",
    "新建": "Add", "删除": "Del", "编辑": "Edit", "规则详情设置": "Rule Editor",
    "1. 规则触发条件 (自动模式下生效)": "1. Trigger Conditions (Auto Mode)",
    "规则命名:": "Rule Name:", "生效网卡:": "Target Adapter:", "任意网卡": "Any Adapter",
    "当连入 WiFi:": "When WiFi SSID:", "留空则任意WiFi生效": "Leave blank for any WiFi",
    "且运行程序:": "And Process Running:", "如 xunlei.exe，留空则忽略": "e.g. app.exe, blank to ignore",
    "生效时间段:": "Time Range:", "如 09:00-18:00，留空全天有效": "e.g. 09:00-18:00, blank for 24/7",
    "2. 执行网络配置 (自动或手动应用生效)": "2. Network Config (Auto/Manual)",
    "自动获取 (DHCP)": "Auto (DHCP)", "静态 IP": "Static IP",
    "本机 IP:": "Local IP:", "公网 IP:": "Public IP:", "网关:": "Gateway:", "DNS:": "DNS:",
    "触发附加动作:": "Trigger Action:", "切换成功后自动运行(可选)": "Run exe/bat on success (optional)",
    "保存设置": "Save", "取消": "Cancel", "手动应用 [选中规则]": "Manual Apply",
    "开启自动规则调度引擎": "Start Auto Engine", "停止自动规则调度引擎": "Stop Auto Engine",
    "开机自动启动": "Auto Start", "打开时自动运行引擎": "Auto-Run Engine on Launch",
    "实时网络状态:": "Real-time Network Status:",
    "当前网络状态：等待刷新...": "Network Status: Waiting for refresh...",
    "刷新": "Refresh", "新规则": "New Rule", 
    "默认自动获取": "Default DHCP", "系统级保底规则，禁止修改或删除！": "System fallback rule, cannot be modified or deleted!",
    "外网:": "Internet:", "延迟": "ms", "离线": "Offline", "检测中...": "Checking...",
    "警告": "Warning", "提示": "Info", "错误": "Error", "成功": "Success",
    "显示主界面": "Show Main Window", "彻底退出": "Quit", "ms": "ms", "获取中...": "Fetching...",
    "请选择目标程序 (已过滤核心进程):": "Select Target App (filtered core procs):", "确定": "Confirm",
    "自动触发:": "Auto switched to:", "自动引擎已开启，后台监控中...": "Auto Engine started, monitoring...",
    "自动引擎已停止，切换为手动模式": "Auto Engine stopped, manual mode.",
    "请先选择要操作的网卡！": "Please select a target adapter first!",
    "该规则绑定了特定网卡【{}】，已自动为其下发配置！": "Rule bound to adapter [{}], config applied!"
}

def tr(zh_text):
    if CURRENT_LANG == "en":
        for k, v in EN_DICT.items():
            if zh_text == k: return v
        res = zh_text
        for k, v in EN_DICT.items():
            if len(k) > 2: res = res.replace(k, v)
        return res
    return zh_text

class RuleListWidget(QListWidget):
    def dropEvent(self, event):
        super().dropEvent(event)
        for i in range(self.count()):
            item = self.item(i)
            r = item.data(Qt.UserRole)
            if r and r.get("name") in ["默认自动获取", "Default DHCP"]:
                if i != 0:
                    taken = self.takeItem(i)
                    self.insertItem(0, taken)
                break

# ================= [ OS_HAL ] 硬件抽象层 =================
class WindowsNetAdapter:
    _adapter_mapping_cache = {}
    _adapter_mapping_last_update = 0

    @staticmethod
    def get_adapter_mapping(force_refresh=False):
        now = time.time()
        if not force_refresh and WindowsNetAdapter._adapter_mapping_cache and (now - WindowsNetAdapter._adapter_mapping_last_update < 30):
            return WindowsNetAdapter._adapter_mapping_cache
        
        visible_names = []
        try:
            raw = decode_cmd(subprocess.check_output(['netsh', 'interface', 'show', 'interface'], creationflags=CREATE_NO_WINDOW))
            for line in raw.split('\n'):
                parts = re.split(r'\s{2,}', line.strip())
                if len(parts) >= 4 and parts[-1] not in ['接口名称', 'Interface']:
                    name = parts[-1]
                    if "蓝牙" not in name and "Bluetooth" not in name and "VMware" not in name:
                        if name not in visible_names:
                            visible_names.append(name)
        except Exception as e:
            logger.error(f"Failed to get visible interfaces: {e}")

        desc_map = {}
        try:
            cmd = "Get-NetAdapter | ForEach-Object { $_.Name + '|||' + $_.InterfaceDescription }"
            raw = decode_cmd(subprocess.check_output(['powershell', '-NoProfile', '-Command', cmd], creationflags=CREATE_NO_WINDOW))
            for line in raw.split('\n'):
                if '|||' in line:
                    name, desc = line.split('|||', 1)
                    name, desc = name.strip(), desc.strip()
                    desc_map[name] = desc
        except Exception as e:
            logger.debug(f"PowerShell adapter query failed: {e}")

        if not desc_map:
            try:
                raw = decode_cmd(subprocess.check_output(['getmac', '/v', '/fo', 'csv'], creationflags=CREATE_NO_WINDOW))
                reader = csv.reader(io.StringIO(raw))
                next(reader, None) 
                for row in reader:
                    if len(row) >= 2:
                        name, desc = row[0].strip(), row[1].strip()
                        if name and name != "Connection Name":
                            desc_map[name] = desc
            except Exception as e:
                logger.debug(f"Getmac fallback failed: {e}")

        mapping = {}
        for name in visible_names:
            desc = desc_map.get(name, name)
            if "Loopback" not in desc and "Virtual" not in desc_map.get(name, ""):
                mapping[name] = desc
                
        if mapping:
            WindowsNetAdapter._adapter_mapping_cache = mapping
            WindowsNetAdapter._adapter_mapping_last_update = now
            
        return mapping

    @staticmethod
    def get_interfaces():
        return list(WindowsNetAdapter.get_adapter_mapping().keys())

    @staticmethod
    def get_interfaces_formatted():
        mapping = WindowsNetAdapter.get_adapter_mapping()
        res = []
        for name, desc in mapping.items():
            if name == desc: res.append(name)
            else: res.append(f"{name} [{desc}]")
        return res

    @staticmethod
    def get_current_ssid():
        try:
            raw = decode_cmd(subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces'], creationflags=CREATE_NO_WINDOW))
            for line in raw.split('\n'):
                if 'SSID' in line and 'BSSID' not in line:
                    parts = line.split(':')
                    if len(parts) > 1: return parts[1].strip()
            return ""
        except: return ""

    @staticmethod
    def get_status_dict(adapter):
        net_path = r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}"
        tcpip_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
        def clean_val(val):
            if isinstance(val, list): return str(val[0]) if val else ""
            if isinstance(val, str) and val.strip(): return val.strip()
            return ""
            
        res = {"ip": "", "gw": "", "dns": ""}
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, net_path) as net_key:
                num_adapters = winreg.QueryInfoKey(net_key)[0]
                for i in range(num_adapters):
                    guid = winreg.EnumKey(net_key, i)
                    try:
                        with winreg.OpenKey(net_key, f"{guid}\\Connection") as conn_key:
                            name = winreg.QueryValueEx(conn_key, "Name")[0]
                            if name == adapter:
                                try:
                                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, f"{tcpip_path}\\{guid}") as if_key:
                                        try: is_dhcp = winreg.QueryValueEx(if_key, "EnableDHCP")[0]
                                        except: is_dhcp = 0
                                        if is_dhcp == 1:
                                            try: ip_raw = winreg.QueryValueEx(if_key, "DhcpIPAddress")[0]
                                            except: ip_raw = ""
                                            try: gw_raw = winreg.QueryValueEx(if_key, "DhcpDefaultGateway")[0]
                                            except: gw_raw = ""
                                        else:
                                            try: ip_raw = winreg.QueryValueEx(if_key, "IPAddress")[0]
                                            except: ip_raw = ""
                                            try: gw_raw = winreg.QueryValueEx(if_key, "DefaultGateway")[0]
                                            except: gw_raw = ""
                                        try: static_dns = winreg.QueryValueEx(if_key, "NameServer")[0]
                                        except: static_dns = ""
                                        try: dhcp_dns = winreg.QueryValueEx(if_key, "DhcpNameServer")[0]
                                        except: dhcp_dns = ""
                                        
                                        ip_c = clean_val(ip_raw); gw_c = clean_val(gw_raw)
                                        dns_c = clean_val(static_dns if (isinstance(static_dns, str) and static_dns.strip()) else dhcp_dns).replace(" ", ", ")

                                        if ip_c and ip_c != "0.0.0.0": res["ip"] = ip_c
                                        if gw_c and gw_c != "0.0.0.0": res["gw"] = gw_c
                                        if dns_c: res["dns"] = dns_c
                                except FileNotFoundError: pass
                                break  
                    except OSError: pass
        except Exception: pass

        if not res["ip"] or not res["gw"]:
            try:
                raw_ip = decode_cmd(subprocess.check_output(['netsh', 'interface', 'ip', 'show', 'address', f'name={adapter}'], creationflags=CREATE_NO_WINDOW))
                ip_match = re.search(r'IP(?:v4)? (?:地址|Address):\s*([\d\.]+)', raw_ip)
                gw_match = re.search(r'(?:默认网关|Default Gateway):\s*([\d\.]+)', raw_ip)
                if ip_match and not res["ip"]: res["ip"] = ip_match.group(1)
                if gw_match and not res["gw"]: res["gw"] = gw_match.group(1)
            except: pass
            
        if not res["dns"]:
            try:
                raw_dns = decode_cmd(subprocess.check_output(['netsh', 'interface', 'ip', 'show', 'dns', f'name={adapter}'], creationflags=CREATE_NO_WINDOW))
                dns_ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', raw_dns)
                for d in dns_ips:
                    if d != "127.0.0.1": 
                        res["dns"] = d; break
            except: pass

        if res["ip"] and res["ip"].startswith("169.254"): res["ip"] = f"<span style='color:#EA580C;'>{tr('获取中...')}</span>"
        res["ip"] = res["ip"] or "未获取"; res["gw"] = res["gw"] or "未获取"; res["dns"] = res["dns"] or "未获取"
        return res

    @staticmethod
    def apply_atomic(adapter, target_conf):
        if not adapter: return False
        logger.info(f"Applying config to adapter [{adapter}]: {target_conf}")
        try:
            subprocess.run(f'powershell -Command "Clear-DnsClientCache"', shell=True, creationflags=CREATE_NO_WINDOW)
            subprocess.run(f'powershell -Command "Set-DnsClientServerAddress -InterfaceAlias \'{adapter}\' -ResetServerAddresses"', shell=True, creationflags=CREATE_NO_WINDOW)
            time.sleep(1.0) 
            
            if target_conf['mode'] == 'dhcp':
                subprocess.run(f'netsh interface ipv4 set dnsservers name="{adapter}" source=dhcp', shell=True, creationflags=CREATE_NO_WINDOW)
                time.sleep(0.5)
                subprocess.run(f'netsh interface ipv4 set address name="{adapter}" source=dhcp', shell=True, creationflags=CREATE_NO_WINDOW)
            else:
                ip, gw, dns = target_conf.get('ip',''), target_conf.get('gateway',''), target_conf.get('dns','')
                subprocess.run(f'netsh interface ipv4 set address name="{adapter}" source=static address={ip} mask=255.255.255.0 gateway={gw}', shell=True, creationflags=CREATE_NO_WINDOW)
                time.sleep(0.5)
                if dns: subprocess.run(f'netsh interface ipv4 set dnsservers name="{adapter}" source=static address={dns} register=primary validate=no', shell=True, creationflags=CREATE_NO_WINDOW)
                else: subprocess.run(f'netsh interface ipv4 set dnsservers name="{adapter}" source=dhcp', shell=True, creationflags=CREATE_NO_WINDOW)
            logger.info("Configuration applied successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to apply configuration: {e}")
            return False

# ================= [ Logic & Control ] 综合网络监测 =================
class NetworkMonitor(QThread):
    net_info_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        last_pub_ip = tr("检测中...")
        loop_counter = 0
        
        while self.running:
            ping_html = f"<span style='color:#EF4444; font-weight:bold;'>{tr('离线')}</span>"
            try:
                result = subprocess.run(['ping', '-n', '1', '-w', '1000', '223.5.5.5'], capture_output=True, creationflags=CREATE_NO_WINDOW)
                raw = decode_cmd(result.stdout)
                match = re.search(r'([<>=])\s*(\d+)\s*ms', raw, re.IGNORECASE)
                if result.returncode == 0 and match:
                    ms = int(match.group(2))
                    if match.group(1) == '<': ms = 0
                    color = "#10B981" if ms < 50 else "#F59E0B" if ms < 150 else "#EF4444"
                    ping_html = f"<span style='color:{color}; font-weight:bold;'>{ms} {tr('ms')}</span>"
            except: pass

            if loop_counter % 5 == 0:
                try:
                    req = urllib.request.Request('https://api.ipify.org', headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=2) as response:
                        last_pub_ip = response.read().decode('utf-8').strip()
                except:
                    last_pub_ip = f"<span style='color:#EF4444;'>{tr('离线')}</span>"
            
            loop_counter += 1
            self.net_info_signal.emit(ping_html, last_pub_ip)
            
            for _ in range(30):
                if not self.running: break
                time.sleep(0.1)

    def stop(self):
        self.running = False
        self.wait()

# ================= [ Logic & Control ] 全境多网卡并发引擎 =================
class DaemonController(QThread):
    status_signal = pyqtSignal(str)
    active_rule_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, rules):
        super().__init__()
        self.rules = rules
        self.running = True
        self.last_applied_rules = {} 
        logger.info(f"Multi-Adapter Auto Engine started. Rules loaded: {len(self.rules)}")

    def run(self):
        while self.running:
            try:
                mapping = WindowsNetAdapter.get_adapter_mapping()
                interfaces = list(mapping.keys())
                curr_ssid = WindowsNetAdapter.get_current_ssid().lower()
                
                running_procs = set()
                for p in psutil.process_iter(['name', 'exe']):
                    try:
                        if p.info.get('name'): running_procs.add(p.info['name'].lower())
                        if p.info.get('exe'): running_procs.add(p.info['exe'].lower())
                    except: pass
                
                fallback_rule = None
                for r in self.rules:
                    if r["name"] in ["默认自动获取", "Default DHCP"]:
                        fallback_rule = r; break

                for adapter in interfaces:
                    live_desc = mapping.get(adapter, "")
                    matched_rule = None
                    
                    for r in self.rules:
                        if r["name"] in ["默认自动获取", "Default DHCP"]: continue
                            
                        target_adapter = r.get("adapter_match", "任意网卡")
                        if target_adapter not in ["任意网卡", "Any Adapter"]:
                            saved_desc = ""
                            if " [" in target_adapter and target_adapter.endswith("]"):
                                saved_desc = target_adapter.split(" [")[1][:-1]
                            
                            match_success = False
                            if saved_desc and saved_desc == live_desc: match_success = True
                            elif target_adapter.startswith(adapter + " [") or target_adapter == adapter: match_success = True
                            
                            if not match_success: continue 
                            
                        r_ssid = r.get("ssid", "").strip().lower()
                        r_exe = r.get("exe", "").strip().lower()
                        r_time = r.get("time_range", "").strip()
                        
                        ssid_ok = (not r_ssid) or (r_ssid in curr_ssid)
                        exe_ok = (not r_exe) or any(r_exe in proc for proc in running_procs)
                        time_ok = is_time_in_range(r_time)
                        
                        if ssid_ok and exe_ok and time_ok:
                            matched_rule = r
                            break 
                            
                    if not matched_rule:
                        matched_rule = fallback_rule
                            
                    if matched_rule and self.last_applied_rules.get(adapter) != matched_rule["name"]:
                        logger.info(f"Adapter [{adapter}] triggered rule: {matched_rule['name']}")
                        success = WindowsNetAdapter.apply_atomic(adapter, matched_rule["net"])
                        if success:
                            self.last_applied_rules[adapter] = matched_rule["name"]
                            self.active_rule_signal.emit(matched_rule["name"])
                            self.status_signal.emit(f"【{adapter}】 ➡️ 【{matched_rule['name']}】")
                            
                            action_exe = matched_rule.get("action_exe", "").strip()
                            if action_exe and os.path.exists(action_exe):
                                try: os.startfile(action_exe) 
                                except Exception as ex: logger.error(f"Action failed: {ex}")
            except Exception as e:
                logger.error(f"Engine exception: {e}")
            
            for _ in range(30):
                if not self.running: break
                time.sleep(0.1)

        self.finished_signal.emit()

    def stop(self):
        logger.info("Stopping multi-adapter engine...")
        self.running = False
        self.wait()

# ================= [ View ] 对话框组件 =================
class ProcessPicker(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("从运行中选择"))
        self.setFixedSize(500, 450)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet("""
            QDialog { background-color: #F3F4F6; font-family: "Microsoft YaHei"; font-size: 9pt; color: #1F2937; }
            QLabel { font-weight: bold; color: #374151; }
            QListWidget { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 4px; outline: none; }
            QListWidget::item { padding: 8px; border-radius: 4px; color: #4B5563; }
            QListWidget::item:hover { background: #F9FAFB; }
            QListWidget::item:selected { background: #EFF6FF; color: #1D4ED8; font-weight: bold; }
            QPushButton { background-color: #2563EB; color: white; border: none; border-radius: 6px; padding: 8px 15px; font-weight: bold; }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(QLabel(tr("请选择目标程序 (已过滤核心进程):")))
        layout.addWidget(self.list_widget)
        
        procs_dict = {}
        for p in psutil.process_iter(['name', 'exe']):
            name, exe_path = p.info.get('name'), p.info.get('exe')
            if name and exe_path and name.lower() not in ['svchost.exe', 'conhost.exe', 'explorer.exe', 'idle', 'python.exe', 'system', 'registry']:
                procs_dict[exe_path] = name
        for exe_path, name in sorted(procs_dict.items(), key=lambda item: item[1]):
            item = QListWidgetItem(f"{name}   ({exe_path})")
            item.setData(Qt.UserRole, exe_path) 
            self.list_widget.addItem(item)
            
        btn = QPushButton(tr("确定"))
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_selected(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item else None

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("使用帮助"))
        self.setFixedSize(480, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet("""
            QDialog { background-color: #FFFFFF; font-family: "Microsoft YaHei"; font-size: 9.5pt; color: #1F2937; }
            QPushButton { background-color: #10B981; color: white; border-radius: 6px; padding: 8px 15px; font-weight: bold; }
            QPushButton:hover { background-color: #059669; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        
        text_label = QLabel()
        text_label.setWordWrap(True)
        if CURRENT_LANG == "zh":
            help_text = "<b>欢迎使用 GatePilot V1.0</b><br><br>" \
                        "这是一款帮您自动无缝切换网络配置的智能助手。<br><br>" \
                        "<b>💡 核心功能：</b><br>" \
                        "1. <b>多网卡独立管理</b>：您可以为无线网卡（WLAN）和有线网卡（以太网）分别设置不同的规则，软件会在后台同时管理它们，互不干扰。<br>" \
                        "2. <b>精准触发</b>：支持按【物理网卡】、【WiFi名称】、【运行软件】、【时间段】四个条件组合，实现精准自动切换。<br>" \
                        "3. <b>业务联动</b>：支持在切换 IP 后，自动帮您打开指定的业务软件或脚本。<br>" \
                        "4. <b>保底防断网</b>：当所有条件都不满足时，对应的网卡会自动切回【默认自动获取 DHCP】，保证随时有网。<br><br>" \
                        "<b>🚀 优先级说明：</b><br>" \
                        "规则列表从上往下依次匹配，越靠上的规则优先级越高。请用鼠标拖拽，将最具体、最严格的规则放在最上面。"
        else:
            help_text = "<b>Welcome to GatePilot V1.0</b><br><br>" \
                        "A smart assistant to automatically switch your network configurations.<br><br>" \
                        "<b>💡 Core Features:</b><br>" \
                        "1. <b>Independent Adapters</b>: Set different rules for WLAN and Ethernet. The engine manages them simultaneously without interference.<br>" \
                        "2. <b>Precision Triggers</b>: Combine [Adapter], [SSID], [App], and [Time] for exact auto-switching.<br>" \
                        "3. <b>Action Hooks</b>: Automatically launch specific apps/scripts after a successful IP switch.<br>" \
                        "4. <b>Safe Fallback</b>: Adapters revert to 'Default DHCP' if no custom rules match, keeping you online.<br><br>" \
                        "<b>🚀 Rule Priority:</b><br>" \
                        "Rules are scanned from top to bottom. Drag your most specific rules to the top!"
        
        text_label.setText(help_text)
        text_label.setStyleSheet("line-height: 1.5;")
        layout.addWidget(text_label)
        
        layout.addStretch()
        btn = QPushButton(tr("确定"))
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

class RuleEditorDialog(QDialog):
    def __init__(self, parent, rule_data):
        super().__init__(parent)
        self.setWindowTitle(tr("规则详情设置"))
        self.setFixedSize(520, 760) 
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint) 
        self.rule_data = rule_data
        
        self.setStyleSheet("""
            QDialog { background-color: #FFFFFF; font-family: "Microsoft YaHei"; font-size: 9pt; color: #1F2937; }
            QGroupBox { background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; margin-top: 15px; padding-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; top: 0px; color: #111827; font-weight: bold; font-size: 9pt; }
            QLineEdit, QComboBox { border: 1px solid #D1D5DB; border-radius: 6px; padding: 6px 10px; background-color: #FFFFFF; min-height: 20px;}
            QLineEdit:focus, QComboBox:focus { border: 2px solid #3B82F6; }
            QPushButton.btn_save { background-color: #10B981; color: white; border-radius: 6px; padding: 8px 15px; font-weight: bold; font-size: 9pt; }
            QPushButton.btn_save:hover { background-color: #059669; }
            QPushButton.btn_cancel { background-color: #F3F4F6; color: #4B5563; border: 1px solid #D1D5DB; border-radius: 6px; padding: 8px 15px; font-weight: bold; font-size: 9pt;}
            QPushButton.btn_cancel:hover { background-color: #E5E7EB; }
            QPushButton.btn_ghost { background-color: transparent; border: 1px solid #D1D5DB; color: #4B5563; border-radius: 4px; padding: 4px 8px;}
            QPushButton.btn_ghost:hover { background-color: #E5E7EB; }
            QRadioButton { color: #374151; font-size: 9pt; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        g_cond = QGroupBox(tr("1. 规则触发条件 (自动模式下生效)"))
        l_cond = QGridLayout(g_cond)
        l_cond.setVerticalSpacing(12)
        l_cond.setContentsMargins(15, 20, 15, 15)
        l_cond.setColumnMinimumWidth(0, 95)
        l_cond.setColumnStretch(1, 1)

        self.in_name = QLineEdit(self.rule_data.get("name", ""))
        l_cond.addWidget(QLabel(tr("规则命名:")), 0, 0); l_cond.addWidget(self.in_name, 0, 1)
        
        self.combo_adapter = QComboBox()
        any_text = "任意网卡" if CURRENT_LANG == "zh" else "Any Adapter"
        opts = [any_text] + WindowsNetAdapter.get_interfaces_formatted()
        self.combo_adapter.addItems(opts)
        
        saved_adapter = self.rule_data.get("adapter_match", any_text)
        if saved_adapter in ["任意网卡", "Any Adapter"]: self.combo_adapter.setCurrentText(any_text)
        else: self.combo_adapter.setCurrentText(saved_adapter)
            
        l_cond.addWidget(QLabel(tr("生效网卡:")), 1, 0); l_cond.addWidget(self.combo_adapter, 1, 1)
        
        self.in_ssid = QLineEdit(self.rule_data.get("ssid", ""))
        self.in_ssid.setPlaceholderText(tr("留空则任意WiFi生效"))
        l_cond.addWidget(QLabel(tr("当连入 WiFi:")), 2, 0); l_cond.addWidget(self.in_ssid, 2, 1)
        
        self.in_exe = QLineEdit(self.rule_data.get("exe", ""))
        self.in_exe.setPlaceholderText(tr("如 xunlei.exe，留空则忽略"))
        btn_pick_exe = QPushButton("..."); btn_pick_exe.setProperty("class", "btn_ghost")
        btn_pick_exe.clicked.connect(self.pick_process)
        h_exe = QHBoxLayout(); h_exe.setContentsMargins(0,0,0,0); h_exe.setSpacing(5)
        h_exe.addWidget(self.in_exe); h_exe.addWidget(btn_pick_exe)
        l_cond.addWidget(QLabel(tr("且运行程序:")), 3, 0); l_cond.addLayout(h_exe, 3, 1)

        self.in_time = QLineEdit(self.rule_data.get("time_range", ""))
        self.in_time.setPlaceholderText(tr("如 09:00-18:00，留空全天有效"))
        l_cond.addWidget(QLabel(tr("生效时间段:")), 4, 0); l_cond.addWidget(self.in_time, 4, 1)
        layout.addWidget(g_cond)

        g_net = QGroupBox(tr("2. 执行网络配置 (自动或手动应用生效)"))
        l_net = QGridLayout(g_net)
        l_net.setVerticalSpacing(12)
        l_net.setContentsMargins(15, 20, 15, 15)
        l_net.setColumnMinimumWidth(0, 95)
        l_net.setColumnStretch(1, 1)

        self.rad_dhcp = QRadioButton(tr("自动获取 (DHCP)")); self.rad_static = QRadioButton(tr("静态 IP"))
        net = self.rule_data.get("net", {})
        if net.get("mode") == "static": self.rad_static.setChecked(True)
        else: self.rad_dhcp.setChecked(True)
        
        h_rad = QHBoxLayout()
        h_rad.addWidget(self.rad_dhcp); h_rad.addWidget(self.rad_static); h_rad.addStretch()
        l_net.addLayout(h_rad, 0, 0, 1, 2)
        
        self.in_ip = QLineEdit(net.get("ip", "")); l_net.addWidget(QLabel(tr("本机 IP:")), 1, 0); l_net.addWidget(self.in_ip, 1, 1)
        self.in_gw = QLineEdit(net.get("gateway", "")); l_net.addWidget(QLabel(tr("网关:")), 2, 0); l_net.addWidget(self.in_gw, 2, 1)
        self.in_dns = QLineEdit(net.get("dns", "")); l_net.addWidget(QLabel(tr("DNS:")), 3, 0); l_net.addWidget(self.in_dns, 3, 1)
        
        self.in_action = QLineEdit(self.rule_data.get("action_exe", ""))
        self.in_action.setPlaceholderText(tr("切换成功后自动运行(可选)"))
        btn_pick_file = QPushButton("📁"); btn_pick_file.setProperty("class", "btn_ghost")
        btn_pick_file.clicked.connect(self.pick_file)
        h_act = QHBoxLayout(); h_act.setContentsMargins(0,0,0,0); h_act.setSpacing(5)
        h_act.addWidget(self.in_action); h_act.addWidget(btn_pick_file)
        l_net.addWidget(QLabel(tr("触发附加动作:")), 4, 0); l_net.addLayout(h_act, 4, 1)

        layout.addWidget(g_net)

        self.rad_dhcp.toggled.connect(self.update_ui_state)
        self.rad_static.toggled.connect(self.update_ui_state)
        self.update_ui_state()
        
        layout.addStretch()

        h_btn = QHBoxLayout()
        btn_cancel = QPushButton(tr("取消")); btn_cancel.setProperty("class", "btn_cancel"); btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton(tr("保存设置")); btn_save.setProperty("class", "btn_save"); btn_save.clicked.connect(self.save_data)
        h_btn.addWidget(btn_cancel); h_btn.addWidget(btn_save)
        layout.addLayout(h_btn)

    def update_ui_state(self):
        is_static = self.rad_static.isChecked()
        self.in_ip.setEnabled(is_static); self.in_gw.setEnabled(is_static); self.in_dns.setEnabled(is_static)

    def pick_process(self):
        dialog = ProcessPicker(self)
        if dialog.exec_():
            path = dialog.get_selected()
            if path: self.in_exe.setText(os.path.basename(path))

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择可执行文件或脚本", "", "Programs/Scripts (*.exe *.bat *.cmd *.ps1 *.py);;All Files (*)")
        if path: self.in_action.setText(path.replace('/', '\\'))

    def save_data(self):
        mode = "static" if self.rad_static.isChecked() else "dhcp"
        if mode == "static":
            if not is_valid_ip(self.in_ip.text()) or not is_valid_ip(self.in_gw.text()):
                QMessageBox.critical(self, tr("错误"), tr("IP 格式错误"))
                return
        self.rule_data["name"] = self.in_name.text()
        self.rule_data["adapter_match"] = self.combo_adapter.currentText()
        self.rule_data["ssid"] = self.in_ssid.text()
        self.rule_data["exe"] = self.in_exe.text()
        self.rule_data["time_range"] = self.in_time.text()
        self.rule_data["action_exe"] = self.in_action.text()
        self.rule_data["net"] = {"mode": mode, "ip": self.in_ip.text().strip(), "gateway": self.in_gw.text().strip(), "dns": self.in_dns.text().strip()}
        self.accept()

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            main_geom = self.parent().geometry()
            screen_geom = QApplication.desktop().availableGeometry(self.parent())
            x = main_geom.right() + 10
            y = main_geom.top()
            if x + self.width() > screen_geom.right(): 
                x = main_geom.left() - self.width() - 10
            if y + self.height() > screen_geom.bottom(): 
                y = screen_geom.bottom() - self.height() - 10
            self.move(x, y)

# ================= [ View ] GatePilot 主界面 =================
class GatePilotV2(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("GatePilot V1.0"))
        
        self.setMinimumSize(580, 900)
        self.resize(600, 1000)
        
        logo_path = get_res_path("logo.ico")
        if os.path.exists(logo_path): self.setWindowIcon(QIcon(logo_path))
        
        self.auto_mode_on = False
        self.daemon = None
        self.net_monitor = None
        self.current_active_rule = ""
        self.current_ping_str = f"<span style='color:#9CA3AF;'>{tr('检测中...')}</span>"
        self.current_pub_ip_str = f"<span style='color:#9CA3AF;'>{tr('检测中...')}</span>"

        self.last_active_tab = ""
        self.auto_start_engine = False

        self.tray = None
        self.tray_menu = None
        self.tray_icon = None
        
        self.icon_active = self.create_dot_icon('#10B981')
        self.icon_inactive = self.create_dot_icon(None)

        self._load_global_settings()
        self.load_rules()
        self.init_ui()
        self.setup_tray()
        self.retranslate_ui()
        
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_network_status_ui)
        self.status_timer.start(3000)
        self.start_network_monitor()
        logger.info("GatePilot main window loaded successfully")

    def create_dot_icon(self, color_str):
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        if color_str:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor(color_str))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(3, 3, 10, 10)
            painter.end()
        return QIcon(pixmap)

    def start_network_monitor(self):
        self.net_monitor = NetworkMonitor()
        self.net_monitor.net_info_signal.connect(self.on_net_updated)
        self.net_monitor.start()

    def on_net_updated(self, ping_html, pub_ip_html):
        self.current_ping_str = ping_html
        self.current_pub_ip_str = pub_ip_html
        self.update_network_status_ui()

    def _load_global_settings(self):
        global CURRENT_LANG
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: 
                data = json.load(f)
                CURRENT_LANG = data.get("lang", "zh")
                self.last_active_tab = data.get("last_tab", "")
                self.auto_start_engine = data.get("auto_engine", False)
        except: pass

    def save_global_settings(self, lang=None, last_tab=None, auto_engine=None):
        global CURRENT_LANG
        if lang is not None: CURRENT_LANG = lang
        if last_tab is not None: self.last_active_tab = last_tab
        if auto_engine is not None: self.auto_start_engine = auto_engine
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f: 
                json.dump({"lang": CURRENT_LANG, "last_tab": self.last_active_tab, "auto_engine": self.auto_start_engine}, f)
        except: pass

    def load_rules(self):
        try:
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.rules_data = [r for r in data.get("rules", []) if r.get("name") not in ["默认自动获取", "Default DHCP"]]
        except:
            self.rules_data = []

    def save_rules(self):
        rules = []
        for i in range(self.list_rules.count()):
            r = self.list_rules.item(i).data(Qt.UserRole)
            if r and r["name"] not in ["默认自动获取", "Default DHCP"]:
                rules.append(r)
        data = {"adapter": "", "rules": rules} 
        try:
            with open(RULES_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save rules configuration: {e}")

    def init_ui(self):
        self.setStyleSheet("""
            QWidget { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; font-size: 9.5pt; color: #1F2937; background-color: #F3F4F6; }
            QPushButton { background-color: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 6px; padding: 6px 12px; color: #374151; font-weight: bold; }
            QPushButton:hover { background-color: #F9FAFB; border-color: #9CA3AF; }
            QPushButton.btn_ghost { background-color: transparent; border: none; color: #6B7280; padding: 4px; font-weight: bold; }
            QPushButton.btn_ghost:hover { background-color: #E5E7EB; color: #111827; border-radius: 6px; }
            QPushButton.btn_action { background-color: #F3F4F6; border: 1px solid #D1D5DB; border-radius: 6px; padding: 6px 12px;}
            QPushButton.btn_action:hover { background-color: #E5E7EB; }
            QPushButton.btn_manual { background: #EA580C; color: white; border: none; font-size: 10.5pt; padding: 12px; font-weight:bold; }
            QPushButton.btn_manual:hover { background: #C2410C; }
            QPushButton.btn_manual:disabled { background: #D1D5DB; color: #9CA3AF; } 
            QPushButton.btn_auto_on { background: #10B981; color: white; border: none; font-size: 10.5pt; padding: 12px; font-weight:bold; }
            QPushButton.btn_auto_on:hover { background: #059669; }
            QPushButton.btn_auto_off { background: #EF4444; color: white; border: none; font-size: 10.5pt; padding: 12px; font-weight:bold; }
            QPushButton.btn_auto_off:hover { background: #DC2626; }
            QListWidget { border: 1px solid #E5E7EB; border-radius: 8px; background-color: #FFFFFF; padding: 4px; outline: none; }
            QListWidget::item { padding: 12px; border-radius: 6px; color: #4B5563; border-bottom: 1px solid #F3F4F6; }
            QListWidget::item:hover { background: #F9FAFB; }
            QListWidget::item:selected { background-color: #EFF6FF; color: #1D4ED8; font-weight: bold; }
        """)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        h_top_1 = QHBoxLayout()
        self.lbl_radar_title = QLabel("<b>" + tr("实时网络状态:") + "</b>")
        self.b_ref = QPushButton(tr("刷新")); 
        self.b_ref.clicked.connect(lambda: [WindowsNetAdapter.get_adapter_mapping(force_refresh=True), self.update_network_status_ui(force_full=True)])
        self.b_lang = QPushButton("EN" if CURRENT_LANG == 'zh' else "CN")
        self.b_lang.setProperty("class", "btn_ghost")
        self.b_lang.clicked.connect(self.toggle_language)
        
        h_top_1.addWidget(self.lbl_radar_title); h_top_1.addStretch()
        h_top_1.addWidget(self.b_ref); h_top_1.addWidget(self.b_lang)
        layout.addLayout(h_top_1)

        self.global_status_lab = QLabel()
        self.global_status_lab.setStyleSheet("color: #1E3A8A; font-size: 9.5pt; background-color: #EFF6FF; padding: 12px; border-radius: 8px; border: 1px solid #BFDBFE;")
        layout.addWidget(self.global_status_lab)

        self.adapter_tabs = QTabWidget()
        self.adapter_tabs.setMinimumHeight(220) 
        self.adapter_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adapter_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #BFDBFE; border-radius: 4px; background: #FFFFFF; }
            QTabBar::tab { background: #F3F4F6; border: 1px solid #D1D5DB; padding: 6px 12px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #FFFFFF; border-bottom-color: #FFFFFF; font-weight: bold; color: #1D4ED8; }
            QTabBar::tab:hover { background: #E5E7EB; }
        """)
        self.adapter_tabs.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.adapter_tabs)

        self.lbl_rule_title = QLabel("<b>" + tr("网络规则 (选中后应用 / 双击修改)") + "</b>")
        layout.addWidget(self.lbl_rule_title)
        
        self.list_rules = RuleListWidget()
        self.list_rules.setMinimumHeight(300)
        self.list_rules.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.list_rules.setDragDropMode(QAbstractItemView.InternalMove)
        
        fallback_r = {"name": tr("默认自动获取"), "adapter_match": "任意网卡", "ssid": "", "exe": "", "time_range":"", "action_exe":"", "net": {"mode": "dhcp", "ip": "", "gateway": "", "dns": ""}}
        item_def = QListWidgetItem(fallback_r["name"])
        item_def.setData(Qt.UserRole, fallback_r)
        item_def.setIcon(self.icon_inactive)
        item_def.setFlags(item_def.flags() & ~Qt.ItemIsDragEnabled & ~Qt.ItemIsDropEnabled) 
        self.list_rules.addItem(item_def)
        
        for r in self.rules_data:
            item = QListWidgetItem(r["name"])
            item.setData(Qt.UserRole, r)
            item.setIcon(self.icon_inactive) 
            self.list_rules.addItem(item)
            
        self.list_rules.itemDoubleClicked.connect(self.edit_selected_rule)
        layout.addWidget(self.list_rules)
        
        h_list_btns = QHBoxLayout()
        self.btn_add = QPushButton(tr("新建")); self.btn_add.setProperty("class", "btn_action"); self.btn_add.clicked.connect(self.add_rule)
        self.btn_del = QPushButton(tr("删除")); self.btn_del.setProperty("class", "btn_action"); self.btn_del.clicked.connect(self.del_rule)
        self.btn_edit = QPushButton(tr("编辑")); self.btn_edit.setProperty("class", "btn_action"); self.btn_edit.clicked.connect(self.edit_selected_rule)
        h_list_btns.addWidget(self.btn_add); h_list_btns.addWidget(self.btn_del); h_list_btns.addWidget(self.btn_edit)
        layout.addLayout(h_list_btns)

        v_ctrl = QVBoxLayout()
        v_ctrl.setContentsMargins(0, 10, 0, 5)
        v_ctrl.setSpacing(10)
        
        self.btn_manual = QPushButton(tr("手动应用 [选中规则]"))
        self.btn_manual.setProperty("class", "btn_manual")
        self.btn_manual.clicked.connect(self.on_manual_apply)
        v_ctrl.addWidget(self.btn_manual)
        
        self.btn_auto = QPushButton(tr("开启自动规则调度引擎"))
        self.btn_auto.setProperty("class", "btn_auto_on")
        self.btn_auto.clicked.connect(self.toggle_auto_mode)
        v_ctrl.addWidget(self.btn_auto)
        layout.addLayout(v_ctrl)

        h_sys = QHBoxLayout()
        h_sys.setContentsMargins(5, 5, 5, 0)
        
        self.cb_autostart = QCheckBox(tr("开机自动启动"))
        self.cb_autostart.setStyleSheet("color: #6B7280;")
        self.cb_autostart.setChecked(self.check_autostart_status())
        self.cb_autostart.clicked.connect(self.toggle_autostart)
        
        self.cb_auto_engine = QCheckBox(tr("打开时自动运行引擎"))
        self.cb_auto_engine.setStyleSheet("color: #6B7280;")
        self.cb_auto_engine.setChecked(self.auto_start_engine)
        self.cb_auto_engine.clicked.connect(self.toggle_auto_engine_setting)
        
        self.b_help = QPushButton(tr("帮助")); self.b_help.setProperty("class", "btn_ghost"); self.b_help.clicked.connect(self.show_help)
        self.b_log = QPushButton(tr("日志")); self.b_log.setProperty("class", "btn_ghost"); self.b_log.clicked.connect(self.open_log_file)
        
        h_sys.addWidget(self.cb_autostart); h_sys.addWidget(self.cb_auto_engine)
        h_sys.addStretch()
        h_sys.addWidget(self.b_help); h_sys.addWidget(self.b_log)
        layout.addLayout(h_sys)
        
        if self.list_rules.count() > 0: self.list_rules.setCurrentRow(0)

    def toggle_auto_engine_setting(self, checked):
        self.auto_start_engine = checked
        self.save_global_settings(auto_engine=self.auto_start_engine)

    def show_help(self):
        dialog = HelpDialog(self)
        dialog.exec_()

    def setup_tray(self):
        if hasattr(self, 'tray') and self.tray:
            self.tray.hide()
            self.tray.deleteLater()
            
        icon_path = get_res_path("tray.ico")
        if not os.path.exists(icon_path): icon_path = get_res_path("logo.ico")
        if os.path.exists(icon_path): self.tray_icon = QIcon(icon_path)
        else: self.tray_icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)
            
        self.tray = QSystemTrayIcon(self.tray_icon, self)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray_menu = QMenu(self)
        self.tray.setContextMenu(self.tray_menu)
        self.rebuild_tray_menu()
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()
            self.activateWindow()

    def rebuild_tray_menu(self):
        if getattr(self, 'tray_menu', None) is None: return
        self.tray_menu.clear()
        self.tray_menu.addAction(tr("显示主界面"), self.showNormal)
        self.tray_menu.addSeparator()
        
        auto_text = tr("停止自动规则调度引擎") if self.auto_mode_on else tr("开启自动规则调度引擎")
        auto_action = self.tray_menu.addAction(auto_text)
        auto_action.triggered.connect(self.toggle_auto_mode)
        
        if not self.auto_mode_on:
            self.tray_menu.addSeparator()
            for i in range(self.list_rules.count()):
                r = self.list_rules.item(i).data(Qt.UserRole)
                if not r: continue
                name = r['name']
                action = self.tray_menu.addAction(name)
                if name == self.current_active_rule: action.setIcon(self.icon_active)
                else: action.setIcon(self.icon_inactive)
                action.triggered.connect(lambda checked, n=name: self.apply_rule_from_tray(n))
                
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(tr("彻底退出"), self.real_quit)

    def set_active_rule(self, rule_name):
        self.current_active_rule = rule_name
        for i in range(self.list_rules.count()):
            item = self.list_rules.item(i)
            r = item.data(Qt.UserRole)
            if not r: continue
            item.setText(r['name'])
            if r['name'] == rule_name: item.setIcon(self.icon_active)
            else: item.setIcon(self.icon_inactive)
        self.rebuild_tray_menu()

    def toggle_language(self):
        new_lang = "en" if CURRENT_LANG == "zh" else "zh"
        self.save_global_settings(lang=new_lang)

        old_default_name = "默认自动获取" if new_lang == "en" else "Default DHCP"
        new_default_name = "Default DHCP" if new_lang == "en" else "默认自动获取"

        for i in range(self.list_rules.count()):
            item = self.list_rules.item(i)
            r = item.data(Qt.UserRole)
            if r and r["name"] == old_default_name:
                r["name"] = new_default_name
                item.setData(Qt.UserRole, r)
        
        if self.current_active_rule == old_default_name:
            self.current_active_rule = new_default_name

        self.retranslate_ui()
        self.save_rules()

    def retranslate_ui(self):
        self.setWindowTitle(tr("GatePilot V1.0"))
        self.b_lang.setText("EN" if CURRENT_LANG == 'zh' else "CN")
        self.lbl_radar_title.setText(f"<b>{tr('实时网络状态:')}</b>")
        self.b_ref.setText(tr("刷新"))
        self.b_help.setText(tr("帮助"))
        self.b_log.setText(tr("日志"))
        self.lbl_rule_title.setText(f"<b>{tr('网络规则 (选中后应用 / 双击修改)')}</b>")
        self.btn_add.setText(tr("新建")); self.btn_del.setText(tr("删除")); self.btn_edit.setText(tr("编辑"))
        self.btn_manual.setText(tr("手动应用 [选中规则]"))
        if self.auto_mode_on: self.btn_auto.setText(tr("停止自动规则调度引擎"))
        else: self.btn_auto.setText(tr("开启自动规则调度引擎"))
        self.cb_autostart.setText(tr("开机自动启动"))
        self.cb_auto_engine.setText(tr("打开时自动运行引擎"))
        
        if self.tray: self.tray.setToolTip(tr("GatePilot V1.0"))
            
        self.set_active_rule(self.current_active_rule) 
        self.update_network_status_ui(force_full=True)
        self.rebuild_tray_menu()

    def on_tab_changed(self, index):
        if index >= 0:
            self.last_active_tab = self.adapter_tabs.tabText(index)
            self.save_global_settings(last_tab=self.last_active_tab)
            self.update_network_status_ui() 

    def update_network_status_ui(self, force_full=False):
        try:
            daemon_txt = tr("状态：自动引擎 [运行中]，多网卡同步监控中...") if self.auto_mode_on else tr("状态：自动引擎已关闭，等待手动操作")
            color = "#10B981" if self.auto_mode_on else "#059669"
            
            global_html = f"<div style='line-height: 1.4;'><span style='color:{color}; font-weight:bold;'>{daemon_txt}</span><br>"
            global_html += f"<b>{tr('外网:')}</b> {self.current_ping_str} &nbsp;|&nbsp; <b>{tr('公网 IP:')}</b> {self.current_pub_ip_str}</div>"
            self.global_status_lab.setText(global_html)

            mapping = WindowsNetAdapter.get_adapter_mapping()
            interfaces = list(mapping.keys())
            
            current_tabs = [self.adapter_tabs.tabText(i) for i in range(self.adapter_tabs.count())]
            
            if set(interfaces) != set(current_tabs) or force_full:
                curr_active = self.adapter_tabs.tabText(self.adapter_tabs.currentIndex()) if self.adapter_tabs.count() > 0 else self.last_active_tab
                
                self.adapter_tabs.blockSignals(True)
                
                while self.adapter_tabs.count() > 0:
                    w = self.adapter_tabs.widget(0)
                    self.adapter_tabs.removeTab(0)
                    if w: w.deleteLater()
                
                for adapter in interfaces:
                    tab_content = QTextBrowser()
                    tab_content.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                    tab_content.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                    tab_content.setStyleSheet("padding: 8px; border: none; background: transparent; color: #1F2937;")
                    self.adapter_tabs.addTab(tab_content, adapter)
                
                if curr_active in interfaces:
                    self.adapter_tabs.setCurrentIndex(interfaces.index(curr_active))
                elif self.last_active_tab in interfaces:
                    self.adapter_tabs.setCurrentIndex(interfaces.index(self.last_active_tab))
                    
                self.adapter_tabs.blockSignals(False)

            idx = self.adapter_tabs.currentIndex()
            if idx >= 0:
                adapter = self.adapter_tabs.tabText(idx)
                st = WindowsNetAdapter.get_status_dict(adapter)
                desc = mapping.get(adapter, "")
                
                curr_ssid = WindowsNetAdapter.get_current_ssid() if "wlan" in adapter.lower() or "无线" in adapter else ""
                ssid_disp = f" <span style='color:#6B7280; font-size:8.5pt;'>(WiFi: {curr_ssid})</span>" if curr_ssid else ""

                html = f"<div style='font-family: \"Microsoft YaHei\"; font-size: 9.5pt; line-height: 1.6;'>"
                html += f"<b>【{adapter}】</b> <span style='color:#4B5563; font-size:8.5pt;'>[{desc}]</span>{ssid_disp}<br>"
                html += f"{tr('本机 IP:')} <b>{st['ip']}</b> &nbsp;|&nbsp; {tr('网关:')} <b>{st['gw']}</b><br>"
                html += f"{tr('DNS:')} <b>{st['dns']}</b></div>"

                widget = self.adapter_tabs.widget(idx)
                if isinstance(widget, QTextBrowser):
                    widget.setHtml(html)
        except Exception as e:
            logger.error(f"UI update exception: {e}")

    def edit_selected_rule(self):
        item = self.list_rules.currentItem()
        if not item: return
        r = item.data(Qt.UserRole)
        if r and r["name"] in [tr("默认自动获取"), "Default DHCP"]:
            QMessageBox.information(self, tr("提示"), tr("系统级保底规则，禁止修改或删除！"))
            return
        self.edit_rule(item)

    def edit_rule(self, item):
        r = item.data(Qt.UserRole)
        if r and r["name"] in [tr("默认自动获取"), "Default DHCP"]:
            QMessageBox.information(self, tr("提示"), tr("系统级保底规则，禁止修改或删除！"))
            return
        rule_data = item.data(Qt.UserRole)
        dialog = RuleEditorDialog(self, rule_data)
        if dialog.exec_():
            item.setData(Qt.UserRole, dialog.rule_data)
            self.set_active_rule(self.current_active_rule) 
            self.save_rules()
            self.rebuild_tray_menu()

    # ================= [ BUG FIX: 追加到末尾，防止挤占第0行 ] =================
    def add_rule(self):
        r = {"name": f"{tr('新规则')} {self.list_rules.count()}", "adapter_match": "任意网卡", "ssid": "", "exe": "", "time_range":"", "action_exe":"", "net": {"mode": "dhcp", "ip": "", "gateway": "", "dns": ""}}
        item = QListWidgetItem(r["name"])
        item.setData(Qt.UserRole, r)
        item.setIcon(self.icon_inactive)
        
        # 核心修改：直接追加到最后，保证“默认自动获取”绝对锚定在第0行
        self.list_rules.addItem(item)
        
        self.list_rules.setCurrentItem(item)
        self.set_active_rule(self.current_active_rule) 
        self.save_rules()
        self.edit_rule(item)

    def del_rule(self):
        row = self.list_rules.currentRow()
        if row <= 0: 
            QMessageBox.warning(self, tr("警告"), tr("系统级保底规则，禁止修改或删除！"))
            return
            
        self.list_rules.takeItem(row)
        self.save_rules()
        self.rebuild_tray_menu()

    def apply_rule_from_tray(self, rule_name):
        target_rule = None
        for i in range(self.list_rules.count()):
            r = self.list_rules.item(i).data(Qt.UserRole)
            if r and r['name'] == rule_name:
                target_rule = r; break
                
        if target_rule:
            adapter = target_rule.get("adapter_match", "任意网卡")
            mapping = WindowsNetAdapter.get_adapter_mapping()
            
            if adapter in ["任意网卡", "Any Adapter"]:
                interfaces = list(mapping.keys())
                if not interfaces: return
                adapter = interfaces[0] 
            else:
                saved_desc = ""
                if " [" in adapter and adapter.endswith("]"):
                    saved_desc = adapter.split(" [")[1][:-1]
                
                found_adapter = None
                for live_name, live_desc in mapping.items():
                    if saved_desc and saved_desc == live_desc:
                        found_adapter = live_name; break
                    elif adapter.startswith(live_name + " [") or adapter == live_name:
                        found_adapter = live_name; break
                
                if found_adapter: adapter = found_adapter
                else:
                    if self.tray and self.tray.isVisible(): self.tray.showMessage(tr("GatePilot V1.0"), tr("状态：网关配置应用失败！"), QSystemTrayIcon.Warning, 2000)
                    return
                    
            logger.info(f"Tray triggered rule: {rule_name} on adapter {adapter}")
            success = WindowsNetAdapter.apply_atomic(adapter, target_rule["net"])
            if success:
                self.set_active_rule(rule_name)
                action_exe = target_rule.get("action_exe", "").strip()
                if action_exe and os.path.exists(action_exe):
                    try: os.startfile(action_exe)
                    except Exception as ex: logger.error(f"Failed to execute attached action: {ex}")
                try:
                    if self.tray and self.tray.isVisible():
                        self.tray.showMessage(tr("GatePilot V1.0"), tr("该规则绑定了特定网卡【{}】，已自动为其下发配置！").format(adapter), QSystemTrayIcon.Information, 2000)
                except: pass
            self.update_network_status_ui()

    def on_manual_apply(self):
        if self.auto_mode_on: return 
        item = self.list_rules.currentItem()
        if not item: return
        r = item.data(Qt.UserRole)
        if not r: return
        
        adapter = r.get("adapter_match", "任意网卡")
        mapping = WindowsNetAdapter.get_adapter_mapping()
        
        if adapter in ["任意网卡", "Any Adapter"]:
            idx = self.adapter_tabs.currentIndex()
            if idx >= 0: adapter = self.adapter_tabs.tabText(idx)
            else:
                QMessageBox.warning(self, tr("警告"), tr("请先选择要操作的网卡！"))
                return
        else:
            saved_desc = ""
            if " [" in adapter and adapter.endswith("]"):
                saved_desc = adapter.split(" [")[1][:-1]
            
            found_adapter = None
            for live_name, live_desc in mapping.items():
                if saved_desc and saved_desc == live_desc:
                    found_adapter = live_name; break
                elif adapter.startswith(live_name + " [") or adapter == live_name:
                    found_adapter = live_name; break
                    
            if found_adapter: adapter = found_adapter
            else:
                QMessageBox.warning(self, tr("错误"), tr("未找到规则绑定的物理网卡，请确认网卡已连接！"))
                return
            
        logger.info(f"Manually applying rule: {r['name']} to adapter {adapter}")
        success = WindowsNetAdapter.apply_atomic(adapter, r["net"])
        if success: 
            self.set_active_rule(r["name"])
            action_exe = r.get("action_exe", "").strip()
            if action_exe and os.path.exists(action_exe):
                try: os.startfile(action_exe)
                except Exception as ex: logger.error(f"Failed to execute attached action: {ex}")
            QMessageBox.information(self, tr("成功"), tr("该规则绑定了特定网卡【{}】，已自动为其下发配置！").format(adapter))
        else: QMessageBox.warning(self, tr("错误"), tr("状态：网关配置应用失败！"))
        self.update_network_status_ui()

    def on_daemon_status(self, msg):
        if hasattr(self, 'tray') and self.tray and self.tray.isVisible():
            self.tray.showMessage(tr("GatePilot V1.0"), msg, QSystemTrayIcon.Information, 2000)

    def on_daemon_aborted(self):
        if self.daemon:
            self.daemon = None
            self.auto_mode_on = False
            self.btn_auto.setText(tr("开启自动规则调度引擎"))
            self.btn_auto.setProperty("class", "btn_auto_on")
            self.btn_auto.style().unpolish(self.btn_auto); self.btn_auto.style().polish(self.btn_auto)
            
            self.list_rules.setEnabled(True)
            self.btn_add.setEnabled(True); self.btn_del.setEnabled(True); self.btn_edit.setEnabled(True)
            self.btn_manual.setEnabled(True) 
            self.update_network_status_ui()
            self.rebuild_tray_menu()
            
            if hasattr(self, 'tray') and self.tray and self.tray.isVisible():
                self.tray.showMessage(tr("GatePilot V1.0"), tr("自动引擎已停止，切换为手动模式"), QSystemTrayIcon.Information, 2000)

    def toggle_auto_mode(self):
        if self.auto_mode_on:
            if self.daemon: self.daemon.stop()
        else:
            self.save_rules()
            rules_to_run = []
            for i in range(self.list_rules.count()):
                r = self.list_rules.item(i).data(Qt.UserRole)
                if r: rules_to_run.append(r)
                
            self.daemon = DaemonController(rules_to_run)
            self.daemon.status_signal.connect(self.on_daemon_status)
            self.daemon.active_rule_signal.connect(self.set_active_rule) 
            self.daemon.finished_signal.connect(self.on_daemon_aborted) 
            self.daemon.start()
            
            self.auto_mode_on = True
            self.btn_auto.setText(tr("停止自动规则调度引擎"))
            self.btn_auto.setProperty("class", "btn_auto_off")
            self.btn_auto.style().unpolish(self.btn_auto); self.btn_auto.style().polish(self.btn_auto)
            
            self.list_rules.setEnabled(False)
            self.btn_add.setEnabled(False); self.btn_del.setEnabled(False); self.btn_edit.setEnabled(False)
            self.btn_manual.setEnabled(False)
            
            if hasattr(self, 'tray') and self.tray and self.tray.isVisible():
                self.tray.showMessage(tr("GatePilot V1.0"), tr("自动引擎已开启，后台监控中..."), QSystemTrayIcon.Information, 2000)
            
        self.update_network_status_ui()
        self.rebuild_tray_menu()

    def check_autostart_status(self):
        try:
            subprocess.check_output(['schtasks', '/query', '/tn', TASK_NAME], creationflags=CREATE_NO_WINDOW, stderr=subprocess.DEVNULL)
            return True
        except: return False

    def toggle_autostart(self, checked):
        try:
            if checked:
                tr_arg = f'\\"{sys.executable}\\" --autostart' if getattr(sys, 'frozen', False) else f'\\"{sys.executable}\\" \\"{os.path.abspath(__file__)}\\" --autostart'
                subprocess.run(f'schtasks /create /tn "{TASK_NAME}" /tr "{tr_arg}" /sc onlogon /rl highest /f', shell=True, check=True, creationflags=CREATE_NO_WINDOW)
                QMessageBox.information(self, tr("成功"), tr("已开启开机自启！"))
            else:
                subprocess.run(f'schtasks /delete /tn "{TASK_NAME}" /f', shell=True, check=True, creationflags=CREATE_NO_WINDOW)
        except Exception as e:
            QMessageBox.warning(self, tr("错误"), str(e))
            self.cb_autostart.setChecked(not checked)

    def closeEvent(self, event):
        event.ignore()
        try:
            self.hide()
            self.save_rules() 
            if self.tray and self.tray.isVisible():
                self.tray.showMessage(tr("GatePilot V1.0"), tr("程序已最小化到系统托盘运行"), QSystemTrayIcon.Information, 2000)
        except Exception as e:
            logger.error(f"Exception occurred while closing window: {e}")

    def open_log_file(self):
        if not os.path.exists(LOG_FILE): open(LOG_FILE, "w").close()
        try: os.startfile(LOG_FILE)
        except: pass

    def real_quit(self):
        self.save_rules() 
        if self.daemon and self.daemon.isRunning(): self.daemon.stop()
        if self.net_monitor and self.net_monitor.isRunning(): self.net_monitor.stop()
        if self.tray: self.tray.hide()
        QApplication.quit()

if __name__ == '__main__':
    is_autostart = "--autostart" in sys.argv
    try:
        if not is_admin():
            args = "--autostart" if is_autostart else ""
            if getattr(sys, 'frozen', False): ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
            else: ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{os.path.abspath(__file__)}" {args}', None, 1)
            sys.exit()

        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('gatepilot.v1.0')
        ex = GatePilotV2()
        
        if is_autostart:
            ex.hide()
        else:
            ex.show()
            
        if ex.auto_start_engine and not ex.auto_mode_on:
            ex.toggle_auto_mode()
            
        sys.exit(app.exec_())
    except Exception as e:
        import traceback
        with open(os.path.join(APP_DIR, "gatepilot_crash.log"), "w", encoding="utf-8") as f: f.write("GatePilot Crash:\n" + traceback.format_exc())
