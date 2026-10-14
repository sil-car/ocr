#!/usr/bin/env python3

# Show bar chart with CER on Y-axis and Model Name on X-axis.

import argparse
import csv
import sys
from dataclasses import dataclass
from itertools import groupby
from operator import attrgetter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

CHART_TYPES = {
    "best",
    "comp",
    "language",
    "model",
    "summary",
}
SUMMARY_Y_AXIS_MIN = 800


@dataclass
class ChartData:
    # x, y, z, out_file, title, xlabel, ylabel
    term_title: str = None
    term_lines: list = None
    x: np.array = None
    y: np.array = None
    z: np.array = None
    out_file: Path = None
    title: str = None
    x_label: str = None
    y_label: str = None

@dataclass
class EvalItem:
    # iso_lang,image-file,truth-text-file,model,ocr-text-file,cer,number-truth,substitutions,deletions,insertions,hits
    row: dict

    @property
    def cer(self):
        return float(self.row.get("cer"))

    @property
    def document(self):
        return Path(self.image_file).name.split("-p")[0]

    @property
    def deletions(self):
        return int(self.row.get("deletions"))

    @property
    def hits(self):
        return int(self.row.get("hits"))

    @property
    def image_file(self):
        return self.row.get("image-file")

    @property
    def insertions(self):
        return int(self.row.get("insertions"))

    @property
    def iso_lang(self):
       return self.row.get("iso_lang")

    @property
    def model(self):
        return self.row.get("model")

    @property
    def substitutions(self):
        return int(self.row.get("substitutions"))


class EvalDocument:
    def __init__(self, name=None, items=None):
        if items is None:
            items = []
        self.items = items
        self._name = name
        self._cer = None
        self._deletions = None
        self._hits = None
        self._insertions = None
        self._iso = None
        self._model = None
        self._substitutions = None

    @property
    def cer(self):
        """Return CER calculated collectively over all document items."""
        if self._cer is None:
            self._cer = calculate_cer(
                self.substitutions,
                self.deletions,
                self.insertions,
                self.hits,
            )
        return self._cer

    @property
    def deletions(self):
        if self._deletions is None:
            self._deletions = sum(int(i.deletions) for i in self.items)
        return self._deletions

    @property
    def name(self):
        if self._name is None and self.items:
            self._name = self.items[0].document
        return self._name

    @property
    def hits(self):
        if self._hits is None:
            self._hits = sum(int(i.hits) for i in self.items)
        return self._hits

    @property
    def insertions(self):
        if self._insertions is None:
            self._insertions = sum(int(i.insertions) for i in self.items)
        return self._insertions

    @property
    def iso(self):
        if self._iso is None and self.items:
           self._iso = self.items[0].iso_lang
        return self._iso

    @property
    def model(self):
        if self._model is None and self.items:
            self._model = self.items[0].model
        return self._model

    @property
    def substitutions(self):
        if self._substitutions is None:
            self._substitutions = sum(int(i.substitutions) for i in self.items)
        return self._substitutions


class EvalLanguage:
    def __init__(self, items=None):
        if items is None:
            items = []
        self.items = items
        self._cer = None
        self._documents = None
        self._iso = None
        self._language = None
        self._model = None

    @property
    def cer(self):
        """Return average CER of all documents."""
        if self._cer is None:
            self._cer = round(np.average([d.cer for d in self.documents]), 4)
        return self._cer

    @property
    def documents(self):
        if self._documents is None:
            self._documents = [
                EvalDocument(items=list(group))
                for _, group in groupby(self.items, key=attrgetter('document'))
            ]
        return self._documents

    @property
    def iso(self):
        if self._iso is None and self.items:
            self._iso = self.items[0].iso_lang
        return self._iso

    @property
    def model(self):
        if self._model is None and self.items:
            self._model = self.items[0].model
        return self._model

    @property
    def name(self):
        return self.iso


