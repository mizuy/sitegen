# -*- coding: utf-8 -*-

# Static Site Generator powered by markdown ,pandoc and jinja2
# Copyright (c) 2012-2018 MIZUGUCHI Yasuhiko
# based on http://obraz.pirx.ru/
# install requirements: pandoc

import sys, os, io, re, traceback, errno, subprocess
import shutil, fnmatch, yaml, concurrent.futures
from contextlib import contextmanager
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, PackageLoader
from jinja2.exceptions import TemplateSyntaxError
from pathlib import Path
from pyquery import PyQuery
from urllib.parse import urlparse, urljoin
import tqdm
DEBUG = False
PAGE_ENCODING = 'UTF-8'
DEFAULT_TEMPLATE = 'default.j2.html'
MARKDOWN_TEMPLATE = 'markdown.j2.html'
INDEX_TEMPLATE = 'index.j2.html'
CONFIG_YAML = 'config.yaml'
DOCX_TEMPLATE = 'reference.docx'
PANTABLE = shutil.which('pantable')

def makedirs(directory):
    if os.path.exists(directory):
        return
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass

def remove(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
        
def log(message):
    sys.stderr.write(f'{message}\n')
    sys.stderr.flush()

@contextmanager
def report_exceptions():
    try:
        yield
    except KeyboardInterrupt:
        raise KeyboardInterrupt()
    except Exception:
        import sys
        e, m, tb = sys.exc_info()
        print('exception traceback:'.ljust(80, '='))
        for tbi in traceback.format_tb(tb):
            print(tbi)
        print('  %s' % str(m))
        print(''.rjust(80, '='))
        if DEBUG:
            import pdb
            pdb.post_mortem(tb)

def command_str(args, src=None, cwd=None):
    if src and isinstance(src,str):
        src = src.encode(PAGE_ENCODING)
    out,err = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=cwd).communicate(input=src)
    return '' if not out else out.decode(PAGE_ENCODING), '' if not err else err.decode(PAGE_ENCODING)

class ConfigYaml:
    def __init__(self, path, yaml_src):
        self.metadata = {}
        self.path = path
        if yaml_src:
            try:
                self.metadata = yaml.load(yaml_src)
            except:
                log(f'error loading yaml: {path}')

    def get(self, name):
        return self.metadata.get(name)

    def get_fullpath(self, name):
        """ get fullpath of metadata[name] as relative path from self.path """
        a = self.metadata.get(name)
        if a:
            return self.path.parent.joinpath(a).resolve()
        return None

    @classmethod
    def from_file(cls, path):
        return cls(path, open(path).read())
        
class LocalConfigYaml(ConfigYaml):
    def __init__(self, path, yaml_src, parent):
        super().__init__(path, yaml_src)
        self.parent = parent

    def get(self, name):
        return self.get(name) or self.parent.get(name)

    def get_fullpath(self, name):
        return self.get_fullpath(name) or self.parent.get_fullpath(name)


class TemplateEngine:
    def __init__(self, templatedir=None):
        self.defaultloader = PackageLoader("sitegen", "templates")

        self.templatedir = templatedir
        if self.templatedir:
            self.template_files = list(p for p in Path(templatedir).glob('**/*') if p.is_file())
            if not self.template_files:
                self.templatedir = None
                
        if self.templatedir:
            loader = ChoiceLoader([
                FileSystemLoader(self.templatedir),
                self.defaultloader])
        else:
            loader = self.defaultloader

        self.env = Environment(loader=loader)

    def render(self, template, metadata):
        try:
            t = self.env.get_template(template)
            return t.render(**metadata)
        except TemplateSyntaxError as e:
            raise Exception(f"{e.filename}:{e.lineno}: {e.name}, {e.message}")

    @property
    def lastmodified(self):
        "return if one of the template is updated."
        lm = Path(__file__).stat().st_mtime
        if not self.templatedir:
            return lm
        tmp = max(p.stat().st_mtime for p in self.template_files)
        return max(lm, tmp)
        #return max(lm, max(p.stat().st_mtime for p in walk_files(self.templatedir)))

    
