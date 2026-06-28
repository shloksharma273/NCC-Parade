from __future__ import annotations

from .services.pairing_service import pairing_service


def print_startup_banner() -> None:
    info = pairing_service.info()
    line = "=" * 50
    print(f"\n{line}")
    print("DRILL RECOGNITION SERVER")
    print(line)
    print(f"\nBackend:  {info['backend_url']}")
    print(f"Webapp:   {info['webapp_url']}")
    print(f"Pairing:  {info['pairing_url']}")
    print("\nScan this QR code from the tablet:\n")
    try:
        qr = __import__("qrcode")
        qr_obj = qr.QRCode(border=1)
        qr_obj.add_data(info["qr_url"])
        qr_obj.make(fit=True)
        qr_obj.print_ascii(invert=True)
    except Exception:
        print(f"  {info['qr_url']}")
    print(f"\n{line}\n")
