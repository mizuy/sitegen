"""
retrieve first header text as title.
"""
import markdown
from markdown.util import etree
from markdown.extensions.headerid import itertext
import re

class TitleTreeprocessor(markdown.treeprocessors.Treeprocessor):
    # Iterator wrapper to get parent and child all at once
    def iterparent(self, root):
        for parent in root.getiterator():
            for child in parent:
                yield parent, child

    def run(self, doc):
        self.markdown.title = ''
        header_rgx = re.compile("[Hh][123456]")

        for (p, c) in self.iterparent(doc):
            text = ''.join(itertext(c)).strip()

            if not text:
                continue
                    
            if header_rgx.match(c.tag):
                self.markdown.title = text
                break

class TitleExtension(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        titleext = TitleTreeprocessor(md)
        md.treeprocessors.add("title", titleext, "_begin")
    
def makeExtension(configs={}):
    return TitleExtension(configs=configs)
