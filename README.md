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
    cd root
    sitegen src -o _site


## Environment setup and install

Mac OS X Lion, Brew's python.

    % python --version
    Python 2.7.3
    % which python
    /usr/local/bin/python
    % sudo easy_install virtualenv
    % virtualenv --version
    1.8.2
    % which virtualenv
    /usr/local/share/python/virtualenv
    % virtualenv env
    New python executable in env/bin/python
    Installing setuptools............done.
    Installing pip...............done.
    % source env/bin/activate
    (env)% python setup.py install
    ...
    Finished processing dependencies for sitegen==1.0.0
    (env)% sitegen example -o _site

for fixed Markdown,
    
    % pip install git+git://github.com/mizuy/Python-Markdown.git@fix_deflist#egg=Markdown
