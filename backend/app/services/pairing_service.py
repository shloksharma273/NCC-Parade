from __future__ import annotations

import io
import secrets

import qrcode

from ..config import settings
from ..utils.network import get_local_ip


class PairingService:
    def __init__(self) -> None:
        self._token = secrets.token_urlsafe(8)

    @property
    def pairing_token(self) -> str:
        return self._token

    def reset_token(self) -> str:
        self._token = secrets.token_urlsafe(8)
        return self._token

    def local_ip(self) -> str:
        return get_local_ip()

    def backend_url(self) -> str:
        host = self.local_ip()
        return f"http://{host}:{settings.port}"

    def webapp_url(self) -> str:
        return f"{self.backend_url()}/app"

    def qr_url(self) -> str:
        backend = self.backend_url()
        return f"{self.webapp_url()}?backend={backend}&pairing_token={self._token}"

    def info(self) -> dict:
        backend = self.backend_url()
        return {
            "server_name": settings.app_name,
            "backend_url": backend,
            "webapp_url": self.webapp_url(),
            "pairing_url": f"{backend}/pair",
            "qr_url": self.qr_url(),
            "pairing_token": self._token,
            "local_ip": self.local_ip(),
            "port": settings.port,
            "version": settings.version,
        }

    def qr_png_bytes(self) -> bytes:
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(self.qr_url())
        qr.make(fit=True)
        image = qr.make_image(fill_color="#263315", back_color="#f7f1dc")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


pairing_service = PairingService()
