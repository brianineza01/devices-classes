import base64
import io
import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Iterable, NotRequired, TypedDict

import numpy as np
import seaborn as sns
import tkinter as tk
import matplotlib.dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

CHART_TYPES = ["line", "bar", "scatter", "step", "stem"]
DEFAULT_CHART_TYPE = "line"
MARKER_STYLE_CHOICES = ("o", "s", "^", "v", "D", "P", "X", "*", "p", "h")
SLIDER_TICKS = 10_000



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
class ChartMarker:
    style: str
    x_frac: float
    y_value: float


@dataclass(frozen=True)
class SensorAppState:
    datasets: dict[str, list[dict[str, object]] | None]
    chart_types: dict[str, str]
    markers: dict[str, tuple[ChartMarker, ...]]
    marker_selected_index: dict[str, int | None]
    grid_visible: bool = True


def normalize_chart_type(value: str) -> str:
    return value if value in CHART_TYPES else DEFAULT_CHART_TYPE


def normalize_marker_style(value: str) -> str:
    return value if value in MARKER_STYLE_CHOICES else MARKER_STYLE_CHOICES[0]


def interpolate_x_coord(x_coords: list[object], frac: float) -> object:
    if not x_coords:
        raise ValueError("x_coords must not be empty")
    frac = max(0.0, min(1.0, frac))
    n = len(x_coords)
    if n == 1:
        return x_coords[0]
    a = x_coords[0]
    b = x_coords[-1]
    if isinstance(a, datetime) and isinstance(b, datetime):
        span_sec = (b - a).total_seconds()
        if span_sec <= 0:
            return a
        return a + timedelta(seconds=span_sec * frac)
    return float(a) + (float(b) - float(a)) * frac


def float_bounds_from_numeric(y_numeric: Iterable[object]) -> tuple[float, float]:
    ys = [float(v) for v in y_numeric]
    lo = min(ys)
    hi = max(ys)
    if hi <= lo:
        pad = abs(lo) * 0.05 + 1.0
        return lo - pad, hi + pad
    margin = (hi - lo) * 0.05
    return lo - margin, hi + margin


def draw_seaborn_markers(
    ax,
    *,
    markers: tuple[ChartMarker, ...],
    x_coords: list[object],
    selected_index: int | None,
    selected_caption: str | None = None,
) -> None:
    if not markers:
        return
    palette = sns.color_palette("deep", max(len(markers), 3))
    for i, m in enumerate(markers):
        xv = interpolate_x_coord(x_coords, m.x_frac)
        st = normalize_marker_style(m.style)
        sel = selected_index is not None and i == selected_index
        sns.scatterplot(
            x=[xv],
            y=[m.y_value],
            ax=ax,
            marker=st,
            s=220 if sel else 160,
            color=palette[i % len(palette)],
            edgecolor="black",
            linewidths=3.6 if sel else 0.9,
            zorder=16 if sel else 15,
            legend=False,
        )
    if (
        selected_caption
        and selected_index is not None
        and 0 <= selected_index < len(markers)
    ):
        m = markers[selected_index]
        xv = interpolate_x_coord(x_coords, m.x_frac)
        ax.annotate(
            selected_caption,
            (xv, m.y_value),
            xytext=(10, 10),
            textcoords="offset points",
            fontsize=8,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.85, edgecolor="0.5"),
            zorder=20,
        )


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


def _interpolated_x_display(xi: object, x_is_time: bool, t0: object, t1: object) -> str:
    if x_is_time and isinstance(xi, datetime) and isinstance(t0, datetime) and isinstance(t1, datetime):
        span = t1 - t0
        return xi.strftime("%H:%M:%S") if span.days == 0 else xi.strftime("%Y-%m-%d %H:%M:%S")
    return _annotate_x_text(xi)


def _format_y_readout(y: float, unit: str | None) -> str:
    u = str(unit).strip() if unit is not None else ""
    if u:
        return f"{y:.4g} {u}"
    return f"{y:.4g}"


def marker_readout_strings(
    panel: ChartPanelConfig,
    records: list[dict[str, object]] | None,
    m: ChartMarker,
) -> tuple[str, str] | None:
    if not records:
        return None
    xk = panel["x_axis_value_key"]
    yu = panel.get("y_axis_unit")
    xs = [r[xk] for r in records]
    x, x_is_time = coerce_time_axis_x(xk, xs)
    if not x:
        return None
    xi = interpolate_x_coord(x, m.x_frac)
    t0, t1 = x[0], x[-1]
    xs_s = _interpolated_x_display(xi, x_is_time, t0, t1)
    ys_s = _format_y_readout(m.y_value, yu if yu and str(yu).strip() else None)
    return xs_s, ys_s


