#!/usr/bin/env python3
#Shebang to tell computer to use python to interpret program

#Initialize GPIO and pin numbering scheme
#Based on: https://raspi.tv/2013/how-to-use-interrupts-with-python-on-the-raspberry-pi-and-rpi-gpio-part-3
import RPi.GPIO as GPIO #Catch GPIO pin interrupts
import time #track system time
from multiprocessing import Process, Pipe, Value #Multiprocessing set
from multiprocessing.connection import wait #Extract data from pipes when available
import pygame #Show images and log keypress events
from pygame.locals import * #Import pyGame constants locally
import re #regex
import fileinput #Allows files to be editted in place and to generate backups
from pathlib import Path #Allows for checking if a file exists without exceptions
import subprocess #Allows OS programs to be run as separate threads
import os #Allows access to os, including errors, and terminal commands
import sys #Allows execution of binary within Python - such as Pip, as well as retrieving terminal arguments
import imp #Allows for modules to be imported into program
import signal #Allows programs/processes to be terminated
from datetime import datetime #Allows recording of current date and time
import hashlib #Allows for calculating hashes of files for data verification
import random #Select from list randomly

#Setup variables
devnull = open(os.devnull) #Send subprocess outputs to dummy temp file
reboot = False #Global flag for whether the device needs to be rebooted to have changes take effect
temp_file = "/home/pi/temp_config.txt" #Path for storing temp data to be retrieved after reboot
pyudev = None #Object for importing the pyudev library
PIPE_PATH = "/home/pi/my_pipe.txt" #Create temporary pipe file for exporting text to lxterminal - must be in user directory
terminal = None #Instance of the lxterminal process
mountDir = "/mnt/usb/" #The directory the USB drive will be mounted to

#Experiment variables
imageDir = "/home/pi/exp_Images/" #Directory to transfer images to on the SD card
protocolFile = "Protocol.txt" #Name of the protocol file to be used - must have .txt extension
resultsFile = None #Name of active results file
resultFileBase = "Results.txt" #Base file name for the results file - must have .txt extension
imageExt = ".png" #File extension for valid protocol images

#GPIO variables
pinWheel = 35 #TTL input from mouse wheel
pinDoor = 37 #TTL input from mouse door to reward
pinPump = 29 #TTL output to pump trigger
doorOpen = True #Pin state when door is open
wheelBounce = 1 #Bounce time between events in which to ignore subsequent events (ms)
doorBounce = 1 #Bounce time between events in which to ignore subsequent events (ms)
syncDelay = 0.001 #Sleep delay between GPIO queries to reduce CPU load (s)

#Protocol parameter master dictionary (see retrieveExperiment(driveLabel) for initialization with parsing functions)
parameterDict = {"USB drive ID:": None, "Control image set:": None, "Reward image set:": None,
                "Minimum wheel revolutions for reward:": None,  "Maximum wheel revolutions for reward:": None,
                "Duration of pump \"on\" state (seconds):": None, "Maximum time between wheel events (seconds):": None, 
                "Total duration of the experiment (hours):": None, "Duration of each reward frame (seconds):": None,
                "Maximum duration of reward state (seconds):": None}

def hasher(file):
    HASH = hashlib.md5() #MD5 is used as it is faster, and this is not a cryptographic task
    with open(file, "rb") as f: 
        while True:
            block = f.read(65536) #64 kB buffer for hashing
            if not block: #If block is empty (b'' = False), exit the while loop
                break
            HASH.update(block)
    return HASH.hexdigest()

def lxprint(a): #Status display
    global PIPE_PATH
    with open(PIPE_PATH, "a") as p:
        p.write(a + "\r\n")

#Protocol parsing functions
def matchString(key, line, refString):        
    #Search for refernce string in line from protocol file
    if refString in line:
        lxprint(key + " reference \"" + refString + "\" matches protocol \"" + line + "\"...")
        return line
    else:
        lxprint("ERROR in " + key + " reference \"" + refString + "\" does not match protocol \"" + line + "\"...")
        return None

def parseList(key, line, refArray):
    refArray = []
    
    #Search for a list in the line string
    listArray = [None] #Initialize the protocol list array
    line = "".join(line.split()) #This removes all white space - split cuts on \r\n\t and " ", then join puts the remaining bits back into a string
    listMatch = re.search("\[.*\]", line)
    
    #If there is a valid list string, parse the string
    if listMatch: 
        listString = listMatch.group(0)
        listString = listString[1:-1] #Remove first and last character - "[ ]"
        listArray = listString.split(",")
    
        if not (len(listArray) == 1 and listArray[0] == ""): #Parse images if array is not empty 
            for i in listArray:
                if not i.endswith(imageExt):
                    lxprint("ERROR: Invalid extension in " + key[:-1] + ", \"" + i + "\" is not \"" + imageExt + "\"...")
                    return None
            
            #If loop completes, then image list is valid
            refArray = listArray    
            
        elif key == "Reward image set:":
            refArray = []
            lxprint("ERROR: No reward images found, there must be at least one reward image specified...")
            return None
        
        else:
            refArray = []
            
    lxprint(key[:-1] + " parsed: " + str(refArray))
    return refArray

