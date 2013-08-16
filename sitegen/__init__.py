# -*- coding: utf-8 -*-

# Static Site Generator powered by markdown and jinja2
# Copyright (c) 2012 MIZUGUCHI Yasuhiko
# based on http://obraz.pirx.ru/

import sys, traceback
import os
import re
import shutil
import fnmatch
from contextlib import contextmanager
import errno
from glob import glob
import yaml
import subprocess
from jinja2 import Environment, FileSystemLoader
from jinja2.exceptions import TemplateSyntaxError

PAGE_ENCODING = 'UTF-8'
DEFAULT_TEMPLATE = 'default.j2.html'
TEMPLATE_DIR = '_templates'
IGNORE_LIST = ['.', '_', '*~']

class File(object):
    def __init__(self, basedir, path):
        self.basedir = basedir
        self.path = path
        self.filename = os.path.join(basedir, path)
        self.basename = os.path.basename(self.filename)
        self.dirname = os.path.dirname(self.filename)
        _ , self.suffix = os.path.splitext(self.basename)

    def exists(self):
        return os.path.exists(self.filename)

    def mtime(self):
        return os.path.getmtime(self.filename)

    def open(self):
        return open(self.filename, 'rb')

    def makedirs(self):
        try:
            os.makedirs(self.dirname)
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass

    def remove(self):
        try:
            os.remove(self.filename)
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass

def load_metadata(source):
    """
    split file contents into metadata and remaining contents

    metadata is yaml formatted data at head tagged by two '---' lines

        ---
        yaml formatted metadata
        ---
        contents
    """
    SPLIT = r'^---+\s*'
    metadata = {}
    line_offset = 0
    content = source

    i = 0
    lines = source.splitlines()

    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        if re.match(SPLIT, lines[i]):
            i += 1
            yaml_start = i
            while i < len(lines):
                if re.match(SPLIT, lines[i]):
                    yaml_end = i
                    i += 1
                    break
                i += 1
            metadata = yaml.load('\n'.join(lines[yaml_start:yaml_end])) or metadata
            line_offset = yaml_end+1
            content = '\n'.join(lines[line_offset:])
        else:
            break
    return metadata, line_offset, content

def changeext(path, ext):
    base, suffix = os.path.splitext(path)
    return base+'.'+ext