def marker_readout_strings_figure(
    config: ChartFigureConfig,
    records: list[dict[str, object]] | None,
    m: ChartMarker,
) -> tuple[str, str] | None:
    if not records:
        return None
    xk = config["x_axis_value_key"]
    yu = config.get("y_axis_unit")
    xs = [r[xk] for r in records]
    x, x_is_time = coerce_time_axis_x(xk, xs)
    if not x:
        return None
    xi = interpolate_x_coord(x, m.x_frac)
    t0, t1 = x[0], x[-1]
    xs_s = _interpolated_x_display(xi, x_is_time, t0, t1)
    ys_s = _format_y_readout(m.y_value, yu if yu and str(yu).strip() else None)
    return xs_s, ys_s


def format_marker_list_label(
    panel: ChartPanelConfig,
    records: list[dict[str, object]] | None,
    index: int,
    m: ChartMarker,
) -> str:
    st = normalize_marker_style(m.style)
    rd = marker_readout_strings(panel, records, m)
    if rd:
        xs, ys = rd
        return f"#{index + 1}  {st}  {xs}  {ys}"
    return f"#{index + 1}  {st}  x={m.x_frac:.0%}  y={m.y_value:.4g}"


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
    markers: tuple[ChartMarker, ...],
    marker_selected_index: int | None,
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
    if markers:
        caption = None
        if (
            marker_selected_index is not None
            and 0 <= marker_selected_index < len(markers)
        ):
            tup = marker_readout_strings_figure(config, records, markers[marker_selected_index])
            if tup:
                caption = f"{tup[0]}\n{tup[1]}"
        draw_seaborn_markers(
            ax,
            markers=markers,
            x_coords=x,
            selected_index=marker_selected_index,
            selected_caption=caption,
        )
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
        self._suppress_marker_slide = False
        self._suppress_marker_list = False

        empty_ds: dict[str, list[dict[str, object]] | None] = {p["records_key"]: None for p in self.panels}
        initial_markers: dict[str, tuple[ChartMarker, ...]] = {p["id"]: () for p in self.panels}
        initial_marker_sel: dict[str, int | None] = {p["id"]: None for p in self.panels}
        self.marker_style_vars: dict[str, tk.StringVar] = {}
        self.marker_x_vars: dict[str, tk.IntVar] = {}
        self.marker_y_vars: dict[str, tk.IntVar] = {}
        self.marker_y_scales: dict[str, tk.Scale] = {}
        self.marker_x_scales: dict[str, tk.Scale] = {}
        self.marker_y_slider_wraps: dict[str, tk.Frame] = {}
        self.marker_x_slider_wraps: dict[str, tk.Frame] = {}
        self.marker_readout_y_labels: dict[str, tk.Label] = {}
        self.marker_readout_x_labels: dict[str, tk.Label] = {}
        self.marker_list_wraps: dict[str, tk.Frame] = {}
        self.marker_listboxes: dict[str, tk.Listbox] = {}
        half = SLIDER_TICKS // 2
        for p in self.panels:
            pid = p["id"]
            self.marker_style_vars[pid] = tk.StringVar(master=self.root, value=MARKER_STYLE_CHOICES[0])
            self.marker_x_vars[pid] = tk.IntVar(master=self.root, value=half)
            self.marker_y_vars[pid] = tk.IntVar(master=self.root, value=half)

        self._state = SensorAppState(
            datasets=empty_ds,
            chart_types=initial_chart_types(self.panels),
            markers=initial_markers,
            marker_selected_index=initial_marker_sel,
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

            ctr = tk.Frame(frame)
            ctr.pack(fill="x", padx=4, pady=(0, 6))
            tk.Label(ctr, text="Marker:").pack(side=tk.LEFT, padx=(0, 4))
            tk.OptionMenu(
                ctr,
                self.marker_style_vars[pid],
                *MARKER_STYLE_CHOICES,
            ).pack(side=tk.LEFT, padx=(0, 6))
            tk.Button(ctr, text="Add marker", command=lambda i=pid: self._add_marker(i)).pack(side=tk.LEFT)

            plot_outer = tk.Frame(frame)
            plot_outer.pack(fill="both", expand=True)

            body = tk.Frame(plot_outer)
            body.pack(fill="both", expand=True)

            axis_col = tk.Frame(body)
            axis_col.pack(side="left", fill="y", padx=(0, 4))
            y_wrap = tk.Frame(axis_col)
            tk.Label(y_wrap, text="Y ↕︎").pack()
            ry_lab = tk.Label(y_wrap, text="", font=("Helvetica", 8), wraplength=100, justify=tk.CENTER)
            ry_lab.pack()
            y_scale = tk.Scale(
                y_wrap,
                variable=self.marker_y_vars[pid],
                from_=SLIDER_TICKS,
                to=0,
                orient=tk.VERTICAL,
                length=220,
                resolution=1,
                showvalue=0,
                command=lambda _v, i=pid: self._on_marker_y_slide(i),
            )
            y_scale.pack(fill="y", expand=True)
            self.marker_y_scales[pid] = y_scale
            self.marker_readout_y_labels[pid] = ry_lab
            self.marker_y_slider_wraps[pid] = y_wrap

            chart_col = tk.Frame(body)
            chart_col.pack(side="left", fill="both", expand=True)
            lab = tk.Label(chart_col)
            lab.pack(fill="both", expand=True)
            x_wrap = tk.Frame(chart_col)
            tk.Label(x_wrap, text="X ← →", anchor="center", font=("Helvetica", 8)).pack(fill="x", pady=(2, 0))
            rx_lab = tk.Label(x_wrap, text="", font=("Helvetica", 8), anchor="center")
            rx_lab.pack(fill="x")
            x_scale = tk.Scale(
                x_wrap,
                variable=self.marker_x_vars[pid],
                from_=0,
                to=SLIDER_TICKS,
                orient=tk.HORIZONTAL,
                resolution=1,
                showvalue=0,
                command=lambda _v, i=pid: self._on_marker_x_slide(i),
            )
            x_scale.pack(fill="x")
            self.marker_x_scales[pid] = x_scale
            self.marker_readout_x_labels[pid] = rx_lab
            self.marker_x_slider_wraps[pid] = x_wrap

            markers_side = tk.Frame(body)
            self.marker_list_wraps[pid] = markers_side
            tk.Label(markers_side, text="Markers", font=("Helvetica", 9)).pack(anchor="nw")
            lb_fr = tk.Frame(markers_side)
            lb_fr.pack(fill="both", expand=True)
            sb = tk.Scrollbar(lb_fr)
            lb = tk.Listbox(
                lb_fr,
                height=12,
                width=36,
                exportselection=False,
                font=("TkFixedFont", 9),
                yscrollcommand=sb.set,
            )
            sb.config(command=lb.yview)
            sb.pack(side="right", fill="y")
            lb.pack(side="left", fill="both", expand=True)
            lb.bind("<<ListboxSelect>>", lambda _e, i=pid: self._on_marker_list_select(i))
            lb.bind("<ButtonRelease-1>", lambda e, i=pid: self._on_marker_list_release(i, e))
            self.marker_listboxes[pid] = lb

            self.chart_labels[pid] = lab

        for p in self.panels:
            self._sync_marker_slider_ui(p["id"])

        self._generate()

    def _set_state(self, state: SensorAppState) -> None:
        self._state = state

    def _panel_y_bounds(self, panel_id: str) -> tuple[float, float] | None:
        panel = next(p for p in self.panels if p["id"] == panel_id)
        rows = self._state.datasets.get(panel["records_key"])
        if not rows:
            return None
        yk = panel["y_axis_values_key"]
        return float_bounds_from_numeric(r[yk] for r in rows)

    def _effective_marker_index(self, panel_id: str) -> int | None:
        cur = tuple(self._state.markers.get(panel_id, ()))
        if not cur:
            return None
        idx = self._state.marker_selected_index.get(panel_id)
        if idx is None:
            return None
        return max(0, min(idx, len(cur) - 1))

    def _normalize_marker_selection(self, panel_id: str) -> None:
        cur = tuple(self._state.markers.get(panel_id, ()))
        msi = dict(self._state.marker_selected_index)
        pid = panel_id
        if not cur:
            if msi.get(pid) is not None:
                self._set_state(replace(self._state, marker_selected_index={**msi, pid: None}))
            return
        idx = msi.get(pid)
        if idx is None:
            return
        if idx < 0 or idx >= len(cur):
            msi[pid] = max(0, min(idx, len(cur) - 1))
            self._set_state(replace(self._state, marker_selected_index=msi))

    def _replace_marker_at(self, panel_id: str, index: int, new_m: ChartMarker) -> None:
        cur = tuple(self._state.markers.get(panel_id, ()))
        if index < 0 or index >= len(cur):
            return
        seq = (*cur[:index], new_m, *cur[index + 1:])
        self._set_state(replace(self._state, markers={**self._state.markers, panel_id: seq}))

    def _refresh_marker_list(self, panel_id: str) -> None:
        lb = self.marker_listboxes[panel_id]
        panel = next(p for p in self.panels if p["id"] == panel_id)
        records = self._state.datasets.get(panel["records_key"])
        cur = tuple(self._state.markers.get(panel_id, ()))
        lb.delete(0, tk.END)
        for i, m in enumerate(cur):
            lb.insert(tk.END, format_marker_list_label(panel, records, i, m))
        sel = self._effective_marker_index(panel_id)
        self._suppress_marker_list = True
        try:
            lb.selection_clear(0, tk.END)
            if sel is not None:
                lb.selection_set(sel)
                lb.activate(sel)
                lb.see(sel)
        finally:
            self._suppress_marker_list = False

    def _on_marker_list_select(self, panel_id: str) -> None:
        if self._suppress_marker_list:
            return
        lb = self.marker_listboxes[panel_id]
        t = lb.curselection()
        if not t:
            msi = dict(self._state.marker_selected_index)
            if msi.get(panel_id) is not None:
                msi[panel_id] = None
                self._set_state(replace(self._state, marker_selected_index=msi))
                self._render_panel(panel_id)
            return
        idx = int(t[0])
        cur = tuple(self._state.markers.get(panel_id, ()))
        if idx < 0 or idx >= len(cur):
            return
        if self._state.marker_selected_index.get(panel_id) == idx:
            return
        msi = dict(self._state.marker_selected_index)
        msi[panel_id] = idx
        self._set_state(replace(self._state, marker_selected_index=msi))
        self._render_panel(panel_id)

    def _on_marker_list_release(self, panel_id: str, event: tk.Event) -> None:
        if self._suppress_marker_list:
            return
        lb = self.marker_listboxes[panel_id]
        if lb.size() == 0:
            return
        idx = lb.nearest(event.y)
        bbox = lb.bbox(idx)
        if bbox is None:
            return
        _x, y_top, _w, h = bbox
        if event.y >= y_top and event.y < y_top + h:
            return
        msi = dict(self._state.marker_selected_index)
        if msi.get(panel_id) is None:
            return
        msi[panel_id] = None
        self._set_state(replace(self._state, marker_selected_index=msi))
        self._suppress_marker_list = True
        try:
            lb.selection_clear(0, tk.END)
        finally:
            self._suppress_marker_list = False
        self._render_panel(panel_id)

    def _sync_marker_slider_ui(self, panel_id: str) -> None:
        cur = tuple(self._state.markers.get(panel_id, ()))
        has_markers = bool(cur)
        list_wrap = self.marker_list_wraps[panel_id]
        if has_markers:
            if not list_wrap.winfo_ismapped():
                list_wrap.pack(side="left", fill="y", padx=(8, 0))
        else:
            if list_wrap.winfo_ismapped():
                list_wrap.pack_forget()

        sel_idx = self._state.marker_selected_index.get(panel_id)
        show = bool(cur) and sel_idx is not None
        y_wrap = self.marker_y_slider_wraps[panel_id]
        x_wrap = self.marker_x_slider_wraps[panel_id]
        if show:
            if not y_wrap.winfo_ismapped():
                y_wrap.pack(fill="y", expand=True)
            if not x_wrap.winfo_ismapped():
                x_wrap.pack(fill="x", pady=(2, 0))
        else:
            if y_wrap.winfo_ismapped():
                y_wrap.pack_forget()
            if x_wrap.winfo_ismapped():
                x_wrap.pack_forget()

        st = tk.NORMAL if show else tk.DISABLED
        self.marker_x_scales[panel_id].config(state=st)
        self.marker_y_scales[panel_id].config(state=st)

        ry = self.marker_readout_y_labels[panel_id]
        rx = self.marker_readout_x_labels[panel_id]
        if not show:
            ry.config(text="")
            rx.config(text="")
            return

        bounds = self._panel_y_bounds(panel_id)
        idx = self._effective_marker_index(panel_id)
        if idx is None or not bounds:
            ry.config(text="")
            rx.config(text="")
            return
        picked = cur[idx]
        ymin, ymax = bounds
        self._suppress_marker_slide = True
        try:
            self.marker_x_vars[panel_id].set(max(0, min(SLIDER_TICKS, round(picked.x_frac * SLIDER_TICKS))))
            if ymax > ymin:
                ty = round((picked.y_value - ymin) / (ymax - ymin) * SLIDER_TICKS)
                self.marker_y_vars[panel_id].set(max(0, min(SLIDER_TICKS, ty)))
            else:
                self.marker_y_vars[panel_id].set(SLIDER_TICKS // 2)
        finally:
            self._suppress_marker_slide = False

        panel = next(p for p in self.panels if p["id"] == panel_id)
        records = self._state.datasets.get(panel["records_key"])
        rd = marker_readout_strings(panel, records, picked)
        if rd:
            xs, ys = rd
            ry.config(text=ys)
            rx.config(text=xs)
        else:
            yu = panel.get("y_axis_unit")
            ry.config(text=_format_y_readout(picked.y_value, yu if yu and str(yu).strip() else None))
            rx.config(text=f"{picked.x_frac:.0%}")

    def _add_marker(self, panel_id: str) -> None:
        bounds = self._panel_y_bounds(panel_id)
        if bounds is None:
            return
        ymin, ymax = bounds
        style = normalize_marker_style(self.marker_style_vars[panel_id].get())
        y_mid = ymin + (ymax - ymin) * 0.5
        nm = ChartMarker(style=style, x_frac=0.5, y_value=float(y_mid))
        prev = tuple(self._state.markers.get(panel_id, ()))
        new_markers: dict[str, tuple[ChartMarker, ...]] = {**self._state.markers, panel_id: (*prev, nm)}
        msi = dict(self._state.marker_selected_index)
        msi[panel_id] = len(prev)
        self._set_state(
            replace(self._state, markers=new_markers, marker_selected_index=msi),
        )
        self._render_panel(panel_id)

    def _on_marker_x_slide(self, panel_id: str) -> None:
        if self._suppress_marker_slide:
            return
        idx = self._effective_marker_index(panel_id)
        if idx is None:
            return
        cur = tuple(self._state.markers.get(panel_id, ()))
        xf = max(0.0, min(1.0, self.marker_x_vars[panel_id].get() / SLIDER_TICKS))
        old = cur[idx]
        self._replace_marker_at(panel_id, idx, replace(old, x_frac=float(xf)))
        self._render_panel(panel_id)

    def _on_marker_y_slide(self, panel_id: str) -> None:
        if self._suppress_marker_slide:
            return
        bounds = self._panel_y_bounds(panel_id)
        if bounds is None:
            return
        ymin, ymax = bounds
        idx = self._effective_marker_index(panel_id)
        if idx is None:
            return
        cur = tuple(self._state.markers.get(panel_id, ()))
        tick = self.marker_y_vars[panel_id].get()
        y_new = ymin + (ymax - ymin) * (tick / SLIDER_TICKS)
        old = cur[idx]
        self._replace_marker_at(panel_id, idx, replace(old, y_value=float(y_new)))
        self._render_panel(panel_id)

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
        self._normalize_marker_selection(panel_id)
        panel = next(p for p in self.panels if p["id"] == panel_id)
        records = self._state.datasets.get(panel["records_key"])
        marks = self._state.markers.get(panel_id, ())
        sel = self._state.marker_selected_index.get(panel_id) if marks else None
        render_chart_figure(
            self.figures[panel_id],
            records,
            self._state.chart_types[panel_id],
            panel_figure_config(panel),
            show_grid=self._state.grid_visible,
            markers=marks,
            marker_selected_index=sel,
        )
        self.chart_photos[panel_id] = figure_to_tk_photo(
            self.figures[panel_id], self.figure_canvases[panel_id]
        )
        self.chart_labels[panel_id].config(image=self.chart_photos[panel_id])
        self.status_label.config(text=status_for_state(self._state, self.panels))
        self._sync_marker_slider_ui(panel_id)
        self._refresh_marker_list(panel_id)

    def _render_all(self) -> None:
        self._sync_chart_types_from_ui()
        for p in self.panels:
            self._render_panel(p["id"])


def run() -> None:
    app = RandomSensorApp()
    app.root.mainloop()


if __name__ == "__main__":
    run()