def parseNum(key, line, refNum):
    #Float search string from: https://stackoverflow.com/questions/4703390/how-to-extract-a-floating-number-from-a-string
    numeric_const_pattern = '[-+]? (?: (?: \d* \. \d+ ) | (?: \d+ \.? ) )(?: [Ee] [+-]? \d+ ) ?'
    rx = re.compile(numeric_const_pattern, re.VERBOSE)
    
    listMatch = rx.search(line)
    if listMatch:
        number = float(listMatch.group(0))
        if(number >= 0):
            lxprint(key[:-1] + " parsed: " + str(number))
            return number
        else:
            lxprint("ERROR: " + key + " \"" + str(parameterDict[key]) + "\" is less than 0 seconds.")
            return None
    else:
        lxprint("ERROR: \"" + key[:-1] + "\" cannot be parsed...")
        return None

#----------------------------Raspberry Pi Config--------------------------------------------------------------------------------------------------------------------
def import_package(p):
    global devnull
    try:
        #Needs directory hint - 1) dir when pip is run in sudo, 2) dir when pip is run without sudo, 3) dir when package loaded with apt-get
        #https://www.raspberrypi.org/forums/viewtopic.php?t=213591                                              
        file, pathname, description = imp.find_module(p, ["/usr/local/lib/python2.7/dist-packages", "/home/pi/.local/lib/python2.7/site-packages", "/usr/lib/python2.7/dist-packages", "/usr/local/lib/python3.5/dist-packages", "/home/pi/.local/lib/python3.5/site-packages", "/usr/lib/python3.5/dist-packages"]) 
        module_obj = imp.load_module(p, file, pathname, description)
        lxprint(p + " is already installed...")
        return module_obj
          
    #If pachage is not found, use PIP3 to download package
    except ImportError:
        lxprint("Downloading " + p + "...")
        
        #Make sure pip is installed before trying to install package
        checkPip()
        
        #Use .wait() rather than .communicate() as .wait() returns returnCode, while .communicate() returns tuple with stdout and stderr
        retcode = subprocess.Popen(["(sudo pip3 install " + p + ")"], shell=True, stdout=devnull, stderr=devnull).wait()

        if retcode == 0:
            lxprint("Installing " + p + "...")                                             
            file, pathname, description = imp.find_module(p, ["/usr/local/lib/python2.7/dist-packages", "/home/pi/.local/lib/python2.7/site-packages", "/usr/lib/python2.7/dist-packages", "/usr/local/lib/python3.5/dist-packages", "/home/pi/.local/lib/python3.5/site-packages", "/usr/lib/python3.5/dist-packages"])
            module_obj = imp.load_module(p, file, pathname, description)
            lxprint(p + " is installed...")
            return module_obj
        else:
            lxprint("Could not install \"" + p + "\", aborting program. Check internet connection?")
            quit()

def checkPip():
    global reboot
    global devnull
    try:
        lxprint("Checking if pip3 is installed...")
        #Any outputs from program are redirected to /dev/null
        #Use Popen.communicate() instead of call so that output does not spam terminal - .communicate() will wait for process to terminate 
        subprocess.Popen(["pip3"], stdout=devnull, stderr=devnull).wait()
        lxprint("Pip is already installed...")
        return
    except OSError as e:
        if e.errno == os.errno.ENOENT:
            lxprint("Installing pip, this may take a few minutes...")

        #Use .wait() rather than .communicate() as .wait() returns returnCode, while .communicate() returns tuple with stdout and stderr
        retcode = subprocess.Popen(["(sudo apt-get install -y python-pip)"], shell=True, stdout=devnull, stderr=devnull).wait()
        if retcode != 100:
            lxprint("Cannot install pip, aborting program. Check internet connection?")
            quit()
        else:
            reboot = True #Flag device for reboot
    lxprint("Pip is installed...")

