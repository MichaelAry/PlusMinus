import unittest
from engine import execute, find_runner, check

class Smoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = find_runner()
        if not cls.runner:
            raise RuntimeError('Build the C++ runner first')

    def run_source(self, source, mode='run', timeout=5):
        return execute(self.runner, source, mode, timeout)

    def test_output(self):
        r = self.run_source('print(2 + 3 * 4);')
        self.assertTrue(r['ok'], r['error'])
        self.assertEqual(r['output'], '14\n')
        self.assertTrue(check({'kind':'output','expected':'14\n'}, r))
        self.assertFalse(check({'kind':'output','expected':'15\n'}, r))

    def test_variables(self):
        r = self.run_source('x = 10; print(x);')
        self.assertTrue(r['ok'], r['error'])
        self.assertIn('x = 10', r['variables'])

    def test_compile(self):
        r = self.run_source('print(2);', 'compile')
        self.assertTrue(r['ok'], r['error'])
        self.assertIn('Call', r['bytecode'])
        self.assertEqual(r['output'], '')

    def test_error(self):
        r = self.run_source('if (1) {')
        self.assertFalse(r['ok'])
        self.assertIn('compile:',r['error'])

    def test_bounded_instruction_trace(self):
        report = self.run_source('x = 1 + 2; print(x);', 'trace')
        self.assertTrue(report['ok'], report['error'])
        self.assertTrue(report['trace'])
        self.assertEqual(report['trace'][0]['ip'], 0)
        self.assertTrue(all('opcode' in entry and 'thread' in entry
                            for entry in report['trace']))
        self.assertFalse(report['trace_truncated'])

    def test_timeout(self):
        r = self.run_source('while (1) {}', timeout=0.2)
        self.assertFalse(r['ok'])
        self.assertIn('timed out', r['error'])

if __name__ == '__main__':
    unittest.main()
