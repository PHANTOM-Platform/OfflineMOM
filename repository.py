import requests, os, sys
import settings
from settings import ANSI_RED, ANSI_GREEN, ANSI_YELLOW, ANSI_BLUE, ANSI_MAGENTA, ANSI_CYAN, ANSI_END


repo_token_url = "http://localhost:{}/login?email={}&pw={}".format(
	settings.repository_port, settings.repository_user, settings.repository_pass)



def getAllFilesOfType(type, path):
	"""
	TODO: Cannot make this work yet
	"""
	token = authenticate()
	url = "http://localhost:{}/query_metadata?project=\"{}\"&source=\"{}\"&filepath=\"{}\"&filename=\"{}\"".format(
		settings.repository_port,
		settings.repository_projectname,
		settings.repository_source,
		"",
		""
	)
	headers = {'Authorization': "OAuth {}".format(token), 'Content-Type': 'multipart/form-data'}
	rv = requests.get(url, headers=headers)
	if rv.status_code != 200:
		print("Could not download file from the repository. Status code: {}\n{}".format(rv.status_code, rv.text))
		sys.exit(1)
	print(rv.text)



def authenticate():
	"""
	Authenticate with the repository
	Returns the OAuth token, or exits if authentication fails.
	"""
	try:
		headers = {'content-type': 'text/plain'}
		rv = requests.get(repo_token_url, headers=headers)
		if rv.status_code != 200:
			print("Could not log in to repository. Status code: {}\n{}".format(rv.status_code, rv.text))
			sys.exit(1)
		return rv.text
	except requests.exceptions.ConnectionError as e:
		print(ANSI_RED + "Connection refused when connecting to the repository." + ANSI_END)
		sys.exit(1)


def uploadFile(filetoupload, destpath, data_type, checked, websocket_update=True):
	"""
	Upload the given file to the repository. If websocket_update then the
	metadata for the given file is updated, which will notify all subscribers
	"""
	token = authenticate()
	if not os.path.isfile(filetoupload):
		print("{} is not a valid file.".format(filetoupload))
		sys.exit(1)
	url = "http://localhost:{}/upload?DestFileName={}&Path={}".format(
		settings.repository_port,
		os.path.basename(filetoupload),
		destpath
	)

	headers = {'Authorization': "OAuth {}".format(token)}
	uploadjson = "{{\"project\": \"{}\", \"source\": \"{}\", \"data_type\": \"{}\", \"checked\": \"{}\"}}".format(
		settings.repository_projectname,
		settings.repository_source,
		data_type, checked)
	files = {
		'UploadFile': open(filetoupload, 'rb'),
		'UploadJSON': uploadjson
	}
	rv = requests.post(url, files=files, headers=headers)
	if rv.status_code != 200:
		print("Could not upload file to repository. Status code: {}\n{}".format(rv.status_code, rv.text))
		sys.exit(1)

	if websocket_update:
		uploadjson = "{{\"project\": \"{}\", \"source\": \"{}\"}}".format(
			settings.repository_projectname,
			settings.repository_source)
		url = "http://localhost:{}/update_project_tasks".format(settings.websocket_port)
		rv = requests.post(url, files={'UploadJSON': uploadjson}, headers=headers)
		if rv.status_code != 200:
			print("Could not update task. Status code: {}\n{}".format(rv.status_code, rv.text))
			sys.exit(1)


def downloadFile(filetodownload, destfile):
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

	with open(destfile, 'w') as file:
		file.write(rv.text)

	print(ANSI_YELLOW + "\t{}".format(filetodownload) + ANSI_END)


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


#if __name__ == "__main__":
	#getAllFilesOfType("type", "intecs")
