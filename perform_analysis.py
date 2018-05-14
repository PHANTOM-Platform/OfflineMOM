#!/usr/bin/env python3

import os, sys, glob, subprocess
import settings, repository, epsilon
import websocket
from settings import ANSI_RED, ANSI_GREEN, ANSI_YELLOW, ANSI_BLUE, ANSI_MAGENTA, ANSI_CYAN, ANSI_END
from epsilon import enforce_trailing_slash

from xml.dom import expatbuilder

def main():

	if len(sys.argv) < 2:
		print("Usage: {} [mode] <args for mode>".format(sys.argv[0]))
		print("Valid modes are: upload, download, remote, local, subscribe")
		sys.exit(1)

	if sys.argv[1] == 'upload':
		if len(sys.argv) < 6:
			print("Usage: {} upload <source file> <destpath> <data_type> <checked>".format(sys.argv[0]))
			sys.exit(1)
		repository.uploadFile(sys.argv[2], enforce_trailing_slash(sys.argv[3]), sys.argv[4], sys.argv[5])
		print("Upload complete.")

	elif sys.argv[1] == 'download':
		if len(sys.argv) < 4:
			print("Usage: {} download <file> <outputfile>".format(sys.argv[0]))
			sys.exit(1)
		repository.downloadFile(sys.argv[2], sys.argv[3])
		print("Download complete.")

	elif sys.argv[1] == 'remote':
		if len(sys.argv) < 3:
			print("Usage: {} remote <model name>".format(sys.argv[0]))
			sys.exit(1)
		tmpdir = os.path.join(os.path.dirname(sys.argv[0]), '_tmp')
		repository.downloadFiles(sys.argv[2], tmpdir)
		inputdir = enforce_trailing_slash(tmpdir)
		outputdir = inputdir
		local_mode(inputdir, outputdir, sys.argv[2])

	elif sys.argv[1] == 'local':
		if len(sys.argv) < 4:
			print("Usage: {} local <input model dir> <output dir>".format(sys.argv[0]))
			sys.exit(1)
		inputdir = enforce_trailing_slash(sys.argv[2])
		outputdir = enforce_trailing_slash(sys.argv[3])
		local_mode(inputdir, outputdir, None)

	elif sys.argv[1] == 'subscribe':
		if len(sys.argv) < 3:
			print("Usage: {} subscribe <model name>".format(sys.argv[0]))
			sys.exit(1)
		tmpdir = os.path.join(os.path.dirname(sys.argv[0]), '_tmp')
		inputdir = enforce_trailing_slash(tmpdir)
		outputdir = inputdir

		print(ANSI_GREEN + "Subscribing to project {}. Waiting for updates...".format(sys.argv[2]) + ANSI_END)
		ws = websocket.create_connection("ws://localhost:{}".format(settings.websocket_port))
		req = "{{\"user\":\"{}\" , \"project\":\"{}\"}}".format(settings.repository_user, settings.repository_projectname)
		ws.send(req)
		result = ws.recv()

		#TODO: Parse reply properly

		while True:
			result = ws.recv()
			repository.downloadFiles(sys.argv[2], tmpdir)
			local_mode(inputdir, outputdir, sys.argv[2])
			sys.exit(1)
	else:
		print("Invalid mode.")
		print("Valid modes are: upload, download, remote, local, subscribe")
		sys.exit(1)


def local_mode(inputdir, outputdir, uploadoncedone):
	"""
	Read the model from inputdir, creating all output files into outputdir.
	If uploadoncedone, then the metadata in the repository is updated for eadh
	deployment tested according to the result.
	"""
	verbose = False

	#Find eclipse
	eclipse_install = epsilon.find_eclipse_install(settings.default_eclipse_install)
	print("Using Epsilon install at {}".format(eclipse_install))

	models = find_input_models(inputdir)
	print(ANSI_CYAN + "Found {} deployment{} to test.".format(len(models['de']), '' if len(models['de']) == 1 else 's') + ANSI_END)

	#Prepare output directory
	try:
		os.makedirs(outputdir)
	except OSError as e:
		if e.errno != os.errno.EEXIST:
			raise

	#Now run an analysis for each deployment
	found = None
	for dep in models['de']:
		print(ANSI_CYAN + "Constructing build file {}{} for deployment {}...".format(outputdir, settings.antfile, dep) + ANSI_END)
		epsilon.create_ant_file(settings.antfile, models, dep, inputdir, outputdir)

		#Run the Epsilon installation to create output files in outputdir
		print("Running Epsilon pattern matching and transformations...")
		epsilon.execute_epsilon(eclipse_install, settings.antfile)

		#For each file in outputdir, run a real-time analysis
		result, failure_reason = perform_analyses(outputdir, verbose)
		if result == True:
			print(ANSI_GREEN + "Cannot invalidate deployment {}".format(dep) + ANSI_END)
			found = dep
			summarise_deployment(dep)
			break
		else:
			print(ANSI_RED + "Deployment {} invalidated by test {}.".format(dep, failure_reason) + ANSI_END)
			if uploadoncedone:
				print(ANSI_YELLOW + "Updating metadata of invalidated deployment {} in repository".format(dep) + ANSI_END)
				repository.uploadFile(dep, uploadoncedone, "deployment", failure_reason)

	if found == None:
		print(ANSI_RED + "No valid deployments found." + ANSI_END)

	if uploadoncedone:
		print(ANSI_YELLOW + "Updating metadata of validated deployment {} in repository".format(dep) + ANSI_END)
		repository.uploadFile(dep, uploadoncedone, "deployment", "yes")
		print(ANSI_YELLOW + "Done." + ANSI_END)



