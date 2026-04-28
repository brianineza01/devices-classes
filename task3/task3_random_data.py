import base64
import io
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import NotRequired, TypedDict

import numpy as np
import seaborn as sns
import tkinter as tk
import matplotlib.dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

CHART_TYPES = ["line", "bar", "scatter", "step", "stem"]
DEFAULT_CHART_TYPE = "line"



class ChartFigureConfig(TypedDict):
    x_axis_value_key: str
    y_axis_values_key: str
    title: str
    x_axis_label: str
    y_axis_label: str
    x_axis_unit: NotRequired[str]
    y_axis_unit: NotRequired[str]


class ChartPanelConfig(TypedDict):
    id: str
    panel_title: str
    records_key: str
    x_axis_value_key: str
    y_axis_values_key: str
    title: str
    x_axis_label: str
    y_axis_label: str
    x_axis_unit: NotRequired[str]
    y_axis_unit: NotRequired[str]
    default_chart_type: NotRequired[str]


CHART_PANELS: list[ChartPanelConfig] = json.loads(
    json.dumps(
        [
            {
                "id": "p0",
                "panel_title": "Temperature (°C)",
                "records_key": "temperature",
                "x_axis_value_key": "time",
                "y_axis_values_key": "temperature_c",
                "title": "temperature_c",
                "x_axis_label": "Time",
                "y_axis_label": "Temperature",
                "y_axis_unit": "°C",
            },
            {
                "id": "p1",
                "panel_title": "Pressure (hPa)",
                "records_key": "pressure",
                "x_axis_value_key": "time",
                "y_axis_values_key": "pressure_hpa",
                "title": "pressure_hpa",
                "x_axis_label": "Time",
                "y_axis_label": "Pressure",
                "y_axis_unit": "hPa",
            }
        ]
    )
)


def format_axis_label(label: str, unit: str | None) -> str:
    if unit is None:
        return label
    u = str(unit).strip()
    return f"{label} ({u})" if u else label


def panel_figure_config(panel: ChartPanelConfig) -> ChartFigureConfig:
    cfg: ChartFigureConfig = {
        "x_axis_value_key": panel["x_axis_value_key"],
        "y_axis_values_key": panel["y_axis_values_key"],
        "title": panel["title"],
        "x_axis_label": panel["x_axis_label"],
        "y_axis_label": panel["y_axis_label"],
    }
    if (xu := panel.get("x_axis_unit")) and str(xu).strip():
        cfg["x_axis_unit"] = str(xu).strip()
    if (yu := panel.get("y_axis_unit")) and str(yu).strip():
        cfg["y_axis_unit"] = str(yu).strip()
    return cfg


def chart_config_display_text(config: ChartFigureConfig) -> str:
    return json.dumps(config, indent=2, sort_keys=True)


@dataclass(frozen=True)
class SensorAppState:
    datasets: dict[str, list[dict[str, object]] | None]
    chart_types: dict[str, str]
    grid_visible: bool = True


def normalize_chart_type(value: str) -> str:
    return value if value in CHART_TYPES else DEFAULT_CHART_TYPE


def parse_sample_count(text: str) -> int:
    try:
        n = int(text)
    except ValueError:
        n = 60
    return max(2, min(n, 10_000))


def generate_temperature_records(n: int, rng: np.random.Generator) -> list[dict[str, object]]:
    start = datetime(2024, 1, 1, tzinfo=None)
    rows: list[dict[str, object]] = []
    for i in range(n):
        t = start + timedelta(minutes=i)
        rows.append(
            {
                "time": t.isoformat(),
                "temperature_c": float(20 + rng.standard_normal() * 3),
            }
        )
    return json.loads(json.dumps(rows))


def generate_pressure_records(n: int, rng: np.random.Generator) -> list[dict[str, object]]:
    start = datetime(2024, 1, 1, tzinfo=None)
    rows: list[dict[str, object]] = []
    for i in range(n):
        t = start + timedelta(minutes=i)
        rows.append(
            {
                "time": t.isoformat(),
                "pressure_hpa": float(1013 + rng.standard_normal() * 5),
            }
        )
    return json.loads(json.dumps(rows))


def _parse_time_value(v: object) -> datetime:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        s = v[:-1] + "+00:00" if v.endswith("Z") else v
        return datetime.fromisoformat(s)
    raise TypeError(f"expected time as str or datetime, got {type(v).__name__}")


def coerce_time_axis_x(xk: str, raw: list[object]) -> tuple[list[object], bool]:
    if xk != "time":
        return raw, False
    return [_parse_time_value(v) for v in raw], True


def _annotate_x_text(xi: object) -> str:
    if isinstance(xi, datetime):
        return xi.strftime("%H:%M:%S")
    return str(xi)


