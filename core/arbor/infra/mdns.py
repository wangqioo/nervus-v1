"""
mDNS 服务广播
在局域网内注册 _nervus._tcp 服务，让 nervus-cli 设备发现 能自动发现。
依赖：zeroconf（pip install zeroconf）
"""

import os
import socket
import logging
from typing import Optional

logger = logging.getLogger("arbor.mdns")


def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


_zeroconf_instance = None
_service_info = None


def start_mdns(port: int = 8090, service_name: str = "Nervus") -> bool:
    global _zeroconf_instance, _service_info

    try:
        from zeroconf import Zeroconf, ServiceInfo
    except ImportError:
        logger.info("zeroconf 未安装，跳过 mDNS 广播")
        return False

    try:
        local_ip = _get_local_ip()
        hostname = socket.gethostname()

        _service_info = ServiceInfo(
            type_="_nervus._tcp.local.",
            name=f"{service_name}._nervus._tcp.local.",
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties={
                b"version": b"1.0",
                b"host":    hostname.encode(),
                b"api":     b"/api",
            },
            server=f"{hostname}.local.",
        )

        _zeroconf_instance = Zeroconf()
        _zeroconf_instance.register_service(_service_info)
        logger.info(f"mDNS 已广播: {service_name}._nervus._tcp.local. @ {local_ip}:{port}")
        return True
    except Exception as e:
        logger.warning(f"mDNS 广播失败（非致命，nervus-cli 局域网发现不可用）: {e}")
        return False


def stop_mdns():
    global _zeroconf_instance, _service_info
    if _zeroconf_instance and _service_info:
        try:
            _zeroconf_instance.unregister_service(_service_info)
            _zeroconf_instance.close()
        except Exception:
            pass
        _zeroconf_instance = None
        _service_info = None
        logger.info("mDNS 服务已注销")