class Pandoc:
    # based on https://github.com/bebraw/pypandoc/blob/master/pypandoc/pypandoc.py
    def __init__(self):
        self.src_fmts = command_str(['pandoc', '--list-input-formats'])[0].splitlines()
        self.dst_fmts = command_str(['pandoc', '--list-output-formats'])[0].splitlines()

    def check_format(self, src_format, dst_format):
        if src_format not in self.src_fmts:
            raise RuntimeError('Invalid src format! Expected one of these: ' + ', '.join(self.src_fmts))
        if dst_format not in self.dst_fmts:
            raise RuntimeError('Invalid dst format! Expected one of these: ' + ', '.join(self.dst_fmts))

    def convert(self, src, src_format, dst_format, extra_args=[], cwd=None):
        self.check_format(src_format,dst_format)
        data,error = command_str(['pandoc', '--from='+src_format, '--to='+dst_format] + extra_args, src)
        return data,error

    def convert_write(self, src, src_format, dst_filename, dst_format, extra_args=[], cwd=None):
        self.check_format(src_format,dst_format)
        data,error = command_str(['pandoc', '--from='+src_format, '--to='+dst_format, '-o',dst_filename] + extra_args, src)
        return data, error

    
pandoc = Pandoc()

def asciidoc_convert(src, extra_args=[], cwd=None):
    # args = ['asciidoc', '-a' 'mathjax', '-s', '-o', '-', '-']
    return command_str(['asciidoctor', '-o', '-', '-']+extra_args, src)

class PageBase:
    """
        Page knows dstpath, but don't know destination directory.
        basedir = base directory
        srcpath = src path
        dstpath = srcpath or srcpath.with_suffix(something)
        srcfile = basepath + srcpath
        dstfile = dst_basedir + dstpath
    """
    def __init__(self, site, srcpath):
        self.site = site
        self.src_basedir = site.srcdir
        self.srcpath = Path(srcpath)
        self.dstpath = self.srcpath
        self.srcfile = self.src_basedir / self.srcpath # fullpath
        self.url = str(self.dstpath)
        self.depth = len(self.dstpath.parts)-1
        self.root = '/'.join(['..'] * (self.depth)) if self.depth>0 else '.'

    def generate(self, dstbasedir):
        raise NotImplemented()

    def __repr__(self):
        return f"PageBase({self.srcfile})"

    def need_update(self, lastmodified, dstdir):
        """
        return if dstination file (at basedirectory dstdir) needs update or not
        """
        d = dstdir / self.dstpath
        if not d.is_file():
            return True
        else:
            if d.stat().st_mtime < lastmodified:
                return True
        return False

    @property
    def lastmodified(self):
        return self.srcfile.stat().st_mtime

    @property
    def search_json(self):
        return {'url': self.url, 'title': self.srcpath.stem, 'content': ''}

    def make_dstdir(self, dstbasedir):
        """make dstination dir and return destination file full path
        """
        df = dstbasedir.joinpath(self.dstpath)
        makedirs(df.parent)
        return df

class PageFile(PageBase):
    def __init__(self, site, srcpath):
        super().__init__(site, srcpath)

    def generate(self, dstbasedir):
        df = self.make_dstdir(dstbasedir)
        shutil.copy(self.srcfile, df)

class PageTemplated(PageBase):
    def __init__(self, site, srcpath, default_template):
        super().__init__(site, srcpath)
        self.dstpath = srcpath.with_suffix('.html')
        self.url = str(self.dstpath)
        self.default_template = default_template

        """
        parts = [(link, name)]

        ex.
        a/b/c.html (dd=3)
        (../../../index.html, Index) 0
        (../../index.html, a) 1
        (../index.html, b) 2
        (c.html, c) 3

        ex.
        a/b/index.html (dd=3)
        (../../../index.html, Index) 0
        (../../index.html, a) 1
        (../index.html, b) 2
        (index.html, b) 3

        a/b.html (dd=2)
        (../index.html, Index) 0
        (./index.html, a) 1
        (b.html, b) 2

        a.html (dd=1)
        (./index.html, Index) 0
        (a.html, a)

        index.html (dd=1)
        (index.html, Index) 0

        """

        def rel_parent(n):
            if n==0:
                return self.dstpath.name
            elif n==1:
                return './index.html'
            else:
                return '../'*(n-1)+'index.html'

        pp = list(self.dstpath.with_suffix('').parts)
        dd = len(pp)
        names = ['Home'] + pp
        if names[-1]=='index':
            names.pop()
        self.parts = [(rel_parent(dd-i), name) for i,name in enumerate(names)]

    def render_template(self, metadata={}):
        metadata['url'] = self.url
        metadata['root'] = self.root
        metadata['path'] = self.dstpath
        metadata['parts'] = self.parts
        metadata['mtime'] = self.lastmodified
        metadata['sitename'] = self.site.config.get('sitename')
        metadata['site'] = self.site
        metadata['page'] = self

        template = metadata.get('template') or self.default_template
        return self.site.template_engine.render(template, metadata)

