import time
import re #Allows for regex
import fileinput #Allows files to be editted in place and to generate backups
from pathlib import Path #Allows for checking if a file exists without exceptions
import subprocess #Allows OS programs to be run as separate threads
import os #Allows access to os, including errors, and terminal commands
import sys #Allows execution of binary within Python - such as Pip, as well as retrieving terminal arguments
import imp #Allows for modules to be imported into program
import signal #Allows programs/processes to be terminated
from datetime import datetime #Allows recording of current date and time
import hashlib #Allows for calculating hashes of files for data verification

#Setup variables
devnull = open(os.devnull) #Send subprocess outputs to dummy temp file
pyudev = None #Object for importing the pyudev library
PIPE_PATH = "/home/pi/my_pipe.txt" #Create temporary pipe file for exporting text to lxterminal - must be in user directory
terminal = None #Instance of the lxterminal process
mountDir = "/home/pi/Desktop/" #The directory the USB drive will be mounted to

#Experiment variables
imageArray = []
timeArray = []
rewardArray = []
wheelTrigger = None
rewardDuration = None
wheelInterval = None
imageDir = "/home/pi/exp_Images/"
expFile = "Protocol.txt"
resultsFile = "Results " + str(datetime.now())[:10] + ".txt"
imageExt = ".png"

def hasher(file):
    HASH = hashlib.md5() #MD5 is used as it is faster, and this is not a cryptographic task
    with open(file, "rb") as f: 
        while True:
            block = f.read(65536) #64 kB buffer for hashing
            if not block:
                print(str(block))
                break
            HASH.update(block)
    return HASH.hexdigest()

def lxprint(a):
    global PIPE_PATH
    with open(PIPE_PATH, "a") as p:
        p.write(a + "\r\n")

