all: venv
	venv/bin/sitegen example -o _output -i

test: venv
	venv/bin/python3 -m unittest discover

clean:
	rm -rf _output

setup: venv

venv:
	python3 -m venv venv
	venv/bin/pip3 install --editable .
