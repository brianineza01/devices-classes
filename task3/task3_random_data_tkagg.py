import csv
import json
import math
import numbers
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Iterable, NotRequired, TypedDict

import tkinter as tk
from tkinter import filedialog, messagebox

import pandas as pd
import seaborn as sns
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

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
MAX_SENSOR_ROWS = 10_000
DATA_SOURCE_CHOICES: tuple[str, ...] = ("sensor", "file")

_PERF = os.environ.get("TASK3_PERF") == "1"

PERF_GROUP_RENDER = "render"
PERF_GROUP_CSV = "csv"
PERF_GROUP_CONFIG = "config"
PERF_GROUP_UI = "ui"
PERF_GROUP_POLL = "poll"
PERF_GROUP_DATA = "data"

_PERF_DEPTH = 0


def _perf_fmt_kv(**kv: object) -> str:
    if not kv:
        return ""
    return "  " + " ".join(f"{k}={v!r}" for k, v in kv.items())


def _perf_emit(group: str, marker: str, label: str, ms: float | None, **kv: object) -> None:
    if not _PERF:
        return
    ind = "\t" * _PERF_DEPTH
    ctx = _perf_fmt_kv(**kv)
    head = f"[task3_perf][{group}]{ind}{marker} {label}"
    if ms is not None:
        print(f"{head}\t{ms:.2f}ms{ctx}", flush=True)
    else:
        print(f"{head}{ctx}", flush=True)


def _perf(ms: float, group: str, label: str, **kv: object) -> None:
    _perf_emit(group, "·", label, ms, **kv)


@contextmanager
def _perf_region(group: str, label: str, **ctx: object):
    global _PERF_DEPTH
    if not _PERF:
        yield
        return
    _perf_emit(group, "▼", label, None, **ctx)
    _PERF_DEPTH += 1
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000
        _PERF_DEPTH -= 1
        _perf_emit(group, "╰", f"{label} · Σ", ms, **ctx)


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


def records_render_fingerprint(
    panel: ChartPanelConfig,
    records: list[dict[str, object]] | None,
) -> tuple[object, ...]:
    if not records:
        return ("empty",)
    xk = panel["x_axis_value_key"]
    yk = panel["y_axis_values_key"]
    h = 5381
    for r in records:
        h = ((h * 33) ^ hash((r[xk], r[yk]))) & 0xFFFFFFFFFFFFFFFF
    return (len(records), h)


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


def x_domain_endpoints(x_coords: list[object]) -> tuple[object, object]:
    if not x_coords:
        raise ValueError("x_coords must not be empty")
    if len(x_coords) == 1:
        return x_coords[0], x_coords[0]
    if all(isinstance(v, datetime) for v in x_coords):
        lo = min(x_coords)
        hi = max(x_coords)
        return lo, hi
    lo = min(x_coords, key=float)
    hi = max(x_coords, key=float)
    return lo, hi


def interpolate_x_coord(x_coords: list[object], frac: float) -> object:
    if not x_coords:
        raise ValueError("x_coords must not be empty")
    frac = max(0.0, min(1.0, frac))
    n = len(x_coords)
    if n == 1:
        return x_coords[0]
    a, b = x_domain_endpoints(x_coords)
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
    t0, t1 = x_domain_endpoints(x)
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
    t0, t1 = x_domain_endpoints(x)
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