def retrieveExperiment():
    global mountDir
    global imageDir
    global expFile
    global resultsFile
    global imageArray
    global timeArray
    global rewardArray
    global imageExt
    global wheelTrigger
    global rewardDuration
    global wheelInterval
    f = Path(mountDir + expFile)
    #Extract experiment protocol and make sure it is valid
    valid = 0 #Counter to ensure all necessary parts are included in protocol file
    nProtocol = 6 #Number of protocol files to be parsed in protocol file
    lines = None #Export of protocol to RAM so it can be added as a header to the results file
    if f.is_file():
        #Parse the protocol file
        with open(mountDir + expFile, "r") as exp:
            lines = exp.readlines()
            exp.seek(0) #Return back to the start of the file
            for line in exp:
                listArray = [None] #Initialize the protocol list array
                line = "".join(line.split()) #This removes all white space - split cuts on \r\n\t and " ", then join puts the remaining bits back into a string
                listMatch = re.search("\[.*\]", line)
                if listMatch is not None:
                    listString = listMatch.group(0)
                    listString = listString[1:-1] #Remove first and last character - "[ ]"
                    listArray = listString.split(",")
                if(line.startswith("image:")):
                    imageArray = listArray
                    if len(imageArray) == 0 or None in imageArray or False in imageArray: #Make sure array is filled and valid, False  = "" for strings
                        lxprint("ERROR: Image list in protocol file cannot be parsed...")
                    else:
                        for i in imageArray:
                            if not i.endswith(imageExt):
                                lxprint("ERROR: Invalid extension in image list, \"" + i + "\" is not \"" + imageExt + "\"...")
                                valid = -1
                        if valid != -1:
                            lxprint("Image list parsed...")
                            valid += 1
                elif(line.startswith("time:")):
                    try:
                        timeArray = list(map(float, listArray)) #Create list of floats from list of strings
                        for n in timeArray:
                            if n <= 0:
                                lxprint("ERROR: Time \"" + str(n) + "\" is less than or equal to 0 seconds.")
                                return False
                        if len(timeArray) == 0 or None in timeArray or False in timeArray:
                            lxprint("ERROR: Time list in protocol file cannot be parsed...")
                        else:
                            lxprint("Time list parsed...")
                            valid += 1
                    except:
                        lxprint("ERROR: Time list in protocol file cannot be parsed...")
                elif(line.startswith("reward:")):
                    rewardArray = listArray
                    if len(rewardArray) == 0 or None in rewardArray or False in rewardArray:
                        lxprint("ERROR: Reward list in protocol file cannot be parsed...")
                    else:
                        for i in rewardArray:
                            if not i.endswith(imageExt):
                                lxprint("ERROR: Invalid extension in reward list, \"" + i + "\" is not \"" + imageExt + "\"...")
                                valid = -1
                        if valid != -1:
                            lxprint("Reward list parsed...")
                            valid += 1
                elif(line.startswith("wheeltrigger:")): #String is one word all all white space is removed from line
                    if(("True" in line) ^ ("False" in line)): #xor is used to ensure only one of the two is selected
                        if("True" in line):
                            wheelTrigger = True
                        elif("False" in line):
                            wheelTrigger = False
                        valid += 1
                        lxprint("Wheel trigger parsed...")
                    else:
                        wheelTrigger = None
                        lxprint("ERROR: Wheel trigger is not exclusively \"True\" or \"False\", wheel trigger cannot be parsed...")
                elif(line.startswith("rewardduration:")): #String is one word all all white space is removed from line
                    #Float search string from: https://stackoverflow.com/questions/4703390/how-to-extract-a-floating-number-from-a-string
                    numeric_const_pattern = '[-+]? (?: (?: \d* \. \d+ ) | (?: \d+ \.? ) )(?: [Ee] [+-]? \d+ ) ?'
                    rx = re.compile(numeric_const_pattern, re.VERBOSE)
                    listMatch = rx.search(line)
                    if(listMatch is not None):
                        rewardDuration = float(listMatch.group(0))
                        if(rewardDuration > 0):
                            valid += 1
                            lxprint("Reward duration parsed...")
                        else:
                            lxprint("ERROR: Reward duration \"" + str(rewardDuration) + "\" is less than or equal to 0 seconds.")
                            rewardDuration = None
                    else:
                        rewardDuration = None
                        lxprint("ERROR: Reward duration cannot be parsed...")
                elif(line.startswith("wheelinterval:")): #String is one word all all white space is removed from line
                    #Float search string from: https://stackoverflow.com/questions/4703390/how-to-extract-a-floating-number-from-a-string
                    numeric_const_pattern = '[-+]? (?: (?: \d* \. \d+ ) | (?: \d+ \.? ) )(?: [Ee] [+-]? \d+ ) ?'
                    rx = re.compile(numeric_const_pattern, re.VERBOSE)
                    listMatch = rx.search(line)
                    if(listMatch is not None):
                        wheelInterval = float(listMatch.group(0))
                        if(wheelInterval > 0):
                            valid += 1
                            lxprint("Wheel interval parsed...")
                        else:
                            lxprint("ERROR: Wheel interval \"" + str(wheelInterval) + "\" is less than or equal to 0 seconds.")
                            wheelInterval = None
                    else:
                        wheelInterval = None
                        lxprint("ERROR: Wheel interval cannot be parsed...")
                else:
                    pass
                
        #If all parts of protocl were parsed, check that all images are available and move them to the SD card
        if valid == nProtocol:
            #Verify that the time and image lists are of equal length
            if len(imageArray) != len(timeArray):
                lxprint("ERROR: image array (" + str(len(imageArray)) + ") and time array (" + str(len(timeArray)) + ") are not equal length...")
                return False
            
            #Verify that the reward list is a subset of the image list
            if not set(rewardArray).issubset(imageArray):
                lxprint("ERROR: Reward images are not a subset of all images in the protocol...")
                return
            #Verify that all images in the protocol are included in the file directory
            imageSet = list(set(imageArray)) #Create a list of all unique images in the protocol using "set"
            lxprint("Transferring images to SD card...")
            subprocess.call("sudo mkdir -p " + imageDir, shell=True) #Create directory to which to transfer images if it doesn't exist
            for i in imageSet:
                f = Path(mountDir + "images/" + i)
                if f.is_file():
                    subprocess.call("sudo cp " + mountDir + "images/" + i + " " + imageDir, shell=True) #Move valid images to the SD card
                else:
                    lxprint("ERROR: File \"" + i + "\" could not be found in the image directory...")
                    return False
        else:
            lxprint("ERROR: Could not parse protocol file, " + str(valid) + " of " + str(nProtocol) + " protocols parsed...")
            return False    
    else:
        lxprint("ERROR: \"" + expFile + "\" not found on USB drive.")
        return False
    #Export the protocol to the results file                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           
    if lines is not None:
        lines.insert(0, "Date: " + str(datetime.now()) + "\r\n")
    with open(mountDir + resultsFile, "w+") as f:
        for a in lines:
            f.write(a)
        #Add file hashes
        f.write("Protocol hash: " + hasher(mountDir + expFile) + "\r\n")
        f.write("Image hashes: \r\n")
        for i in sorted(set(imageArray)):
            f.write(i + " - " + hasher(imageDir + i) + "\r\n")
        f.write("\r\n-------------------------------Start of experiment-----------------------------------------------\r\n\r\n")
    return True

with open(PIPE_PATH, "w+") as p:
    p.write("")
terminal = subprocess.Popen(["lxterminal -e tail --follow " + PIPE_PATH], shell=True, stdout=devnull, stderr=devnull)

if(retrieveExperiment()):
    lxprint("SUCCESS!")
else:
    lxprint("FAILURE!")
