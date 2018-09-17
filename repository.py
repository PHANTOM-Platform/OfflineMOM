import requests, os, sys, json, io, configparser
import settings
from settings import ANSI_RED, ANSI_GREEN, ANSI_YELLOW, ANSI_BLUE, ANSI_MAGENTA, ANSI_CYAN, ANSI_END
from epsilon import enforce_trailing_slash


def readCredentials():
	#Read configuration from credentials.txt 
	if not os.path.isfile("credentials.txt"):
		createDefaultCredentials()
		print("credentials.txt does not exist. A default file has been created. This should be edited to contain credentials to access the repository.")
		sys.exit(1)

	config = configparser.ConfigParser()
	try:
		config.read("credentials.txt")
		settings.repository_port = int(config.get('offlinemom', 'repository_port'))
		settings.repository_user = config.get('offlinemom', 'repository_user')
		settings.repository_pass = config.get('offlinemom', 'repository_pass')
	except:
		print("Error whilst parsing credentials.txt. Delete the file and rerun and a default file will be generated.")
		sys.exit(1)


def getAllFilesOfType(type, path):
	"""
	Returns a list of metadata hits of the specified data type at the given path
	"""
	token = authenticate()
	url = "http://localhost:{}/query_metadata?project=\"{}\"&source=\"{}\"&Path=\"{}\"".format(
		settings.repository_port,
		settings.repository_projectname,
		settings.repository_source,
		path
	)
	headers = {'Authorization': "OAuth {}".format(token), 'Content-Type': 'multipart/form-data'}
	rv = requests.get(url, headers=headers)
	if rv.status_code != 200:
		print("Could not download file from the repository. Status code: {}\n{}".format(rv.status_code, rv.text))
		sys.exit(1)
	try:
		reply = json.loads(rv.text)
		if not 'hits' in reply:
			raise json.decoder.JSONDecodeError
	except json.decoder.JSONDecodeError:
		print(ANSI_RED + "Invalid response from Application Manager. Response: {}".format(rv.text))
		sys.exit(1)

	rv = []
	for hit in reply['hits']:
		if hit['data_type'] == type:
			rv.append(hit)
	return rv


def downloadAllFilesOfType(type, path, outputdir):
	"""
	Download all files that match a certain type and save them in the outputdir
	"""
	rv = []
	fls = getAllFilesOfType(type, path)
	for f in fls:
		downloadFile(enforce_trailing_slash(path) + f['filename'], enforce_trailing_slash(outputdir) + f['filename'], True, False)
		rv.append(f['filename'])
	return rv

def authenticate():
	"""
	Authenticate with the repository
	Returns the OAuth token, or exits if authentication fails.
	"""
	repo_token_url = "http://localhost:{}/login?email={}&pw={}".format(
		settings.repository_port, settings.repository_user, settings.repository_pass)

	try:
		headers = {'content-type': 'text/plain'}
		rv = requests.get(repo_token_url, headers=headers)
		if rv.status_code != 200:
			print("Could not log in to repository. Status code: {}\n{}".format(rv.status_code, rv.text))
			sys.exit(1)
		return rv.text
	except requests.exceptions.ConnectionError as e:
		print(ANSI_RED + "Connection refused when connecting to the repository. " + e + ANSI_END)
		sys.exit(1)



def uploadFileContents(filecontents, filename, destpath, data_type, checked, websocket_update=True):
	"""
	Upload the given file contents to the repository as filename at the given path.
	"""
	stringAsFile = io.StringIO(filecontents)
	return upload(stringAsFile, filename, destpath, data_type, checked, websocket_update)



def upload(filetoupload, filename, destpath, data_type, checked, websocket_update):
	"""
	Upload the given file object to the repository. If websocket_update then the
	metadata for the given file is updated, which will notify all subscribers
	"""
	token = authenticate()
	url = "http://localhost:{}/upload?DestFileName={}&Path={}".format(
		settings.repository_port, filename, destpath)

	headers = {'Authorization': "OAuth {}".format(token)}
	uploadjson = "{{\"project\": \"{}\", \"source\": \"{}\", \"data_type\": \"{}\", \"checked\": \"{}\"}}".format(
		settings.repository_projectname,
		settings.repository_source,
		data_type, checked)
	files = {
		'UploadFile': filetoupload,
		'UploadJSON': uploadjson
	}
	rv = requests.post(url, files=files, headers=headers)
	if rv.status_code != 200:
		print("Could not upload file to repository. Status code: {}\n{}".format(rv.status_code, rv.text))
		sys.exit(1)

	if websocket_update:
		websocketUpdate(headers, settings.repository_projectname)



def uploadFile(filetoupload, destpath, data_type, checked, websocket_update=True):
	"""
	Upload the given file to the repository. "filetoupload" must be a path to a valid file.
	"""
	if not os.path.isfile(filetoupload):
		print("{} is not a valid file.".format(filetoupload))
		sys.exit(1)
	filename = os.path.basename(filetoupload)
	return upload(open(filetoupload, 'rb'), filename, destpath, data_type, checked, websocket_update)



def downloadFile(filetodownload, destfile, save=True, verbose=True):
	"""
	Download the requested file from the repository and save it locally
	"""
	token = authenticate()

	url = "http://localhost:{}/download?project=\"{}\"&source=\"{}\"&filepath={}&filename={}".format(
		settings.repository_port,
		settings.repository_projectname,
		settings.repository_source,
		os.path.dirname(filetodownload),
		os.path.basename(filetodownload)
	)
	headers = {'Authorization': "OAuth {}".format(token), 'Content-Type': 'multipart/form-data'}
	rv = requests.get(url, headers=headers)
	if rv.status_code != 200:
		print("Could not download file from the repository. Status code: {}\n{}".format(rv.status_code, rv.text))
		sys.exit(1)

	if save:
		with open(destfile, 'w+') as file:
			file.write(rv.text)
		if verbose: print(ANSI_YELLOW + "\t{}".format(filetodownload) + ANSI_END)
	else:
		return rv.text


