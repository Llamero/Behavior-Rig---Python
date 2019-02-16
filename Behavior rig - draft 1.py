#!/usr/bin/env python3
#Shebang to tell computer to use python to interpret program

#Initialize GPIO and pin numbering scheme
#Based on: https://raspi.tv/2013/how-to-use-interrupts-with-python-on-the-raspberry-pi-and-rpi-gpio-part-3
import RPi.GPIO as GPIO #Catch GPIO pin interrupts
import time #track system time
from multiprocessing import Process, Pipe, Value #Multiprocessing set
from multiprocessing.connection import wait #Extract data from pipes
when available
import pygame #Show images and log keypress events
from pygame.locals import * #Import pyGame constants locally
import re #regex
import fileinput #Allows files to be editted in place and to generate backups
from pathlib import Path #Allows for checking if a file exists without
exceptions
import subprocess #Allows OS programs to be run as separate threads
import os #Allows access to os, including errors, and terminal commands
import sys #Allows execution of binary within Python - such as Pip, as
well as retrieving terminal arguments
import imp #Allows for modules to be imported into program
import signal #Allows programs/processes to be terminated
from datetime import datetime #Allows recording of current date and time
import hashlib #Allows for calculating hashes of files for data verification

#Setup variables
devnull = open(os.devnull) #Send subprocess outputs to dummy temp file
reboot = False #Global flag for whether the device needs to be
rebooted to have changes take effect
temp_file = "/home/pi/temp_config.txt" #Path for storing temp data to
be retrieved after reboot
pyudev = None #Object for importing the pyudev library
PIPE_PATH = "/home/pi/my_pipe.txt" #Create temporary pipe file for
exporting text to lxterminal - must be in user directory
terminal = None #Instance of the lxterminal process
mountDir = "/mnt/usb/" #The directory the USB drive will be mounted to

#Experiment variables
imageArray = [] #List of sequence of images to be shown
timeArray = [] #Time to show each image (seconds)
rewardArray = [] #Images that will trigger a reward event
wheelTrigger = None #Whether the wheel must also be spinning to
trigger a reward event
rewardDuration = None #Time in seconds after end of reward stim for
mouse to get reward
wheelInterval = None #Time in seconds since last wheel event when
wheel flag is still active
imageDir = "/home/pi/exp_Images/" #Directory to transfer images to on
the SD card
expFile = "Protocol.txt" #Name of the protocol file to be used - must
have .txt extension
resultsFile = None #Name of active reuslts file
resultFileBase = "Results.txt" #Base file name for the results file -
must have .txt extension
imageExt = ".png" #File extension for valid protocol images
expStart = None #Set epoch start time of experiment - i.e. time 0

#GPIO variables
pinWheel = 35 #TTL input from mouse wheel
pinDoor = 37 #TTL input from mouse door to reward
pinPump = 29 #TTL output to pump trigger
doorOpen = True #Pin state when door is open
wheelBounce = 1 #Bounce time between events in which to ignore
subsequent events (ms)
doorBounce = 1 #Bounce time between events in which to ignore
subsequent events (ms)

def hasher(file):
    HASH = hashlib.md5() #MD5 is used as it is faster, and this is not
a cryptographic task
    with open(file, "rb") as f:
        while True:
            block = f.read(65536) #64 kB buffer for hashing
            if not block: #If block is empty (b'' = False), exit the while loop
                break
            HASH.update(block)
    return HASH.hexdigest()

def lxprint(a):
    global PIPE_PATH
    with open(PIPE_PATH, "a") as p:
        p.write(a + "\r\n")
#----------------------------Raspberry Pi
Config--------------------------------------------------------------------------------------------------------------------
def import_package(p):
    global devnull
    try:
        #Needs directory hint - 1) dir when pip is run in sudo, 2) dir
when pip is run without sudo, 3) dir when package loaded with apt-get
        #https://www.raspberrypi.org/forums/viewtopic.php?t=213591
        file, pathname, description = imp.find_module(p,
["/usr/local/lib/python2.7/dist-packages",
"/home/pi/.local/lib/python2.7/site-packages",
"/usr/lib/python2.7/dist-packages"])
        module_obj = imp.load_module(p, file, pathname, description)
        lxprint(p + " is already installed...")
        return module_obj

    #If still not sudo, elevate package is not installed, so install elevate
    except ImportError:
        lxprint("Downloading " + p + "...")

        #Make sure pip is installed before trying to install package
        checkPip()

        #Use .wait() rather than .communicate() as .wait() returns