def configXscreen():
    global reboot
    global devnull
    #Check whether xScreensaver exists by trying to run it silently on a separate thread
    try:
        lxprint("Checking if xScreensaver is installed...")
        #Any outputs from program are redirected to /dev/null
        #Use Popen.communicate() instead of call so that output does not spam terminal - .communicate() will wait for process to terminate 
        retcode = subprocess.Popen(["(xscreensaver-command)"], shell=True, stdout=devnull, stderr=devnull).wait()

        #If process was not successfull, install xscreensaver
        if retcode != 1:
            lxprint("Installing xScreensaver, this may take a few minutes...")
            #Use .wait() rather than .communicate() as .wait() returns returnCode, while .communicate() returns tuple with stdout and stderr
            retcode = subprocess.Popen(["(sudo apt-get install -y xscreensaver)"], shell=True, stdout=devnull, stderr=devnull).wait()
            if retcode != 100:
                lxprint("Error in installing xscreensaver.  Check internet connection?")
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
            lxprint("LXDE desktop is needed to format xScreensaver.  Please run this program in the desktop enxironment.")
            quit()
                
        else:       
            #The following code ensures that when the main process is closed, all subprocesses spawned by main process are also closed
            #It does this by attaching a session ID to the parent process, which will make it the groupd leader of all spawned processes
            #This way, when the group leader is told to terminate, all spawned processes will terminate too
            #https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
            xConfig = False
            while not xConfig:
                try:
                    time.sleep(1)
                    p = subprocess.Popen("xscreensaver-command -demo", stdout=devnull, shell = True, preexec_fn=os.setsid)
                    time.sleep(1)
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                    xConfig = True
                except:
                    xConfig = False
            
        
    #Check xScreenSaver config file to ensure that xScreenSaver is off, overwrite if needed
    #With wrapper ensures that file input closes on completion even with exceptions
    #Inplace means data is moved to backup, and outputs (such as print) are directed to input file
    #Backup allows a backup to be generated with the specified extension
    try:
        with fileinput.input(files=("/home/pi/.xscreensaver"), inplace=True, backup=".bak") as f:
            for line in f:
                line = line.rstrip() #removes trailing white spaces (print() will add newline back on)
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
    out1, dummy=subprocess.Popen(["(sudo raspi-config nonint get_boot_cli)"], shell=True, stdout=subprocess.PIPE, stderr=devnull).communicate()
    out1 = int(out1)
    out2, dummy=subprocess.Popen(["(sudo raspi-config nonint get_autologin)"], shell=True, stdout=subprocess.PIPE, stderr=devnull).communicate()
    out2 = int(out2)
    out3, dummy=subprocess.Popen(["(sudo raspi-config nonint get_overscan)"], shell=True, stdout=subprocess.PIPE, stderr=devnull).communicate()
    out3 = int(out3)

    #Setup Raspberry pi so that it will boot into terminal with auto login
    if 0 in {out1, out3} or out2 == 1:     
        try:
            lxprint("Editing raspi-config...") 
            #Set pi to boot to terminal with auto-login          
            subprocess.Popen(["(sudo raspi-config nonint do_boot_behaviour B4)"], shell=True, stdout=devnull, stderr=devnull).communicate()
            #Set pi to turn off overscan
            subprocess.Popen(["(sudo raspi-config nonint do_overscan 1)"], shell=True, stdout=devnull, stderr=devnull).communicate()
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
            with fileinput.input(files=("/home/pi/.config/pcmanfm/LXDE-pi/pcmanfm.conf"), inplace=True, backup=".bak") as f:
                for line in f:
                    line = line.rstrip() #removes trailing white spaces (print() will add newline back on)
                    #r"..." means raw string, where \ are used as escape characters
                    line = re.sub(r"^mount_on_startup=.*", r"mount_on_startup=0", line)
                    line = re.sub(r"^mount_removable=.*", r"mount_removable=0", line)
                    print(line)
            lxprint("USB automount is disabled..")
        except:
            lxprint("Error: pcmanfm.conf could not be edited.")
            quit()
    else: 
        lxprint("ERROR: pcman.conf not found, how is Raspbian running?")
        quit()
        
    #Install "eject" if it isn;t already installed to allow for ejecting USB drives from the command line
    lxprint("Checking if \"eject\" is installed...")
    retcode = subprocess.Popen(["(eject)"], shell=True, stdout=devnull, stderr=devnull).wait()
    #Install eject if it is not currently installed
    if retcode != 1:
        lxprint("Installing \"eject\"...")
        try:
            dummy = subprocess.Popen(["(sudo apt-get install -y eject)"], shell=True, stdout=devnull, stderr=devnull).wait()
        except:
            lxprint("ERROR: could not install \"eject\", please check internet connection.")
            quit()
        
        #Confirm that eject works
        retcode = subprocess.Popen(["(eject)"], shell=True, stdout=devnull, stderr=devnull).wait()
        if retcode == 1:
            lxprint("Eject was successfully installed...")
        else:
            lxprint("ERROR: eject failed to install, please install manually.")
    else:
        lxprint("Eject is already installed...")

