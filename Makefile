all:
	bin/sitegen example -o _site

bootstrap: bin/buildout

install: bin/buildout
	bin/buildout

bin/buildout:
	python bootstrap.py

clean:
	rm -rf _site

cleanall:
	rm -rf bin
	rm -rf develop-eggs
	rm -rf eggs
	rm -rf parts
	rm -rf .installed.cfg
	rm -rf downloads
	rm -rf lib
	rm -rf *.egg-info

virtualenv:
	virtualenv env --no-site-packages
