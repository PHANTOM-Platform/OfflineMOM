#!/usr/bin/env python3

"""
Main entry point for the PHANTOM Offline MOM. For documentation see README.md.
"""

import os, sys, glob, subprocess, json, shutil, errno
import settings, repository, epsilon
import websocket
from settings import ANSI_RED, ANSI_GREEN, ANSI_YELLOW, ANSI_BLUE, ANSI_MAGENTA, ANSI_CYAN, ANSI_END
from epsilon import enforce_trailing_slash

from xml.dom import expatbuilder

def main():
	repository.readCredentials()

	#Check that we can find the MAST executable. It can be set using $MASTEXE
	if 'MASTEXE' in os.environ: 
		settings.mast_executable = os.environ['MASTEXE']
	if epsilon.which(settings.mast_executable) == None:
		print("{} does not point to the `mast_analysis` executable. Set $MASTEXE.".format(settings.mast_executable))
		sys.exit(1)

	#Temporary directory can be set by $OFFLINEMOMTEMP or the current directory is used
	if 'OFFLINEMOMTEMP' in os.environ:
		tempdir = enforce_trailing_slash(os.environ['OFFLINEMOMTEMP'])
	else:
		tempdir = enforce_trailing_slash(os.path.join(
			os.path.dirname(os.path.realpath(__file__)), 
			settings.local_temp_folder))
	
	#Empty the temp dir
	if os.path.isdir(tempdir):
		shutil.rmtree(tempdir)
	os.mkdir(tempdir)

	if len(sys.argv) < 2:
		print("Usage: {} [mode] <args for mode>".format(sys.argv[0]))
		print("Valid modes are: upload, download, remote, local, subscribe")
		sys.exit(1)

	if sys.argv[1] == 'upload':
		"""
		Upload a file to the Repository.
		Arguments:
			[2] - path to the file to upload
			[3] - path in the repository to upload to (including filename)
			[4] - what to set the "data_type" metadata to
			[5] - what to set the "checked" metadata to
		"""
		if len(sys.argv) < 6:
			print("Usage: {} upload <source file> <destpath> <data_type> <checked>".format(sys.argv[0]))
			sys.exit(1)
		repository.uploadFile(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
		print("Upload complete.")

	elif sys.argv[1] == 'download':
		"""
		Download a file from the Repository.
		Arguments:
			[2] - path to the file to download (including filename)
			[3] - local path (including filename) to save the file as
		"""
		if len(sys.argv) < 4:
			print("Usage: {} download <file> <outputfile>".format(sys.argv[0]))
			sys.exit(1)
		repository.downloadFile(sys.argv[2], sys.argv[3])
		print("Download complete.")

	elif sys.argv[1] == 'remote':
		"""
		Download all files from the repository found in a given path, then perform analysis on it.
		Arguments:
			[2] - repository path to the file to download (including filename)
		"""
		if len(sys.argv) < 3:
			print("Usage: {} remote <project name>".format(sys.argv[0]))
			sys.exit(1)
		repository.downloadFiles(sys.argv[1], tempdir)
		local_mode(tempdir, tempdir, False, False)

	elif sys.argv[1] == 'uncheck':
		"""
		Set the "checked" metadata for all deployments to "unchecked"
		Arguments:
			[2] - repository path to the deployments
		"""
		if len(sys.argv) < 3:
			print("Usage: {} uncheck <project name>".format(sys.argv[0]))
			sys.exit(1)
		print("Setting all deployments in {} to 'unchecked'".format(sys.argv[2]))
		repository.setAllDeployments(sys.argv[2], False, True)

	elif sys.argv[1] == 'local':
		"""
		Analyse a folder of XML files.
		Arguments:
			[3] - path to folder to analyse
		"""
		if len(sys.argv) < 3:
			print("Usage: {} local <input model dir>".format(sys.argv[0]))
			sys.exit(1)
		inputdir = enforce_trailing_slash(sys.argv[2])
		local_mode(inputdir, inputdir, False, True)

	elif sys.argv[1] == 'subscribe':
		"""
		Subscribe to a project using the Application Manager. Waits for updates to the project and
		analyses any unchecked deployments continually.
		Arguments:
			[2] - project name to subscribe to
		"""
		if len(sys.argv) < 3:
			print("Usage: {} subscribe <model name>".format(sys.argv[0]))
			sys.exit(1)

		subscribe(sys.argv[2], tempdir)
			
	elif sys.argv[1] == 'verify':
		"""
		Check we can see the other dependencies. (Note MAST is already checked).
		"""
		eclipse_install = epsilon.find_eclipse_install(settings.default_eclipse_install)
		results = glob.glob("{}plugins/org.eclipse.equinox.launcher_*.jar".format(eclipse_install))
		if(len(results) != 1):
			print("Cannot find the org.eclipse.equinox.launcher_*.jar in the Eclipse install at \"{}\"".format(eclipse_install))
			sys.exit(1)

		repository.authenticate()

		print("Dependencies found.")
		sys.exit(0)

	elif sys.argv[1] == 'listdeps':
		"""
		List all deployments in the given path.
		"""
		repository.listDeployments(sys.argv[2])

	else:
		print("Invalid mode.")
		print("Valid modes are: upload, download, remote, local, subscribe, uncheck")
		sys.exit(1)


def local_mode(inputdir, outputdir, uploadoncedone, localmode, models = None):
	"""
	Read the model from inputdir, creating all output files into outputdir.
	If uploadoncedone, then the metadata in the repository is updated for each
	deployment tested according to the result.

	models should be a dictionary of the form:
	{ 'cn': 'filename.xml', 'pd': 'filename.xml', ['de': 'filename.xml'] }
	Otherwise the input directory will be searched for files that start with 'cn', 'pd', and 'de' respectively and will
	fail if they are not found, and apart from deployments, unique.
	
	If multiple deployments are found/specified they are all tested.

	inputdir and outputdir can be the same location.
	"""
	verbose = False

	#Find Epsilon
	eclipse_install = epsilon.find_eclipse_install(settings.default_eclipse_install)
	print("Using Epsilon install at {}".format(eclipse_install))

	if models == None:
		models = find_input_models(inputdir)

	if len(models['de']) > 1:
		print(ANSI_CYAN + "Found {} deployment{} to test.".format(len(models['de']), '' if len(models['de']) == 1 else 's') + ANSI_END)
	else:
		print(ANSI_CYAN + "Testing model: {} {} {}".format(
			os.path.basename(models['cn']),
			os.path.basename(models['pd']),
			os.path.basename(models['de'][0])
		) + ANSI_END)

	#Prepare output directory
	try:
		os.makedirs(outputdir)
	except OSError as e:
		if e.errno != errno.EEXIST:
			raise

	#Now run an analysis for each deployment
	found = None
	for dep in models['de']:
		print(ANSI_CYAN + "Constructing build file {} for deployment {}...".format(settings.antfile, os.path.basename(dep)) + ANSI_END)
		epsilon.create_ant_file(settings.antfile, models, dep, inputdir, outputdir)

		#Run the Epsilon installation to create output files in outputdir
		print("Running Epsilon pattern matching and transformations...")
		epsilon.execute_epsilon(eclipse_install, os.path.join(outputdir, settings.antfile))

		#For each file in outputdir, run a real-time analysis
		result, failure_reason, output = perform_analyses(outputdir, verbose)
		if result == True:
			print(ANSI_GREEN + "Cannot invalidate deployment {}".format(dep) + ANSI_END)
			found = dep
			summarise_deployment(dep)
			if uploadoncedone:
				print(ANSI_YELLOW + "Updating metadata of validated deployment {} in repository".format(dep) + ANSI_END)
				repository.uploadFile(dep, uploadoncedone, "deployment", "yes")
				print(ANSI_YELLOW + "Done." + ANSI_END)
			if localmode:
				updateLocalJSON(os.path.join(outputdir, os.path.splitext(dep)[0] + ".json"), "yes")

		else:
			print(ANSI_RED + "Deployment {} invalidated by test {}.".format(dep, failure_reason) + ANSI_END)
			if uploadoncedone:
				print(ANSI_YELLOW + "Updating metadata of invalidated deployment {} in repository".format(dep) + ANSI_END)
				repository.uploadFile(dep, uploadoncedone, "deployment", failure_reason)

				print(ANSI_YELLOW + failure_reason + ANSI_END)
				repository.uploadFileContents(output, failure_reason, uploadoncedone, "analysis_output", "", False)
			if localmode:
				updateLocalJSON(os.path.join(outputdir, os.path.splitext(dep)[0] + ".json"), failure_reason)

	if found == None:
		print(ANSI_RED + "No valid deployments found." + ANSI_END)


def updateLocalJSON(deploymentName, checkedvalue):
	if os.path.exists(deploymentName):
		with open(deploymentName) as f:
			data = json.load(f)
			if not 'MOM' in data and 'checked' in data['MOM']:
				print("Metadata json for deployment is not in the correct format.")
				return
			data['MOM']['checked'] = checkedvalue
		
		with open(deploymentName, 'w') as outf:
			json.dump(data, outf)
	else:
		print("No metadata json for deployment found. Metadata not updated.")


def subscribe(project, tempdir):
	"""
	Subscribe to a project using the Application Manager. Waits for updates to the project and
	analyses any unchecked deployments continually.
	"""
	def checkForUDs(project, tempdir):
		import time
		time.sleep(1) #We currently seem to have to give the metadata a little time to update inside the repository
		uds = repository.uncheckedDeployments(project)
		if(len(uds) > 0):
			print(ANSI_GREEN + "Project has {} unchecked deployment{}...".format(len(uds), "s" if len(uds) > 1 else "") + ANSI_END)
			print(ANSI_GREEN + "Checking {}...".format(uds[0]['filename']) + ANSI_END)

			#Download the files
			models = {} #This will tell local_mode which XML files are of which type
			cns = repository.downloadAllFilesOfType("componentnetwork", project, tempdir)
			if len(cns) != 1:
				print(ANSI_RED + "Multiple files of type 'componentnetwork' found at path {} when only one was expected.".format(project) + ANSI_END)
				sys.exit(1)
			models['cn'] = os.path.join(tempdir, cns[0])
			pds = repository.downloadAllFilesOfType("platformdescription", project, tempdir)
			if len(pds) != 1:
				print(ANSI_RED + "Multiple files of type 'platformdescription' found at path {} when only one was expected.".format(project) + ANSI_END)
				sys.exit(1)
			models['pd'] = os.path.join(tempdir, pds[0])
			models['de'] = [os.path.join(tempdir, uds[0]['filename'])]

			repository.downloadFile(
				os.path.join(project, uds[0]['filename']),
				os.path.join(tempdir, uds[0]['filename']),
				True, False)

			local_mode(tempdir, tempdir, project, False, models=models)

	print(ANSI_GREEN + "Subscribing to project {}. Waiting for updates...".format(project) + ANSI_END)

	ws = websocket.create_connection("ws://{}:{}".format(settings.websocket_host, settings.websocket_port))
	req = "{{\"user\":\"{}\" , \"project\":\"{}\"}}".format(settings.repository_user, settings.repository_projectname)
	ws.send(req)
	result = ws.recv()
	try:
		reply = json.loads(result)
		if not 'suscribed_to_project' in reply:
			raise json.decoder.JSONDecodeError
	except json.decoder.JSONDecodeError:
		print(ANSI_RED + "Invalid response from Application Manager. Response: {}".format(result))
		sys.exit(1)

	#Run a first check regardless of response from the websocket
	checkForUDs(project, tempdir)

	while True:
		try:
			result = ws.recv()
			reply = json.loads(result)
			if 'project' in reply and reply['project'] == settings.repository_projectname:
				checkForUDs(project, tempdir)
		except json.decoder.JSONDecodeError:
			print(ANSI_RED + "Invalid response from Application Manager. Response: {}".format(result))
			sys.exit(1)


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
		Turn the provided pattern into an absolute filename. Also checks that the de-globbing is unique and
		outputs an error and exits if not.
		'''
		results = glob.glob(pattern)
		if(len(results) != 1):
			print("The pattern {} does not refer to a unique file.".format(pattern))
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
	Run all the analysis files. Returns (True, "", output) if all pass, or (False, "analysis", output) if any fail,
	where "analysis" is the name of the analysis which caused the failure and output is the full output from the tool.
	'''
	outputs = glob.glob('{}/*.txt'.format(outputdir))
	passed = True
	failure_reason = ""
	failure_contents = ""

	#Determine max length of matching filenames
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
				cmd = [settings.mast_executable, "{}".format(" ".join(args[1:])), output]
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
						failure_contents = out
			else:
				print("File {} requests an unknown analysis tool: {}. Skipped.".format(output, args[0]))
	return (passed, failure_reason, failure_contents)


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