def draw_series(
    ax,
    x,
    y,
    chart_type: str,
    *,
    panel_id: str | None = None,
) -> None:
    pid = panel_id or "?"
    ct = normalize_chart_type(chart_type)
    with _perf_region(PERF_GROUP_RENDER, "draw_series", panel_id=pid, ct=ct):
        t_y = time.perf_counter()
        y_seq = list(y)
        _perf((time.perf_counter() - t_y) * 1000, PERF_GROUP_RENDER, "materialize_y_list", n=len(y_seq))
        if ct == "line":
            t_lp = time.perf_counter()
            sns.lineplot(x=x, y=y_seq, ax=ax, errorbar=None)
            _perf((time.perf_counter() - t_lp) * 1000, PERF_GROUP_RENDER, "sns.lineplot")
            t_sc = time.perf_counter()
            ax.scatter(x, y_seq, color="red", s=50, zorder=5)
            _perf((time.perf_counter() - t_sc) * 1000, PERF_GROUP_RENDER, "ax.scatter_overlay")
        elif ct == "bar":
            t_bp = time.perf_counter()
            sns.barplot(x=x, y=y_seq, ax=ax)
            _perf((time.perf_counter() - t_bp) * 1000, PERF_GROUP_RENDER, "sns.barplot")
            t_lb = time.perf_counter()
            for i, bar in enumerate(ax.patches):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{float(y_seq[i]):.2f}",
                    ha="center",
                    va="bottom",
                )
            _perf((time.perf_counter() - t_lb) * 1000, PERF_GROUP_RENDER, "bar_value_labels_loop", nbars=len(ax.patches))
        elif ct == "scatter":
            t_sp = time.perf_counter()
            sns.scatterplot(x=x, y=y_seq, ax=ax)
            _perf((time.perf_counter() - t_sp) * 1000, PERF_GROUP_RENDER, "sns.scatterplot")
            t_an = time.perf_counter()
            for xi, yi in zip(x, y_seq):
                ax.annotate(
                    f"({_annotate_x_text(xi)}, {float(yi):.2f})",
                    (xi, yi),
                    xytext=(5, 5),
                    textcoords="offset points",
                )
            _perf((time.perf_counter() - t_an) * 1000, PERF_GROUP_RENDER, "point_annotation_loop", n=len(y_seq))
        elif ct == "step":
            t_st = time.perf_counter()
            ax.step(x, y_seq, where="post")
            _perf((time.perf_counter() - t_st) * 1000, PERF_GROUP_RENDER, "ax.step")
            t_sc2 = time.perf_counter()
            ax.scatter(x, y_seq, color="red", s=50, zorder=5)
            _perf((time.perf_counter() - t_sc2) * 1000, PERF_GROUP_RENDER, "ax.scatter_overlay")
        elif ct == "stem":
            t_stem = time.perf_counter()
            ax.stem(x, y_seq)
            _perf((time.perf_counter() - t_stem) * 1000, PERF_GROUP_RENDER, "ax.stem")


def render_chart_figure(
    figure: Figure,
    records: list[dict[str, object]] | None,
    chart_type: str,
    config: ChartFigureConfig,
    *,
    show_grid: bool,
    markers: tuple[ChartMarker, ...],
    marker_selected_index: int | None,
    panel_id: str | None = None,
    chart_type_normalized: str | None = None,
) -> None:
    pid = panel_id or "?"
    ct_label = chart_type_normalized or normalize_chart_type(chart_type)
    nrec = len(records) if records else 0
    with _perf_region(PERF_GROUP_RENDER, "render_chart_figure", panel_id=pid, ct=ct_label, n=nrec):
        t_clear = time.perf_counter()
        figure.clear()
        figure.subplots_adjust(bottom=0.24)
        _perf((time.perf_counter() - t_clear) * 1000, PERF_GROUP_RENDER, "figure.clear_and_margin", panel_id=pid)
        if not records:
            return
        t_data = time.perf_counter()
        xk = config["x_axis_value_key"]
        yk = config["y_axis_values_key"]
        x, x_is_time = coerce_time_axis_x(xk, [r[xk] for r in records])
        y = [r[yk] for r in records]
        _perf(
            (time.perf_counter() - t_data) * 1000,
            PERF_GROUP_RENDER,
            "coerce_xy",
            panel_id=pid,
            n=len(records),
            x_is_time=x_is_time,
        )
        t_axes = time.perf_counter()
        ax = figure.add_subplot(111)
        _perf((time.perf_counter() - t_axes) * 1000, PERF_GROUP_RENDER, "figure.add_subplot", panel_id=pid)
        draw_series(ax, x, y, chart_type, panel_id=pid)
        if markers:
            t_markers = time.perf_counter()
            draw_seaborn_markers(
                ax,
                chart_type=chart_type,
                markers=markers,
                x_coords=x,
                selected_index=marker_selected_index,
                figure_config=config,
                records=records,
            )
            _perf(
                (time.perf_counter() - t_markers) * 1000,
                PERF_GROUP_RENDER,
                "draw_seaborn_markers",
                panel_id=pid,
                n_markers=len(markers),
                ct=ct_label,
            )
        t_style = time.perf_counter()
        ax.set_title(config["title"])
        xu: str | None = config.get("x_axis_unit")
        yu: str | None = config.get("y_axis_unit")
        ax.set_xlabel(format_axis_label(config["x_axis_label"], xu))
        ax.set_ylabel(format_axis_label(config["y_axis_label"], yu))
        if x_is_time and len(x) >= 2:
            t_dt0, t_dt1 = x_domain_endpoints(x)
            if isinstance(t_dt0, datetime) and isinstance(t_dt1, datetime):
                span = t_dt1 - t_dt0
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
        if ct_label != "bar":
            ax.margins(x=0)
        _perf((time.perf_counter() - t_style) * 1000, PERF_GROUP_RENDER, "title_labels_ticks_grid", panel_id=pid)


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


