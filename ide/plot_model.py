"""Plot document and coordinate geometry independent of Qt."""
from dataclasses import dataclass, field
import math
from uuid import uuid4


@dataclass(frozen=True)
class Viewport:
    xmin: float = -10
    xmax: float = 10
    ymin: float = -2
    ymax: float = 2

    def __post_init__(self):
        for axis, low, high in (('X', self.xmin, self.xmax), ('Y', self.ymin, self.ymax)):
            if not low < high or not all(map(math.isfinite, (low, high, high - low))):
                raise ValueError(f'Invalid {axis} viewport range')

    def screen(self, x, y, rect):
        left, top, width, height = rect
        return (left + (x - self.xmin) / (self.xmax - self.xmin) * width,
                top + (self.ymax - y) / (self.ymax - self.ymin) * height)

    def data(self, x, y, rect):
        left, top, width, height = rect
        return (self.xmin + (x - left) / width * (self.xmax - self.xmin),
                self.ymax - (y - top) / height * (self.ymax - self.ymin))


@dataclass
class Series:
    label: str
    color: str
    id: str = field(default_factory=lambda: uuid4().hex)
    visible: bool = True


@dataclass
class Formula(Series):
    expression: str = 'sin(x)'
    parameters: dict = field(default_factory=dict)


@dataclass
class Points(Series):
    points: list = field(default_factory=list)


@dataclass
class PlotDocument:
    viewport: Viewport = field(default_factory=Viewport)
    series: list = field(default_factory=lambda: [Formula('Formula', '#5AB0FF')])


def zoom(view, anchor, factor):
    x, y = anchor
    return Viewport(x + (view.xmin - x) * factor, x + (view.xmax - x) * factor,
                    y + (view.ymin - y) * factor, y + (view.ymax - y) * factor)


def fit(document):
    from plot_expression import ExpressionError, parse

    points = [point for series in document.series if isinstance(series, Points) and series.visible
              for point in series.points]
    formulas = [series for series in document.series if isinstance(series, Formula) and series.visible]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    if formulas:
        xs.extend((-10, 10))
        low, high = min(xs), max(xs)
        for series in formulas:
            try:
                expr = parse(series.expression)
            except ExpressionError:
                continue
            for i in range(512):
                fraction = i / 511
                x = low * (1 - fraction) + high * fraction
                y = expr.value(x, series.parameters)
                if y is not None:
                    ys.append(y)
    if not ys:
        return Viewport()

    def limits(values, pad):
        low, high = min(values), max(values)
        if low == high:
            margin = max(1, abs(low) * .05)
        else:
            margin = (high / 20 - low / 20) if pad else 0
        return (low - margin if math.isfinite(low - margin) else low,
                high + margin if math.isfinite(high + margin) else high)

    return Viewport(*limits(xs, False), *limits(ys, True))


MAX_FILE_SIZE = 2 * 1024 * 1024
MAX_SERIES = 16
MAX_POINTS = 10000


def decode(data):
    import re
    from plot_expression import MAX_EXPRESSION, PARAMETERS

    def require(condition, field):
        if not condition:
            raise ValueError(f'Invalid {field}')

    def number(value, field):
        require(type(value) in (float, int), field)
        try:
            result = float(value)
        except OverflowError:
            raise ValueError(f'Invalid {field}') from None
        require(math.isfinite(result), field)
        return result

    require(isinstance(data, dict), 'document')
    require(type(data.get('version')) is int and data['version'] == 1, 'version')
    axes = ('xmin', 'xmax', 'ymin', 'ymax')
    view = data.get('viewport')
    require(isinstance(view, dict), 'viewport')
    viewport = Viewport(*(number(view.get(axis), f'viewport.{axis}') for axis in axes))
    entries = data.get('series')
    require(isinstance(entries, list) and len(entries) <= MAX_SERIES, 'series count')
    document = PlotDocument(viewport, [])
    ids = set()
    count = 0
    for index, entry in enumerate(entries, 1):
        prefix = f'series {index}'
        require(isinstance(entry, dict), prefix)
        identifier = entry.get('id')
        require(isinstance(identifier, str) and identifier and identifier not in ids, f'{prefix}.id')
        ids.add(identifier)
        label, color, visible = (entry.get(key) for key in ('label', 'color', 'visible'))
        require(isinstance(label, str), f'{prefix}.label')
        require(isinstance(color, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', color), f'{prefix}.color')
        require(isinstance(visible, bool), f'{prefix}.visible')
        kind = entry.get('kind')
        if kind == 'formula':
            text, parameters = entry.get('expression'), entry.get('parameters')
            require(isinstance(text, str) and len(text) <= MAX_EXPRESSION, f'{prefix}.expression')
            require(isinstance(parameters, dict) and parameters.keys() <= set(PARAMETERS),
                    f'{prefix}.parameters')
            values = {}
            for key, value in parameters.items():
                field = f'{prefix}.parameters.{key}'
                value = number(value, field)
                require(-10 <= value <= 10 and math.isclose(value * 100, round(value * 100),
                                                            rel_tol=0, abs_tol=1e-9), field)
                values[key] = value
            series = Formula(label, color, identifier, visible, text, values)
        elif kind == 'points':
            rows = entry.get('points')
            require(isinstance(rows, list) and count + len(rows) <= MAX_POINTS, f'{prefix}.points count')
            count += len(rows)
            points = []
            for row, pair in enumerate(rows, 1):
                field = f'{prefix}.points row {row}'
                require(isinstance(pair, (list, tuple)) and len(pair) == 2, field)
                points.append((number(pair[0], field + ' X'), number(pair[1], field + ' Y')))
            series = Points(label, color, identifier, visible, points)
        else:
            raise ValueError(f'Invalid {prefix}.kind')
        document.series.append(series)
    return document


def load_plot(path):
    import json

    with open(path, 'rb') as stream:
        data = stream.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise ValueError('Plot file exceeds 2 MiB')
    try:
        return decode(json.loads(data.decode('utf-8')))
    except RecursionError as error:
        raise ValueError('Plot JSON is nested too deeply') from error


def save_plot(path, document):
    from dataclasses import asdict
    import json
    import os
    from pathlib import Path
    from tempfile import NamedTemporaryFile

    path = Path(path)
    data = dict(version=1, viewport=asdict(document.viewport), series=[
        dict(asdict(series), kind='formula' if isinstance(series, Formula) else 'points')
        for series in document.series])
    decode(data)
    payload = (json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')
    if len(payload) > MAX_FILE_SIZE:
        raise ValueError('Plot file exceeds 2 MiB')
    temp = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temp = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
