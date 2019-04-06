"""
Utility functions for running ANT builds in Eclipse
"""
import os, sys, glob, subprocess

def find_eclipse_install(default_path):
	'''
	Search for an Eclipse-Epsilon install to use for the transformations.
	If the ECLIPSE environment variable is set this is used, otherwise
	default_eclipse_install is seached.
	'''
	if 'ECLIPSE' in os.environ:
		ei = os.environ['ECLIPSE']
	else:
		ei = default_path

	if ei.find('*') > -1:
		results = glob.glob(ei)
		if(len(results) > 1):
			print("Multiple results for pattern {} when searching for Eclipse install".format(ei))
			sys.exit(1)
		if(len(results) < 1):
			print("Path {} does not point to an Eclipse install.".format(ei))
			print("Provide the path to Eclipse via the ECLIPSE environment variable.")
			sys.exit(1)
		ei = results[0]
	ei = enforce_trailing_slash(ei)

	return ei


def create_ant_file(path, models, dep, inputdir, outputdir):
	'''
	Generate the ANT build file which runs the Epsilon transformations as settings.antfile.
	'''
	pattern_models = []

	base = enforce_trailing_slash(os.path.dirname(os.path.realpath(__file__)))

	with open(os.path.join(outputdir, path), 'w+') as f:
		f.write('''
<!-- Autogenerated build file from {} -->

<project default="main">
	<target name="main">
		<epsilon.emf.loadXmlModel name="CN" modelfile="{}"
			xsdfile="{}models/component_network.xsd" read="true" store="false"/>

		<epsilon.emf.loadXmlModel name="DE" modelfile="{}"
			xsdfile="{}models/deployment.xsd" read="true" store="false"/>

		<epsilon.emf.loadXmlModel name="PD" modelfile="{}"
			xsdfile="{}models/platform_description.xsd" read="true" store="false"/>\n'''.format(
				sys.argv[0],
				models['cn'], base,
				dep, base,
				models['pd'], base)
			)

		#Pattern matches
		transf = glob.glob(base + 'transformations/*.epl')
		for tr in transf:
			basename = os.path.splitext(os.path.basename(tr))[0]
			f.write('''
		<epsilon.epl src="{}" exportAs="{}">
			<model ref="CN"/>
			<model ref="PD"/>
			<model ref="DE"/>
		</epsilon.epl>\n'''.format(tr, basename))
			pattern_models.append(basename)

		#Test outputs
		transf = glob.glob('transformations/*.egl')
		for tr in transf:
			basename = os.path.splitext(os.path.basename(tr))[0]
			f.write('\n\t\t<epsilon.egl src="{}{}" target="{}.txt">\n'.format(base, tr, basename))

			for p in pattern_models:
				f.write('\t\t\t<model ref="{}"/>\n'.format(p))

			f.write('''\t\t\t<model ref="CN"/>\n\t\t\t<model ref="PD"/>\n\t\t\t<model ref="DE"/>\n\t\t</epsilon.egl>\n''')
		f.write('\t</target>\n</project>\n')


def execute_epsilon(eclipse, antfile):
	'''
	Run Epsilon using the Eclipse antRunner
	'''
	results = glob.glob("{}plugins/org.eclipse.equinox.launcher_*.jar".format(eclipse))
	if(len(results) != 1):
		print("Cannot find the org.eclipse.equinox.launcher_*.jar in the Eclipse install \"{}\"".format(eclipse))
		sys.exit(1)
	jarfile = results[0]
	cmd = "java -jar {} -application org.eclipse.ant.core.antRunner -buildfile {}".format(jarfile, antfile)
	#os.system(cmd)
	try:
		subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
	except subprocess.CalledProcessError as e:
		print("Error whilst executing Epsilon build.")
		print("Command: {}".format(cmd))
		print(e)
		print(e.output)


def enforce_trailing_slash(path):
	'''
	Returns path, with the '/' character appended if it did not already end with it
	'''
	if path[-1] != '/':
		return path + '/'
	else:
		return path


def which(program):
	def is_exe(fpath):
		return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

	fpath, _ = os.path.split(program)
	if fpath:
		if is_exe(program):
			return program
	else:
		for path in os.environ["PATH"].split(os.pathsep):
			exe_file = os.path.join(path, program)
			if is_exe(exe_file):
				return exe_file
	return None
