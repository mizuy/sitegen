# https://github.com/mayoff/python-markdown-mathjax/blob/master/mdx_mathjax.py

import markdown

class MathJaxPattern(markdown.inlinepatterns.Pattern):

    def __init__(self):
        # When using the default getCompiledRegExp() method provided in the Pattern you can pass in a regular expression without that and getCompiledRegExp will wrap your expression for you and set the re.DOTALL and re.UNICODE flags. This means that the first group of your match will be m.group(2) as m.group(1) will match everything before the pattern.
        markdown.inlinepatterns.Pattern.__init__(self, r'(?<!\\)(\$\$?)(.+?)\2')

    def handleMatch(self, m):
        node = markdown.util.etree.Element('span')
        node.set('class','mathjax')
        node.text = markdown.util.AtomicString(m.group(2) + m.group(3) + m.group(2))
        return node

class MathJaxExtension(markdown.Extension):
    def extendMarkdown(self, md, md_globals):
        # Needs to come before escape matching because \ is pretty important in LaTeX
        md.inlinePatterns.add('mathjax', MathJaxPattern(), '<escape')

def makeExtension(configs=None):
    return MathJaxExtension(configs)
