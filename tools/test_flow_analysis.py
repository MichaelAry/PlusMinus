"""Graph extraction and edge accuracy tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ide'))
from flow_analysis import bytecode_flow, call_graph

class GraphTests(unittest.TestCase):
    def test_branch_edges(self):
        graph=bytecode_flow('0 PushConst\n1 Jz -> 4\n2 PushConst\n3 Jmp -> 5\n4 Pop\n5 Halt')
        self.assertIn(('1','4','Jz'),graph['edges'])
        self.assertIn(('1','2','fallthrough'),graph['edges'])
        self.assertNotIn(('3','4','fallthrough'),graph['edges'])

    def test_call_graph(self):
        graph=call_graph('func a(){ b(); }\nfunc b(){ return 2; }\na();')
        self.assertIn(('a','b','call'),graph['edges'])
        self.assertIn(('__main__','a','call'),graph['edges'])

    def test_truncation(self):
        graph=bytecode_flow('\n'.join(f'{i} PushConst' for i in range(20)),limit=5)
        self.assertTrue(graph['truncated'])
        self.assertEqual(len(graph['nodes']),5)

if __name__=="__main__":
    unittest.main()