class MarkdownHtml:
    def __init__(self, src):
        # dirty 
        self.q = PyQuery(src.replace('xmlns="http://www.w3.org/1999/xhtml"',' '))
        self.title = self.q('title').text() or self.q('h1').text() or self.q('h2').text() or ''
        self.toc = self.get_toc()
        self.body = self.q('body').html()

    def get_toc(self):
        def get_last_child(e, level):
            if level==0:
                return e
            if level>0:
                ee = e.children('ul:last-child')
                if not ee:
                    #e.append('<li>no title</li>')
                    e.append('<ul></ul>')
                    ee = e.children('ul:last-child')
                return get_last_child(ee, level-1)
    
        out = PyQuery('<ul></ul>')
        for tag in self.q('h1, h2, h3').items():
            level = int(tag[0].tag[1])-1
            assert(0<=level)
            aname = tag.attr('id')
            pp = get_last_child(out, level)
            pp.append(f'<li><a href="#{aname}">{tag.text()}</a></li>\n')
        return out.html() or ""

    def get_links(self):
        ll = []
        for tag in self.q('a').items():
            ll.append(tag.attr('href'))
        return ll

    
class PageMarkdown(PageTemplated):
    def __init__(self, site, srcpath):
        super().__init__(site, srcpath, MARKDOWN_TEMPLATE)

    @property
    def search_json(self):
        source = open(self.srcfile, 'r').read()
        yaml_src, source = PageMarkdown.split_metadata_block(source)
        source = re.sub(r'\s+',' ',source)
        return {'url': self.url,
                'title': self.srcpath.stem,
                'content': self.srcpath.stem+' '+source}

    def generate(self, dstbasedir):
        s = open(self.srcfile, 'r').read()
        yaml_src, source = PageMarkdown.split_metadata_block(s)
        y = LocalConfigYaml(self.srcpath, yaml_src, self.site.config)
        # bib = Bibliography(y.get_fullpath('bibliography'), y.get_fullpath('csl'))

        pantable = ['-F', str(PANTABLE)] if PANTABLE else []
        extra_args=['-s', '--mathjax'] + pantable

        s,err = pandoc.convert(source.encode(PAGE_ENCODING), 'markdown', 'html5', extra_args, cwd=self.srcfile.parent)
        
        if not s.strip() or err:
            s = f'<html><head><title>ERROR {self.srcpath}</title></head><body><pre>{err}</pre><div>{s}</div></body></html>'

        parse = MarkdownHtml(s)
        # body = body.replace('[TOC]', toc)

        metadata = y.metadata
        metadata['title'] = parse.title
        metadata['toc'] = parse.toc
        metadata['body'] = parse.body
        metadata['source'] = source
        metadata['siblings'] = self.site.get_siblings(self.dstpath)
        metadata['not_linked'] = self.site.get_siblings_not_linked(self.dstpath, parse.get_links())

        dstfile = self.make_dstdir(dstbasedir)
        with open(dstfile, 'wb') as f:
            f.write(self.render_template(metadata).encode(PAGE_ENCODING))

    def generate_docx(self, dstbasedir):
        s = open(self.srcfile, 'r').read()
        yaml_src, source = PageMarkdown.split_metadata_block(s)
        refer = Path('reference.docx').resolve()
        s,error = pandoc.convert_write(source.encode(PAGE_ENCODING),
                                       'markdown',
                                       dstbasedir.joinpath(self.dstpathdocx).resolve(),
                                       'docx',
                                       extra_args=[f"--reference-docx={refer}"]+pantable,
                                       cwd=self.srcfile.parent)
        if error:
            log(error)


    R_M = re.compile(r'\A\s*^---+\s*$(.*?)^---+\s*$(.*)\Z', re.M|re.DOTALL)
    @classmethod
    def split_metadata_block(cls, source):
        m = cls.R_M.match(source)
        if m:
            return m[1], m[2].lstrip()
        else:
            return '', source

class PageIndex(PageTemplated):
    def __init__(self, site, srcpath):
        super().__init__(site, srcpath, INDEX_TEMPLATE)

    def generate(self, dstbasedir):
        metadata = {}
        metadata['title'] = f"Index of {self.dstpath.parent}"
        metadata['toc'] = ''
        metadata['body'] = ''
        metadata['source'] = ''
        metadata['siblings'] = self.site.get_siblings(self.dstpath)

        dstfile = self.make_dstdir(dstbasedir)
        with open(dstfile, 'wb') as f:
            f.write(self.render_template(metadata).encode(PAGE_ENCODING))

    @property
    def lastmodified(self):
        return 0
            
