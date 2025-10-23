#!/usr/bin/env python3

# Show bar chart with CER on Y-axis and Model Name on X-axis.

import argparse
import csv
import matplotlib.pyplot as plt
import numpy as np

from pathlib import Path


class GroupedData:
    def __init__(self, name, csv_data):
        self.name = name
        self.data = csv_data
        self.data_ct = len(csv_data)
        self.cer_sum = None
        self.cer_avg = None
        self.cer_group = None

        self.c_sum = sum([float(d.get("hits")) for d in self.data])
        self.d_sum = sum([float(d.get("deletions")) for d in self.data])
        self.i_sum = sum([float(d.get("insertions")) for d in self.data])
        self.s_sum = sum([float(d.get("substitutions")) for d in self.data])
        self.set_cer_avg()
        self.set_group_cer()

    def set_cer_avg(self):
        self.cer_sum = sum([float(d.get("cer")) for d in self.data])
        self.cer_avg = round(self.cer_sum / self.data_ct, 4)

    def set_group_cer(self):
        # CER = (S + D + I) / (C + S + D)
        self.cer_group = round(
            float(self.s_sum + self.d_sum + self.i_sum)
            / float(self.c_sum + self.s_sum + self.d_sum),
            4,
        )


def get_csv_data(csv_file):
    with csv_file.open(newline="") as c:
        reader = csv.DictReader(c)
        csv_data = [r for r in reader]
    return csv_data


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
        for r in v.get("data"):
            iso_langs.append(r.get("iso_lang"))
    iso_langs = list(set(iso_langs))
    iso_langs.sort()

    # Get CER for each combo of (model_name, iso_lang).
    for m in model_names:
        rows = data.get(m).get("data")
        for lg in iso_langs:
            c = 0
            for row in rows:
                if row.get("iso_lang") == lg:
                    c = row.get("cer")
                    break
            if lg not in slices.keys():
                slices[lg] = {m: c}
            else:
                slices[lg][m] = c
    return slices


def plot_bar2d(x, y, z, out_file, title, xlabel, ylabel):
    # Generate and format plot.
    bw = 0.3  # bar width
    lw = 0.5  # line width

    fig, ax = plt.subplots(figsize=(8, 7))

    plt.subplots_adjust(
        left=0.1, bottom=0.30, right=0.9, top=0.8, wspace=0.1, hspace=0.1
    )
    plt.title(title, pad=12.0)

    if z is not None:
        # Ref: https://stackoverflow.com/questions/10369681
        ind = np.arange(len(x))
        lx = title.split("&")[0].split()[-1].strip()  # hack
        lz = title.split("&")[1].strip()  # hack
        plt.xticks(ind + bw / 2, x, horizontalalignment="right", rotation=60)
        ax.bar(ind - 0.1, y, width=bw, edgecolor="w", linewidth=lw, label=lx)
        ax.bar(
            ind + 0.1,
            z,
            width=bw,
            edgecolor="w",
            linewidth=lw,
            facecolor="rosybrown",
            label=lz,
        )
        plt.legend(loc="best")
    else:
        plt.xticks(horizontalalignment="right", rotation=60)
        ax.bar(x, y, width=bw, edgecolor="blue", linewidth=0)
    # Remove x-axis grid lines.
    ax.tick_params(axis="x", grid_linewidth=0)
    # Add axis labels.
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    # Add shaded thresholds.
    ax.axhspan(
        0, 0.05, alpha=0.1, color="yellow", zorder=0.0
    )  # 5% CER threshold shading
    ax.axhspan(
        0, 0.02, alpha=0.2, color="green", zorder=0.1
    )  # 2% CER threshold shading

    # Show plot.
    plt.savefig(out_file)
    plt.show()
    exit()