class EvalModel:
    def __init__(self, name=None, items=None):
        if items is None:
            items = []
        self.items = items
        self._name = name
        self._cer = None
        self._cers = None
        self._stdev = None
        self._languages = None
        self._pmcer = None
        self._score = None

    @property
    def languages(self):
        if self._languages is None:
            self._languages = [
                EvalLanguage(items=list(group))
                for _, group in groupby(self.items, key=attrgetter('iso_lang'))
            ]
        return self._languages

    @property
    def name(self):
        if self._name is None and self.items:
            self._name = self.items[0].model
        return self._name

    @property
    def cer(self):
        """Average CER over each recognized data grouping."""
        if self._cer is None:
            self._cer = round(np.average(self.cers), 4)
        return self._cer

    @property
    def cers(self):
        if self._cers is None:
            self._cers = [lg.cer for lg in self.languages]
        return self._cers

    @property
    def pmcer(self):
        """Return the power mean CER.
        The power mean of the per-language CERs always improves when any
        language improves, but weighs the bad languages more heavily.
        """
        if self._pmcer is None:
            p = 2
            cers = np.asarray(self.cers)
            self._pmcer = round(np.mean(cers ** p) ** (1 / p), 4)
        return self._pmcer

    @property
    def score(self):
        """Score is an empirical value based on model's overall CER and it's
       standard deviation.

       It has been superseded by Power Mean CER."""
        if self._score is None and self.stdev:
            self._score = round(
                1000
                / (0.75 * (1 + self.cer) + 0.25 * (1 + self.stdev)) ** 2,
            )
        return self._score

    @property
    def stdev(self):
        if self._stdev is None and len(self.cers) > 1:
            self._stdev = round(np.std(self.cers, ddof=1), 4)
        return self._stdev

    def get_language(self, iso):
        return next((lg for lg in self.languages if lg.iso == iso), None)

    def __str__(self):
        return self.name


