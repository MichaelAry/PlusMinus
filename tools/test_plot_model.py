import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ide'))
from plot_model import Formula, PlotDocument, Points, Viewport


class ModelTests(unittest.TestCase):
    def test_document(self):
        doc = PlotDocument()
        doc.series.extend([Formula('Second', '#123456'), Points('Samples', '#654321')])
        doc.series[0].parameters['a'] = 2
        self.assertIsInstance(doc.series[0], Formula)
        self.assertIsInstance(doc.series[2], Points)
        self.assertEqual(doc.series[1].parameters, {})
        self.assertEqual(doc.viewport, Viewport(-10, 10, -2, 2))
        for limits in [(0, 0, -2, 2), (-1e308, 1e308, -2, 2), (0, 1, 0, float('inf'))]:
            with self.assertRaises(ValueError):
                Viewport(*limits)

    def test_coordinates(self):
        view = Viewport()
        rect = (50, 10, 200, 100)
        for data, screen in [((-10, 2), (50, 10)), ((10, -2), (250, 110)),
                             ((0, 0), (150, 60))]:
            self.assertEqual(view.screen(*data, rect), screen)
            self.assertEqual(view.data(*screen, rect), data)

    def test_zoom_and_fit(self):
        from plot_model import fit, zoom
        rect = (10, 10, 1000, 550)
        cursor = (600, 240)
        view = Viewport()
        anchor = view.data(*cursor, rect)
        for actual, expected in zip(zoom(view, anchor, .8).screen(*anchor, rect), cursor):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(fit(PlotDocument(series=[])), view)
        point = Points('Sample', '#123456', points=[(7, 8)])
        hidden = Points('Hidden', '#123456', visible=False, points=[(1000, 1000)])
        self.assertEqual(fit(PlotDocument(series=[point, hidden])), Viewport(6, 8, 7, 9))
        constant = Formula('Constant', '#123456', expression='3')
        self.assertEqual(fit(PlotDocument(series=[constant])), Viewport(-10, 10, 2, 4))

    def test_version_one_file(self):
        import copy
        import json
        from tempfile import TemporaryDirectory
        from plot_model import decode, load_plot, save_plot

        example = json.loads("""{
          "version": 1,
          "viewport": {"xmin": -10, "xmax": 10, "ymin": -2, "ymax": 2},
          "series": [
            {"id": "wave", "kind": "formula", "label": "Wave", "visible": true,
             "color": "#5AB0FF", "expression": "a*sin(x)", "parameters": {"a": 1}},
            {"id": "samples", "kind": "points", "label": "Measurements", "visible": true,
             "color": "#F2AF57", "points": [[0, 0], [1, 0.84], [2, 0.91]]}
          ]
        }""")
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'experiment.pmplot'
            path.write_text(json.dumps(example), encoding='utf-8')
            doc = load_plot(path)
            self.assertEqual(doc.series[1].points, [(0, 0), (1, .84), (2, .91)])
            doc.series[0].expression = 'sin('
            save_plot(path, doc)
            self.assertEqual(load_plot(path), doc)
            saved = path.read_bytes()
            doc.series[0].parameters['a'] = 11
            with self.assertRaisesRegex(ValueError, 'parameters.a'):
                save_plot(path, doc)
            self.assertEqual(path.read_bytes(), saved)
        for key, value in [('id', 'samples'), ('kind', 'unknown'), ('color', 'red'),
                           ('parameters', {'a': .123})]:
            invalid = copy.deepcopy(example)
            invalid['series'][0][key] = value
            with self.assertRaisesRegex(ValueError, key):
                decode(invalid)
