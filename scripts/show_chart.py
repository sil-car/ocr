#!/usr/bin/env python3

# Show bar chart with CER on Y-axis and Model Name on X-axis.

import csv
import matplotlib.pyplot as plt
import numpy as np

from pathlib import Path


# Prepare data.
csv_file = Path(__file__).expanduser().resolve().parents[1] / 'data' / 'evaluation' / 'data.csv'
if not csv_file.is_file():
    print(f"Error: File does not exist: {str(csv_file)}")

model_data = {}
with csv_file.open(newline='') as c:
    reader = csv.DictReader(c)
    # Separate data by Model Name
    for row in reader:
        m = row.get('model')
        if not model_data.get(m):
            model_data[m] = {
                'cer-avg': None,
                'data': [row],
            }
        else:
            model_data[m]['data'].append(row)

# Compute average CER for each model.
for m, v in model_data.items():
    data_ct = len(v.get('data'))
    # for d in model.get('data'):
    #     cer = d.get('cer')
    cer_sum = sum([float(d.get('cer')) for d in v.get('data')])
    model_data[m]['cer-avg'] = round(cer_sum / data_ct, 4)

# for m, data in model_data.items():
#     print(f"{m}: {data}\n")
# exit()

# Sort Model names alphabetically.
model_names = list(model_data.keys())
model_names.sort()
cer_values = [model_data.get(m).get('cer-avg') for m in model_names]

# Remove models whose CERs are greater than cer_limit.
cer_limit = 0.1
model_names_limited = []
cer_values_limited = []
for i, m in enumerate(model_names):
    if cer_values[i] <= cer_limit:
        model_names_limited.append(m)
        cer_values_limited.append(cer_values[i])

# Plot ideas:
#   https://matplotlib.org/stable/gallery/mplot3d/bars3d.html#sphx-glr-gallery-mplot3d-bars3d-py
plt.style.use('_mpl-gallery')

# Define data to plot.
x = model_names_limited
y = cer_values_limited

# Generate and format plot.
fig, ax = plt.subplots(figsize=(8,7))
plt.subplots_adjust(left=0.1, bottom=0.30, right=0.9, top=0.8, wspace=0, hspace=0)
plt.xticks(horizontalalignment='right', rotation=60)
plt.title("Tesseract Models Below 10% CER", pad=12.0)
# ax.set_title("Tesseract Models Below 10% CER")
ax.bar(x, y, width=0.25, edgecolor="white", linewidth=0.07)
ax.set_xlabel('Model Names')
ax.set_ylabel('Character Error Rate')
ax.axhspan(0, 0.05, alpha=0.1, color='yellow', zorder=0.0)  # 5% CER threshold
ax.axhspan(0, 0.02, alpha=0.2, color='green', zorder=0.1)   # 2% CER threshold

# Show plot.
plt.savefig(csv_file.parent / 'models-below-0.10-CER.png')
plt.show()
