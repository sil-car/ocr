#!/usr/bin/env python3

# Show bar chart with CER on Y-axis and Model Name on X-axis.

import csv
import matplotlib.pyplot as plt
import sys

from pathlib import Path


def get_csv_data(csv_file):
    with csv_file.open(newline='') as c:
        reader = csv.DictReader(c)
        csv_data = [r for r in reader]
    return csv_data

def get_grouped_data(csv_data, key):
    grouped_data = {}
    for row in csv_data:
        k = row.get(key)
        if not grouped_data.get(k):
            grouped_data[k] = {
                'cer-avg': None,
                'data': [row],
            }
        else:
            grouped_data[k]['data'].append(row)
    return grouped_data

def update_computed_avg_cer(grouped_data):
    for k, v in grouped_data.items():
        data_ct = len(v.get('data'))
        cer_sum = sum([float(d.get('cer')) for d in v.get('data')])
        grouped_data[k]['cer-avg'] = round(cer_sum / data_ct, 4)
    return grouped_data

def build_3d_slices(data):
    # Each slice is a unique iso_lang set of (model_name, CER).
    #   slices = {iso_lang: {model_name: CER}, ...}
    slices = {}
    # data = {
    #   model_name: {
    #       'cer-avg': float,
    #       'data': [rows],
    #   }
    # }

    # Get list of model_names.
    model_names = list(data.keys())
    model_names.sort()

    # Get list of iso_langs.
    iso_langs = []
    for m, v in data.items():
        for r in v.get('data'):
            iso_langs.append(r.get('iso_lang'))
    iso_langs = list(set(iso_langs))
    iso_langs.sort()

    # Get CER for each combo of (model_name, iso_lang).
    for m in model_names:
        rows = data.get(m).get('data')
        for l in iso_langs:
            c = 0
            for row in rows:
                if row.get('iso_lang') == l:
                    c = row.get('cer')
                    break
            if not l in slices.keys():
                slices[l] = {m: c}
            else:
                slices[l][m] = c
    return slices

def plot_bar2d(x, y, out_file, title, xlabel, ylabel):
    # Generate and format plot.
    fig, ax = plt.subplots(figsize=(8,7))

    plt.subplots_adjust(left=0.1, bottom=0.30, right=0.9, top=0.8, wspace=0.1, hspace=0.1)
    plt.xticks(horizontalalignment='right', rotation=60)
    plt.title(title, pad=12.0)

    ax.bar(x, y, width=0.25, edgecolor="blue", linewidth=0)
    ax.tick_params(axis='x', grid_linewidth=0)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.axhspan(0, 0.05, alpha=0.1, color='yellow', zorder=0.0)  # 5% CER threshold shading
    ax.axhspan(0, 0.02, alpha=0.2, color='green', zorder=0.1)   # 2% CER threshold shading

    # Show plot.
    plt.savefig(out_file)
    plt.show()
    exit()