#Auto restart sequence from: https://www.raspberrypi.org/forums/viewtopic.php?t=43509#p714119        
def autorestart():
    global temp_file
    global devnull
    
    #Make sure the Python file is executable
    lxprint("Setting program to exectuable...")
    subprocess.call(["sudo", "chmod", "+x", *sys.argv])

    #Elevate to sudo to edit config files
    if os.geteuid() != 0:
        #Create file to flag program that a reboot has occurred, as well as reference file path for sudo to reference
        with open(temp_file, "w+") as conf:
            conf.write(str(*sys.argv) + "\r\n")
        
        #Check if program is configured for autoload on restart
        edit = True
        with open("/etc/xdg/lxsession/LXDE-pi/autostart", "r") as f:
            edit = True
            for line in f:
                line = line.rstrip() #removes trailing white spaces (print() will add newline back on)
                if(("@/usr/bin/python3 " + str(*sys.argv)) in line):
                    edit = False
        
        #If autostart is not set, elevate to su and add line to autostart before rebooting
        if edit:
            #If program is no configured to autoreload, elevete to su and add line to file
            lxprint("Elevating to su...")
            
            #Elevate to su
            subprocess.call(["sudo", "python3", *sys.argv]) #sys.argv returns the last argument set in the console, which would be this file
        
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
            with fileinput.input(files=("/etc/xdg/lxsession/LXDE-pi/autostart"), inplace=True, backup=".bak") as f:
                for line in f:
                    line = line.rstrip() #removes trailing white spaces (print() will add newline back on)
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
            lxprint("Please re-install xScreensaver by opening terminal and typing:")
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

#---------------------------------USB Drive-----------------------------------------------------------------------------------------------------------------------------------------------
def checkForUSB():
    global mountDir 
    lxprint("Please insert USB drive:")
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='usb')
    connected = False
    labelName = None
    while True:
        time.sleep(0.2)
        #Search for whether a USB drive has been connected to the Pi
        for device in iter(monitor.poll, None):
            #If a USB drive is connected, then check for location of drive
            if device.action == 'add' and not connected:
                test = 0;
                timeStep = 0.1 #Time between checks for connected device
                waitTime = 5 #Time out if device is not found
                deviceFound = False #Flag for if a USB device was found
                deviceValid = False #Flag for if USB device is valid (correct label and format)
                deviceFormat = False #Flag for if device has correct partition format (contains a partition #1)
                while test < waitTime:
                    test += timeStep 
                    time.sleep(timeStep)
                    out, err = subprocess.Popen("lsblk -l -o name,label", shell=True, stdout=subprocess.PIPE).communicate() #Name returns partition directory, label returns partition name
                    outString = out.decode()
                    if re.search(r"sd[a-z]{1,3}", outString) and not deviceFound:
                        lxprint("USB device found...")
                        connected = True
                        deviceFound = True
                    if deviceFound and re.search(r"CAGE 1[A-B]", outString):
                        lxprint("Valid USB device...")
                        labelName = re.search(r"CAGE 1[A-B]", outString).group(0)
                        deviceValid = True
                        break
                    else:
                        continue
                
                if test >= waitTime:
                    if deviceFound:
                        labelName = re.search(r"CAGE [1-9][A-B]", outString)
                        if labelName:
                            lxprint("ERROR: This drive is for " + labelName.group(0)[:-1] + ", please disconnect.")
                            
                        else:
                            lxprint("ERROR: USB drive is not a protocol drive, please disconnect.")
                    else:
                        lxprint("ERROR: USB device was not found.  Please reconnect.")
                    break
                
                #Retrieve the drive location
                dirSearch = re.search("sd[a-z]{1,3}1", outString)
                if not dirSearch:
                    dirSearch = re.search("sd[a-z]{1,3}", outString)
                if dirSearch:
                    if deviceValid:
                        USBdir = "/dev/" + dirSearch.group(0)
                        
                        #Mount the USB drive
                        subprocess.call("sudo mkdir -p " + mountDir, shell=True) #Create directory to which to mount the USB drive if it doesn't exist
                        subprocess.call("sudo mount -o uid=pi,gid=pi " + USBdir + " " + mountDir, shell=True) #Mount USB to directory in user "pi"
                        if(retrieveExperiment(labelName)):
                            lxprint("SUCCESS!")
                            lxprint("Starting experiment...")
                            runExperiment()
                        else:
                            lxprint("FAILURE!")
                        input("Press enter...")
                        subprocess.call("sudo eject " + USBdir, shell=True) #Install eject using command sudo apt-get install eject
                        lxprint("USB drive is unmounted.  It is safe to remove the drive...")
                    else:
                        lxprint("USB drive is unmounted.  It is safe to remove the drive...")
                    
                else:
                    lxprint("ERROR: USB device is no longer found.  Please reconnect.")
            
            #if a USB drive is disconnected, print result
            if device.action == 'remove':
                lxprint("USB drive has been removed...")
                return
                
