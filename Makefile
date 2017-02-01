all:
	env/bin/sitegen example -o _output -i

clean:
	rm -rf _output