def plot_bar3d(slices_dict):
    # slices_dict = {iso_lang: {model: l_cer}}

    # Set list of all model_names
    model_names = []
    iso_langs = []
    for l, d1 in slices_dict.items():
        iso_langs.append(l)
        for m, d2 in d1.items():
            model_names.append(m)
    iso_langs = list(set(iso_langs))
    iso_langs.sort()
    model_names = list(set(model_names))
    model_names.sort()

    cers = []
    for l in iso_langs:
        for m in model_names:
            # print(f"{m}, {l}")
            if slices_dict.get(l):
                if slices_dict.get(l).get(m):
                    cer_real = float(slices_dict.get(l).get(m))
                    # cer = cer_real if cer_real < 0.1 else 0 # hide large CERs
                    cer = cer_real
                    cers.append(cer)
                else:
                    cers.append(0.0)
            else:
                cers.append(0.0)

    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')

    xticklabels = model_names #[f"\n{m}\n\n" for m in model_names]
    yticklabels = iso_langs
    sp = 8
    pi = 2
    d = 2

    # x is list of numbers to set x-axis placement of every bar.
    x = [pi+i*sp for i in range(len(xticklabels))] * len(yticklabels)
    # xticks is list of numbers to set placement of x-axis labels.
    xticks = [sp*(i+1) for i in range(len(xticklabels))]

    # y is list of numbers to set y-axis placement of every bar.
    y = [pi+i//len(xticklabels)*sp for i in range(len(yticklabels) * len(xticklabels))]
    # yticks is list of numbers to set placement of y-axis labels.
    yticks = [sp*(i+1) for i in range(len(yticklabels))]

    z = 0 # value of bottom of every bar
    dx = d # thickness of bar
    dy = d # width of bar
    # Hide dz == 0 bars:
    #   https://stackoverflow.com/questions/70196729/matplotlib-hide-bar-in-bar3d-if-height-is-zero
    dz = cers
    s0 = 0
    s1 = -1
    ax.bar3d(x[s0:s1], y[s0:s1], z, dx, dy, dz[s0:s1], alpha=0.6)
    ax.set_xticks(xticks)
    fs = 8
    lpad = 30
    tlpad = 0.5
    xha = 'right'
    yha = 'left'
    ax.set_xticklabels(
        xticklabels,
        fontdict={'fontsize':fs, 'horizontalalignment':xha},
    )
    ax.set_yticks(yticks)
    ax.set_yticklabels(
        yticklabels,
        fontdict={'fontsize':fs, 'horizontalalignment':yha},
    )
    ax.xaxis.labelpad=lpad
    ax.yaxis.labelpad=lpad
    ax.set_xlabel('Model Name')
    ax.set_ylabel('ISO_Language')
    ax.set_zlabel('CER')

    plt.show()

def main():
    # Prepare data.
    csv_file = Path(__file__).expanduser().resolve().parents[1] / 'data' / 'evaluation' / 'data.csv'
    if not csv_file.is_file():
        print(f"Error: File does not exist: {str(csv_file)}")

    csv_data = get_csv_data(csv_file)
    model_data = get_grouped_data(csv_data, 'model')
    # lang_data = get_grouped_data(csv_data, 'iso_lang')

    # Update model_data with average CERs by model.
    model_data = update_computed_avg_cer(model_data)

    plt.style.use('_mpl-gallery')
    out_dir = csv_file.parent

    if len(sys.argv) > 1:
        if sys.argv[1] == '3d':
            data_slices = build_3d_slices(model_data)
            plot_bar3d(data_slices)
        elif sys.argv[1] == 'lang':
            # Show summary chart of CER by ISO_Language with given Model Name.

            # Determine best_model and its CER.
            best_model = [None, None]
            for m, v in model_data.items():
                a = v.get('cer-avg')
                if best_model[0] is None or a < best_model[1]:
                    best_model = [m, a]

            # Gather data for best_model.
            lang_data = get_grouped_data(csv_data, 'iso_lang')
            lang_names = list(lang_data.keys())
            lang_names.sort()
            # print(lang_data)
            cer_values = []
            lang_names_filtered = []
            for l in lang_names:
                rows = lang_data.get(l).get('data')
                for r in rows:
                    if r.get('model') == best_model[0]:
                        cer_values.append(float(r.get('cer')))
                        lang_names_filtered.append(l)
                        break

            x = lang_names_filtered
            y = cer_values
            out_file = out_dir / 'best-model-perf-by-lang.png'
            title = f"CERs by ISO_Language for {best_model[0]}"
            xlabel = "ISO_Language"
            ylabel = "Character Error Rate"
            plot_bar2d(x, y, out_file, title, xlabel, ylabel)
    else:
        # Show summary chart of CER by Model Name.

        # Sort Model names alphabetically.
        model_names = list(model_data.keys())
        model_names.sort()
        cer_values = [model_data.get(m).get('cer-avg') for m in model_names]

        # Remove models whose CERs are greater than cer_limit.
        cer_limit = 0.1
        model_names_limited = []
        cer_values_limited = []
        for i, m in enumerate(model_names):
            if cer_values[i] <= cer_limit or m == 'Latin':
                model_names_limited.append(m)
                cer_values_limited.append(cer_values[i])

        x = model_names_limited
        y = cer_values_limited
        out_file = out_dir / 'models-below-0.10-CER.png'
        title = "Models Below 10% CER"
        xlabel = "Model Name"
        ylabel = "Character Error Rate"
        plot_bar2d(x, y, out_file, title, xlabel, ylabel)


if __name__ == '__main__':
    main()
