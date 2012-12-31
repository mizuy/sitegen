all:
	sitegen example -o _site

install:
	python setup.py develop

clean:
	rm -rf _site
