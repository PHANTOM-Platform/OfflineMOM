#The name of the XML file to be created in the output folder
antfile = "build.xml"

#The name of the temporary folder (to be placed in the same directory as offlinemom.py)
local_temp_folder = "_tmp" 

#The default location to search for the eclipse installation. May be a glob.
default_eclipse_install = "/opt/eclipse*"

#Repository login and connection details
repository_port = 8000 #Read from credentials.txt
repository_user = "" #Read from credentials.txt
repository_pass = "" #Read from credentials.txt
repository_projectname = "offlinemom"
repository_source = "user"

#The port number used by the websockets of the Application Manager
websocket_port = 8500

#The path to the MAST executable
mast_executable = "mast_analysis"

#ANSI colour code constants used to improve the legibility of the output
ANSI_RED = "\033[1;31m"
ANSI_GREEN = "\033[1;32m"
ANSI_YELLOW = "\033[1;33m"
ANSI_BLUE = "\033[1;34m"
ANSI_MAGENTA = "\033[1;35m"
ANSI_CYAN = "\033[1;36m"
ANSI_END = "\033[0;0m"
