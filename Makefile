all:
	env/bin/sitegen example -o _site

clean:
	rm -rf _site

virtualenv:
	virtualenv-2.7 env --no-site-packages
