import base64
import copy
import csv
import io
import json
import math
import multiprocessing
import numbers
import os
import queue
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Iterable, NotRequired, TypedDict

import tkinter as tk
from tkinter import filedialog, messagebox

if os.environ.get("SENSOR_RENDER_WORKER") == "1":
    import matplotlib as matplotlib_for_worker

    matplotlib_for_worker.use("Agg", force=True)

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

import pandas as pd
import seaborn as sns

from task3_bmp280 import BMP280I2C, bmp280_sample_row

CHART_TYPES = ["line", "bar", "scatter", "step", "stem"]
DEFAULT_CHART_TYPE = "line"
MARKER_STYLE_ORDER: tuple[tuple[str, str], ...] = (
    ("Circle", "o"),
    ("Square", "s"),
    ("Triangle up", "^"),
    ("Triangle down", "v"),
    ("Diamond", "D"),
    ("Plus (filled)", "P"),
    ("Cross (filled)", "X"),
    ("Star", "*"),
    ("Pentagon", "p"),
    ("Hexagon", "h"),
)
MARKER_STYLE_DISPLAY_NAMES: tuple[str, ...] = tuple(n for n, _ in MARKER_STYLE_ORDER)
MARKER_STYLE_CHAR_BY_DISPLAY: dict[str, str] = dict(MARKER_STYLE_ORDER)
MARKER_STYLE_CHOICES: tuple[str, ...] = tuple(c for _, c in MARKER_STYLE_ORDER)
SLIDER_TICKS = 10_000
POLL_INTERVAL_MS = 3000
SENSOR_UI_DRAIN_MS = 75
MAX_SENSOR_ROWS = 10_000
DATA_SOURCE_CHOICES: tuple[str, ...] = ("sensor", "file")


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
    data_csv_path: NotRequired[str]
    data_source: NotRequired[str]


_PANEL_CONFIG_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "panel_title",
        "records_key",
        "x_axis_value_key",
        "y_axis_values_key",
        "title",
        "x_axis_label",
        "y_axis_label",
    }
)