def draw_series(ax, x, y, chart_type: str) -> None:
    current = normalize_chart_type(chart_type)
    y_seq = list(y)
    if current == "line":
        sns.lineplot(x=x, y=y_seq, ax=ax)
        ax.scatter(x, y_seq, color="red", s=50, zorder=5)
    elif current == "bar":
        sns.barplot(x=x, y=y_seq, ax=ax)
        for i, bar in enumerate(ax.patches):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{float(y_seq[i]):.2f}",
                ha="center",
                va="bottom",
            )
    elif current == "scatter":
        sns.scatterplot(x=x, y=y_seq, ax=ax)
        for xi, yi in zip(x, y_seq):
            ax.annotate(
                f"({_annotate_x_text(xi)}, {float(yi):.2f})",
                (xi, yi),
                xytext=(5, 5),
                textcoords="offset points",
            )
    elif current == "step":
        ax.step(x, y_seq, where="post")
        ax.scatter(x, y_seq, color="red", s=50, zorder=5)
    elif current == "stem":
        ax.stem(x, y_seq)


def render_chart_figure(
    figure: Figure,
    records: list[dict[str, object]] | None,
    chart_type: str,
    config: ChartFigureConfig,
    *,
    show_grid: bool,
) -> None:
    figure.clear()
    figure.subplots_adjust(bottom=0.24)
    if not records:
        return
    xk = config["x_axis_value_key"]
    yk = config["y_axis_values_key"]
    x, x_is_time = coerce_time_axis_x(xk, [r[xk] for r in records])
    y = [r[yk] for r in records]
    ax = figure.add_subplot(111)
    draw_series(ax, x, y, chart_type)
    ax.set_title(config["title"])
    xu: str | None = config.get("x_axis_unit")
    yu: str | None = config.get("y_axis_unit")
    ax.set_xlabel(format_axis_label(config["x_axis_label"], xu))
    ax.set_ylabel(format_axis_label(config["y_axis_label"], yu))
    if x_is_time and len(x) >= 2:
        t0, t1 = x[0], x[-1]
        if isinstance(t0, datetime) and isinstance(t1, datetime):
            span = t1 - t0
            fmt = "%H:%M:%S" if span.days == 0 else "%Y-%m-%d %H:%M:%S"
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
            ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
    ax.tick_params(axis="x", rotation=40, labelsize=9)
    for lb in ax.get_xticklabels():
        lb.set_horizontalalignment("right")
    if show_grid:
        ax.grid(True, linestyle="--", alpha=0.4)
    else:
        ax.grid(False)


def status_for_state(state: SensorAppState, panels: list[ChartPanelConfig]) -> str:
    parts: list[str] = []
    for p in panels:
        pid = p["id"]
        key = p["records_key"]
        rows = state.datasets.get(key)
        n = len(rows) if rows else 0
        ct = normalize_chart_type(state.chart_types.get(pid, DEFAULT_CHART_TYPE))
        parts.append(f"{pid}: {ct} ({n} rows)")
    return " · ".join(parts)


def figure_to_tk_photo(figure: Figure, canvas: FigureCanvasAgg) -> tk.PhotoImage:
    canvas.draw()
    buf = io.BytesIO()
    figure.savefig(buf, format="png")
    buf.seek(0)
    return tk.PhotoImage(data=base64.b64encode(buf.getvalue()))