def downloadFiles(srcdir, targetdir):
	"""
	Download the entire contents of a given directory in the repository to targetdir
	Hidden files (that begin with a .) are not downloaded.
	"""
	token = authenticate()
	url = "http://localhost:{}/downloadlist?project=\"{}\"&source=\"{}\"&filepath={}".format(
		settings.repository_port,
		settings.repository_projectname,
		settings.repository_source,
		srcdir)
	headers = {'Authorization': "OAuth {}".format(token), 'Content-Type': 'multipart/form-data'}
	rv = requests.get(url, headers=headers)

	if not os.path.isdir(targetdir):
		os.mkdir(targetdir)

	print(ANSI_YELLOW + "Fetching files from repository..." + ANSI_END)

	for fn in rv.text.split('\n'):
		if len(fn) > 0 and os.path.basename(fn)[0] != '.':
			downloadFile(srcdir + "/" + os.path.basename(fn), targetdir + "/" + os.path.basename(fn))


def getMetadata(path, filename):
	"""
	Get the metadata for a specified file.
	Returns a JSON as follows:
	{
		hits: [
			{metadata for file}
			...
		]
	}
	This will usually only be one hit.
	"""
	token = authenticate()
	url = "http://localhost:{}/query_metadata?project=\"{}\"&source=\"{}\"&Path=\"{}\"&filename=\"{}\"".format(
		settings.repository_port,
		settings.repository_projectname,
		settings.repository_source,
		path,
		filename)
	headers = {'Authorization': "OAuth {}".format(token), 'Content-Type': 'multipart/form-data'}
	rv = requests.get(url, headers=headers)
	if rv.status_code != 200:
		print("Could not download metadata from the repository. Status code: {}\n{}".format(rv.status_code, rv.text))
		sys.exit(1)
	try:
		reply = json.loads(rv.text)
		if not 'hits' in reply:
			raise json.decoder.JSONDecodeError
	except json.decoder.JSONDecodeError:
		print(ANSI_RED + "Invalid response from Application Manager. Response: {}".format(rv.text))
		sys.exit(1)
	return reply



def websocketUpdate(headers, project):
	"""
	Ping an update to the Application Manager for the project
	"""
	uploadjson = "{{\"project\": \"{}\", \"source\": \"{}\"}}".format(
		project,
		settings.repository_source)
	url = "http://localhost:{}/update_project_tasks".format(settings.websocket_port)
	rv = requests.post(url, files={'UploadJSON': uploadjson}, headers=headers)
	if rv.status_code != 200 and rv.status_code != 420:
		print("Could not update task. Status code: {}\n{}".format(rv.status_code, rv.text))
		sys.exit(1)



def setMetadata(filename, path, uploadjson, websocket_update=True):
	"""
	Edit the metadata of a file. Unfortunately we have to download and reupload the file to change its
	metadata.
	"""
	filedata = downloadFile(enforce_trailing_slash(path) + filename, None, False)

	token = authenticate()
	url = "http://localhost:{}/upload?DestFileName={}&Path={}".format(settings.repository_port, filename, path)

	headers = {'Authorization': "OAuth {}".format(token)}
	files = {'UploadFile': io.StringIO(filedata), 'UploadJSON': uploadjson}

	rv = requests.post(url, files=files, headers=headers)
	if rv.status_code != 200:
		print("Could not upload file to repository. Status code: {}\n{}".format(rv.status_code, rv.text))
		sys.exit(1)

	if websocket_update:
		websocketUpdate(headers, settings.repository_projectname)


def setAllDeployments(path, checked, verbose=False):
	"""
	Set all deployments of a given project to either checked, or unchecked.
	"""
	rv = getAllFilesOfType("deployment", path)
	for hit in rv:
		if verbose:
			setString = " -> Set to 'yes'" if checked else " -> Set to 'no'"
			print("\t" + hit['filename'] + ": " + hit['checked'] + setString)

		metad = getMetadata(path, hit['filename'])
		metad = metad['hits'][0]

		metad['checked'] = "yes" if checked else "no"
		setMetadata(hit['filename'], path, json.dumps(metad), False)


def uncheckedDeployments(path):
	"""
	Returns the unchecked deployments for the given path
	"""
	rv = getAllFilesOfType("deployment", path)
	r = []
	for hit in rv:
		if not 'checked' in hit or hit['checked'] == "no":
			r.append(hit)
	return r

def listDeployments(path):
	"""
	Pretty print the deployments
	"""
	rv = getAllFilesOfType("deployment", path)
	r = []
	print("All deployments:")
	for hit in rv:
		if(hit['checked'] == 'no'):
			print("\t" + hit['filename'] + ": unchecked")
		else:
			if(hit['checked'] == 'yes'):
				print("\t" + hit['filename'] + ": Passes all checks")
			else:
				print("\t" + hit['filename'] + ": Fails on test '" + hit['checked'] + "'")


def createDefaultCredentials():
	"""
	Create the default credentials file.
	"""
	with open("credentials.txt", 'w') as cfg:
			cfg.write("""
[offlinemom]
repository_port = 8000
repository_user = ausername
repository_pass = 1234
""")



if __name__ == "__main__":
	readCredentials()
	#tmpdir = os.path.join(os.path.dirname(sys.argv[0]), settings.local_temp_folder)
	#downloadAllFilesOfType("componentnetwork", "intecs", tmpdir)
	for i in getAllFilesOfType("deployment", "intecs"):
		print(i)
