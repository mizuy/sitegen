all:
	env/bin/sitegen example -o _output -i

test:
	env/bin/python3 -m unittest discover

clean:
	rm -rf _output
