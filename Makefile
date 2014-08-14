all:
	env/bin/sitegen example -o _output

clean:
	rm -rf _output