CHART_PANELS: list[ChartPanelConfig] = json.loads(
    json.dumps(
        [
            {
                "id": "p0",
                "panel_title": "Temperature (°C)",
                "records_key": "temperature",
                "data_source": "sensor",
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
                "data_source": "sensor",
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
    label: str = ""


@dataclass(frozen=True)
class SensorAppState:
    datasets: dict[str, list[dict[str, object]] | None]
    chart_types: dict[str, str]
    markers: dict[str, tuple[ChartMarker, ...]]
    marker_selected_index: dict[str, int | None]
    grid_visible: dict[str, bool]
    config_json_visible: dict[str, bool]


def normalize_chart_type(value: str) -> str:
    return value if value in CHART_TYPES else DEFAULT_CHART_TYPE


def normalize_marker_style(value: str) -> str:
    v = str(value).strip()
    if v in MARKER_STYLE_CHAR_BY_DISPLAY:
        return MARKER_STYLE_CHAR_BY_DISPLAY[v]
    return v if v in MARKER_STYLE_CHOICES else MARKER_STYLE_CHOICES[0]


def marker_style_display_name(char: str) -> str:
    c = normalize_marker_style(char)
    for name, ch in MARKER_STYLE_ORDER:
        if ch == c:
            return name
    return MARKER_STYLE_DISPLAY_NAMES[0]


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


def marker_axes_x(ax, chart_type: str, x_coords: list[object], frac: float) -> object:
    ct = normalize_chart_type(chart_type)
    n = len(x_coords)
    if ct == "bar" and n > 0:
        patches = ax.patches
        if len(patches) >= n:
            pos = max(0.0, min(1.0, frac)) * (n - 1)
            i0 = int(math.floor(pos))
            i1 = min(i0 + 1, n - 1)
            t = pos - i0

            def bar_center(i: int) -> float:
                p = patches[i]
                return float(p.get_x() + p.get_width() / 2)

            if i0 == i1:
                return bar_center(i0)
            return bar_center(i0) * (1.0 - t) + bar_center(i1) * t
    return interpolate_x_coord(x_coords, frac)


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
    chart_type: str,
    markers: tuple[ChartMarker, ...],
    x_coords: list[object],
    selected_index: int | None,
    figure_config: ChartFigureConfig,
    records: list[dict[str, object]] | None,
) -> None:
    if not markers:
        return
    palette = sns.color_palette("deep", max(len(markers), 3))
    ct = normalize_chart_type(chart_type)
    xy_offsets = ((10, 10), (10, -26), (-10, 12), (-10, -26), (24, 4), (-24, -8), (8, 20), (-18, 20))
    for i, m in enumerate(markers):
        xv = marker_axes_x(ax, ct, x_coords, m.x_frac)
        st = normalize_marker_style(m.style)
        sel = selected_index is not None and i == selected_index
        ax.scatter(
            [xv],
            [m.y_value],
            marker=st,
            s=220 if sel else 160,
            color=palette[i % len(palette)],
            edgecolors="black",
            linewidths=3.6 if sel else 0.9,
            zorder=16 if sel else 15,
        )
        parts: list[str] = []
        if m.label.strip():
            parts.append(m.label.strip())
        rd = marker_readout_strings_figure(figure_config, records, m)
        if rd:
            xs_s, ys_s = rd
            parts.extend((xs_s, ys_s))
        else:
            yu = figure_config.get("y_axis_unit")
            parts.append(f"{m.x_frac:.0%}")
            parts.append(
                _format_y_readout(m.y_value, yu if yu and str(yu).strip() else None),
            )
        caption = "\n".join(parts)
        ox, oy = xy_offsets[i % len(xy_offsets)]
        ax.annotate(
            caption,
            (xv, m.y_value),
            xytext=(ox, oy),
            textcoords="offset points",
            fontsize=7,
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", alpha=0.85, edgecolor="0.5"),
            zorder=20,
        )


def normalize_panel_data_source(panel: ChartPanelConfig) -> str:
    raw = panel.get("data_source", "sensor")
    s = str(raw).strip().lower()
    if s not in DATA_SOURCE_CHOICES:
        raise ValueError(
            f"panel {panel.get('id', '?')}: data_source must be 'sensor' or 'file', not {raw!r}"
        )
    return s


def panel_uses_sensor(panel: ChartPanelConfig) -> bool:
    return normalize_panel_data_source(panel) == "sensor"


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


def marker_axis_readout_lines(
    panel: ChartPanelConfig,
    records: list[dict[str, object]] | None,
    markers: tuple[ChartMarker, ...],
) -> tuple[str, str]:
    x_lines: list[str] = []
    y_lines: list[str] = []
    yu_raw = panel.get("y_axis_unit")
    yu = yu_raw if yu_raw and str(yu_raw).strip() else None
    for i, m in enumerate(markers):
        pfx = f"{m.label.strip()}: " if m.label.strip() else f"#{i + 1}: "
        rd = marker_readout_strings(panel, records, m)
        if rd:
            xs_s, ys_s = rd
            x_lines.append(f"{pfx}{xs_s}")
            y_lines.append(f"{pfx}{ys_s}")
        else:
            x_lines.append(f"{pfx}{m.x_frac:.0%}")
            y_lines.append(_format_y_readout(m.y_value, yu))
    return "\n".join(x_lines), "\n".join(y_lines)


def format_marker_list_label(
    panel: ChartPanelConfig,
    records: list[dict[str, object]] | None,
    index: int,
    m: ChartMarker,
) -> str:
    st = marker_style_display_name(m.style)
    head = m.label.strip() if m.label.strip() else f"#{index + 1}"
    rd = marker_readout_strings(panel, records, m)
    if rd:
        xs, ys = rd
        return f"{head}  {st}  {xs}  {ys}"
    return f"{head}  {st}  x={m.x_frac:.0%}  y={m.y_value:.4g}"


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
        draw_seaborn_markers(
            ax,
            chart_type=chart_type,
            markers=markers,
            x_coords=x,
            selected_index=marker_selected_index,
            figure_config=config,
            records=records,
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
        rows = state.datasets.get(pid)
        n = len(rows) if rows else 0
        ct = normalize_chart_type(state.chart_types.get(pid, DEFAULT_CHART_TYPE))
        g = "on" if state.grid_visible.get(pid, True) else "off"
        parts.append(f"{pid}: {ct} grid {g} ({n} rows)")
    return " · ".join(parts)


    if not isinstance(raw, list) or not raw:
        raise ValueError("configuration must be a non-empty JSON array")
    out: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each panel must be a JSON object")
        keys = frozenset(item.keys())
        if not _PANEL_CONFIG_REQUIRED_KEYS <= keys:
            missing = _PANEL_CONFIG_REQUIRED_KEYS - keys
            raise ValueError(f"panel missing required keys: {sorted(missing)}")
        pid = str(item["id"])
        if pid in seen:
            raise ValueError(f"duplicate panel id: {pid}")
        seen.add(pid)
        ds_raw = item.get("data_source", "sensor")
        ds_s = str(ds_raw).strip().lower()
        if ds_s not in DATA_SOURCE_CHOICES:
            raise ValueError(
                f"panel {pid}: data_source must be 'sensor' or 'file', not {ds_raw!r}"
            )
        item["data_source"] = ds_s
        out.append(item)
    return out


def parse_graph_template(raw: object) -> list[dict[str, object]]:
    root_csv = ""
    if isinstance(raw, list):
        out = validate_panel_config_json_list(raw)
    elif isinstance(raw, dict):
        pr = raw.get("panels")
        if not isinstance(pr, list):
            raise ValueError("template object must include a non-empty 'panels' array")
        rc = raw.get("data_csv_path")
        if rc is not None and not isinstance(rc, str):
            raise ValueError("template root data_csv_path must be a string")
        root_csv = str(rc).strip() if rc else ""
        out = validate_panel_config_json_list(pr)
    else:
        raise ValueError("configuration must be a JSON array or an object with 'panels'")
    if root_csv:
        for item in out:
            if not str(item.get("data_csv_path") or "").strip():
                item["data_csv_path"] = root_csv
    return out


def wide_rows_from_datasets(
    datasets: dict[str, list[dict[str, object]] | None],
) -> list[dict[str, object]]:
    series_list = sorted((k, v) for k, v in datasets.items() if v)
    if not series_list:
        return []
    max_len = max(len(v) for _, v in series_list)
    rows: list[dict[str, object]] = []
    for i in range(max_len):
        merged: dict[str, object] = {}
        for _rk, series in series_list:
            if i < len(series):
                for col, val in series[i].items():
                    merged.setdefault(col, val)
        rows.append(merged)
    return rows


def write_datasets_wide_csv(path: str, rows: list[dict[str, object]]) -> None:
    keys: set[str] = set()
    for r in rows:
        keys.update(r.keys())
    cols: list[str] = []
    if "time" in keys:
        cols.append("time")
        keys.discard("time")
    cols.extend(sorted(keys))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def _csv_scalar(v: object) -> object:
    try:
        if pd.isna(v):
            raise ValueError("missing value in CSV")
    except TypeError:
        pass
    if isinstance(v, pd.Timestamp):
        t = v.to_pydatetime()
        return t.isoformat()
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, bool):
        return v
    if isinstance(v, numbers.Integral):
        return int(v)
    if isinstance(v, numbers.Real):
        return float(v)
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            return v.item()
        except (ValueError, AttributeError):
            pass
    return v


def dataset_rows_from_wide_csv(csv_path: str, panel: ChartPanelConfig) -> list[dict[str, object]]:
    df = pd.read_csv(csv_path)
    xk = str(panel["x_axis_value_key"])
    yk = str(panel["y_axis_values_key"])
    pid = str(panel["id"])
    if xk not in df.columns or yk not in df.columns:
        raise ValueError(
            f"CSV {csv_path!r} missing columns for panel {pid}: "
            f"need {xk!r} and {yk!r}; columns are {list(df.columns)}"
        )
    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        rows.append({xk: _csv_scalar(row[xk]), yk: _csv_scalar(row[yk])})
    return rows


def initial_chart_types(panels: list[ChartPanelConfig]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in panels:
        d = p.get("default_chart_type", DEFAULT_CHART_TYPE)
        out[p["id"]] = normalize_chart_type(d)
    return out


def _bmp280_poll_worker(stop: threading.Event, out_q: queue.Queue[tuple[str, object]]) -> None:
    sensor: BMP280I2C | None = None
    try:
        try:
            sensor = BMP280I2C()
        except Exception as e:
            out_q.put(("init_error", str(e)))
            return
        interval_s = POLL_INTERVAL_MS / 1000.0
        while not stop.is_set():
            try:
                out_q.put(("row", bmp280_sample_row(sensor)))
            except Exception as e:
                out_q.put(("read_error", str(e)))
            if stop.wait(timeout=interval_s):
                break
    finally:
        if sensor is not None:
            sensor.close()


CHART_RENDER_FIGSIZE = (5.5, 5)
CHART_RENDER_DPI = 100
CHART_RENDER_POLL_MS = 50


def _render_specs_to_png(
    specs: list[dict[str, object]],
    *,
    default_figsize: tuple[float, float] = CHART_RENDER_FIGSIZE,
    default_dpi: int = CHART_RENDER_DPI,
) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for item in specs:
        pid = str(item["id"])
        fs_raw = item.get("figsize", default_figsize)
        fs = (float(fs_raw[0]), float(fs_raw[1]))  # type: ignore[index]
        dpi_i = int(item.get("dpi", default_dpi))
        fig = Figure(figsize=fs, dpi=dpi_i)
        canvas_agg = FigureCanvasAgg(fig)
        cfg = _cast_figure_cfg(item["figure_config"])
        render_chart_figure(
            fig,
            item["records"],  # type: ignore[arg-type]
            normalize_chart_type(str(item["chart_type"])),
            cfg,
            show_grid=bool(item["show_grid"]),
            markers=item["markers"],  # type: ignore[arg-type]
            marker_selected_index=item.get("marker_selected_index"),
        )
        canvas_agg.draw()
        bio = io.BytesIO()
        fig.savefig(bio, format="png")
        plt.close(fig)
        out[pid] = bio.getvalue()
    return out


def _cast_figure_cfg(raw: object) -> ChartFigureConfig:
    d = dict(raw)  # type: ignore[arg-type]
    xs: ChartFigureConfig = {
        "x_axis_value_key": str(d["x_axis_value_key"]),
        "y_axis_values_key": str(d["y_axis_values_key"]),
        "title": str(d["title"]),
        "x_axis_label": str(d["x_axis_label"]),
        "y_axis_label": str(d["y_axis_label"]),
    }
    if d.get("x_axis_unit"):
        xs["x_axis_unit"] = str(d["x_axis_unit"])
    if d.get("y_axis_unit"):
        xs["y_axis_unit"] = str(d["y_axis_unit"])
    return xs


def _render_worker_main(cmd_q: object, result_q: object) -> None:
    while True:
        msg = cmd_q.get()
        if msg is None:
            break
        generation, specs = msg
        try:
            pngs = _render_specs_to_png(specs)
            result_q.put((generation, pngs, ""))
        except Exception as e:
            result_q.put((generation, None, str(e)))


class SensorDashboardApp:
    def __init__(self) -> None:
        self._sensor_rows: list[dict[str, object]] = []
        self._sensor_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._sensor_stop = threading.Event()
        self._sensor_thread: threading.Thread | None = None
        self._sensor_poll_active = False
        self._sensor_ui_after_id: str | None = None
        self.panels: list[ChartPanelConfig] = []
        self.panel_frames: dict[str, tk.LabelFrame] = {}
        self.graph_config_labels: dict[str, tk.Label] = {}
        self.root = tk.Tk()
        self.root.title("BMP280 charts (sensor / file)")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

        self.figures: dict[str, Figure] = {}
        self.figure_canvases: dict[str, FigureCanvasAgg] = {}
        self.chart_photos: dict[str, tk.PhotoImage | None] = {}
        self.chart_labels: dict[str, tk.Label] = {}
        self.chart_type_vars: dict[str, tk.StringVar] = {}

        self._suppress_marker_slide = False
        self._suppress_marker_list = False

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
        self.marker_label_vars: dict[str, tk.StringVar] = {}
        self.marker_label_entries: dict[str, tk.Entry] = {}
        self.marker_label_frames: dict[str, tk.Frame] = {}
        self._suppress_marker_label = False
        self.grid_buttons: dict[str, tk.Button] = {}
        self.config_json_buttons: dict[str, tk.Button] = {}
        self._template_dir: str | None = None
        self._render_mp_ctx = multiprocessing.get_context("spawn")
        self._render_cmd_q: multiprocessing.Queue | None = None
        self._render_result_q: multiprocessing.Queue | None = None
        self._render_proc: multiprocessing.Process | None = None
        self._render_generation = 0
        self._render_busy = False
        self._render_queued_job: tuple[int, list[dict[str, object]]] | None = None
        self._render_poll_after_id: str | None = None

        toolbar = tk.Frame(self.root)
        toolbar.pack(pady=5, padx=10, fill="x")
        tk.Button(toolbar, text="Save template…", command=self._save_graph_template).pack(side="left")
        tk.Button(toolbar, text="Load configuration…", command=self._load_graph_configuration).pack(
            side="left",
            padx=(8, 0),
        )
        tk.Button(toolbar, text="Save data to CSV…", command=self._save_data_csv).pack(
            side="left",
            padx=(8, 0),
        )
        self.status_label = tk.Label(
            toolbar,
            text="Data source and CSV paths come from the loaded JSON template; use Load configuration… to change them.",
        )
        self.status_label.pack(pady=(8, 0), anchor="w")

        self.charts_container = tk.Frame(self.root)
        self.charts_container.pack(pady=5, padx=10, fill="both", expand=True)

        self._apply_panels_list(json.loads(json.dumps(CHART_PANELS)), initial=True)

    def _any_sensor_panel(self) -> bool:
        return any(panel_uses_sensor(p) for p in self.panels)

    def _on_window_close(self) -> None:
        self._stop_sensor_worker()
        self._shutdown_render_worker()
        self.root.destroy()

    def _shutdown_render_worker(self) -> None:
        self._cancel_render_poll()
        cq = self._render_cmd_q
        if cq is not None:
            try:
                cq.put_nowait(None)
            except Exception:
                pass
        proc = self._render_proc
        self._render_proc = None
        if proc is not None:
            proc.join(timeout=4.0)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1.0)
        self._render_busy = False
        self._render_queued_job = None
        rq = self._render_result_q
        if rq is not None:
            while True:
                try:
                    rq.get_nowait()
                except queue.Empty:
                    break

    def _cancel_render_poll(self) -> None:
        if self._render_poll_after_id is not None:
            self.root.after_cancel(self._render_poll_after_id)
            self._render_poll_after_id = None

    def _ensure_render_process(self) -> None:
        if self._render_proc is not None and self._render_proc.is_alive():
            return
        self._render_proc = None
        self._render_cmd_q = self._render_mp_ctx.Queue()
        self._render_result_q = self._render_mp_ctx.Queue()
        os.environ["SENSOR_RENDER_WORKER"] = "1"
        try:
            self._render_proc = self._render_mp_ctx.Process(
                target=_render_worker_main,
                args=(self._render_cmd_q, self._render_result_q),
                daemon=True,
                name="chart-render",
            )
            self._render_proc.start()
        finally:
            os.environ.pop("SENSOR_RENDER_WORKER", None)

    def _build_render_spec(self, panel_ids: frozenset[str]) -> list[dict[str, object]]:
        spec: list[dict[str, object]] = []
        for p in self.panels:
            pid = p["id"]
            if pid not in panel_ids:
                continue
            marks = tuple(self._state.markers.get(pid, ()))
            sel = self._state.marker_selected_index.get(pid) if marks else None
            rec = self._state.datasets.get(pid)
            spec.append(
                {
                    "id": pid,
                    "figure_config": dict(panel_figure_config(p)),
                    "chart_type": normalize_chart_type(
                        self._state.chart_types.get(pid, DEFAULT_CHART_TYPE)
                    ),
                    "records": copy.deepcopy(rec) if rec is not None else None,
                    "markers": copy.deepcopy(marks),
                    "marker_selected_index": sel,
                    "show_grid": self._state.grid_visible.get(pid, True),
                    "figsize": CHART_RENDER_FIGSIZE,
                    "dpi": CHART_RENDER_DPI,
                }
            )
        return spec

    def _maybe_submit_render_job(self, job: tuple[int, list[dict[str, object]]]) -> None:
        if self._render_busy:
            self._render_queued_job = job
            return
        self._ensure_render_process()
        if self._render_cmd_q is None:
            return
        self._render_busy = True
        try:
            self._render_cmd_q.put(job)
        except Exception as e:
            self._render_busy = False
            self.status_label.config(text=f"Chart render queue: {e}")
            return
        self._arm_render_poll()

    def _arm_render_poll(self) -> None:
        if self._render_poll_after_id is not None:
            return
        self._render_poll_after_id = self.root.after(CHART_RENDER_POLL_MS, self._poll_render_results)

    def _poll_render_results(self) -> None:
        self._render_poll_after_id = None
        rq = self._render_result_q
        proc = self._render_proc
        if rq is None:
            return
        try:
            generation, pngs, err_s = rq.get_nowait()
        except queue.Empty:
            if proc is not None and proc.is_alive():
                self._arm_render_poll()
            elif self._render_busy:
                self._render_busy = False
                self._render_proc = None
                qj = self._render_queued_job
                self._render_queued_job = None
                if qj is not None:
                    self._maybe_submit_render_job(qj)
                else:
                    self._maybe_submit_render_job(
                        (
                            self._render_generation,
                            self._build_render_spec(frozenset(p["id"] for p in self.panels)),
                        )
                    )
            return

        self._render_busy = False

        if err_s:
            self.status_label.config(text=f"Chart render: {err_s}")
        elif generation == self._render_generation and pngs is not None:
            self._apply_render_pngs(pngs)

        next_job = self._render_queued_job
        self._render_queued_job = None
        if next_job is not None:
            self._maybe_submit_render_job(next_job)
        elif generation != self._render_generation:
            self._maybe_submit_render_job(
                (
                    self._render_generation,
                    self._build_render_spec(frozenset(p["id"] for p in self.panels)),
                )
            )

    def _apply_render_pngs(self, pngs: dict[str, bytes]) -> None:
        for pid, data in pngs.items():
            self.chart_photos[pid] = tk.PhotoImage(data=base64.b64encode(data))
            self.chart_labels[pid].config(image=self.chart_photos[pid])
        self.status_label.config(text=status_for_state(self._state, self.panels))
        for pid in pngs:
            self._sync_marker_slider_ui(pid)
            self._refresh_marker_list(pid)

    def _schedule_render_async(self, panel_ids: frozenset[str] | None = None) -> None:
        self._sync_chart_types_from_ui()
        ids = frozenset(p["id"] for p in self.panels) if panel_ids is None else frozenset(panel_ids)
        for pid in ids:
            self._normalize_marker_selection(pid)
        spec = self._build_render_spec(ids)
        self._render_generation += 1
        self._maybe_submit_render_job((self._render_generation, spec))

    def _stop_sensor_worker(self, join_timeout: float = 5.0) -> None:
        self._sensor_poll_active = False
        self._sensor_stop.set()
        if self._sensor_ui_after_id is not None:
            self.root.after_cancel(self._sensor_ui_after_id)
            self._sensor_ui_after_id = None
        t = self._sensor_thread
        self._sensor_thread = None
        if t is not None:
            t.join(timeout=join_timeout)
        self._sensor_stop = threading.Event()

    def _sensor_ui_drain(self) -> None:
        self._sensor_ui_after_id = None
        got_row = False
        for _ in range(256):
            try:
                kind, payload = self._sensor_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "row":
                assert isinstance(payload, dict)
                self._sensor_rows.append(payload)
                lim = MAX_SENSOR_ROWS
                while len(self._sensor_rows) > lim:
                    self._sensor_rows.pop(0)
                got_row = True
            elif kind == "init_error":
                assert isinstance(payload, str)
                self._sensor_poll_active = False
                messagebox.showerror("BMP280", payload)
                self._stop_sensor_worker(join_timeout=1.0)
                return
            elif kind == "read_error":
                assert isinstance(payload, str)
                self.status_label.config(text=f"Sensor read error: {payload}")
        if got_row:
            self._rebind_dataset_refs()
            self._render_all()

        if (
            self._sensor_poll_active
            and self._any_sensor_panel()
            and self._sensor_thread is not None
            and self._sensor_thread.is_alive()
        ):
            self._sensor_ui_after_id = self.root.after(SENSOR_UI_DRAIN_MS, self._sensor_ui_drain)

    def _start_sensor_poll_if_needed(self) -> None:
        self._stop_sensor_worker()
        while True:
            try:
                self._sensor_queue.get_nowait()
            except queue.Empty:
                break
        if not self._any_sensor_panel():
            return
        self._sensor_poll_active = True
        self._sensor_thread = threading.Thread(
            target=_bmp280_poll_worker,
            args=(self._sensor_stop, self._sensor_queue),
            daemon=True,
            name="bmp280-poller",
        )
        self._sensor_thread.start()
        self._sensor_ui_after_id = self.root.after(SENSOR_UI_DRAIN_MS, self._sensor_ui_drain)

    def _rebind_dataset_refs(self) -> None:
        ds_out: dict[str, list[dict[str, object]] | None] = {}
        cur = dict(self._state.datasets)
        for p in self.panels:
            pid = p["id"]
            prev = cur.get(pid)
            if panel_uses_sensor(p):
                ds_out[pid] = self._sensor_rows
            else:
                ds_out[pid] = [] if prev is self._sensor_rows else prev
        self._set_state(replace(self._state, datasets=ds_out))

    def _panel_column_padx(self, index: int, total: int) -> tuple[int, int]:
        if total <= 1:
            return (0, 0)
        if index == 0:
            return (0, 5)
        if index == total - 1:
            return (5, 0)
        return (5, 5)

    def _build_panel_column(
        self,
        parent: tk.Misc,
        p: ChartPanelConfig,
        padx: tuple[int, int],
        *,
        grid_on: bool,
        config_json_on: bool,
    ) -> None:
        pid = p["id"]
        frame = tk.LabelFrame(parent, text=p["panel_title"])
        frame.pack(side="left", fill="both", expand=True, padx=padx)
        self.panel_frames[pid] = frame
        hdr = tk.Frame(frame)
        hdr.pack(fill="x", padx=4, pady=(4, 0))
        tk.Label(hdr, text="Graph configuration", font=("", 9, "bold")).pack(side="left")
        jb = tk.Button(
            hdr,
            text="Hide JSON" if config_json_on else "Show JSON",
            command=lambda i=pid: self._toggle_config_json(i),
        )
        jb.pack(side="right")
        self.config_json_buttons[pid] = jb
        cfg_lab = tk.Label(
            frame,
            text=chart_config_display_text(panel_figure_config(p)),
            justify=tk.LEFT,
            anchor="nw",
            font=("TkFixedFont", 10),
        )
        self.graph_config_labels[pid] = cfg_lab
        if config_json_on:
            cfg_lab.pack(fill="x", padx=4, pady=(0, 4))

        dsrc = normalize_panel_data_source(p)
        src_fr = tk.Frame(frame)
        src_fr.pack(fill="x", padx=4, pady=(0, 6))
        tk.Label(src_fr, text="Data source:").pack(side="left", padx=(0, 4))
        tk.Label(src_fr, text=dsrc, anchor="w").pack(
            side="left",
            fill="x",
            expand=True,
        )
        if dsrc == "file":
            csv_fr = tk.Frame(frame)
            csv_fr.pack(fill="x", padx=4, pady=(0, 6))
            tk.Label(csv_fr, text="Data CSV:").pack(side="left", padx=(0, 4), anchor="nw")
            rel = str(p.get("data_csv_path") or "").strip()
            tk.Label(
                csv_fr,
                text=rel if rel else "—",
                anchor="w",
                justify=tk.LEFT,
                wraplength=480,
            ).pack(side="left", fill="x", expand=True)

        ctr_marker = tk.Frame(frame)
        ctr_marker.pack(fill="x", padx=4, pady=(0, 6))
        tk.Label(ctr_marker, text="Marker:").pack(side=tk.LEFT, padx=(0, 4))
        tk.OptionMenu(
            ctr_marker,
            self.marker_style_vars[pid],
            *MARKER_STYLE_DISPLAY_NAMES,
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(ctr_marker, text="Add marker", command=lambda i=pid: self._add_marker(i)).pack(side=tk.LEFT)

        ctr_chart = tk.Frame(frame)
        ctr_chart.pack(fill="x", padx=4, pady=(0, 6))
        tk.Label(ctr_chart, text="Chart:").pack(side=tk.LEFT, padx=(0, 4))
        tk.OptionMenu(
            ctr_chart,
            self.chart_type_vars[pid],
            *CHART_TYPES,
            command=lambda _v, i=pid: self._on_chart_type_change(i),
        ).pack(side=tk.LEFT)
        gb = tk.Button(
            ctr_chart,
            text="Grid: On" if grid_on else "Grid: Off",
            command=lambda i=pid: self._toggle_grid(i),
        )
        gb.pack(side=tk.LEFT, padx=(12, 0))
        self.grid_buttons[pid] = gb

        ctr_name = tk.Frame(frame)
        tk.Label(ctr_name, text="Marker name:").pack(side=tk.LEFT, padx=(0, 4))
        ent = tk.Entry(ctr_name, textvariable=self.marker_label_vars[pid], width=32)
        ent.pack(side=tk.LEFT)
        ent.bind("<FocusOut>", lambda _e, i=pid: self._on_marker_label_commit(i))
        ent.bind("<Return>", lambda _e, i=pid: self._on_marker_label_commit(i))
        self.marker_label_entries[pid] = ent
        self.marker_label_frames[pid] = ctr_name

        plot_outer = tk.Frame(frame)
        plot_outer.pack(fill="both", expand=True)

        body = tk.Frame(plot_outer)
        body.pack(fill="both", expand=True)

        axis_col = tk.Frame(body)
        axis_col.pack(side="left", fill="y", padx=(0, 4))
        y_wrap = tk.Frame(axis_col)
        tk.Label(y_wrap, text="Y ↕︎").pack()
        ry_lab = tk.Label(y_wrap, text="", font=("Helvetica", 8), wraplength=140, justify=tk.CENTER)
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
        rx_lab = tk.Label(x_wrap, text="", font=("Helvetica", 8), anchor="center", wraplength=280, justify=tk.CENTER)
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

    def _apply_panels_list(
        self, panel_dicts: list[dict[str, object]], *, initial: bool, render: bool = True
    ) -> None:
        ordered = [json.loads(json.dumps(p)) for p in panel_dicts]
        for p in ordered:
            p["data_source"] = normalize_panel_data_source(p)
        if not ordered:
            messagebox.showerror("Configuration", "At least one panel is required.")
            return
        old: SensorAppState | None = None
        if not initial:
            old = self._state
        if initial:
            new_ds = {}
            for p in ordered:
                pid = p["id"]
                new_ds[pid] = self._sensor_rows if panel_uses_sensor(p) else None
            new_ct = initial_chart_types(ordered)
            new_markers = {p["id"]: () for p in ordered}
            new_msi = {p["id"]: None for p in ordered}
            new_grid = {p["id"]: True for p in ordered}
            new_cfg_json = {p["id"]: False for p in ordered}
        else:
            assert old is not None
            new_ds = {}
            for p in ordered:
                pid = p["id"]
                prev = old.datasets.get(pid)
                if panel_uses_sensor(p):
                    new_ds[pid] = self._sensor_rows
                elif prev is self._sensor_rows:
                    new_ds[pid] = None
                else:
                    new_ds[pid] = prev
            new_markers = {}
            new_msi = {}
            new_ct = {}
            for p in ordered:
                pid = p["id"]
                new_markers[pid] = tuple(old.markers.get(pid, ()))
                new_msi[pid] = old.marker_selected_index.get(pid)
                raw_dct = p.get("default_chart_type")
                if raw_dct is not None and str(raw_dct).strip():
                    new_ct[pid] = normalize_chart_type(str(raw_dct))
                else:
                    fb = old.chart_types.get(pid) or p.get("default_chart_type") or DEFAULT_CHART_TYPE
                    new_ct[pid] = normalize_chart_type(str(fb))
            new_grid = {p["id"]: old.grid_visible.get(p["id"], True) for p in ordered}
            new_cfg_json = {p["id"]: old.config_json_visible.get(p["id"], False) for p in ordered}

        for fig in list(self.figures.values()):
            plt.close(fig)
        for w in self.charts_container.winfo_children():
            w.destroy()

        self.panels = ordered
        self.figures = {}
        self.figure_canvases = {}
        self.chart_photos = {p["id"]: None for p in self.panels}
        self.chart_labels = {}
        self.chart_type_vars = {}
        self.marker_style_vars = {}
        self.marker_x_vars = {}
        self.marker_y_vars = {}
        self.marker_y_scales = {}
        self.marker_x_scales = {}
        self.marker_y_slider_wraps = {}
        self.marker_x_slider_wraps = {}
        self.marker_readout_y_labels = {}
        self.marker_readout_x_labels = {}
        self.marker_list_wraps = {}
        self.marker_listboxes = {}
        self.marker_label_vars = {}
        self.marker_label_entries = {}
        self.marker_label_frames = {}
        self.panel_frames = {}
        self.graph_config_labels = {}
        self.grid_buttons = {}
        self.config_json_buttons = {}

        half = SLIDER_TICKS // 2
        for p in self.panels:
            pid = p["id"]
            self.figures[pid] = Figure(figsize=(5.5, 5), dpi=100)
            self.figure_canvases[pid] = FigureCanvasAgg(self.figures[pid])
            v = tk.StringVar(self.root)
            v.set(new_ct[pid])
            self.chart_type_vars[pid] = v
            self.marker_style_vars[pid] = tk.StringVar(master=self.root, value=MARKER_STYLE_DISPLAY_NAMES[0])
            self.marker_label_vars[pid] = tk.StringVar(master=self.root, value="")
            self.marker_x_vars[pid] = tk.IntVar(master=self.root, value=half)
            self.marker_y_vars[pid] = tk.IntVar(master=self.root, value=half)

        n = len(self.panels)
        for i, p in enumerate(self.panels):
            pid = p["id"]
            self._build_panel_column(
                self.charts_container,
                p,
                self._panel_column_padx(i, n),
                grid_on=new_grid[pid],
                config_json_on=new_cfg_json[pid],
            )

        self._set_state(
            SensorAppState(
                datasets=new_ds,
                chart_types=new_ct,
                markers=new_markers,
                marker_selected_index=new_msi,
                grid_visible=new_grid,
                config_json_visible=new_cfg_json,
            ),
        )
        for p in self.panels:
            pid = p["id"]
            self._normalize_marker_selection(pid)
            self._sync_marker_slider_ui(pid)
        if render:
            self._render_all()
        if render:
            self._start_sensor_poll_if_needed()

    def _set_state(self, state: SensorAppState) -> None:
        self._state = state

    def _resolved_csv_path(self, rel: str) -> str:
        rel = rel.strip()
        if not rel:
            return ""
        if os.path.isabs(rel):
            return os.path.normpath(rel)
        base = self._template_dir if self._template_dir else os.getcwd()
        return os.path.normpath(os.path.join(base, rel))

    def _save_data_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        rows = wide_rows_from_datasets(self._state.datasets)
        if not rows:
            messagebox.showwarning("Save data", "No data to export.")
            return
        try:
            write_datasets_wide_csv(path, rows)
        except OSError as e:
            messagebox.showerror("Save data", str(e))

    def _panel_y_bounds(self, panel_id: str) -> tuple[float, float] | None:
        panel = next(p for p in self.panels if p["id"] == panel_id)
        rows = self._state.datasets.get(panel_id)
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
        records = self._state.datasets.get(panel_id)
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
        y_wrap = self.marker_y_slider_wraps[panel_id]
        x_wrap = self.marker_x_slider_wraps[panel_id]
        y_scale = self.marker_y_scales[panel_id]
        x_scale = self.marker_x_scales[panel_id]
        ry = self.marker_readout_y_labels[panel_id]
        rx = self.marker_readout_x_labels[panel_id]
        panel = next(p for p in self.panels if p["id"] == panel_id)
        records = self._state.datasets.get(panel_id)

        if not has_markers:
            if list_wrap.winfo_ismapped():
                list_wrap.pack_forget()
            if y_wrap.winfo_ismapped():
                y_wrap.pack_forget()
            if x_wrap.winfo_ismapped():
                x_wrap.pack_forget()
            if y_scale.winfo_ismapped():
                y_scale.pack_forget()
            if x_scale.winfo_ismapped():
                x_scale.pack_forget()
            ry.config(text="")
            rx.config(text="")
            self._sync_marker_label_entry(panel_id)
            return

        if not list_wrap.winfo_ismapped():
            list_wrap.pack(side="left", fill="y", padx=(8, 0))
        if not y_wrap.winfo_ismapped():
            y_wrap.pack(fill="y", expand=True)
        if not x_wrap.winfo_ismapped():
            x_wrap.pack(fill="x", pady=(2, 0))

        sel_idx = self._state.marker_selected_index.get(panel_id)
        show_sliders = sel_idx is not None

        if show_sliders:
            if not y_scale.winfo_ismapped():
                y_scale.pack(fill="y", expand=True)
            if not x_scale.winfo_ismapped():
                x_scale.pack(fill="x")
            y_scale.config(state=tk.NORMAL)
            x_scale.config(state=tk.NORMAL)
            bounds = self._panel_y_bounds(panel_id)
            idx = self._effective_marker_index(panel_id)
            if idx is not None and bounds:
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

                rd = marker_readout_strings(panel, records, picked)
                if rd:
                    xs, ys = rd
                    ry.config(text=ys)
                    rx.config(text=xs)
                else:
                    yu = panel.get("y_axis_unit")
                    ry.config(text=_format_y_readout(picked.y_value, yu if yu and str(yu).strip() else None))
                    rx.config(text=f"{picked.x_frac:.0%}")
            else:
                lx, ly = marker_axis_readout_lines(panel, records, cur)
                ry.config(text=ly)
                rx.config(text=lx)
        else:
            if y_scale.winfo_ismapped():
                y_scale.pack_forget()
            if x_scale.winfo_ismapped():
                x_scale.pack_forget()
            y_scale.config(state=tk.DISABLED)
            x_scale.config(state=tk.DISABLED)
            lx, ly = marker_axis_readout_lines(panel, records, cur)
            ry.config(text=ly)
            rx.config(text=lx)

        self._sync_marker_label_entry(panel_id)

    def _sync_marker_label_entry(self, panel_id: str) -> None:
        ent = self.marker_label_entries[panel_id]
        name_fr = self.marker_label_frames[panel_id]
        cur = tuple(self._state.markers.get(panel_id, ()))
        idx = self._effective_marker_index(panel_id)
        if not cur or idx is None:
            if name_fr.winfo_ismapped():
                name_fr.pack_forget()
            self._suppress_marker_label = True
            try:
                self.marker_label_vars[panel_id].set("")
            finally:
                self._suppress_marker_label = False
            ent.config(state=tk.DISABLED)
            return
        if not name_fr.winfo_ismapped():
            name_fr.pack(fill="x", padx=4, pady=(0, 6))
        ent.config(state=tk.NORMAL)
        self._suppress_marker_label = True
        try:
            self.marker_label_vars[panel_id].set(cur[idx].label)
        finally:
            self._suppress_marker_label = False

    def _on_marker_label_commit(self, panel_id: str) -> None:
        if self._suppress_marker_label:
            return
        idx = self._effective_marker_index(panel_id)
        if idx is None:
            return
        cur = tuple(self._state.markers.get(panel_id, ()))
        if idx < 0 or idx >= len(cur):
            return
        text = self.marker_label_vars[panel_id].get()
        old = cur[idx]
        if text == old.label:
            return
        self._replace_marker_at(panel_id, idx, replace(old, label=text))
        self._render_panel(panel_id)

    def _add_marker(self, panel_id: str) -> None:
        bounds = self._panel_y_bounds(panel_id)
        if bounds is None:
            return
        ymin, ymax = bounds
        style = normalize_marker_style(self.marker_style_vars[panel_id].get())
        y_mid = ymin + (ymax - ymin) * 0.5
        prev = tuple(self._state.markers.get(panel_id, ()))
        nm = ChartMarker(
            style=style,
            x_frac=0.5,
            y_value=float(y_mid),
            label=f"Marker {len(prev) + 1}",
        )
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

    def _refresh_datasets(self) -> None:
        self._sync_chart_types_from_ui()
        datasets: dict[str, list[dict[str, object]] | None] = {}
        summaries: list[str] = []
        for p in self.panels:
            pid = p["id"]
            if panel_uses_sensor(p):
                datasets[pid] = self._sensor_rows
                summaries.append(f"{pid}: sensor({len(self._sensor_rows)})")
            else:
                rel = str(p.get("data_csv_path") or "").strip()
                if not rel:
                    messagebox.showerror(
                        "CSV",
                        f"Panel {pid}: set data_csv_path for file source in the JSON configuration and load it again.",
                    )
                    return
                fp = self._resolved_csv_path(rel)
                try:
                    datasets[pid] = dataset_rows_from_wide_csv(fp, p)
                except (OSError, ValueError) as e:
                    messagebox.showerror("CSV data", str(e))
                    return
                summaries.append(f"{pid}: CSV({len(datasets[pid] or [])})")
        self._set_state(replace(self._state, datasets=datasets))
        self.status_label.config(text=" · ".join(summaries))
        self._start_sensor_poll_if_needed()

    def _on_chart_type_change(self, panel_id: str) -> None:
        ct = normalize_chart_type(self.chart_type_vars[panel_id].get())
        new_ct = dict(self._state.chart_types)
        new_ct[panel_id] = ct
        self.chart_type_vars[panel_id].set(ct)
        self._set_state(replace(self._state, chart_types=new_ct))
        self._render_panel(panel_id)

    def _toggle_grid(self, panel_id: str) -> None:
        gv = dict(self._state.grid_visible)
        on = not gv.get(panel_id, True)
        gv[panel_id] = on
        self._set_state(replace(self._state, grid_visible=gv))
        self.grid_buttons[panel_id].config(text="Grid: On" if on else "Grid: Off")
        self._render_panel(panel_id)

    def _toggle_config_json(self, panel_id: str) -> None:
        cv = dict(self._state.config_json_visible)
        on = not cv.get(panel_id, False)
        cv[panel_id] = on
        self._set_state(replace(self._state, config_json_visible=cv))
        self.config_json_buttons[panel_id].config(text="Hide JSON" if on else "Show JSON")
        lab = self.graph_config_labels[panel_id]
        if on:
            lab.pack(fill="x", padx=4, pady=(0, 4))
        else:
            lab.pack_forget()

    def _save_graph_template(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        self._template_dir = os.path.dirname(os.path.abspath(path))
        try:
            payload = {"panels": json.loads(json.dumps(self.panels))}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.write("\n")
        except OSError as e:
            messagebox.showerror("Save template", str(e))

    def _load_graph_configuration(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror("Load configuration", str(e))
            return
        self._template_dir = os.path.dirname(os.path.abspath(path))
        try:
            validated = parse_graph_template(raw)
        except ValueError as e:
            messagebox.showerror("Load configuration", str(e))
            return
        self._stop_sensor_worker()
        while True:
            try:
                self._sensor_queue.get_nowait()
            except queue.Empty:
                break
        self._sensor_rows.clear()
        self._apply_panels_list(validated, initial=True, render=False)
        self._refresh_datasets()
        self._render_all()

    def _render_panel(self, panel_id: str) -> None:
        self._schedule_render_async(frozenset({panel_id}))

    def _render_all(self) -> None:
        self._schedule_render_async(None)


def run() -> None:
    app = SensorDashboardApp()
    app.root.mainloop()


if __name__ == "__main__":
    run()
