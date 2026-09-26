#!/usr/bin/env python3
"""
Générateur de fichier .icns Apple pour macOS.
Convertit une image source (PNG 1024x1024 recommandé) en conteneur multi-résolution .icns.
"""

import io
import os
import struct
import sys
from PIL import Image


def create_icns(source_path: str, output_path: str) -> None:
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Image source introuvable : {source_path}")

    with Image.open(source_path) as im:
        img_rgba = im.convert("RGBA")

        # Tailles requises pour macOS (standard et Retina @2x)
        resolutions = [16, 32, 64, 128, 256, 512, 1024]
        png_data = {}

        for sz in resolutions:
            resized = img_rgba.resize((sz, sz), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            resized.save(buf, format="PNG", optimize=True)
            png_data[sz] = buf.getvalue()

    # Définition des blocs ICNS (OSType -> PNG bytes)
    # Couvre l'ensemble des formats macOS (10.7 Lion jusqu'à macOS 15+ Sequoia)
    chunks = [
        (b"icp4", png_data[16]),    # 16x16 PNG
        (b"ic04", png_data[16]),    # 16x16
        (b"icp5", png_data[32]),    # 32x32 PNG
        (b"ic11", png_data[32]),    # 16x16@2x
        (b"ic05", png_data[32]),    # 32x32
        (b"icp6", png_data[64]),    # 64x64 PNG
        (b"ic12", png_data[64]),    # 32x32@2x
        (b"ic07", png_data[128]),   # 128x128
        (b"ic13", png_data[256]),   # 128x128@2x
        (b"ic08", png_data[256]),   # 256x256
        (b"ic14", png_data[512]),   # 256x256@2x
        (b"ic09", png_data[512]),   # 512x512
        (b"ic10", png_data[1024]),  # 512x512@2x (1024x1024)
    ]

    total_length = 8 + sum(8 + len(data) for _, data in chunks)

    out = io.BytesIO()
    out.write(b"icns")
    out.write(struct.pack(">I", total_length))

    for tag, data in chunks:
        out.write(tag)
        out.write(struct.pack(">I", 8 + len(data)))
        out.write(data)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(out.getvalue())

    print(f"✅ Fichier .icns créé : {output_path} ({os.path.getsize(output_path)} octets)")


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "assets/icon_1024.png"
    dst = sys.argv[2] if len(sys.argv) > 2 else "assets/icon.icns"

    try:
        create_icns(src, dst)
        # Copie également à la racine pour un accès direct
        root_dst = "icon.icns"
        if os.path.abspath(dst) != os.path.abspath(root_dst):
            with open(dst, "rb") as f_in, open(root_dst, "wb") as f_out:
                f_out.write(f_in.read())
            print(f"✅ Copie créée à la racine : {root_dst}")
    except Exception as e:
        print(f"❌ Erreur lors de la génération : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