def retrieveExperiment(driveLabel):
    global mountDir
    global imageDir
    global protocolFile
    global resultsFile
    global resultsFileBase
    global imageExt
    global parameterDict
    
    #Re-initialize the parameter dictionary with the appropriate parsing functions
    parameterDict = {"USB drive ID:": matchString, "Control image set:": parseList, "Reward image set:": parseList,
                "Minimum wheel revolutions for reward:": parseNum,  "Maximum wheel revolutions for reward:": parseNum,
                "Duration of pump \"on\" state (seconds):": parseNum, "Maximum time between wheel events (seconds):": parseNum, 
                "Total duration of the experiment (hours):": parseNum, "Duration of each reward frame (seconds):": parseNum,
                "Maximum duration of reward state (seconds):": parseNum}
        
    f = Path(mountDir + protocolFile)
    #Extract experiment protocol and make sure it is valid
    lines = None #Export of protocol to RAM so it can be added as a header to the results file
    if f.is_file():
        #Append date to protocol file to flag it as being used and prevent accidental reuse
        protocolHash = hasher(mountDir + protocolFile)
        newProtocolFile = re.sub(".txt", " - " + str(datetime.now())[:10] + " " + protocolHash + ".txt", protocolFile)
##################################        os.rename(mountDir + protocolFile, mountDir + newProtocolFile)
        newProtocolFile = protocolFile
        
        #Parse the protocol file
        ref = None #Ref variable to be passed to parsing functions if needed
        with open(mountDir + newProtocolFile, "r") as exp:
            lines = exp.readlines()
            exp.seek(0) #Return back to the start of the file
            for line in exp:               
                for key, func in parameterDict.items():
                     if(line.startswith(key)):
                        if "USB drive ID:" in key:
                            ref = driveLabel
                        else:
                            ref = None
                        parameterDict[key] = func(key, line.split(key, 1)[1].strip(), ref) #Send key and data afer ":" with leading and trailing whitespace removed

        #Check dict and flag missing components
        nValid = 0
        for key, value in parameterDict.items():
            if callable(value): #If value is still function = line not found
                lxprint("Cannot find: \"" + key + "\" in protocol file...")
            elif value is None:
                pass
            else:
                nValid += 1
                
        lxprint(str(nValid) + " of " + str(len(parameterDict)) + " lines parsed...")        
        
        
        #If all components parsed successfully, check that all images are available 
        if nValid == len(parameterDict): #If all elements passed parsing

            #Verify that all images in the protocol are included in the file directory
            
            imageSet = list(set(parameterDict["Control image set:"] + parameterDict["Reward image set:"])) #Create a list of all unique images in the protocol using "set"
            lxprint("Transferring images to SD card...")
            subprocess.call("sudo mkdir -p " + imageDir, shell=True) #Create directory to which to transfer images if it doesn't exist
            for i in imageSet:
                f = Path(mountDir + "images/" + i)
                if f.is_file():
                    subprocess.call("sudo cp " + mountDir + "images/" + i + " " + imageDir, shell=True) #Move valid images to the SD card
                else:
                    lxprint("ERROR: File \"" + i + "\" could not be found in \"" + mountDir + "images/\"")
                    return False
            
            #Export the protocol to the results file
            if lines is not None:
                resultsFile = re.sub(".txt", " - " + str(datetime.now())[:10] + " " + protocolHash + ".txt", resultFileBase)
                lines.insert(0, "Date: " + str(datetime.now()) + "\r\n")
            with open(mountDir + resultsFile, "w+") as f:
                for a in lines:
                    f.write(a)
                    
                #Add file hashes
                f.write("Protocol hash: " + protocolHash + "\r\n")
                f.write("Image hashes: \r\n")
                for i in sorted(set(parameterDict["Control image set:"] + parameterDict["Reward image set:"])):
                    f.write(i + " - " + hasher(imageDir + i) + "\r\n")
                f.write("\r\n-------------------------------Start of experiment-----------------------------------------------\r\n\r\n")
            return True
        
    else:
        lxprint("ERROR: \"" + protocolFile + "\" not found on USB drive.")
    
    return False