class Site:
    def __init__(self, srcdir, templatedir=None):
        self.srcdir = Path(srcdir)
        self.template_engine = TemplateEngine(templatedir)
        self.pages = []
        self.config = ConfigYaml.from_file(CONFIG_YAML)

        dstpaths = []
        for srcpath in self.walk_site(srcdir):
            suffix = srcpath.suffix

            with report_exceptions():
                if suffix in ['.md', '.markdown']:
                    page = PageMarkdown(self, srcpath)
                else:
                    page = PageFile(self, srcpath)

                if page.dstpath in dstpaths:
                    log(f'WARNING: destination file overlapped: dst={page.dstpath}, src={page.srcpath}')
                dstpaths.append(page.dstpath)

                self.pages.append(page)

        for srcpath in self.walk_site(srcdir,get_dir=True):
            with report_exceptions():
                index = srcpath / Path('index.html')
                if not index in dstpaths:
                    page = PageIndex(self, index)
                    self.pages.append(page)

        log(f'Loaded {len(self.pages)} files')

    def is_ignored(self, filepath, ignore_list=['.', '.*','_', '*~', '#*#']):
        for ignore in ignore_list:
            if any(fnmatch.fnmatch(part, ignore) for part in filepath.parts):
                return True
        return False

    def walk_site(self, basedir, get_dir=False):
        for p in Path(basedir).glob('**/*'):
            if self.is_ignored(p):
                continue
            if (p.is_file() and not get_dir) or (p.is_dir() and get_dir):
                yield p.relative_to(basedir)
        
    def get_siblings(self, dstpath):
        def is_siblings(a, b):
            if a==b:
                return None
            if a.parent==b.parent:
                return True
            if a.parent==b.parent.parent and b.name=='index.html':
                return True
            return False
        return {str(page.dstpath.relative_to(dstpath.parent)) for page in self.pages if is_siblings(dstpath, page.dstpath)}
        
    def get_siblings_not_linked(self, dstpath, hrefs):
        sibs = self.get_siblings(dstpath)

        def href_to_path(href):
            result = urlparse(href)
            if result.netloc:
                return None
            else:
                return result.path
                #return urljoin(str(dstpath), result.path)

        links = {href_to_path(href) for href in hrefs} - {None}
        return list(sibs - links)

    def generate(self, dstdir, indexupdate):
        dstdir = Path(dstdir)
        searchindex_path = 'searchindex.js'
        searchindex_update = False

        makedirs(dstdir)
        current_dst = set(self.walk_site(dstdir))
        next_dst = {Path(searchindex_path)}|{page.dstpath for page in self.pages}
        deleted_dst = current_dst - next_dst

        if len(deleted_dst) > 0:
            log(f'delete {len(deleted_dst)} abandoned files from destination directory')
            for f in deleted_dst:
                log(f'delete {f}')
                remove(dstdir/f)
            searchindex_update = True

        tl = self.template_engine.lastmodified

        def g(page):
            sm = max(page.lastmodified, tl)
            if page.need_update(sm, dstdir):
                #log(f'generating {page.url}...')
                with report_exceptions():
                    page.generate(dstdir)
                return True
            return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            futures = [executor.submit(g, page) for page in self.pages]
            for f in tqdm.tqdm(concurrent.futures.as_completed(futures), total=len(futures), unit='file'):
                pass
            searchindex_update |= any(f.result() for f in futures)

        if indexupdate and searchindex_update:
            log(f'making search index: {searchindex_path}')
            open(dstdir/searchindex_path,'w').write(self.search_index(self.pages))

    def search_index(self, pages):
        import json
        jj = [page.search_json for page in pages if page.search_json]
        return f"var data={json.dumps(jj)}"

def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(prog='sitegen', description='generating html static site from markdown documents')
    parser.add_argument("inputdir", help="input directory")
    parser.add_argument("-o", "--output", dest="outputdir", help="output directory", default="_output")
    parser.add_argument("-t", "--template", dest="templatedir", help="template directory", default=None)
    parser.add_argument("-i", dest="index_update",action='store_true', help="update search index")

    args = parser.parse_args()

    if not args.inputdir:
        parser.error('no input directory')
        return

    site = Site(args.inputdir, args.templatedir)
    site.generate(args.outputdir, args.index_update)