class EvalCollection:
    def __init__(self):
        self.data_file = Path(__file__).parents[1] / "data" / "evaluation" / "data.csv"
        self.out_dir = self.data_file.parent
        self._data = None
        self._documents = None
        self._isos = None
        self._items = None
        self._model_names = None
        self._models = None

    @property
    def data(self):
        if self._data is None:
            with self.data_file.open(newline="") as c:
                reader = csv.DictReader(c)
                self._data = [r for r in reader]
        return self._data

    @property
    def items(self):
        if self._items is None:
            self._items = (EvalItem(r) for r in self.data)
        return self._items

    @property
    def isos(self):
        if self._isos is None and self.items:
            self._isos = sorted({i.iso_lang for i in self.items})
        return self._isos

    @property
    def model_names(self):
        if self._model_names is None:
            self._model_names = sorted([m.name for m in self.models])
        return self._model_names

    @property
    def models(self):
        if self._models is None:
            self._models = [
                EvalModel(items=list(group))
                for _, group in groupby(self.items, key=attrgetter('model'))
            ]
        return self._models

    def best_model(self, basis="pmcer"):
        """Return the best-performing model using the given basis."""
        basis = basis.lower()
        if basis == "score":
            best = max(self.models, key=lambda x: getattr(x, basis))
        else:
            best = min(self.models, key=lambda x: getattr(x, basis))
        return best

    def chart_data(
        self,
        basis="cer",
        chart_type="summary",
        iso=None,
        model_names=None,
    ):
        basis = basis.lower()
        if model_names is None:
            model_names = []
        elif model_names == "all":
            model_names = self.model_names

        match chart_type:
            case "best":
                chart_data = self._chart_data__best(basis)
            case "comp":
                chart_data = self._chart_data__comparison(basis, model_names)
            case "language":
                chart_data = self._chart_data__language(iso)
            case "model":
                chart_data = self._chart_data__model(model_names[0])
            case "summary":
                chart_data = self._chart_data__summary(basis)
        return chart_data

    def _chart_data__best(self, basis):
        best_model = self.best_model(basis=basis)
        chart_data = ChartData()
        y = []
        isos = []
        for lg in best_model.languages:
            y.append(lg.cer)
            isos.append(lg.iso)
        chart_data.term_title = f"ISO_Language\tCER for {best_model.name}"
        chart_data.term_lines = [f"{lg}\t{c}" for lg, c in zip(isos, y)]
        chart_data.title = f"CERs by ISO_Language for model: {best_model.name}"
        chart_data.x = isos
        chart_data.y = y
        chart_data.out_file = self.out_dir / "best-model-perf-by-lang.png"
        chart_data.x_label = "ISO_Language"
        chart_data.y_label = "Character Error Rate"
        return chart_data

    def _chart_data__comparison(self, basis, model_names):
        chart_data = ChartData()
        best_model = self.best_model(basis=basis)
        for i, n in enumerate(model_names[:]):
            if n == "best":
                model_names[i] = best_model.name
        n1, n2 = model_names
        m1 = None
        m2 = None
        for m in self.models:
            if n1 == m.name:
                m1 = m
            elif n2 == m.name:
                m2 = m
            if m1 and m2:
                break

        chart_data.title = f"CER Comparison for {m1.name} & {m2.name}"
        chart_data.x = [lg.iso for lg in m1.languages]
        chart_data.y = [lg.cer for lg in m1.languages]
        chart_data.z = [lg.cer for lg in m2.languages]
        chart_data.x_label = "ISO_Language"
        chart_data.y_label = "Character Error Rate"
        chart_data.out_file = self.out_dir / f"comp-{m1.name}-{m2.name}.png"
        return chart_data

    def _chart_data__language(self, iso):
        iso = iso.lower()
        chart_data = ChartData()
        # List CER values.
        cers = []
        models = []
        for m in self.models:
            lg = m.get_language(iso)
            cers.append(lg.cer)
            models.append(m.name)
        chart_data.term_title = "Model\tCER"
        chart_data.term_lines = [f"{m}\t{c}" for m, c in zip(models, cers)]
        chart_data.title = f"CERs by model for ISO_Language: {iso}"
        chart_data.x = models
        chart_data.y = cers
        chart_data.x_label = "Model"
        chart_data.y_label = "Character Error Rate"
        chart_data.out_file = self.out_dir / f"{iso}-perf-by-model.png"
        return chart_data

    def _chart_data__model(self, name):
        chart_data = ChartData()
        model = None
        for m in self.models:
            if m.name == name:
                model = m
                break
        if model is None:
            print(f"Error: Model not found: {name}")
            sys.exit(1)

        # List CER values and filtered ISO_Langs.
        cers = []
        isos = []
        for lg in model.languages:
            cers.append(lg.cer)
            isos.append(lg.iso)
        chart_data.term_title = "ISO_Language\tCER"
        chart_data.term_lines = [f"{lg}\t{c}" for lg, c in zip(isos, cers)]
        chart_data.term_lines.append(f"PM-CER\t{model.pmcer}")
        chart_data.title = f"CERs by ISO_Language for model: {model.name}"
        chart_data.x = isos
        chart_data.y = cers
        chart_data.x_label = "ISO_Language"
        chart_data.y_label = "Character Error Rate"
        chart_data.out_file = self.out_dir / f"{model.name}-perf-by-lang.png"
        return chart_data

    def _chart_data__summary(self, basis):
        chart_data = ChartData()
        chart_data.term_title = f"Model Name{" "*14}  {basis.upper()}"
        chart_data.x = []
        chart_data.y = []
        chart_data.term_lines = []
        for m in self.top_models(basis=basis):
            chart_data.x.append(m.name)
            chart_data.y.append(getattr(m, basis))
            chart_data.term_lines.append(f"{m.name:24}  {getattr(m, basis)}")
        chart_data.x_label = "Model Name"

        if basis == "score":
            chart_data.title = "Top Models by Score"
            chart_data.y_label = "Score (function of CER & STDEV; perfect: 1000)"
        elif basis == "cer":
            chart_data.title = "Top Models by CER"
            chart_data.y_label = "CER"
        elif basis == "pmcer":
            chart_data.title = "Top Models by Power Mean CER"
            chart_data.y_label = "Power Mean CER"
        chart_data.out_file = self.out_dir / f"top-models-by-{basis}.png"
        return chart_data

    def top_models(self, basis="pmcer", count=5):
        """Return a list of best-performing models using the given basis."""
        basis = basis.lower()
        top = sorted(self.models, key=attrgetter(basis))[:count]
        top.sort(key=attrgetter("name"))  # re-sort by model name
        top.insert(0, self.models[0])  # add Latin
        return top


def calculate_cer(subs, dels, ins, hits):
    """Return CER, calcluated as (S + D + I) / (C + S + D)"""
    return round((subs + dels + ins) / (hits + subs + dels), 4)