def initial_chart_types(panels: list[ChartPanelConfig]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in panels:
        d = p.get("default_chart_type", DEFAULT_CHART_TYPE)
        out[p["id"]] = normalize_chart_type(d)
    return out


class RandomSensorApp:
    def __init__(self) -> None:
        self.panels = CHART_PANELS
        self.root = tk.Tk()
        self.root.title("Random Temperature & Pressure")
        self.root.geometry("1200x800")

        self.figures: dict[str, Figure] = {}
        self.figure_canvases: dict[str, FigureCanvasAgg] = {}
        self.chart_photos: dict[str, tk.PhotoImage | None] = {p["id"]: None for p in self.panels}
        self.chart_labels: dict[str, tk.Label] = {}
        self.chart_type_vars: dict[str, tk.StringVar] = {}
        for p in self.panels:
            pid = p["id"]
            self.figures[pid] = Figure(figsize=(5.5, 5), dpi=100)
            self.figure_canvases[pid] = FigureCanvasAgg(self.figures[pid])
            v = tk.StringVar(self.root)
            v.set(initial_chart_types(self.panels)[pid])
            self.chart_type_vars[pid] = v

        self.samples_var = tk.StringVar(value="60")

        empty_ds: dict[str, list[dict[str, object]] | None] = {p["records_key"]: None for p in self.panels}
        self._state = SensorAppState(
            datasets=empty_ds,
            chart_types=initial_chart_types(self.panels),
            grid_visible=True,
        )

        top = tk.Frame(self.root)
        top.pack(pady=5, padx=10, fill="x")
        tk.Button(top, text="Generate data", command=self._generate_and_render).pack(side="left")
        tk.Label(top, text="Samples:").pack(side="left", padx=(12, 2))
        tk.Entry(top, textvariable=self.samples_var, width=8).pack(side="left")
        for p in self.panels:
            pid = p["id"]
            tk.Label(top, text=f"Chart ({pid}):").pack(side="left", padx=(12, 2))
            tk.OptionMenu(
                top,
                self.chart_type_vars[pid],
                *CHART_TYPES,
                command=lambda _v, i=pid: self._on_chart_type_change(i),
            ).pack(side="left")

        render = tk.Frame(self.root)
        render.pack(pady=5, padx=10, fill="x")
        tk.Button(render, text="Render all", command=self._render_all).pack(side="left")
        self.grid_button = tk.Button(render, text="Grid: On", command=self._toggle_grid)
        self.grid_button.pack(side="left", padx=(12, 0))
        for p in self.panels:
            pid = p["id"]
            tk.Button(
                render,
                text=f"Render {pid}",
                command=lambda i=pid: self._render_panel(i),
            ).pack(side="left", padx=(8, 0))
        self.status_label = tk.Label(render, text="Generating random sensor data")
        self.status_label.pack(pady=(8, 0))

        charts = tk.Frame(self.root)
        charts.pack(pady=5, padx=10, fill="both", expand=True)
        for i, p in enumerate(self.panels):
            pid = p["id"]
            padx = (0, 5) if i == 0 else (5, 0)
            frame = tk.LabelFrame(charts, text=p["panel_title"])
            frame.pack(side="left", fill="both", expand=True, padx=padx)
            tk.Label(frame, text="Graph configuration", font=("", 9, "bold")).pack(anchor="w", padx=4, pady=(4, 0))
            tk.Label(
                frame,
                text=chart_config_display_text(panel_figure_config(p)),
                justify=tk.LEFT,
                anchor="nw",
                font=("TkFixedFont", 10),
            ).pack(fill="x", padx=4, pady=(0, 4))
            lab = tk.Label(frame)
            lab.pack(fill="both", expand=True)
            self.chart_labels[pid] = lab

        self._generate()

    def _set_state(self, state: SensorAppState) -> None:
        self._state = state

    def _sync_chart_types_from_ui(self) -> None:
        new_ct: dict[str, str] = {}
        for p in self.panels:
            pid = p["id"]
            ct = normalize_chart_type(self.chart_type_vars[pid].get())
            self.chart_type_vars[pid].set(ct)
            new_ct[pid] = ct
        self._set_state(replace(self._state, chart_types=new_ct))

    def _generate(self) -> None:
        n = parse_sample_count(self.samples_var.get())
        rng = np.random.default_rng()
        datasets = dict(self._state.datasets)
        datasets["temperature"] = generate_temperature_records(n, rng)
        datasets["pressure"] = generate_pressure_records(n, rng)
        self._sync_chart_types_from_ui()
        self._set_state(replace(self._state, datasets=datasets))
        self.status_label.config(text=f"Generated {n} samples per series")

    def _on_chart_type_change(self, panel_id: str) -> None:
        ct = normalize_chart_type(self.chart_type_vars[panel_id].get())
        new_ct = dict(self._state.chart_types)
        new_ct[panel_id] = ct
        self.chart_type_vars[panel_id].set(ct)
        self._set_state(replace(self._state, chart_types=new_ct))

    def _toggle_grid(self) -> None:
        on = not self._state.grid_visible
        self._set_state(replace(self._state, grid_visible=on))
        self.grid_button.config(text="Grid: On" if on else "Grid: Off")
        self._render_all()

    def _generate_and_render(self) -> None:
        self._generate()
        self._render_all()

    def _render_panel(self, panel_id: str) -> None:
        self._sync_chart_types_from_ui()
        panel = next(p for p in self.panels if p["id"] == panel_id)
        records = self._state.datasets.get(panel["records_key"])
        render_chart_figure(
            self.figures[panel_id],
            records,
            self._state.chart_types[panel_id],
            panel_figure_config(panel),
            show_grid=self._state.grid_visible,
        )
        self.chart_photos[panel_id] = figure_to_tk_photo(
            self.figures[panel_id], self.figure_canvases[panel_id]
        )
        self.chart_labels[panel_id].config(image=self.chart_photos[panel_id])
        self.status_label.config(text=status_for_state(self._state, self.panels))

    def _render_all(self) -> None:
        self._sync_chart_types_from_ui()
        for p in self.panels:
            self._render_panel(p["id"])


def run() -> None:
    app = RandomSensorApp()
    app.root.mainloop()


if __name__ == "__main__":
    run()