def find_input_models(inputdir):
	'''
	Determine input models as:
	{
		'cn': <inputdir>cn*.xml,
		'pd': <inputdir>pd*.xml,
		['de': <inputdir>de*.xml]
	}
	'''
	def deglob_input_models(pattern):
		'''
		Turn the provided pattern into an absolute filename. Also checks that the deglobbing is unique and
		outputs an error and exits if not.
		'''
		results = glob.glob(pattern);
		if(len(results) != 1):
			print("The pattern {} does not refer to a unique file.".format(pattern));
			sys.exit(1)
		else:
			return results[0]

	models = {
		'cn': deglob_input_models("{}cn*.xml".format(inputdir)),
		'pd': deglob_input_models("{}pd*.xml".format(inputdir))
	}

	models['de'] = glob.glob("{}de*.xml".format(inputdir))

	if len(models['de']) < 1:
		print("Cannot find deployments in directory {}".format(inputdir))
		sys.exit(1)
	return models


def perform_analyses(outputdir, verbose):
	'''
	Run all the analysis files. Returns (True, "") if all pass, or (False, "analysis") if any fail,
	where "analysis" is the name of the analysis which caused the failure.
	'''
	outputs = glob.glob('{}/*.txt'.format(outputdir))
	passed = True
	failure_reason = ""

	#Determine max length of maching filenames
	maxlen = 0
	for output in outputs:
		l = len(os.path.splitext(os.path.basename(output))[0])
		if l > maxlen: maxlen = l

	#Now analyse
	for output in outputs:
		basename = os.path.splitext(os.path.basename(output))[0]
		args = None
		with open(output, 'r') as f:
			#Get first non-blank line, starting --, then @@, then the tool name
			data = f.readlines()
			for i in range(len(data)):
				if data[i].strip() != '':
					line = data[i].strip()
					if line[:2] == '--':
						line = line[2:].strip()
						if line[:2] == '@@':
							line = line[2:].strip()
							if len(line.split()) >= 2:
								args = line.split()

		if args == None:
			print("File {} is not a valid output format. Skipped.".format(output))
		else:
			print("Analysing file {}...{}".format(basename, " " * ((maxlen + 1) - len(basename))), end="")
			if args[0] == 'mast':
				cmd = ["mast_analysis", "{}".format(" ".join(args[1:])), output]
				result = subprocess.run(cmd, stdout=subprocess.PIPE)
				out = str(result.stdout,'utf-8')
				if verbose:
					print(out)
				if result.returncode != 0:
					print("Error code {} running MAST on file: {}\n{}\nSkipping file.".format(result.returncode, output, out))
				else:
					if out.split()[-1] == "DONE":
						print(ANSI_GREEN + "Schedulability check passed." + ANSI_END)
					else:
						print(ANSI_RED + "System unschedulable!" + ANSI_END)
						passed = False
						failure_reason = basename
			else:
				print("File {} requests an unknown analysis tool: {}. Skipped.".format(output, args[0]))
	return (passed, failure_reason)


def summarise_deployment(filename):
	print(ANSI_MAGENTA + "Mappings:")
	doc = expatbuilder.parse(filename, False)
	mappings = doc.getElementsByTagName('mapping')
	for m in mappings:
		comp = m.getElementsByTagName('component')
		proc = m.getElementsByTagName('processor')
		if len(comp) == 1 and len(proc) == 1:
			print("\t{} -> {}".format(comp[0].getAttribute('name'), proc[0].getAttribute('name')))
	print(ANSI_END)


if __name__ == "__main__":
	main()
