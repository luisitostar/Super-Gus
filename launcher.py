import os
import sys
from pathlib import Path

import streamlit.web.cli as stcli


def main():
    if getattr(sys, "frozen", False):
        carpeta = Path(sys.executable).parent
        recursos = Path(sys._MEIPASS)
    else:
        carpeta = Path(__file__).resolve().parent
        recursos = carpeta

    archivo_app = recursos / "supercre.py"

    os.chdir(carpeta)

    sys.argv = [
        "streamlit",
        "run",
        str(archivo_app),
        "--global.developmentMode=false",
        "--server.headless=true",
    ]

    sys.exit(stcli.main())


if __name__ == "__main__":
    main()