import unittest
from sitegen.sitegen import *

class TestSitegen(unittest.TestCase):
    def test_tt(self):
        a = """
        <html>
        <head></head>
        <title>This is title</title>
        <h1></h1>
        <h2></h2>
        <h3></h3>
        <h1></h1>
        <h3></h3>
        </html>
        """
        title, toc = generate_title_toc(a)
        self.assertEqual(title, "This is title")
        self.assertEqual(toc, '<ul class="toc"><li><a href="#None"/></li><ul><li><a href="#None"/></li><ul><li><a href="#None"/></li></ul></ul><li><a href="#None"/></li><ul><ul><li><a href="#None"/></li></ul></ul></ul>')

    def test_lm(self):
        a = """
---
test: path/to/directory
another: 123
---
others
"""
        m,o = load_metadata(a)
        self.assertEqual(m, {'test':'path/to/directory', 'another':123})
        self.assertEqual(o.strip(), 'others')

if __name__ == '__main__':
    unittest.main()