def remove(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass

def makedirs(directory):
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass

def log(message):
    sys.stderr.write('{0}\n'.format(message))
    sys.stderr.flush()

@contextmanager
def report_exceptions():
    import traceback
    import pdb
    import sys
    try:
        yield
    except Exception:
        e, m, tb = sys.exc_info()
        print('exception traceback:'.ljust( 80, '=' ))
        for tbi in traceback.format_tb( tb ):
            print(tbi)
        print('  %s' % str( m ))
        print(''.rjust( 80, '=' ))
        pdb.post_mortem(tb)
        
def is_ignored(filename, ignore_list):
    for ignore in ignore_list:
        if any( fnmatch.fnmatch(part, ignore) for part in filename.split(os.path.sep)):
            return False
    return True

def all_files(basedir, ignore_list=None):
    for path, dirs, files in os.walk(basedir):
        for file in files:
            abspath = os.path.join(path, file)
            relpath = os.path.relpath(abspath, basedir)

            if ignore_list and not is_ignored(relpath, ignore_list):
                continue

            yield abspath, relpath


class TemplateEngine(object):
    def __init__(self, templatedir):
        self.templatedir = templatedir
        self.env = Environment(loader=FileSystemLoader(templatedir))

    def render(self, template, context):
        try:
            t = self.env.get_template(template)
            # env.from_string()
            return t.render(**context)
        except TemplateSyntaxError as e:
            raise Exception("{0}:{1}: {2}, {3}".format(e.filename, e.lineno, e.name, e.message))

    def lastmodified(self):
        "return if one of the template is updated."
        return max(os.path.getmtime(abspath) for abspath, relpath in all_files(self.templatedir, IGNORE_LIST))

template_engine = TemplateEngine(TEMPLATE_DIR)

class Pandoc(object):
    # based on https://github.com/bebraw/pypandoc/blob/master/pypandoc/pypandoc.py
    def __init__(self):
        self.src_fmts, self.dst_fmts = self.get_formats()
        self.templates = os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))

    def convert(self, src, src_format, dst_format, extra_args=[]):
        if src_format not in self.src_fmts:
            raise RuntimeError('Invalid src format! Expected one of these: ' + ', '.join(self.src_fmts))
        if dst_format not in self.dst_fmts:
            raise RuntimeError('Invalid dst format! Expected one of these: ' + ', '.join(self.dst_fmts))

        args = ['pandoc', '--from='+src_format, '--to='+dst_format]
        args.extend(extra_args)
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        data,error = p.communicate(src)
        return data, error

    def get_formats(self):
        '''
        Dynamic preprocessor for Pandoc formats.
        Return 2 lists. "from_formats" and "to_formats".
        ''' 
        p = subprocess.Popen(['pandoc', '-h'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        help_text = p.communicate()[0].splitlines(False)
        txt = ' '.join(help_text[1:help_text.index('Options:')])

        aux = txt.split('Output formats: ')
        in_ = aux[0].split('Input formats: ')[1].split(',')
        out = aux[1].split(',')

        return [f.strip() for f in in_], [f.strip() for f in out]

pandoc = Pandoc()
        
class Site(object):
    def __init__(self, basedir):
        self.basedir = basedir

        # todo load .ignore file
        self.pages = {}

        log('Loading source files...')

        for abspath, relpath in all_files(basedir, IGNORE_LIST):
            srcfile = File(basedir, relpath)

            with report_exceptions():
                if srcfile.suffix in ['.md', '.markdown']:
                    page = PageMarkdown(srcfile)
                else:
                    page = PageFile(srcfile)
                self.pages[page.dstpath] = page

        log('Loaded {0} files'.format(len(self.pages)))

    def __iter__(self):
        for p in self.pages.values():
            yield p

    def get_page(self, path):
        return self.pages.get(path)

class PageBase(object):
    def __init__(self, srcfile, dstpath=None):
        self.srcfile = srcfile
        self.dstpath = dstpath or srcfile.path
        self.url = os.path.sep + self.dstpath

    def dependencies(self):
        """
        return path of all templates and includes which are refered by this page directly or indirectly
        """
        return []

    def write(self, filename):
        raise NotImplemented()

    def dstfile(self, dstbasedir):
        return File(dstbasedir, self.dstpath)

    def generate(self, dstfile):
        """
        public wrapper function.
        """
        dstfile.makedirs()
        self.write(dstfile.filename)

class PageFile(PageBase):
    def __init__(self, srcfile):
        super(PageFile, self).__init__(srcfile)

    def write(self, filename):
        shutil.copy(self.srcfile.filename, filename)

class PageTemplated(PageBase):
    def __init__(self, srcfile):
        super(PageTemplated, self).__init__(srcfile, changeext(srcfile.path, 'html'))
        self.depth = len(self.url.strip('/').split('/')) - 1
        self.root = '/'.join(['..'] * (self.depth)) if self.depth>0 else '.'

    def render_template(self, contents, context={}):
        context['contents'] = contents
        context['url'] = self.url
        context['root'] = self.root
        context['path'] = self.dstpath
        context['mtime'] = self.srcfile.mtime()

        template = context.get('template') or DEFAULT_TEMPLATE
        return template_engine.render(template, context)

    def render(self):
        contents = self.srcfile.open().read().decode(PAGE_ENCODING)
        context = {}
        return self.render_template(contents, context)

    def write(self, filename):
        with open(filename, 'wb') as f:
            f.write(self.render().encode(PAGE_ENCODING))

class PageMarkdown(PageTemplated):
    def __init__(self, srcfile):
        super(PageMarkdown, self).__init__(srcfile)

    def render(self):
        with report_exceptions():
            with open(self.srcfile.filename, 'r') as f:
                # TODO(future): next version of pandoc has their own yaml metadata extention.

                source = f.read()
                metadata, offset, content = load_metadata(source)

                extra_args=['--mathjax',
                            '--data-dir='+pandoc.templates,
                            '--template=_templates/vars',
                            '--toc']
                if 'bibliography' in metadata:
                    bib = os.path.abspath(os.path.join(self.srcfile.dirname, metadata['bibliography']))
                    extra_args.append('--bibliography='+bib)
                if 'csl' in metadata:
                    csl = metadata['csl']
                    extra_args.append('--csl='+csl)

                s,error = pandoc.convert(content, 'markdown', 'html5', extra_args)
                if not s.strip():
                    title = 'ERROR'
                    toc = ''
                    body = '<pre>{}</pre>'.format(error)
                else:
                    title, toc, body = s.decode(PAGE_ENCODING).split('<><><><>')

                    title = title.strip()
                    toc = toc.strip()
                    body = body.replace('[TOC]', toc)

                if title:
                    metadata['title'] = title
                metadata['toc'] = toc
                metadata['offset'] = offset
                metadata['source'] = source.decode(PAGE_ENCODING)

                return self.render_template(body, metadata)

class SiteGenerator(object):
    def __init__(self, srcdir, dstdir):
        #self.dependencies = []
        self.dstdir = dstdir
        self.site = Site(srcdir)

    def generate(self):
        makedirs(self.dstdir)
        current_dst = set(abspath for abspath, relpath in all_files(self.dstdir))
        next_dst = set(page.dstfile(self.dstdir).filename for page in self.site)

        deleted_dst = current_dst - next_dst
        log('delete {0} abandoned files from destination directory'.format(len(deleted_dst)))
        for f in deleted_dst:
            log('delete {0}'.format(f))
            remove(f)

        tl = template_engine.lastmodified()

        for page in self.site:
            src = page.srcfile
            dst = page.dstfile(self.dstdir)

            # TODO: more accurate dependency graph.
            if dst.exists() and dst.mtime() > max(src.mtime(), tl):
                continue

            try:
                log('generating {0}...'.format(page.url))
                page.generate(dst)
            except:
                dst.remove()
                log('error while generating {0}'.format(page.url))
                print_exception_traceback()

def print_exception_traceback():
    info = sys.exc_info()
    tbinfo = traceback.format_tb( info[2] )             
    print 'exception traceback:'.ljust( 80, '=' )
    for tbi in tbinfo:
        print tbi
    print '  %s' % str( info[1] )
    print ''.rjust( 80, '=' )


def main():
    import sys
    from argparse import ArgumentParser
    parser = ArgumentParser(prog='makesite', description='generating html static site from markdown documents')
    parser.add_argument("inputdir", help="input directory")
    parser.add_argument("-o", "--output", dest="outputdir", help="output directory")
    
    args = parser.parse_args()

    inputdir = args.inputdir
    outputdir = args.outputdir

    if not inputdir:
        parser.error('no input directory')
        return

    if not outputdir:
        outputdir = '_site'

    sg = SiteGenerator(inputdir, outputdir)
    sg.generate()

if __name__ == '__main__':
    main()