def validate_panel_config_json_list(raw: object) -> list[dict[str, object]]:
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
    with _perf_region(PERF_GROUP_CONFIG, "parse_graph_template"):
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
    pid = str(panel["id"])
    with _perf_region(PERF_GROUP_CSV, "dataset_rows_from_wide_csv", panel_id=pid, path=csv_path):
        t0 = time.perf_counter()
        df = pd.read_csv(csv_path)
        _perf((time.perf_counter() - t0) * 1000, PERF_GROUP_CSV, "pd.read_csv", panel_id=pid, rows=len(df))
        xk = str(panel["x_axis_value_key"])
        yk = str(panel["y_axis_values_key"])
        if xk not in df.columns or yk not in df.columns:
            raise ValueError(
                f"CSV {csv_path!r} missing columns for panel {pid}: "
                f"need {xk!r} and {yk!r}; columns are {list(df.columns)}"
            )
        rows: list[dict[str, object]] = []
        t1 = time.perf_counter()
        for _, row in df.iterrows():
            rows.append({xk: _csv_scalar(row[xk]), yk: _csv_scalar(row[yk])})
        _perf((time.perf_counter() - t1) * 1000, PERF_GROUP_CSV, "iterrows_to_row_dicts", panel_id=pid, n=len(rows))
    return rows


