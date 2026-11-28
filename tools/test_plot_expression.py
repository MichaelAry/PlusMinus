import unittest

from test_plot_model import Viewport
from plot_expression import ExpressionError, parse


class ExpressionTests(unittest.TestCase):
    def test_precedence(self):
        for source, value in [('-2^2', -4), ('(-2)^2', 4), ('2^3^2', 512),
                              ('2^-2', .25), ('sin(0)', 0), ('pow(a,c)', 9)]:
            self.assertEqual(parse(source).value(0, {'a': 3, 'c': 2}), value)

    def test_errors_and_recovery(self):
        for source in ['sin(', 'sin(1,2)', '2x', 'abc', '-' * 40 + '2',
                       '2^' * 40 + '2', '(' * 40 + '2' + ')' * 40, ' ' * 513]:
            with self.assertRaises(ExpressionError) as error:
                parse(source)
            self.assertLessEqual(error.exception.position, len(source))
        self.assertIsNone(parse('1/x').value(0, {}))
        self.assertEqual(parse('1/x').value(2, {}), .5)

    def test_discontinuities(self):
        from plot_expression import sample
        for source, pole in [('1/x', 0), ('1/(x-0.123)', .123)]:
            curves = sample(parse(source), {}, Viewport(), 256, 300)
            self.assertGreater(len(curves), 1)
            self.assertFalse(any(segment[0][0] < pole < segment[-1][0] for segment in curves))
        line = sample(parse('1000*x'), {}, Viewport(), 256, 300)
        self.assertEqual(len(line), 1)
        self.assertEqual(len(line[0]), 256)