def plot_bar2d(cd, plottype="cer"):
    # Print table to terminal.
    if cd.term_title:
        print(cd.term_title)
    if cd.term_lines:
        for i in cd.term_lines:
            print(i)

    # Prepare plot.
    bw = 0.3  # bar width
    lw = 0.5  # line width

    _, ax = plt.subplots(figsize=(8, 7))

    plt.subplots_adjust(
        left=0.1, bottom=0.30, right=0.9, top=0.8, wspace=0.1, hspace=0.1
    )
    plt.title(cd.title, pad=12.0)

    if cd.z is not None:
        # Ref: https:/DataRow/stackoverflow.com/questions/10369681
        ind = np.arange(len(cd.x))
        lx = cd.title.split("&")[0].split()[-1].strip()  # hack
        lz = cd.title.split("&")[1].strip()  # hack
        plt.xticks(ind + bw / 2, cd.x, horizontalalignment="right", rotation=60)
        ax.bar(ind - 0.1, cd.y, width=bw, edgecolor="w", linewidth=lw, label=lx)
        ax.bar(
            ind + 0.1,
            cd.z,
            width=bw,
            edgecolor="w",
            linewidth=lw,
            facecolor="rosybrown",
            label=lz,
        )
        plt.legend(loc="best")
    else:
        plt.xticks(horizontalalignment="right", rotation=60)
        ax.bar(cd.x, cd.y, width=bw, edgecolor="blue", linewidth=0)
    # Remove x-axis grid lines.
    ax.tick_params(axis="x", grid_linewidth=0)
    # Add axis labels.
    ax.set_xlabel(cd.x_label)
    ax.set_ylabel(cd.y_label)
    if plottype in ("cer", "pmcer"):
        # Add shaded thresholds.
        ax.axhspan(
            0, 0.05, alpha=0.1, color="yellow", zorder=0.0
        )  # 5% CER threshold shading
        ax.axhspan(
            0, 0.02, alpha=0.2, color="green", zorder=0.1
        )  # 2% CER threshold shading
    elif plottype == "score":
        # Set y-axis limits.
        ax.set_ylim([SUMMARY_Y_AXIS_MIN, 1000])
        # Add shaded thresholds.
        ax.axhspan(
            900, 1000, alpha=0.1, color="yellow", zorder=0.0
        )  # 900 threshold shading
        ax.axhspan(
            980, 1000, alpha=0.2, color="green", zorder=0.1
        )  # 980 threshold shading

    # Show plot.
    plt.savefig(cd.out_file)
    plt.show()
    sys.exit()


def get_args():
    description = (
        "Create and show various charts of CERs vs Tesseract models and languages."
    )
    parser = argparse.ArgumentParser(
        description=description,
    )
    parser.add_argument(
        "-b",
        "--basis",
        type=str,
        choices=("cer", "pmcer"),
        default="pmcer",
        help="property used for comparing models",
    )
    parser.add_argument(
        "-t",
        "--chart-type",
        type=str,
        default="summary",
        choices=CHART_TYPES,
        help="type of chart to display",
    )
    parser.add_argument(
        "-l",
        "--language-iso",
        type=str,
        default=[],
        help="language to display",
    )
    parser.add_argument(
        "-m",
        "--models",
        nargs="+",
        type=str,
        default=[],
        help="OCR models to display",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main():
    plt.style.use("_mpl-gallery")
    args = get_args()

    if args.test:
        c = EvalCollection()
        print(f"{c.models[0].name=}")
        sys.exit()

    # Set output variables.
    if args.chart_type == "summary" and args.models:
        print("INFO: Models not needed for summary chart")

    models = ["Latin", "best"]
    if len(args.models) == 1:
        models[1] = args.models[0]
    elif len(args.models) >= 2:
        models = args.models[:2]
        if len(args.models) > 2:
            print(f"INFO: Ignoring extra models: {', '.join(args.models[2:])}")

    # Output chosen chart with chosen language models.
    eval_data = EvalCollection()
    if args.chart_type == "best":
        # Show best model summary chart of CER by ISO_Language.
        chart_data = eval_data.chart_data(chart_type=args.chart_type)
    elif args.chart_type.startswith("comp"):
        # Produce summary chart with both 'best' and 'Latin' models together.
        chart_data = eval_data.chart_data(chart_type=args.chart_type, model_names=models)
    elif args.chart_type == "language":
        # Show CER bar for each model in the given language (ISO).
        if not args.models:
            models = "all"
        else:
            models = args.models
        chart_data = eval_data.chart_data(
            chart_type=args.chart_type,
            iso=args.language_iso,
            model_names=models,
        )
    elif args.chart_type == "model":
        # Show summary chart of CER by ISO_Language for the given model.
        if not args.models:
            print("ERROR: Please pass a model name; e.g. '-m Latin'")
            sys.exit(1)
        model = args.models[0]
        if len(args.models) > 1:
            print(f"INFO: Ignoring extra models: {', '.join(models[1:])}")
        chart_data = eval_data.chart_data(chart_type=args.chart_type, model_names=[model])
    elif args.chart_type == "summary":
        # Show summary chart of scores by Model Name.
        chart_data = eval_data.chart_data(basis=args.basis)

    plot_bar2d(chart_data, plottype=args.basis)


if __name__ == "__main__":
    main()