#---------------------------------Run experiment-----------------------------------------------------------------------------------------------------------------------------------------------
def imageProcess(connLog, stopQueue, doorPipe, wheelPipe, expStart):
    global imageDir
    global syncDelay
    global parameterDict
    
    rewardDuration = parameterDict["Maximum duration of reward state (seconds):"]
    rewardFramePeriod = parameterDict["Duration of each reward frame (seconds):"]
      
    def sendLog(image):
        global imageDir
        #Send image data to log
        HASH = str(hasher(imageDir + image)) #Get image hash - computing hash takes 2 ms
        timer = time.time() - expStart #Get experiment time
        connLog.send("Image - Name: " + image + ", Hash: " + HASH + ", Time: " + str(time.time() - expStart))
        return
    
    def displayImage(i):
        nonlocal pictureDict
        windowSurfaceObj.blit(pictureDict[i],(0,0))
        pygame.display.update()
        sendLog(i)
        return
    
    def preloadImages(array):
        global imageDir
        subset = set(array) #Create list of all unique entries
        pictures = {}
        for i in subset:
            pictures[i] = pygame.image.load(imageDir + i)
        return pictures
        
    def changeToControl():
        nonlocal wheelPipe
        nonlocal pictureDict
        global parameterDict
        nonlocal rewardIndex
        
        wheelPipe.send(1) #Tell wheel process that reward state ended
        if parameterDict["Control image set:"]: #If the control array is not empty, switch to a randomly selected control image
            displayImage(random.choice(parameterDict["Control image set:"]))
        else:
            displayImage(random.choice(parameterDict["Reward image set:"])) #If no control images are available, show a reward image
        rewardIndex = 0 #Reset the reward frame index
        return False
        
    connLog.send("Image starting at: " + str(time.time()-expStart))
   
    #Exit program on any key press
    run = True
        
    #Get the current reslution of the monitor
    displayObj = pygame.display.Info()
    windowSurfaceObj = pygame.display.set_mode((displayObj.current_w, displayObj.current_h), pygame.FULLSCREEN)
    #windowSurfaceObj = pygame.display.set_mode((displayObj.current_w, displayObj.current_h))
    
    #Hide mouse cursor
    pygame.mouse.set_visible(False)
    
    #Preload images to RAM
    pictureDict = preloadImages((parameterDict["Control image set:"] + parameterDict["Reward image set:"]))

    #initialize varible for tracking image list index
    imageIndex = 0
    
    #Record experiemnt end time
    expEnd = time.time() 
    
    #Initialize state variabes
    wheelState = 0
    doorState = 0
    rewardState = False
    
    #Calculate experiment end time:
    currentTime = time.time()
    expEnd = 60*60*parameterDict["Total duration of the experiment (hours):"] + currentTime
    rewardEnd = currentTime #Track when a reward state times out
    frameEnd = currentTime #Track when a reward frame times out
    rewardIndex = 0 #Index of current reward frame
    
    changeToControl() #Initialize to a control image 
    
    while run and expEnd > currentTime:
        time.sleep(syncDelay)
        
        #Record time for current cycle
        currentTime = time.time()
        
        #Poll for state changes
        if rewardState: #If in reward state monitor door for trigger to control state
            if doorPipe.poll(): #Check if wheel state has changed
                doorState = doorPipe.recv()
                rewardState = changeToControl()
            else:
                doorState = False
        
        else: #If in control state, monitor wheel
            if wheelPipe.poll(): #Check if wheel state has changed
                wheelState = wheelPipe.recv()
                doorPipe.send(1) #Tell door process that wheel has triggered a reward event
                rewardState = True
                rewardEnd = currentTime + rewardDuration #start reward timers
            else:
                wheelState = False
        
        if rewardState:
            if rewardEnd > currentTime: #Check that reward state has not timed out
                if frameEnd < currentTime: #If frame has expired move to next reward frame
                    displayImage(parameterDict["Reward image set:"][rewardIndex%len(parameterDict["Reward image set:"])]) #Show next image in reward sequence
                    rewardIndex += 1 #Increment reward index
            
            else: #If reward state has timed out, cancel reward state
                rewardState = changeToControl()
                    
        #Check for keypress event if available
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                lxprint("Key press")
                run = False
        
        #If keypress, exit run loop
        if not run:
            break
        
    #Flag other processes to stop
    stopQueue.value = 1    
    lxprint("Image stop at: " + str(datetime.now()))