def plot_bar3d(slices_dict):
    # slices_dict = {iso_lang: {model: l_cer}}

    # Set list of all model_names
    model_names = []
    iso_langs = []
    for lg, d1 in slices_dict.items():
        iso_langs.append(lg)
        for m, d2 in d1.items():
            model_names.append(m)
    iso_langs = list(set(iso_langs))
    iso_langs.sort()
    model_names = list(set(model_names))
    model_names.sort()

    cers = []
    for lg in iso_langs:
        for m in model_names:
            # print(f"{m}, {l}")
            if slices_dict.get(lg):
                if slices_dict.get(lg).get(m):
                    cer_real = float(slices_dict.get(lg).get(m))
                    # cer = cer_real if cer_real < 0.1 else 0 # hide large CERs
                    cer = cer_real
                    cers.append(cer)
                else:
                    cers.append(0.0)
            else:
                cers.append(0.0)

    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")

    xticklabels = model_names  # [f"\n{m}\n\n" for m in model_names]
    yticklabels = iso_langs
    sp = 8
    pi = 2
    d = 2

    # x is list of numbers to set x-axis placement of every bar.
    x = [pi + i * sp for i in range(len(xticklabels))] * len(yticklabels)
    # xticks is list of numbers to set placement of x-axis labels.
    xticks = [sp * (i + 1) for i in range(len(xticklabels))]

    # y is list of numbers to set y-axis placement of every bar.
    y = [
        pi + i // len(xticklabels) * sp
        for i in range(len(yticklabels) * len(xticklabels))
    ]
    # yticks is list of numbers to set placement of y-axis labels.
    yticks = [sp * (i + 1) for i in range(len(yticklabels))]

    z = 0  # value of bottom of every bar
    dx = d  # thickness of bar
    dy = d  # width of bar
    # Hide dz == 0 bars:
    #   https://stackoverflow.com/questions/70196729/matplotlib-hide-bar-in-bar3d-if-height-is-zero
    dz = cers
    s0 = 0
    s1 = -1
    ax.bar3d(x[s0:s1], y[s0:s1], z, dx, dy, dz[s0:s1], alpha=0.6)
    ax.set_xticks(xticks)
    fs = 8
    lpad = 30
    # tlpad = 0.5
    xha = "right"
    yha = "left"
    ax.set_xticklabels(
        xticklabels,
        fontdict={"fontsize": fs, "horizontalalignment": xha},
    )
    ax.set_yticks(yticks)
    ax.set_yticklabels(
        yticklabels,
        fontdict={"fontsize": fs, "horizontalalignment": yha},
    )
    ax.xaxis.labelpad = lpad
    ax.yaxis.labelpad = lpad
    ax.set_xlabel("Model Name")
    ax.set_ylabel("ISO_Language")
    ax.set_zlabel("CER")

    plt.show()


def get_best_model(model_data):
    # Determine best_model and its CER.
    best_model = [None, None]
    for m in model_data:
        # a = m.cer_avg
        a = m.cer_group
        if best_model[0] is None or a < best_model[1]:
            best_model = [m.name, a]
    return best_model


def prepare_chart_data(chart_type, model_data, out_dir, model_names=None):
    x = None
    y = None
    z = None
    out_file = None
    title = None
    xlabel = None
    ylabel = None

    if chart_type == "summary" and model_names is not None:
        # Print data table to stdout.
        print("Model Name\tCER")
        for m in model_data:
            # print(f"{m.name}\t{m.cer_avg}\t{round(m.cer_sum, 4)}/{m.data_ct}")
            print(f"{m.name}\t{m.cer_group}")

        # Get CER averages by model.
        # cer_values = [m.cer_avg for m in model_data]
        cer_values = [m.cer_group for m in model_data]

        # Remove models whose CERs are greater than cer_limit.
        cer_limit = 0.1
        model_names_limited = []
        cer_values_limited = []
        for i, m in enumerate(model_names):
            if cer_values[i] <= cer_limit or m == "Latin":
                model_names_limited.append(m)
                cer_values_limited.append(cer_values[i])

        # Prepare plot data.
        x = model_names_limited
        y = cer_values_limited
        out_file = out_dir / "models-below-0.10-CER.png"
        title = "Models Below 10% CER"
        xlabel = "Model Name"
        ylabel = "Character Error Rate"
    elif chart_type == "best":
        # Determine best_model and its CER.
        best_model = get_best_model(model_data)

        # List CER values and filtered ISO_Langs.
        cer_values = []
        lang_names_filtered = []
        for m in model_data:
            if m.name == best_model[0]:
                for lg in m.lang_data:
                    cer_values.append(lg.cer_group)
                    lang_names_filtered.append(lg.name)
                break

        # Print data table to stdout.
        print("ISO_Language\tCER")
        for lg, c in zip(lang_names_filtered, cer_values):
            print(f"{lg}\t{c}")

        x = lang_names_filtered
        y = cer_values
        out_file = out_dir / "best-model-perf-by-lang.png"
        title = f"CERs by ISO_Language for model: {best_model[0]}"
        xlabel = "ISO_Language"
        ylabel = "Character Error Rate"
    elif chart_type == "comp" and model_names is not None:
        for i, n in enumerate(model_names[:]):
            if n == "best":
                n = get_best_model(model_data)[0]
                model_names[i] = n
        m1 = model_names[0]
        m2 = model_names[1]

        print(f"Updated {model_names = }")
        x1, y1, z1, outf1, t1, xl1, yl1 = prepare_chart_data(
            "model", model_data, out_dir, model_names=[m1]
        )
        x2, y2, z2, outf2, t2, xl2, yl2 = prepare_chart_data(
            "model", model_data, out_dir, model_names=[m2]
        )

        x = x1
        y = y1
        z = y2
        out_file = out_dir / f"comp-{m1}-{m2}.png"
        title = f"CER Comparison for {m1} & {m2}"
        xlabel = xl1
        ylabel = yl1
    elif chart_type == "model" and model_names is not None:
        model_name = model_names[0]
        # List CER values and filtered ISO_Langs.
        cer_values = []
        lang_names_filtered = []
        for m in model_data:
            if m.name == model_name:
                for lg in m.lang_data:
                    cer_values.append(lg.cer_group)
                    lang_names_filtered.append(lg.name)
                break

        print(f"{model_name = }")

        # Print data table to stdout.
        print("ISO_Language\tCER")
        for lg, c in zip(lang_names_filtered, cer_values):
            print(f"{lg}\t{c}")

        x = lang_names_filtered
        y = cer_values
        out_file = out_dir / f"{model_name}-perf-by-lang.png"
        title = f"CERs by ISO_Language for model: {model_name}"
        xlabel = "ISO_Language"
        ylabel = "Character Error Rate"
    return x, y, z, out_file, title, xlabel, ylabel


