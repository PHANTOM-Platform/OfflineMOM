# The PHANTOM Offline MOM

This tool attempts to invalidate deployments which are generated by the PHANTOM Multi-Objective Mapper using real-time analysis.

When a deployment is created, the Offline MOM runs a variety of analysis techniques to determine ahead of time whether the system will fail to meet its deadlines.

Whilst the tool can be triggered manually, it is designed to work with the PHANTOM Application Manager to automatically check deployments that are added to a given project.

## Installation

This tool requires:
 * [Python3](https://www.python.org/downloads/)
 * [Epsilon](http://www.eclipse.org/epsilon/download/)
 * [MAST](https://mast.unican.es/)

Python 3 probably comes with your operating system. If you are using MacOS and find you do not have Python 3, it is easy to install using Homebrew. [Install Homebrew]/(https://brew.sh/) and then issue the following install command:

	brew install python3

Epsilon should just be downloaded from its website and unarchived to `/opt/eclipse`. If installed anywhere else, then set the environment variable `ECLIPSE` to point to the installation directory.

	export ECLIPSE=/my/custom/install/location

MAST can be installed by downloading [the latest binary release](https://mast.unican.es/#downloading), unpacking it, and adding it to your system path. To check this is installed, the tool `mast_analysis` should be on your system path, or you can set the $MASTEXE variable.

	export MASTEXE=/mast/install/location/mast_analysis

You should also ensure that the [PHANTOM Application Manager](https://github.com/PHANTOM-Platform/Application-Manager) is correctly set up and running.


## Running

To start the Offline MOM, it should be told to subscribe to an Application Manager project. To subscribe to a project called `projectname` use the following:

	./offlinemom.py subscribe projectname

The tool will connect to the Application Manager and subscribe. It will then automatically run when new deployments are added. If you do not want to subscribe using the Application Manager, you can trigger an analysis manually on a project using the `remote` command:

	./offlinemom.py remote projectname

Finally, to avoid all dependencies on the Application Manager and Repository, you can simply run on a folder of PHANTOM XML files with `local`:

	./offlinemom.py local /path/to/folder/
