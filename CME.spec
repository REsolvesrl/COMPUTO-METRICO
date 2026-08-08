# Ricetta di PyInstaller per costruire CME.exe.
#
# Si costruisce con:   python -m PyInstaller CME.spec --noconfirm
#
# Due cose vanno dette a PyInstaller esplicitamente, perché da solo non le
# indovina:
#
# 1. I file dell'app (streamlit_app.py e i moduli) viaggiano come DATI, non
#    come codice compilato: Streamlit esegue lo script leggendolo dal disco,
#    quindi deve trovarlo come file. Di conseguenza PyInstaller non "vede" gli
#    import fatti là dentro —
# 2. ...e le librerie vanno raccolte a mano con collect_all, che porta con sé
#    anche i loro file di appoggio (l'interfaccia di Streamlit, i dati di
#    Plotly, le librerie compilate di OpenCV e PyMuPDF).

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# Librerie che si portano dietro file propri, non solo codice.
for pacchetto in ("streamlit", "plotly", "pyarrow", "altair", "pandas",
                  "numpy", "cv2", "pymupdf", "fitz", "PIL", "openpyxl",
                  "requests", "webview"):
    try:
        d, b, h = collect_all(pacchetto)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as errore:            # pacchetto assente: si tira avanti
        print(f"[CME.spec] salto {pacchetto}: {errore}")

# collect_all raccoglie TUTTO, comprese le suite di test delle librerie:
# centinaia di MB di roba che non verrà mai eseguita. Via.
def _e_zavorra(nome):
    pezzi = nome.split(".")
    return any(p in ("tests", "test", "testing", "conftest") for p in pezzi) \
        or pezzi[-1].startswith("test_")


prima = len(hiddenimports)
hiddenimports = [h for h in hiddenimports if not _e_zavorra(h)]
datas = [(o, d) for o, d in datas
         if not any(p in ("tests", "test") for p in str(d).split("\\"))]
print(f"[CME.spec] tolti {prima - len(hiddenimports)} moduli di test")

# I file dell'app: lo script principale, i moduli di logica, il componente
# della planimetria (che è HTML+JS letto dal disco), il tema e il logo.
datas += [
    ("streamlit_app.py", "."),
    ("calcoli.py", "."),
    ("planimetria.py", "."),
    ("rilevamento.py", "."),
    ("listino.py", "."),
    ("fattibilita.py", "."),
    ("fattura.py", "."),
    ("archivio.py", "."),
    ("archivio_locale.py", "."),
    ("cme_viewer", "cme_viewer"),
    (".streamlit/config.toml", ".streamlit"),
    ("assets", "assets"),
]

a = Analysis(
    ["cme_exe.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CME",
    debug=False,
    strip=False,
    upx=False,
    console=False,             # niente finestra nera
    icon="assets/cme.ico" if __import__("os").path.exists("assets/cme.ico")
         else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CME",
)