def initial_chart_types(panels: list[ChartPanelConfig]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in panels:
        d = p.get("default_chart_type", DEFAULT_CHART_TYPE)
        out[p["id"]] = normalize_chart_type(d)
    return out


class SensorDashboardApp:
    def __init__(self) -> None:
        self._sensor_rows: list[dict[str, object]] = []
        self._bmp280: BMP280I2C | None = None
        self._poll_after_id: str | None = None
        self.panels: list[ChartPanelConfig] = []
        self.panel_frames: dict[str, tk.LabelFrame] = {}
        self.graph_config_labels: dict[str, tk.Label] = {}
        self.root = tk.Tk()
        self.root.title("BMP280 charts (sensor / file)")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

        self.figures: dict[str, Figure] = {}
        self.figure_canvases: dict[str, FigureCanvasTkAgg] = {}
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
        self._last_render_sig: dict[str, object] = {}

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
        self._cancel_poll()
        if self._bmp280 is not None:
            try:
                self._bmp280.close()
            finally:
                self._bmp280 = None
        self.root.destroy()

    def _cancel_poll(self) -> None:
        if self._poll_after_id is not None:
            self.root.after_cancel(self._poll_after_id)
            self._poll_after_id = None

    def _start_sensor_poll_if_needed(self) -> None:
        self._cancel_poll()
        if not self._any_sensor_panel():
            if self._bmp280 is not None:
                try:
                    self._bmp280.close()
                finally:
                    self._bmp280 = None
            return
        if self._bmp280 is None:
            try:
                self._bmp280 = BMP280I2C()
            except Exception as e:
                messagebox.showerror("BMP280", str(e))
                return
        self._poll_after_id = self.root.after(0, self._poll_tick)

    def _schedule_next_poll(self) -> None:
        if self._bmp280 is None or not self._any_sensor_panel():
            return
        self._poll_after_id = self.root.after(POLL_INTERVAL_MS, self._poll_tick)

    def _poll_tick(self) -> None:
        self._poll_after_id = None
        if self._bmp280 is None or not self._any_sensor_panel():
            return
        try:
            row = bmp280_sample_row(self._bmp280)
        except Exception as e:
            self.status_label.config(text=f"Sensor read error: {e}")
            self._schedule_next_poll()
            return
        self._sensor_rows.append(row)
        lim = MAX_SENSOR_ROWS
        while len(self._sensor_rows) > lim:
            self._sensor_rows.pop(0)
        with _perf_region(
            PERF_GROUP_POLL,
            "poll_tick.after_sample",
            sensor_rows=len(self._sensor_rows),
        ):
            self._rebind_dataset_refs()
            self._render_all()
        self.status_label.config(text=status_for_state(self._state, self.panels))
        self._schedule_next_poll()

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
        canvas = FigureCanvasTkAgg(self.figures[pid], master=chart_col)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self.figure_canvases[pid] = canvas
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

        n = len(ordered)
        with _perf_region(PERF_GROUP_UI, "apply_panels_list", initial=initial, render=render, panels=n):
            t_destroy = time.perf_counter()
            for w in self.charts_container.winfo_children():
                w.destroy()
            _perf(
                (time.perf_counter() - t_destroy) * 1000,
                PERF_GROUP_UI,
                "destroy_chart_widgets",
                n_widgets_cleared=n,
            )

            self.panels = ordered
            self.figures = {}
            self.figure_canvases = {}
            self._last_render_sig.clear()
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
            t_fig = time.perf_counter()
            for p in self.panels:
                pid = p["id"]
                self.figures[pid] = Figure(figsize=(5.5, 5), dpi=100)
                v = tk.StringVar(self.root)
                v.set(new_ct[pid])
                self.chart_type_vars[pid] = v
                self.marker_style_vars[pid] = tk.StringVar(master=self.root, value=MARKER_STYLE_DISPLAY_NAMES[0])
                self.marker_label_vars[pid] = tk.StringVar(master=self.root, value="")
                self.marker_x_vars[pid] = tk.IntVar(master=self.root, value=half)
                self.marker_y_vars[pid] = tk.IntVar(master=self.root, value=half)

            _perf(
                (time.perf_counter() - t_fig) * 1000,
                PERF_GROUP_UI,
                "init_figures_and_tk_vars",
                panels=len(self.panels),
            )

            n_panels = len(self.panels)
            t_build = time.perf_counter()
            for i, p in enumerate(self.panels):
                pid = p["id"]
                self._build_panel_column(
                    self.charts_container,
                    p,
                    self._panel_column_padx(i, n_panels),
                    grid_on=new_grid[pid],
                    config_json_on=new_cfg_json[pid],
                )
            _perf(
                (time.perf_counter() - t_build) * 1000,
                PERF_GROUP_UI,
                "build_panel_columns_loop",
                panels=n_panels,
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
            t_msync = time.perf_counter()
            for p in self.panels:
                pid = p["id"]
                self._normalize_marker_selection(pid)
                self._sync_marker_slider_ui(pid)
            _perf(
                (time.perf_counter() - t_msync) * 1000,
                PERF_GROUP_UI,
                "marker_ui_sync_loop",
                panels=n_panels,
            )
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

    def _chart_render_signature(self, panel_id: str) -> tuple[object, ...]:
        panel = next(p for p in self.panels if p["id"] == panel_id)
        records = self._state.datasets.get(panel_id)
        marks = self._state.markers.get(panel_id, ())
        sel = self._state.marker_selected_index.get(panel_id) if marks else None
        ct = normalize_chart_type(self._state.chart_types.get(panel_id, DEFAULT_CHART_TYPE))
        cfg_txt = chart_config_display_text(panel_figure_config(panel))
        grid_on = self._state.grid_visible.get(panel_id, True)
        return (
            cfg_txt,
            ct,
            grid_on,
            marks,
            sel,
            records_render_fingerprint(panel, records),
        )

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
        with _perf_region(PERF_GROUP_DATA, "refresh_datasets", panels=len(self.panels)):
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
        with _perf_region(PERF_GROUP_CONFIG, "load_configuration", path=path):
            t_load = time.perf_counter()
            try:
                with open(path, encoding="utf-8") as f:
                    raw = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                messagebox.showerror("Load configuration", str(e))
                return
            _perf((time.perf_counter() - t_load) * 1000, PERF_GROUP_CONFIG, "json.load", path=path)
            self._template_dir = os.path.dirname(os.path.abspath(path))
            try:
                validated = parse_graph_template(raw)
            except ValueError as e:
                messagebox.showerror("Load configuration", str(e))
                return
            self._apply_panels_list(validated, initial=False, render=False)
            self._refresh_datasets()
            self._render_all()

    def _render_panel(self, panel_id: str) -> None:
        with _perf_region(PERF_GROUP_RENDER, "_render_panel", panel_id=panel_id):
            self._sync_chart_types_from_ui()
            self._normalize_marker_selection(panel_id)
            sig = self._chart_render_signature(panel_id)
            cached = sig == self._last_render_sig.get(panel_id)
            if cached:
                _perf_emit(PERF_GROUP_RENDER, "·", "render_panel_cache_hit", None, panel_id=panel_id)
            else:
                panel = next(p for p in self.panels if p["id"] == panel_id)
                records = self._state.datasets.get(panel_id)
                marks = self._state.markers.get(panel_id, ())
                sel = self._state.marker_selected_index.get(panel_id) if marks else None
                ct = normalize_chart_type(self._state.chart_types.get(panel_id, DEFAULT_CHART_TYPE))
                render_chart_figure(
                    self.figures[panel_id],
                    records,
                    ct,
                    panel_figure_config(panel),
                    show_grid=self._state.grid_visible.get(panel_id, True),
                    markers=marks,
                    marker_selected_index=sel,
                    panel_id=panel_id,
                    chart_type_normalized=ct,
                )
                t_draw = time.perf_counter()
                self.figure_canvases[panel_id].draw()
                _perf(
                    (time.perf_counter() - t_draw) * 1000,
                    PERF_GROUP_RENDER,
                    "canvas_tkagg.draw",
                    panel_id=panel_id,
                )
                self._last_render_sig[panel_id] = sig
            t_ui = time.perf_counter()
            self.status_label.config(text=status_for_state(self._state, self.panels))
            self._sync_marker_slider_ui(panel_id)
            self._refresh_marker_list(panel_id)
            _perf(
                (time.perf_counter() - t_ui) * 1000,
                PERF_GROUP_RENDER,
                "tk.status_markers_lists",
                panel_id=panel_id,
            )

    def _render_all(self) -> None:
        with _perf_region(PERF_GROUP_RENDER, "_render_all", panels=len(self.panels)):
            self._sync_chart_types_from_ui()
            for p in self.panels:
                self._render_panel(p["id"])


def run() -> None:
    app = SensorDashboardApp()
    app.root.mainloop()


if __name__ == "__main__":
    run()