def get_args():
    description = (
        "Create and show various charts of CERs vs Tesseract models and languages."
    )
    parser = argparse.ArgumentParser(
        description=description,
        # formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-t",
        "--chart-type",
        nargs=1,
        type=str,
        help="type of chart to display",
    )
    parser.add_argument(
        "-l",
        "--models",
        nargs="+",
        type=str,
        help="language models to display",
    )

    return parser.parse_args()


def main():
    chart_types = {
        "3d",
        "best",
        "comp",
        "comparison",
        "model",
        "summary",
    }

    args = get_args()

    # Prepare csv_data.
    csv_file = (
        Path(__file__).expanduser().resolve().parents[1]
        / "data"
        / "evaluation"
        / "data.csv"
    )
    if not csv_file.is_file():
        print(f"ERROR: File does not exist: {str(csv_file)}")
    csv_data = get_csv_data(csv_file)

    # Prepare sorted lists of model_names and iso_langs.
    all_model_names = list(set([r.get("model") for r in csv_data]))
    all_model_names.sort()
    iso_langs = list(set([r.get("iso_lang") for r in csv_data]))
    iso_langs.sort()

    # model_data is a list of GroupedData objects of models.
    model_data = [
        GroupedData(m, [r for r in csv_data if r.get("model") == m])
        for m in all_model_names
    ]

    # lang_data is a list of iso_lang GroupedData objects.
    for m in model_data:
        m.lang_data = []
        for lg in iso_langs:
            sub_data = [r for r in m.data if r.get("iso_lang") == lg]
            if sub_data:
                m.lang_data.append(GroupedData(lg, sub_data))

    plt.style.use("_mpl-gallery")
    out_dir = csv_file.parent

    # Set output variables.
    chart_type = "summary"
    if args.chart_type is not None:
        if args.chart_type[0] in chart_types:
            chart_type = args.chart_type[0]
        else:
            print(f"ERROR: Valid chart types: {', '.join(chart_types)}")
            exit(1)
    if chart_type == "summary" and args.models is not None:
        print("INFO: Models not needed for summary chart")
    models = ["Latin", "best"]
    if len(args.models) == 1:
        models = ["Latin", args.models[0]]
    elif len(args.models) >= 2:
        models = args.models[:2]
        if len(args.models) > 2:
            print(f"INFO: Ignoring extra models: {', '.join(args.models[2:])}")

    # Output chosen chart with chosen language models.
    if chart_type == "3d":
        data_slices = build_3d_slices(model_data)
        plot_bar3d(data_slices)

    elif chart_type == "best":
        # Show best model summary chart of CER by ISO_Language.
        x, y, z, out_file, title, xlabel, ylabel = prepare_chart_data(
            "best", model_data, out_dir
        )
        plot_bar2d(x, y, z, out_file, title, xlabel, ylabel)

    elif chart_type in ["comp", "comparison"]:
        print(f"INFO: Comparing {models = }")

        # Produce summary chart with both 'best' and 'Latin' models together.
        x, y, z, outf, t, xl, yl = prepare_chart_data(
            "comp", model_data, out_dir, model_names=models
        )
        plot_bar2d(x, y, z, outf, t, xl, yl)

    elif chart_type == "model":
        # Show summary chart of CER by ISO_Language for the given model.
        model = models[0]
        if len(models) > 1:
            print(f"INFO: Ignoring extra models: {', '.join(models[1:])}")
        x, y, z, outf, t, xl, yl = prepare_chart_data(
            "model", model_data, out_dir, model_names=[model]
        )
        plot_bar2d(x, y, z, outf, t, xl, yl)

    elif chart_type == "summary":
        # Show summary chart of CER by Model Name.
        x, y, z, outf, t, xl, yl = prepare_chart_data(
            "summary", model_data, out_dir, model_names=all_model_names
        )
        plot_bar2d(x, y, z, outf, t, xl, yl)


if __name__ == "__main__":
    main()