returnCode, while .communicate() returns tuple with stdout and stderr
        retcode = subprocess.Popen(["(sudo pip install " + p + ")"],
shell=True, stdout=devnull, stderr=devnull).wait()

        if retcode == 0:
            lxprint("Installing " + p + "...")
            file, pathname, description = imp.find_module(p,
["/usr/local/lib/python2.7/dist-packages",
"/home/pi/.local/lib/python2.7/site-packages",
"/usr/lib/python2.7/dist-packages"])
            module_obj = imp.load_module(p, file, pathname, description)
            lxprint(p + " is installed...")
            return module_obj
        else:
            lxprint("Could not install \"" + p + "\", aborting
program. Check internet connection?")
            quit()

def checkPip():
    global reboot
    global devnull
    try:
        lxprint("Checking if pip is installed...")
        #Any outputs from program are redirected to /dev/null
        #Use Popen.communicate() instead of call so that output does
not spam terminal - .communicate() will wait for process to terminate
        subprocess.Popen(["pip"], stdout=devnull, stderr=devnull).wait()
        lxprint("Pip is already installed...")
        return
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            lxprint("Installing pip, this may take a few minutes...")

        #Use .wait() rather than .communicate() as .wait() returns
returnCode, while .communicate() returns tuple with stdout and stderr
        retcode = subprocess.Popen(["(sudo apt-get install -y
python-pip)"], shell=True, stdout=devnull, stderr=devnull).wait()
        if retcode != 100:
            lxprint("Cannot install pip, aborting program. Check
internet connection?")
            quit()
        else:
            reboot = True #Flag device for reboot
    lxprint("Pip is installed...")

def configXscreen():
    global reboot
    global devnull
    #Check whether xScreensaver exists by trying to run it silently on
a separate thread
    try:
        lxprint("Checking if xScreensaver is installed...")
        #Any outputs from program are redirected to /dev/null
        #Use Popen.communicate() instead of call so that output does
not spam terminal - .communicate() will wait for process to terminate
        retcode = subprocess.Popen(["(xscreensaver-command)"],
shell=True, stdout=devnull, stderr=devnull).wait()

        #If process was not successfull, install xscreensaver
        if retcode != 1:
            lxprint("Installing xScreensaver, this may take a few minutes...")
            #Use .wait() rather than .communicate() as .wait() returns
returnCode, while .communicate() returns tuple with stdout and stderr
            retcode = subprocess.Popen(["(sudo apt-get install -y
xscreensaver)"], shell=True, stdout=devnull, stderr=devnull).wait()
            if retcode != 100:
                lxprint("Error in installing xscreensaver.  Check
internet connection?")
                quit()
            else:
                reboot = True #Flag the device for reboot
    except:
        lxprint("Error in installing xscreensaver.  Check internet connection?")
        quit()

    #Verify that there is an xScreensaver config file
    lxprint("Editing xScreensaver config...")
    f = Path("/home/pi/.xscreensaver")
    #If config file doesn't exist, toggle demo to generate a config file
    if not f.is_file():
        #If configuration file is missing, return false
        #Make sure program is in desktop environemnt before running xscreensaver
        desktop = os.environ.get('DESKTOP_SESSION')
        if desktop is None:
            lxprint("LXDE desktop is needed to format xScreensaver.
Please run this program in the desktop enxironment.")
            quit()

        else:
            #The following code ensures that when the main process is
closed, all subprocesses spawned by main process are also closed
            #It does this by attaching a session ID to the parent
process, which will make it the groupd leader of all spawned processes
            #This way, when the group leader is told to terminate, all
spawned processes will terminate too
            #https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
            xConfig = False
            while not xConfig:
                try:
                    time.sleep(1)
                    p = subprocess.Popen("xscreensaver-command -demo",
stdout=devnull, shell = True, preexec_fn=os.setsid)
                    time.sleep(1)
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                    xConfig = True
                except:
                    xConfig = False


    #Check xScreenSaver config file to ensure that xScreenSaver is
off, overwrite if needed
    #With wrapper ensures that file input closes on completion even
with exceptions
    #Inplace means data is moved to backup, and outputs (such as
print) are directed to input file
    #Backup allows a backup to be generated with the specified extension
    try:
        with fileinput.input(files=("/home/pi/.xscreensaver"),
inplace=True, backup=".bak") as f:
            for line in f:
                line = line.rstrip() #removes trailing white spaces
(print() will add newline back on)
                #r"..." means raw string, where \ are used as escape characters
                line = re.sub(r"^mode:.*", r"mode:\t\toff", line)
                print(line)
        lxprint("xScreensaver is configured...")
        return True
    except:
        lxprint("Error: .xscreensaver config file could not be found.")
        quit()


def configBoot():
    global reboot
    global devnull
    lxprint("Checking if monitor is configured correctly...")
    #use raspi-config to change device sonfiguration
    #Any outputs from program are redirected to /dev/null
    #Check if Raspberry Pi is already set to boot into terminal with autologin
    out1, dummy=subprocess.Popen(["(sudo raspi-config nonint
get_boot_cli)"], shell=True, stdout=subprocess.PIPE,
stderr=devnull).communicate()
    out1 = int(out1)
    out2, dummy=subprocess.Popen(["(sudo raspi-config nonint
get_autologin)"], shell=True, stdout=subprocess.PIPE,
stderr=devnull).communicate()
    out2 = int(out2)
    out3, dummy=subprocess.Popen(["(sudo raspi-config nonint
get_overscan)"], shell=True, stdout=subprocess.PIPE,
stderr=devnull).communicate()
    out3 = int(out3)

    #Setup Raspberry pi so that it will boot into terminal with auto login
    if 0 in {out1, out3} or out2 == 1:
        try:
            lxprint("Editing raspi-config...")
            #Set pi to boot to terminal with auto-login
            subprocess.Popen(["(sudo raspi-config nonint
do_boot_behaviour B4)"], shell=True, stdout=devnull,
stderr=devnull).communicate()
            #Set pi to turn off overscan
            subprocess.Popen(["(sudo raspi-config nonint do_overscan
1)"], shell=True, stdout=devnull, stderr=devnull).communicate()
            #Set pi to reboot to apply new settings
            reboot = True #Flag the device for reboot so changes can be applied
        except:
            lxprint("Error: can't edit raspi-config.")
            quit()

    else:
        lxprint("Monitor is already configured correctly...")

#Command from - https://www.raspberrypi.org/forums/viewtopic.php?t=91677#p641130
def disableAutomount():
    global devnull
    lxprint("Disabling USB drive automount...")
    f = Path("/home/pi/.config/pcmanfm/LXDE-pi/pcmanfm.conf")
    #If config file doesn't exist, toggle demo to generate a config file
    if f.is_file():
        try:
            with
fileinput.input(files=("/home/pi/.config/pcmanfm/LXDE-pi/pcmanfm.conf"),
inplace=True, backup=".bak") as f:
                for line in f:
                    line = line.rstrip() #removes trailing white
spaces (print() will add newline back on)
                    #r"..." means raw string, where \ are used as
escape characters
                    line = re.sub(r"^mount_on_startup=.*",
r"mount_on_startup=0", line)
                    line = re.sub(r"^mount_removable=.*",
r"mount_removable=0", line)
                    print(line)
            lxprint("USB automount is disabled..")
        except:
            lxprint("Error: pcmanfm.conf could not be edited.")
            quit()
    else:
        lxprint("ERROR: pcman.conf not found, how is Raspbian running?")
        quit()

    #Install "eject" if it isn;t already installed to allow for
ejecting USB drives from the command line
    lxprint("Checking if \"eject\" is installed...")
    retcode = subprocess.Popen(["(eject)"], shell=True,
stdout=devnull, stderr=devnull).wait()
    #Install eject if it is not currently installed
    if retcode != 1:
        lxprint("Installing \"eject\"...")
        try:
            dummy = subprocess.Popen(["(sudo apt-get install -y
eject)"], shell=True, stdout=devnull, stderr=devnull).wait()
        except:
            lxprint("ERROR: could not install \"eject\", please check
internet connection.")
            quit()

        #Confirm that eject works
        retcode = subprocess.Popen(["(eject)"], shell=True,
stdout=devnull, stderr=devnull).wait()
        if retcode == 1:
            lxprint("Eject was successfully installed...")
        else:
            lxprint("ERROR: eject failed to install, please install manually.")
    else:
        lxprint("Eject is already installed...")

#Auto restart sequence from:
https://www.raspberrypi.org/forums/viewtopic.php?t=43509#p714119
def autorestart():
    global temp_file
    global devnull

    #Make sure the Python file is executable
    lxprint("Setting program to exectuable...")
    subprocess.call(["sudo", "chmod", "+x", *sys.argv])

    #Elevate to sudo to edit config files
    if os.geteuid() != 0:
        #Create file to flag program that a reboot has occurred, as
well as reference file path for sudo to reference
        with open(temp_file, "w+") as conf:
            conf.write(str(*sys.argv) + "\r\n")

        #Check if program is configured for autoload on restart
        edit = True
        with open("/etc/xdg/lxsession/LXDE-pi/autostart", "r") as f:
            edit = True
            for line in f:
                line = line.rstrip() #removes trailing white spaces
(print() will add newline back on)
                if(("@/usr/bin/python3 " + str(*sys.argv)) in line):
                    edit = False

        #If autostart is not set, elevate to su and add line to
autostart before rebooting
        if edit:
            #If program is no configured to autoreload, elevete to su
and add line to file
            lxprint("Elevating to su...")

            #Elevate to su
            subprocess.call(["sudo", "python3", *sys.argv]) #sys.argv
returns the last argument set in the console, which would be this file

        #If autostart is set, ready to reboot
        lxprint("Rebooting system to apply changes...")
        time.sleep(3)
        subprocess.call("reboot")

    #if su, edit autostart file as needed
    else:
        try:
            lxprint("Configuring LXDE autoload to boot this file on restart...")

            #Load the configuration data into an array
            with open(temp_file, "r") as conf:
                confArray = conf.readlines()

            #Modify the autostart LXDE file to run this code on boot
            edit = True
            with
fileinput.input(files=("/etc/xdg/lxsession/LXDE-pi/autostart"),
inplace=True, backup=".bak") as f:
                for line in f:
                    line = line.rstrip() #removes trailing white
spaces (print() will add newline back on)
                    print(line)
                    if(("@/usr/bin/python3 " + confArray[0]) in line):
                        edit = False

            #If the program isn't already set to autostart, configure file
            if edit:
                with open("/etc/xdg/lxsession/LXDE-pi/autostart", "a") as f:
                    f.write("@/usr/bin/python3 " + confArray[0].rstrip())


        except:
            lxprint("Error: autostart config file could not be found.")
            quit()

#Check setup and run experimient if logged in as pi
def checkPiConfig():
    global reboot
    global temp_file
    global pyudev
    reboot = False
    if os.geteuid() != 0:
        #Remove temp config file if it exists
        f = Path(temp_file)
        if f.is_file():
            subprocess.call("sudo rm " + temp_file, shell=True)
        configBoot()
        if not configXscreen():
            lxprint("Please re-install xScreensaver by opening
terminal and typing:")
            lxprint("sudo apt-get install xscreensaver")
        else:
            lxprint("Screen configuration successful...")
        pyudev = import_package("pyudev")
        disableAutomount()
        if reboot == True:
            autorestart()

    elif os.geteuid() == 0:
        autorestart()

    else:
        lxprint("Invalid user ID: " + str(os.geteuid))

#---------------------------------USB
Drive-----------------------------------------------------------------------------------------------------------------------------------------------
def checkForUSB():
    global mountDir
    lxprint("Please insert USB drive:")
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='usb')
    nDevice = 0
    nConnect = 0

    while True:
        time.sleep(0.2)
        #Search for whether a USB drive has been connected to the Pi
        for device in iter(monitor.poll, None):
            #If a USB drive is connected, then check for location of drive
            if device.action == 'add' and nDevice == 0:
                test = 0;
                timeStep = 0.1 #Time between checks for connected device
                waitTime = 5 #Time out if device is not found
                while test < waitTime:
                    test += timeStep
                    time.sleep(timeStep)
                    out, err = subprocess.Popen("lsblk -o name",
shell=True, stdout=subprocess.PIPE).communicate()
                    outString = out.decode()
                    if "sd" in outString:
                        lxprint("USB device found...")
                        break
                    else:
                        continue

                if test >= waitTime:
                    lxprint("ERROR: USB device was not found.  Please
reconnect.")

                #Retrieve the drive location
                dirSearch = re.search("sd[a-z]", outString)
                if dirSearch:
                    USBdir = "/dev/" + dirSearch.group(0)

                    #Mount the USB drive
                    subprocess.call("sudo mkdir -p " + mountDir,
shell=True) #Create directory to which to mount the USB drive if it
doesn't exist
                    subprocess.call("sudo mount -o uid=pi,gid=pi " +
USBdir + " " + mountDir, shell=True) #Mount USB to directory in user
"pi"
                    if(retrieveExperiment()):
                        lxprint("SUCCESS!")
                        lxprint("Starting experiment...")
                        runExperiment()
                    else:
                        lxprint("FAILURE!")
                    input("Press enter...")
                    subprocess.call("sudo eject " + USBdir,
shell=True) #Install eject using command sudo apt-get install eject
                    lxprint("USB drive is unmounted.  It is safe to
remove the drive...")
                    nDevice = 1
                    nConnect += 1

                else:
                    lxprint("ERROR: USB device is no longer found.
Please reconnect.")


            #if a USB drive is disconnected, print result
            if device.action == 'remove' and nDevice == 1:
                nDevice = 0
                lxprint("USB drive has been removed...")
                return

def retrieveExperiment():
    global mountDir
    global imageDir
    global expFile
    global resultsFile
    global resultsFileBase
    global imageArray
    global timeArray
    global rewardArray
    global imageExt
    global wheelTrigger
    global rewardDuration
    global wheelInterval
    f = Path(mountDir + expFile)
    #Extract experiment protocol and make sure it is valid
    valid = 0 #Counter to ensure all necessary parts are included in
protocol file
    nProtocol = 6 #Number of protocol files to be parsed in protocol file
    lines = None #Export of protocol to RAM so it can be added as a
header to the results file
    if f.is_file():
        #Append date to protocol file to flag it as being used and
prevent accidental reuse
        protocolHash = hasher(mountDir + expFile)
        newExpFile = re.sub(".txt", " - " + str(datetime.now())[:10] +
" " + protocolHash + ".txt", expFile)
#        os.rename(mountDir + expFile, mountDir + newExpFile)
        newExpFile = expFile

        #Parse the protocol file
        with open(mountDir + newExpFile, "r") as exp:
            lines = exp.readlines()
            exp.seek(0) #Return back to the start of the file
            for line in exp:
                listArray = [None] #Initialize the protocol list array
                line = "".join(line.split()) #This removes all white
space - split cuts on \r\n\t and " ", then join puts the remaining
bits back into a string
                listMatch = re.search("\[.*\]", line)
                if listMatch is not None:
                    listString = listMatch.group(0)
                    listString = listString[1:-1] #Remove first and
last character - "[ ]"
                    listArray = listString.split(",")
                if(line.startswith("image:")):
                    imageArray = listArray
                    if len(imageArray) == 0 or None in imageArray or
False in imageArray: #Make sure array is filled and valid, False  = ""
for strings
                        lxprint("ERROR: Image list in protocol file
cannot be parsed...")
                    else:
                        for i in imageArray:
                            if not i.endswith(imageExt):
                                lxprint("ERROR: Invalid extension in
image list, \"" + i + "\" is not \"" + imageExt + "\"...")
                                valid = -1
                        if valid != -1:
                            lxprint("Image list parsed...")
                            valid += 1
                elif(line.startswith("time:")):
                    try:
                        timeArray = list(map(float, listArray))
#Create list of floats from list of strings
                        for n in timeArray:
                            if n <= 0:
                                lxprint("ERROR: Time \"" + str(n) +
"\" is less than or equal to 0 seconds.")
                                return False
                        if len(timeArray) == 0 or None in timeArray or
False in timeArray:
                            lxprint("ERROR: Time list in protocol file
cannot be parsed...")
                        else:
                            lxprint("Time list parsed...")
                            valid += 1
                    except:
                        lxprint("ERROR: Time list in protocol file
cannot be parsed...")
                elif(line.startswith("reward:")):
                    rewardArray = listArray
                    if len(rewardArray) == 0 or None in rewardArray or
False in rewardArray:
                        lxprint("ERROR: Reward list in protocol file
cannot be parsed...")
                    else:
                        for i in rewardArray:
                            if not i.endswith(imageExt):
                                lxprint("ERROR: Invalid extension in
reward list, \"" + i + "\" is not \"" + imageExt + "\"...")
                                valid = -1
                        if valid != -1:
                            lxprint("Reward list parsed...")
                            valid += 1
                elif(line.startswith("wheeltrigger:")): #String is one
word all all white space is removed from line
                    if(("True" in line) ^ ("False" in line)): #xor is
used to ensure only one of the two is selected
                        if("True" in line):
                            wheelTrigger = True
                        elif("False" in line):
                            wheelTrigger = False
                        valid += 1
                        lxprint("Wheel trigger parsed...")
                    else:
                        wheelTrigger = None
                        lxprint("ERROR: Wheel trigger is not
exclusively \"True\" or \"False\", wheel trigger cannot be parsed...")
                elif(line.startswith("rewardduration:")): #String is
one word all all white space is removed from line
                    #Float search string from:
https://stackoverflow.com/questions/4703390/how-to-extract-a-floating-number-from-a-string
                    numeric_const_pattern = '[-+]? (?: (?: \d* \. \d+
) | (?: \d+ \.? ) )(?: [Ee] [+-]? \d+ ) ?'
                    rx = re.compile(numeric_const_pattern, re.VERBOSE)
                    listMatch = rx.search(line)
                    if(listMatch is not None):
                        rewardDuration = float(listMatch.group(0))
                        if(rewardDuration > 0):
                            valid += 1
                            lxprint("Reward duration parsed...")
                        else:
                            lxprint("ERROR: Reward duration \"" +
str(rewardDuration) + "\" is less than or equal to 0 seconds.")
                            rewardDuration = None
                    else:
                        rewardDuration = None
                        lxprint("ERROR: Reward duration cannot be parsed...")
                elif(line.startswith("wheelinterval:")): #String is
one word all all white space is removed from line
                    #Float search string from:
https://stackoverflow.com/questions/4703390/how-to-extract-a-floating-number-from-a-string
                    numeric_const_pattern = '[-+]? (?: (?: \d* \. \d+
) | (?: \d+ \.? ) )(?: [Ee] [+-]? \d+ ) ?'
                    rx = re.compile(numeric_const_pattern, re.VERBOSE)
                    listMatch = rx.search(line)
                    if(listMatch is not None):
                        wheelInterval = float(listMatch.group(0))
                        if(wheelInterval > 0):
                            valid += 1
                            lxprint("Wheel interval parsed...")
                        else:
                            lxprint("ERROR: Wheel interval \"" +
str(wheelInterval) + "\" is less than or equal to 0 seconds.")
                            wheelInterval = None
                    else:
                        wheelInterval = None
                        lxprint("ERROR: Wheel interval cannot be parsed...")
                else:
                    pass

        #If all parts of protocl were parsed, check that all images
are available and move them to the SD card
        if valid == nProtocol:
            #Verify that the time and image lists are of equal length
            if len(imageArray) != len(timeArray):
                lxprint("ERROR: image array (" + str(len(imageArray))
+ ") and time array (" + str(len(timeArray)) + ") are not equal
length...")
                return False

            #Verify that the reward list is a subset of the image list
            if not set(rewardArray).issubset(imageArray):
                lxprint("ERROR: Reward images are not a subset of all
images in the protocol...")
                return
            #Verify that all images in the protocol are included in
the file directory
            imageSet = list(set(imageArray)) #Create a list of all
unique images in the protocol using "set"
            lxprint("Transferring images to SD card...")
            subprocess.call("sudo mkdir -p " + imageDir, shell=True)
#Create directory to which to transfer images if it doesn't exist
            for i in imageSet:
                f = Path(mountDir + "images/" + i)
                if f.is_file():
                    subprocess.call("sudo cp " + mountDir + "images/"
+ i + " " + imageDir, shell=True) #Move valid images to the SD card
                else:
                    lxprint("ERROR: File \"" + i + "\" could not be
found in the image directory...")
                    return False
        else:
            lxprint("ERROR: Could not parse protocol file, " +
str(valid) + " of " + str(nProtocol) + " protocols parsed...")
            return False
    else:
        lxprint("ERROR: \"" + newExpFile + "\" not found on USB drive.")
        return False
    #Export the protocol to the results file
    if lines is not None:
        resultsFile = re.sub(".txt", " - " + str(datetime.now())[:10]
+ " " + protocolHash + ".txt", resultFileBase)
        lines.insert(0, "Date: " + str(datetime.now()) + "\r\n")
    with open(mountDir + resultsFile, "w+") as f:
        for a in lines:
            f.write(a)
        #Add file hashes
        f.write("Protocol hash: " + protocolHash + "\r\n")
        f.write("Image hashes: \r\n")
        for i in sorted(set(imageArray)):
            f.write(i + " - " + hasher(imageDir + i) + "\r\n")
        f.write("\r\n-------------------------------Start of
experiment-----------------------------------------------\r\n\r\n")
    return True

#---------------------------------Run
experiment-----------------------------------------------------------------------------------------------------------------------------------------------
def imageProcess(connLog, stopQueue, rewardActive, wheelActive):
    global imageDir
    global displayTime
    global expStart
    global timeArray
    global imageArray
    global rewardArray
    global wheelTrigger

    def sendLog(dir, image):
        #Send image data to log
        #HASH = ", Hash: " + hasher(dir + image) #Get image hash -
computing hash takes 2 ms
        HASH = ""
        timer = time.time() - expStart #Get epxeriment time
        connLog.send("Image - Name: " + image + HASH + ", Time: " +
str(time.time() - expStart))
        return 1

    def displayImage(i):
        windowSurfaceObj.blit(i,(0,0))
        pygame.display.update()
        return False

    def preloadImages(dir, array):
        subset = set(array) #Create list of all unique entries
        pictures = {}
        for i in subset:
            pictures[i] = pygame.image.load(dir + i)
        return pictures

    connLog.send("Image starting")

    #Exit program on any key press
    run = True

    #Get the current reslution of the monitor
    displayObj = pygame.display.Info()
    windowSurfaceObj = pygame.display.set_mode((displayObj.current_w,
displayObj.current_h), pygame.FULLSCREEN)
    #windowSurfaceObj = pygame.display.set_mode((displayObj.current_w,
displayObj.current_h))

    #Hide mouse cursor
    pygame.mouse.set_visible(False)

    #Preload images to RAM
    pictures = preloadImages(imageDir, imageArray)

    #initialize varible for tracking image list index
    imageIndex = 0

    #Start image display timer
    stopTime = time.time()

    for t in timeArray:
        imageOff = True
        rewardImage = False
        stopTime += t #update next image display time

        #Check if image is reward image
        if(imageArray[imageIndex] in rewardArray):
            rewardImage = True
        else:
            imageOff = displayImage(pictures[imageArray[imageIndex]])
            rewardActive.value = sendLog(imageDir, imageArray[imageIndex]) - 1

        #Wait specified delay time, checking for keypress event
        while time.time() < stopTime:
            #Display image
            if imageOff and rewardImage and (wheelActive.value == 1 or
not wheelTrigger):
                imageOff = displayImage(pictures[imageArray[imageIndex]])
                rewardActive.value = sendLog(imageDir, imageArray[imageIndex])

            #Check for keypress event if availalbe
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    lxprint("Key press")
                    run = False
            #If keypress, exit run loop
            if not run:
                break

        imageIndex += 1

    stopQueue.value = 1
    lxprint("GUI stop")

def logProcess(connGPIO, connWheel, connImage, stopQueue):
    global mountDir
    global resultsFile
    connArray = []
    connArray.append(connGPIO)
    connArray.append(connWheel)
    connArray.append(connImage)

    f = open(mountDir + resultsFile, "a") #Create text file to store results
    run = True
    while run:
        #If a data entry is available in the queue, process it
        #multiprocessing.connection.wait
        for r in wait(connArray, timeout=0.1):
            try:
                data = r.recv()
            except EOFError:
                lxprint("Error reading from pipe: " + str(r))
                f.write("Error reading from pipe: " + str(r) + "\r\n")
            else:
                f.write(str(data) + "\r\n")

        #Stop process on stop command from GUI process
        if stopQueue.value == 1:
            run = False

    #Perform last check of pipes to make sure all data has been gathered
    for r in wait(connArray, timeout=1):
        try:
            data = r.recv()
        except EOFError:
            print ("Error reading from pipe: " + str(r))
            f.write("Error reading from pipe: " + str(r) + "\r\n")
        else:
            f.write(str(data) + "\r\n")

    lxprint("Log stop")

def GPIOprocess(pin, connLog, stopQueue, stateFlag):
    global pinDoor
    global pinWheel
    global pinPump
    global wheelBounce
    global doorBounce
    global GPIOstring
    global wheelInterval
    global rewardDuration
    global doorOpen

    run = True
    header = '' #Device string
    pinState = False #Previous state of GPIO pin at last state change
    newState = False #Current state of GPIO pin
    stateStr = '' #High/low string
    stopString = '' #String to print when process stops
    delay = 0

    try:
        #Setup GPIO pin with pull-up resistor, and detection
interrupts for both rising and falling events
        #If the GPIO pin is the wheel pin, then log wheel events
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        if pin == pinWheel:
            header = "Wheel - "
            delay = wheelBounce/1000
            stopString = "Wheel stop"
            eventTime = wheelInterval

        #Otherwise, log all other door events, and activate pump output
        else:
            header = "Door - "
            delay = doorBounce/1000
            stopString = "Door stop"
            eventTime = rewardDuration
            GPIO.setup(pinPump, GPIO.OUT)

        #Poll GPIO pin and send events to log when state changes
        pinState = GPIO.input(pin)
        eventStop = time.time() #Track when the wheel flag goes false
after last wheel event
        pumpOn = False
        while run:
            #If reward image is active, reset the reward duration timer
            if(pin == pinDoor):
                if(stateFlag.value == 1):
                    eventStop = time.time() + eventTime
                #If door is open and reward is active, turn on pump
                if(eventStop > time.time() and pinState == doorOpen
and not pumpOn):
                    GPIO.output(pinPump, GPIO.HIGH)
                    pumpOn = True
                    connLog.send("Pump - State: On, Time: " +
str(time.time() - expStart))
                elif(pinState != doorOpen and pumpOn):
                    GPIO.output(pinPump, GPIO.LOW) #Otherwise turn
pump off when door is closed
                    pumpOn = False
                    connLog.send("Pump - State: Off, Time: " +
str(time.time() - expStart))

            #Otherwise, update wheel state flag
            else:
                if(eventStop > time.time() and stateFlag.value == 0):
                    stateFlag.value = 1
                elif(eventStop <= time.time() and stateFlag.value == 1):
                    stateFlag.value = 0


            #If GPIO state changes, log event
            newState = GPIO.input(pin)
            if (newState ^ pinState):
                timer = str(time.time() - expStart) #Get event time
                pinState = newState #Update current state

                if pinState:
                    stateStr = "State: High, Time: "
                else:
                    stateStr = "State: Low, Time: "

                #Reset wheel active timer
                if(pin == pinWheel):
                    eventStop = time.time() + wheelInterval

                connLog.send(header + stateStr + timer)

                #Debounce delay
                time.sleep(delay)
                lxprint(header + str(stateFlag.value))

            #Stop process on stop command from GUI process
            if stopQueue.value == 1:
                run = False
    except:
        lxprint("GPIO Error!")
    finally:
        GPIO.cleanup()
        lxprint(stopString)

def runExperiment():
    global expStart
    pygame.init()

    #Global Variables
    GPIO.setmode(GPIO.BOARD) #Sets GPIO pin numbering convention

    GPIOrec, GPIOsend = Pipe() #Setup a duplex line of communication
for processes to send data to log process
    imageRec, imageSend = Pipe()
    wheelRec, wheelSend = Pipe()
    stopQueue = Value('i', 0) #Setup a shared variable to allow a
keypress to flag all processes to stop
    rewardActive = Value('i', 0) #Setup a shared variable to flag that
a reward event is active
    wheelActive = Value('i', 0) #Setup a shared variable to flag that
a wheel event is active
    #NOTE: A pipe can only connect two processes while a queue can
connect multiple processes
    #Also, a pipe is much faster than a queue.  A SimpleQueue has a
simplified instruction set

    #Initialize Image, GPIO and logging sub processes
    pLog = Process(target = logProcess, args=(GPIOrec, wheelRec,
imageRec, stopQueue))
    pGPIO = Process(target = GPIOprocess, args=(pinDoor, GPIOsend,
stopQueue, rewardActive))
    pWheel = Process(target = GPIOprocess, args=(pinWheel, wheelSend,
stopQueue, wheelActive))

    try:
        lxprint("Starting")
        expStart = time.time() #Record the start time of the experiemnt
        pLog.start() #Start subprocesses before continuing with main
thread, otherwise main thread will be too busy to start subprocesses
        pGPIO.start()
        pWheel.start()
        imageProcess(imageSend, stopQueue, rewardActive, wheelActive)
#PyGame does not support multi-processing, so it must stay in the main
thread
        pLog.terminate()
        pGPIO.terminate()
        pWheel.terminate()
        pLog.join() #Verify that all subprocesses are successfully terminated
        pGPIO.join()
        pWheel.join()


    except KeyboardInterrupt:
        pLog.terminate()
        pGPIO.terminate()
        pWheel.terminate()
        pLog.join() #Verify that all subprocesses are successfully terminated
        pGPIO.join()
        pWheel.join()

    pygame.quit()
        #    GPIO.cleanup()       # clean up GPIO on CTRL+C exit
    #GPIO.cleanup()           # clean up GPIO on normal exit
    lxprint("End.")

#---------------------------------Initialize-----------------------------------------------------------------------------------------------------------------------------------------------

def main():
    #e specifies commands to be run in terminal, tail --follow is a
program that outputs text as a file grows and follow means show new
lines every 1 second (default rate)
    #Clear the log file
    with open(PIPE_PATH, "w+") as p:
        p.write("")
    terminal = subprocess.Popen(["lxterminal -e tail --follow " +
PIPE_PATH], shell=True, stdout=devnull, stderr=devnull)

    checkPiConfig()
    checkForUSB()

if __name__ == '__main__':
    main()

