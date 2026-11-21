"""Pure tests for click-to-definition language source links."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'ide'))
from internals import SYMBOLS, SourceTarget, editable_checkout, keyword_at, locate_target, source_targets


class LanguageInternalsTests(unittest.TestCase):
    def test_all_language_constructs_are_mapped(self):
        for name in ('if','else','while','func','proc','return','go','sync','lock','unlock',
                     'print','len','resize','sin','cos','pow','fact','multifact',
                     'int','float','double'):
            self.assertIn(name,SYMBOLS)
            self.assertGreater(len(source_targets(name)),0)

    def test_keyword_only_from_code(self):
        source = '// while in comment\nprint("if in string");\nwhile (1) {}'
        self.assertIsNone(keyword_at(source,source.index('while')))
        self.assertIsNone(keyword_at(source,source.index('if')))
        self.assertEqual(keyword_at(source,source.rindex('while')+2),'while')

    def test_block_comments_are_ignored(self):
        source = '/* print(1); */ print(2);'
        self.assertIsNone(keyword_at(source,3))
        self.assertEqual(keyword_at(source,source.rindex('print')),'print')

    def test_partial_and_unknown_words(self):
        self.assertIsNone(keyword_at('printer=1;',2))
        self.assertIsNone(keyword_at('while',-1))
        self.assertIsNone(keyword_at('while',5))

    def test_repository_targets_resolve(self):
        root = Path(__file__).resolve().parents[1]
        for name in SYMBOLS:
            for target in source_targets(name):
                path, line = locate_target(root, target)
                self.assertTrue(path.is_file(), name)
                self.assertGreater(line, 0, name)

    def test_source_anchor_and_sandbox(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'src/compiler').mkdir(parents=True)
            (root/'src/compiler/statements.cpp').write_text('a\nb\nvoid Compiler::parseIf() {}\n')
            target=SourceTarget('src/compiler/statements.cpp','void Compiler::parseIf()','Compiler')
            self.assertEqual(locate_target(root,target)[1],3)
            with self.assertRaises(ValueError):
                locate_target(root,SourceTarget('../outside.txt','x','Invalid'))
            with self.assertRaises(ValueError):
                locate_target(root,SourceTarget('src/compiler/statements.cpp','no such target','Invalid'))
            self.assertFalse(editable_checkout(root))


if __name__ == '__main__':
    unittest.main()
