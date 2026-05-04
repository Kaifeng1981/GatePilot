# GatePilot 🚀

[![Platform](https://img.shields.io/badge/Platform-Windows-blue.svg)]()
[![Language](https://img.shields.io/badge/Language-Python_3.x-yellow.svg)]()
[![GUI](https://img.shields.io/badge/GUI-PyQt5-green.svg)]()

*(English below | 中文说明在下方)*

---

## 🇬🇧 English

**GatePilot** is a smart Windows network scheduling engine designed to automatically and seamlessly switch network configurations (IP, Gateway, DNS) based on customizable triggers. 

It was originally developed to solve a common pain point for Homelab and NAS enthusiasts: seamlessly switching between a bypass router (VPN/Proxy) and a standard local network gateway depending on location, active Wi-Fi, or running applications.

### ✨ Key Features
* **Independent Multi-Adapter Management**: Simultaneously manages Ethernet and WLAN adapters in the background without interference.
* **Smart Context Awareness**: Triggers network profile changes based on a combination of:
  * Specific Physical Adapters
  * Wi-Fi SSID
  * Running Processes (e.g., switching gateways only when a specific download client is running to save VPN bandwidth).
  * Specific Time Ranges.
* **Safe Fallback Mechanism**: Automatically reverts to DHCP mode when no custom rules match, ensuring continuous internet access.
* **Action Hooks**: Automatically launches specific applications or scripts upon a successful IP switch.

### 🚀 Getting Started
1. Go to the [Releases](../../releases) page and download the latest `GatePilot_vX.X_beta.exe`.
2. Run the executable (Administrator privileges are required to modify network adapters).
3. Set up your custom rules in the GUI and click "Start Auto Engine".

*Note: You can also run it directly from the source code by installing the dependencies (PyQt5, psutil) and running `gatepilot.py`.*

---

## 🇨🇳 中文说明

**GatePilot** 是一款专为软路由、旁路由和 NAS 玩家打造的 Windows 网络环境自动调度引擎。

开发初衷是为了解决家庭网络环境中的痛点：当用户携带电脑回家时，需要固定 IP 和网关以连接旁路由（走特定网络环境）；而离家时需要恢复 DHCP。同时，为了避免特定的本地下载软件消耗旁路由流量，GatePilot 支持“按进程识别”进行网关的动态无缝切换。

### ✨ 核心功能
* **多网卡独立守护**：引擎可在后台同时独立管理有线网卡（Ethernet）与无线网卡（WLAN），互不干扰。
* **智能场景感知**：支持组合以下条件触发自动切换：
  * 指定物理网卡
  * 特定 WiFi 名称 (SSID)
  * 特定运行中的进程（例如：只有当识别到某下载软件运行时才切换网络）
  * 指定时间段
* **防断网保底机制**：当所有条件都不满足时，网卡会自动回退至【默认自动获取 DHCP】，确保设备永远在线。
* **执行附加动作**：网络切换成功后，可自动拉起用户指定的业务程序或脚本。

### 🚀 如何使用
1. 前往右侧的 [Releases](../../releases) 页面，下载最新的 `GatePilot_vX.X_beta.exe`。
2. 双击运行程序（修改网卡配置需要 UAC 管理员权限）。
3. 在界面中配置您的网络规则，并点击“开启自动规则调度引擎”即可。

*注：如果您希望直接通过源码运行，请确保安装了相关依赖（PyQt5, psutil），并运行 `gatepilot.py`。*