def logProcess(connGPIO, connWheel, connImage, stopQueue):
    global mountDir
    global resultsFile
    global syncDelay
    connArray = []
    connArray.append(connGPIO)
    connArray.append(connWheel)
    connArray.append(connImage)
    
    #f = open(mountDir + resultsFile, "a") #Append log to results file
    run = True
    while run:
        time.sleep(syncDelay)
        #If a data entry is available in the queue, process it
        #multiprocessing.connection.wait
        for r in wait(connArray, timeout=0.1):
            with open(mountDir + resultsFile, "a") as f: #Use with in loop so that data is continuously saved to drive preventing data loss in the event of a device failure
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
        with open(mountDir + resultsFile, "a") as f:
            try:
                data = r.recv()
            except EOFError:
                print ("Error reading from pipe: " + str(r))
                f.write("Error reading from pipe: " + str(r) + "\r\n")
            else:
                f.write(str(data) + "\r\n")
            
    lxprint("Log stop at: " + str(datetime.now()))

def GPIOprocess(pin, connLog, stopQueue, imagePipe, expStart):
    global pinDoor
    global pinWheel
    global pinPump
    global wheelBounce
    global doorBounce
    global doorOpen
    global syncDelay 
    global parameterDict

    #Retrieve protocol parameters
    wheelInterval = parameterDict["Maximum time between wheel events (seconds):"]
    minRev = parameterDict["Minimum wheel revolutions for reward:"]
    maxRev = parameterDict["Maximum wheel revolutions for reward:"]
    pumpDuration = parameterDict["Duration of pump \"on\" state (seconds):"]
    delay = 0 #Debounce delay
    
    #Set state flags
    wheelCount = 0 #Number of wheel revolutions
    wheelEnd = 0 #Timeout for wheel
    pumpEnd = 0 #Timeout for pump
    runState = False #Whether to send data to the image process or to only log events
    pinState = False #Previous state of GPIO pin at last state change
    newState = False #Current state of GPIO pin
    run = True  
    
    #Set output strings
    header = '' #Device string
    stateStr = '' #High/low string
    stopString = '' #String to print when process stops
    
    try:
        #Setup GPIO pin with pull-up resistor, and detection interrupts for both rising and falling events  
        #If the GPIO pin is the wheel pin, then log wheel events
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        if pin == pinWheel:    
            header = "Wheel - "
            delay = wheelBounce/1000
            stopString = "Wheel stop at: "
            runState = True #Initialize assuming control state
            connLog.send("Wheel starting at: " + str(time.time()-expStart))
            
        #Otherwise, log all other door events, and activate pump output
        else:        
            header = "Door - "
            delay = doorBounce/1000
            stopString = "Door stop at: "
            GPIO.setup(pinPump, GPIO.OUT)
            GPIO.output(pinPump, GPIO.LOW) #Initialize with pump low
            runState = False #Initialize assuming control state
            connLog.send("Door starting at: " + str(time.time()-expStart))
        
        #Poll GPIO pin and send events to log when state changes
        pinState = GPIO.input(pin)
        pumpOn = False
        currentTime = time.time()
        
        while run:
            time.sleep(syncDelay)
            currenTime = time.time()
            
            #see if there is a state flag from the image process
            if imagePipe.poll():
                runState = imagePipe.recv()
                wheelCount = 0 #Reset wheel count
                wheelEnd = currentTime
            
            #Toggle pump on if state is active and door is open
            if(pin == pinDoor and runState):
                #If door is open and reward is active, turn on pump
                if(pinState == doorOpen and not pumpOn):
                    GPIO.output(pinPump, GPIO.HIGH)
                    pumpOn = True
                    connLog.send("Pump - State: On, Time: " + str(currentTime - expStart))
                    pumpEnd = currentTime + pumpDuration
                elif(currentTime > pumpEnd and pumpOn): #Otherwise turn pump off when pump times out
                    GPIO.output(pinPump, GPIO.LOW) 
                    pumpOn = False
                    connLog.send("Pump - State: Off, Time: " + str(currentTime - expStart))
                    imagePipe.send(1) #Tell image process reward state is over
                    runState = False

            #If GPIO state changes, log event
            newState = GPIO.input(pin)      
            if (newState ^ pinState):
                timer = str(currentTime - expStart) #Get event time
                pinState = newState #Update current state
                
                if pinState:
                    stateStr = "State: High, Time: "
                    if wheelEnd > currentTime: #If wheel event happens before timeout, add event to counter
                        wheelCount += 1
                    else: #If event happens after timeout, reset counter
                        wheelCount = 1
                    wheelEnd = currentTime + wheelInterval #Update timeout timer
                else:
                    stateStr = "State: Low, Time: "
      
                connLog.send(header + stateStr + timer) 
                
                #Debounce delay
                time.sleep(delay)
                
            #Stop process on stop command from GUI process
            if stopQueue.value == 1:
                run = False
    except:
        lxprint("GPIO Error!")

    finally:
        GPIO.cleanup()
        lxprint(stopString + str(datetime.now()))

