from citeproc.source.bibtex import BibTeX
from citeproc import CitationStylesStyle, CitationStylesBibliography, formatter
class Bibliography:
    def __init__(self, bib_file, csl_file):
        self.bib_file = bib_file
        self.csl_file = csl_file
        self.bibtex = BibTeX(bib_file)
        self.style = CitationStylesStyle(csl_file, validate=False)
        self.bibliography = CitationStylesBibliography(bib_style, bib_source,formatter.plain)

    def citation(self, pandocname):
        c = Citation([CitationItem('whole-collection')])
        self.bibliography.register(c)
        return self.bibliography.cite(c)
    
    def bibliography(self):
        for item in self.bibliography.bibliography():
            str(item)
        
