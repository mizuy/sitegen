# Static site generator

## Directories

    - root
        + _template         : jinja2 template files
        + src               : source markdown files
            + index.md
            + subdir/others.md
            + css/default.css
            + image.jpg
        + _site             : ooutput html files

command:
    sitegen src -o _site

## Environment setup and install

Mac OS X Yosemite, Brew's python

    % python3 --version
    Python 3.5.1
    % which python3
    /usr/local/bin/python3
    % python3 -m venv env
    % source env/bin/activate
    (env) % which python3
    /Users/mizuy/note/sitegen/env/bin/python3
    (env) % which python
    /Users/mizuy/note/sitegen/env/bin/python
    (env) % python --version
    Python 3.5.1
    (env) % python setup.py develop
    (env) % deactivate
    % make

## Pandoc

1. Install Haskell-platform
2. set $PATH to $CABALDIR
3. Install pandoc, pandoc-citeproc

    % cabal install pandoc
    % cabal install pandoc-citeproc

4. test run

    % pandoc -v
    pandoc 1.16.0.2
    
## CSL

Please put your .csl file into ~/.csl/