def runExperiment():
    global mountDir
    global resultsFile
    pygame.init()

    #Global Variables 
    GPIO.setmode(GPIO.BOARD) #Sets GPIO pin numbering convention
    #GPIO.setwarnings(False) #Suppress runtime cleanup warnings
    
    #Initialize pipe dictionary
    pipeDict = {"door_to_log_rec": None, "door_to_log_send": None, "image_to_log_rec": None, "image_to_log_send": None, "wheel_to_log_rec": None, "wheel_to_log_send":None, "door_to_image_duplex": None, "image_to_door_duplex": None, "wheel_to_image_duplex": None, "image_to_wheel_duplex": None} 
    
    pipeDict["door_to_log_rec"], pipeDict["door_to_log_send"] = Pipe(False) #Setup a unidirectional (duplex = False) line of communication for processes to send data to log process
    pipeDict["image_to_log_rec"], pipeDict["image_to_log_send"] = Pipe(False)
    pipeDict["wheel_to_log_rec"], pipeDict["wheel_to_log_send"] = Pipe(False)
    
    pipeDict["door_to_image_duplex"], pipeDict["image_to_door_duplex"] = Pipe() #Setup a duplex line of communication for coordinating rewards
    pipeDict["wheel_to_image_duplex"], pipeDict["image_to_wheel_duplex"] = Pipe()
    stopQueue = Value('i', 0) #Setup a shared variable to allow a keypress to flag all processes to stop

    #NOTE: A pipe can only connect two processes while a queue can connect multiple processes
    #Also, a pipe is much faster than a queue.  A SimpleQueue has a simplified instruction set
    
    #Initialize Image, GPIO and logging sub processes
    expStart = time.time() #Record start time for experiment
    pLog = Process(target = logProcess, args=(pipeDict["door_to_log_rec"], pipeDict["image_to_log_rec"], pipeDict["wheel_to_log_rec"], stopQueue))
    pDoor = Process(target = GPIOprocess, args=(pinDoor, pipeDict["door_to_log_send"], stopQueue, pipeDict["door_to_image_duplex"], expStart))
    pWheel = Process(target = GPIOprocess, args=(pinWheel, pipeDict["wheel_to_log_send"], stopQueue, pipeDict["wheel_to_image_duplex"], expStart))
    
    try:  
        lxprint("Experiment start at: " + str(datetime.now()))
        pLog.start() #Start subprocesses before continuing with main thread, otherwise main thread will be too busy to start subprocesses
        pDoor.start()
        pWheel.start()
        imageProcess(pipeDict["image_to_log_send"], stopQueue, pipeDict["image_to_door_duplex"], pipeDict["image_to_wheel_duplex"], expStart) #PyGame does not support multi-processing, so it must stay in the main thread
        pLog.terminate()
        pDoor.terminate()
        pWheel.terminate()
        pLog.join() #Verify that all subprocesses are successfully terminated
        pDoor.join()
        pWheel.join()
        
      
    except KeyboardInterrupt:
        pLog.terminate()
        pDoor.terminate()
        pWheel.terminate()
        pLog.join() #Verify that all subprocesses are successfully terminated
        pDoor.join()
        pWheel.join()
    
    finally: #Cleanup on exit
        with open(mountDir + resultsFile, "a") as f: #Append stop time to results file
            f.write("Successful termination at: " + str(time.time()-expStart) + "\r\n")
        for key, value in pipeDict.items(): #Close all active pipes
            value.close()
        
        pygame.quit() #close pygame
        
        try: #Clear out GPIO library if still active
            GPIO.cleanup()
        except:
            pass
            
        lxprint("Experiment end at: " + str(datetime.now()))

#---------------------------------Initialize-----------------------------------------------------------------------------------------------------------------------------------------------

def main():    
    #If logged in as Pi, then run the code in a loop
    if os.geteuid() != 0:
        #Open lxterminal running tail to show status of program
        #e specifies commands to be run in terminal, tail --follow is a program that outputs text as a file grows and follow means show new lines every 1 second (default rate)
        #Clear the log file
        with open(PIPE_PATH, "w+") as p:
            p.write("")
        terminal = subprocess.Popen(["lxterminal -e tail --follow " + PIPE_PATH], shell=True, stdout=devnull, stderr=devnull)
        
        while(True):
            checkPiConfig()
            checkForUSB()
    else: #If su, then only check the configuration, and then exit the program
        checkPiConfig()

if __name__ == '__main__':
    main()















