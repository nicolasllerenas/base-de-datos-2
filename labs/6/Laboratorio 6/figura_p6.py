# Figura P6.a - linea de tiempo de ejecucion de T1..T4 respecto al checkpoint
# y a la falla del sistema. Mismo estilo que imagenes/dbrecovery.png del enunciado.

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Times New Roman"

CP = 9.0
FALLA = 19.0

# (nombre, inicio, fin, termina con commit)
TX = [
    ("T1",  1.0, 11.0,  True),
    ("T2",  3.0,  7.6,  True),
    ("T3", 11.8, 19.0, False),
    ("T4", 14.5, 17.8,  True),
]

fig, ax = plt.subplots(figsize=(8.0, 3.1))

Y_EJE = 4.75
Y_BASE = 0.35

# eje de tiempo
ax.annotate("", xy=(20.2, Y_EJE), xytext=(1.0, Y_EJE),
            arrowprops=dict(arrowstyle="-|>", color="black",
                            linewidth=0.9, mutation_scale=11))
ax.text(0.0, Y_EJE + 0.12, "tiempo", fontsize=9, fontweight="bold", va="bottom")

# verticales: checkpoint y falla
for x in (CP, FALLA):
    ax.plot([x, x], [Y_BASE, Y_EJE], color="black", linewidth=0.9)

# transacciones
for i, (nombre, ini, fin, commit) in enumerate(TX):
    y = 3.85 - i * 0.9
    ax.plot([ini, fin], [y, y], color="black", linewidth=0.9)
    ax.text(ini + 0.55, y + 0.14, nombre, fontsize=10)
    if commit:
        ax.text(fin - 0.15, y + 0.14, "commit", fontsize=9, ha="right")

ax.text(CP - 0.12, Y_BASE - 0.22, "Punto de\nverificación",
        fontsize=8.5, fontweight="bold", ha="left", va="top", linespacing=1.35)
ax.text(FALLA - 0.12, Y_BASE - 0.22, "Fallo del\nsistema",
        fontsize=8.5, fontweight="bold", ha="left", va="top", linespacing=1.35)

ax.set_xlim(-0.5, 21.4)
ax.set_ylim(-1.15, 5.35)
ax.axis("off")

fig.savefig("imagenes/p6_linea_tiempo.png", dpi=220,
            bbox_inches="tight", pad_inches=0.12, facecolor="white")
