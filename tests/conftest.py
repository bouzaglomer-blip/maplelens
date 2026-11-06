import os

# Offscreen Qt finds no fonts on its own; give it the real ones so text measures (and
# elides) as it does on screen. Must be set before the first QApplication.
os.environ.setdefault(
    "QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
)
