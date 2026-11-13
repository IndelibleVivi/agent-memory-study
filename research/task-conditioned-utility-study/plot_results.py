#!/usr/bin/env python3
"""Plot reproduced measurements beside an explicitly hypothetical standardisation."""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
figure_data = json.loads((ROOT / "figure-data.json").read_text())
actual = {value["arm"]: value for value in figure_data["left_panel"]["arms"]}
curves = {value["stratum"]: value for value in figure_data["right_panel"]["curves"]}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.labelcolor": "#282534", "text.color": "#282534"})
fig, axes = plt.subplots(1, 2, figsize=(11, 4.9))
fig.patch.set_facecolor("#faf9fc")
for ax in axes:
    ax.set_facecolor("#faf9fc")
    ax.axhline(0, color="#a8a3af", lw=1)
    ax.grid(axis="y", color="#e4e0e9", lw=.7)
    ax.set_axisbelow(True)

arm_names = [("raw", "Raw"), ("summary", "Summary"), ("structured", "Structured"), ("trunc_last_matched", "Matched\ntruncation")]
for i, (key, label) in enumerate(arm_names):
    v = actual[key]
    y = v["mean"]
    axes[0].errorbar(i, y, yerr=[[y-v["ci95"][0]], [v["ci95"][1]-y]],
                     fmt="o", markersize=7, capsize=4, color="#776391" if key=="raw" else "#65918d")
    axes[0].text(i, y+.045, f"{y:+.3f}", ha="center", fontsize=10)
axes[0].set_xticks(range(len(arm_names)), [label for _, label in arm_names])
axes[0].set_ylim(-.08, .57)
axes[0].set_xlim(-.5, 3.5)
axes[0].set_ylabel("Mean paired change in correctness")
axes[0].set_title("Archived outputs: matched total context", loc="left", fontsize=12, pad=20)
axes[0].text(0, 1.02, "77 answer-bearing cells; task-clustered 95% intervals", transform=axes[0].transAxes, fontsize=9, color="#6b6573")

palette = [("BEARING", "Answer-bearing", "#776391"), ("MATCHED_CONTROL", "Matched control", "#b18a6c"), ("RANDOM", "Random task", "#65918d")]
for key, label, color in palette:
    v = curves[key]
    points = np.array(v["points"])
    axes[1].plot(points[:, 0], points[:, 1], color=color, label=label, lw=2)
    axes[1].scatter([v["observed_p"]], [v["observed_delta"]], color=color, s=30, zorder=5)
axes[1].set_ylim(-.32, .46)
axes[1].set_xlim(0, 1)
axes[1].set_xlabel("Hypothetical no-memory correctness p")
axes[1].set_ylabel("(1 - p) h - p e")
axes[1].set_title("Scenario: hold help and harm rates fixed", loc="left", fontsize=12, pad=20)
axes[1].text(0, 1.02, "Dots show original strata; curves are not new inference", transform=axes[1].transAxes, fontsize=9, color="#6b6573")
axes[1].legend(frameon=False, loc="lower left", fontsize=9)
fig.subplots_adjust(left=.08, right=.98, top=.82, bottom=.23, wspace=.32)
fig.text(.08, .09, "Source: Yang et al., arXiv:2611.03930v1, pinned public artifacts; AMS reanalysis, 13 November 2026.", fontsize=9, color="#6b6573")
fig.text(.08, .045, "Right panel holds h/e fixed for illustration. Model upgrades can change all three quantities; no model-scaling claim is made.", fontsize=9, color="#6b6573")
svg_path = ROOT / "utility-opportunities.svg"
fig.savefig(svg_path)
# Matplotlib emits trailing spaces inside path attributes. Newlines already
# separate their SVG tokens; removing line-end spaces preserves the drawing.
svg_path.write_text("\n".join(line.rstrip() for line in svg_path.read_text().splitlines())+"\n")
fig.savefig(ROOT / "utility-opportunities.png", dpi=180)
print("Saved utility-opportunities.svg and utility-opportunities.png")
