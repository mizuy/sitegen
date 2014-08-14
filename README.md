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

Mac OS X Lion, Brew's python.

    % python3 --version
    Python 3.4.1
    % which python3
    /usr/local/bin/python3
    % python3 -m ensurepip
    Ignoring indexes: https://pypi.python.org/simple/
    Requirement already satisfied (use --upgrade to upgrade): setuptools in /usr/local/lib/python3.4/site-packages
    Requirement already satisfied (use --upgrade to upgrade): pip in /usr/local/lib/python3.4/site-packages
    Cleaning up...
    % pyvenv-3.4 env
    % source env/bin/activate
    (env)% python setup.py install
    (env)% deactivate
    % make

## Pandoc

1. Install Haskell-platform
2. set $PATH to $CABALDIR
3. Install pandoc, pandoc-citeproc

    cabal install pandoc
    cabal install pandoc-citeproc

4. test run

    pandoc -v
    
## CSL

Please put your .csl file into ~/.csl/
