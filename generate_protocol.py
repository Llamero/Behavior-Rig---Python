# !/usr/bin/env/python3.6
#Install instructions for psutil - https://github.com/giampaolo/psutil/blob/master/INSTALL.rst
#Follow the same instructions for pygame

import os #Create directory
import sys #Allows program to exit on completion
import psutil #Gives access to USB drive mount events
import time #Gives access to delays and timing
from PIL import Image, ImageDraw #Draw images and save as PNG
from tkinter import font, Tk, Label, Entry, Frame, Checkbutton, Text, Scrollbar, Button, DoubleVar, IntVar, Radiobutton #GUI library
from tkinter.constants import *
import re #REGEX library
import threading #Allow running the protocol generator as a separate thread to not lock the GUI
import queue #Allow kill flag to be sent to threads
import win32api #Get name of USB drive - windows only

nCages = 4 #Global variable declaring number of cages
imageWidth = 1024
imageHeight = 768

def buildGUI():
    ####See "def loadPreset()" to change default protocol settings###
    entryDict = {} #Values for the entry portion of the GUI - tuple - (label, var, entry)
    imageBarDict = {} #Outputs from image select check boxes
    prevImageBarVars = {} #Last recorded state of check boxes
    imageList = ['Solid', 'Checkerboard', 'Horizontal_Stripes', 'Vertical_Stripes'] #List of images available for a protocol
    presetList = [("Day #1", 1), ("Day #2", 2), ("Day #3", 3), ("Day #4", 4), ("Custom", 5)] #List of available presets
    radioList = [None]*len(presetList) #List of radiobutton objects
    presetVar = None #Preset protocol ID
    initialPreset = 1 #Starting preset value
    statusLabel = None #This label updates the user on the status of the program and the next required step
    metadataBox = None #Text box object that contains the metadata
    entryList = ["minReward", "maxReward", "rewardDuration", "wheelDuration", "experimentDuration", "imageFreq", "rewardFreq"] #Keys to the entryDict
    labelList = ["Minimum wheel revolutions for reward: ", #Label text for the entry frame
                 "Maximum wheel revolutions for reward: ",
                 "Duration of reward state (seconds): ",
                 "Maximum time between wheel events (seconds): ",
                 "Total duration of the experiment (hours): ",
                 "Pattern frequency for images: ",
                 "Reward image cycle frequency (seconds): "]
    protocolThread = None #Thread object for generating protocol file and exporting it to a USB drive
    killFlag = queue.Queue() #Queue object for passing kill flag to protocol thread from main thread
    
    def testbox(): #Make sure that there is at least one reward image selected
        nonlocal imageBarDict
        nonlocal prevImageBarVars
        nonlocal statusLabel
        nonlocal imageList
        rSum = 0
        cSum = 0
        error = False

        if len(imageBarDict) == len(imageList): #Only check when GUI is fully populated
            for key, value in imageBarDict.items(): #Count number of active control and reward images
                cVar, rVar = value["var"]
                rSum += rVar.get()
                cSum += cVar.get()
            for key, value in imageBarDict.items():
                cVar, rVar = value["var"]
                if len(prevImageBarVars) == len(imageBarDict): #If previous state is fully populated
                    prevC, prevR = prevImageBarVars[key]
                    if rSum == 0: #If no reward image is selected, restore previous state
                        rVar.set(prevR)
                        cVar.set(prevC)
                        error = True                
                    else:
                        error = False        
                prevImageBarVars[key] = (cVar.get(), rVar.get()) #Update previous state to current state
                if error:
                    statusLabel.config(text="ERROR: There must be at least one reward image in the protocol.")
                else:
                    statusLabel.config(text = "Set protocol parameters and press \"Upload\"...")
    
    #Verify that all entries in the GUI are valid
    def testEntry(proceed):
        nonlocal entryDict
        nonlocal statusLabel
        nonlocal entryList
        nonlocal imageBarDict
        nonlocal metadataBox
        nonlocal uploadButton
        nonlocal protocolThread
        nonlocal killFlag
        #["minReward", "maxReward", "rewardDuration", "wheelDuration", "experimentDuration", "imageFreq", "rewardFreq"]
        error = False
        if len(entryDict) == len(entryList): #Only start proofreading if GUI is fully populated 
            for key, value in entryDict.items(): #Check for any negative entries
                try:
                    if value["var"].get() < 0:
                        statusLabel.config(text="ERROR: " + key + " cannot be a negative value.")
                        error = True
                    if key in ["minReward", "maxReward"] and not value["var"].get().is_integer(): #These values can only be integers
                        statusLabel.config(text="ERROR: " + key + " must be an integer value.")
                        error = True
                except:
                    statusLabel.config(text="ERROR: " + key + " is not a valid number - check syntax.")
                    error = True               

            if entryDict["minReward"]["var"].get() > entryDict["maxReward"]["var"].get():
                statusLabel.config(text="ERROR: minReward cannot be greater than maxReward.")
                error = True
                
            if not error and statusLabel is not None:
                statusLabel.config(text = "Set protocol parameters and press \"Upload\"...")
                
                if proceed:
                    if uploadButton['text'] == "Upload":
                        #Run the protocol generator as a separate thread from the GUI so that the GUI doesn't lock up       
                        killFlag.put(1)
                        protocolThread = threading.Thread(target=uploadProtocol, args=(entryDict, imageBarDict, metadataBox, statusLabel, killFlag, uploadButton, presetVar, presetList))
                        toggleGUI('disabled')
                        protocolThread.start()
                        #protocolThread.join()
                    elif uploadButton['text'] == "Quit":
                        sys.exit()
                    else:
                        killFlag.put(0) #Kill protocol thread
                        while protocolThread.is_alive(): #Wait for thread to stop
                            time.sleep(0.1)
                        toggleGUI('normal') #restore GUI

        return not error
            
    def loadPreset():
        nonlocal entryDict
        nonlocal imageBarDict
        nonlocal presetVar
        nonlocal presetList
        nonlocal statusLabel
        presetID = presetVar.get()
        statusLabel.config(text = "Set protocol parameters and press \"Upload\"...")
        
        #Apply nonlocal defaults if preset option is selected
        if presetID < len(presetList):
            #Set default image check state to solid control and checkerboard reward
            for key, value in imageBarDict.items():
                cVar, rVar = value["var"]
                if(key == "Solid"):
                    rVar.set(0)
                    cVar.set(1)
                elif(key == "Checkerboard"):
                    rVar.set(1)
                    cVar.set(0)
                else:
                    rVar.set(0)
                    cVar.set(0)        
            
            #Inactivate entry boxes and check boxes
            for key, value in entryDict.items():
                value["entry"].config(state='disabled')
            for key, value in imageBarDict.items():
                cChk, rChk = value["chk"]
                cChk.config(state='disabled')
                rChk.config(state='disabled')
                
 ############################DEFAULT PROTOCOLS##########################################################################################            
            entryDict["minReward"]["var"].set(2)
            entryDict["maxReward"]["var"].set(20)
            entryDict["rewardDuration"]["var"].set(10)
            entryDict["wheelDuration"]["var"].set(10)
            entryDict["rewardFreq"]["var"].set(entryDict["rewardDuration"]["var"].get())
            entryDict["imageFreq"]["var"].set(8)
            entryDict["experimentDuration"]["var"].set(12)
            
            #On days 1 and 2, reward never times out
            if presetID <= 2:
                entryDict["rewardDuration"]["var"].set(entryDict["experimentDuration"]["var"].get()*60*60)
                entryDict["wheelDuration"]["var"].set(entryDict["experimentDuration"]["var"].get()*60*60)
                entryDict["rewardFreq"]["var"].set(entryDict["experimentDuration"]["var"].get()*60*60)
                
                #Day 1 - Always show reward image and leave reward active - no wheel trigger needed
                if presetID == 1:                
                    #Set image checkbox
                    cVar, rVar = imageBarDict["Solid"]["var"]
                    cVar.set(0)
     
                    #Change any defaults
                    entryDict["minReward"]["var"].set(0)
                    entryDict["maxReward"]["var"].set(0)
                   
            #On days 2 and 3 the number of wheel revolutions for a reward is constant
            if presetID >= 2 and presetID <= 3:
                entryDict["minReward"]["var"].set(5)
                entryDict["maxReward"]["var"].set(entryDict["minReward"]["var"].get()) 
                       
            #Day 4 - Same as day 3, but control and reward intervals are randomized - default protocol
            else:
                pass

##################################################################################################################
        
        #if custom is selected activate all entry options
        else:
            #Activate entry boxes and check boxes
            for key, value in entryDict.items():
                value["entry"].config(state='normal')
            for key, value in imageBarDict.items():
                cChk, rChk = value["chk"]
                cChk.config(state='normal')
                rChk.config(state='normal')    
        testbox() #Make sure at least one image is selected
    
    def toggleGUI(state):
        nonlocal radioList
        nonlocal entryDict
        nonlocal imageBarDict
        
        #Inactivate entry boxes, radio buttons, and check boxes
        for key, value in entryDict.items():
            value["entry"].config(state=state)
        for key, value in imageBarDict.items():
            cChk, rChk = value["chk"]
            cChk.config(state=state)
            rChk.config(state=state)
        for b in radioList:
            b.config(state=state)
            
        #Switch button state
        if state == 'disabled':
            uploadButton.config(text="Cancel")
        else:
            uploadButton.config(text="Upload")
            loadPreset() #Setup GUI to match current preset
        
    gui = Tk()
    gui.title("Protocol generator...")

    #Initialize frame set
    frameList = ["entry", "check", "radio", "metadata", "button"]
    frameDict = {}
    for row in range(len(frameList)):
        frameDict[frameList[row]] = Frame(master=gui)
        frameDict[frameList[row]].grid(column=0, row=row, sticky=W)
    frameDict["button"].grid(sticky=W+E) #Stretch button frame to width of window
    
    #Set default font to 12
    default_font = font.nametofont("TkDefaultFont")
    default_font.configure(size=12)
    gui.option_add("*Font", default_font)

    #Create set of entry boxes for entering in protocol                 
    for a in range(len(entryList)):
        label = Label(frameDict["entry"], text = labelList[a], anchor=W)
        label.grid(column=0, row=a, sticky=W)
        var = DoubleVar(frameDict["entry"])
        entry = Entry(frameDict["entry"], width=10, textvariable=var, justify=RIGHT, disabledforeground="BLACK", validate="focus", validatecommand=lambda: testEntry(False))
        entry.grid(column=1, row=a, sticky=E, pady=10, padx=(0,5))
        entryDict[entryList[a]] = {"label": label, "var": var, "entry": entry}
    
    #Create pair of check box bars to select preset images for control and reward
    row = a+1
    controlImageLabel = Label(frameDict["check"], text = "Control images(s): ", anchor=W)
    controlImageLabel.grid(column=0, row=row, sticky=W, padx=(0,150))
    rewardImageLabel = Label(frameDict["check"], text = "Reward images(s): ", anchor=W)
    rewardImageLabel.grid(column=1, row=row, sticky=W)
    row += 1

    
    imageBarDict = {}
    for a in imageList:
        cVar = IntVar()
        cChk = Checkbutton(frameDict["check"], text=re.sub(r"_", " ", a), variable=cVar, command=testbox, disabledforeground="BLACK")
        cChk.grid(column=0, row=row, sticky=W)
        rVar = IntVar()
        rChk = Checkbutton(frameDict["check"], text=re.sub(r"_", " ", a), variable=rVar, command=testbox, disabledforeground="BLACK")
        rChk.grid(column=1, row=row, sticky=W)
        imageBarDict[a] = {"var": (cVar, rVar), "chk": (cChk, rChk)}
        row += 1
    
    #Create preset radio buttons
    presetLabel = Label(frameDict["radio"], text = "Select protocol preset: ")
    presetLabel.pack(side=TOP, anchor=W)
    presetVar = IntVar()
    presetVar.set(initialPreset) # initialize
    a=0
    for text, mode in presetList:
        b = Radiobutton(frameDict["radio"], text=text, variable=presetVar, value=mode, command=loadPreset)                   
        b.pack(side=LEFT)
        radioList[a] = b
        a += 1
    
    #Add text box with scroll bar for entering any metadata
    metadataBox = Text(frameDict["metadata"], height=5, width=50)
    metadataBox.pack(side=LEFT, padx=5, pady=5)
    metadataBox.insert(END, "Type metadata here...")
    textScroll = Scrollbar(frameDict["metadata"])
    textScroll.pack(side=RIGHT, padx=5, pady=5, fill=Y)
    textScroll.config(command=metadataBox.yview)
    metadataBox.config(yscrollcommand=textScroll.set)
    
    #Add upload button
    uploadButton = Button(frameDict["button"], text="Upload", command=lambda: testEntry(True)) #On click, check entries and upload if valid
    uploadButton.pack(side=RIGHT, anchor=E, padx=10, pady=10)
    statusLabel = Label(frameDict["button"], text = "Set protocol parameters and press \"Upload\"...")
    statusLabel.pack(side=LEFT, anchor=W) 
    
    #Initialize to default preset
    loadPreset()
    
    gui.mainloop() #Blocks rest of code from executing - similar to while True with update loop

def uploadProtocol(entryDict, imageBarDict, metadataBox, statusLabel, killFlag, uploadButton, presetVar, presetList):
    global nCages
    
    def parseProtocol():
        nonlocal entryDict
        nonlocal imageBarDict
        nonlocal metadataBox
        nonlocal imageList
        nonlocal driveName
        
        controlList = []
        rewardList = []
        
        #Parse image sets
        for key, value in imageBarDict.items(): #Count number of active control and reward images
            cVar, rVar = value["var"]
            if cVar.get() == 1:
                controlList.append(key + ".png")
            if rVar.get() == 1:
                rewardList.append(key + ".png")
        imageList = list(set(rewardList + controlList)) #generate a list of all unique images used in the protocol
        preset = presetVar.get()
        for k,v in presetList:
            if v == preset:
                preset = k
        
        return ("experiment preset: " + preset + "\n" +
                "USB drive ID: " + driveName + "\n" + 
                "control image set: " + re.sub("\'", "", str(controlList)) + "\n" +
                "reward image subset: " + re.sub("\'", "", str(rewardList)) + "\n" +
                "minimum wheel revolution: " + str(entryDict["minReward"]["var"].get()) + "\n" +
                "maximum wheel revolution: " + str(entryDict["maxReward"]["var"].get()) + "\n" +
                "reward duration: " + str(entryDict["rewardDuration"]["var"].get()) + "\n" +
                "wheel duration: " + str(entryDict["wheelDuration"]["var"].get()) + "\n" +
                "reward frequency: " + str(entryDict["rewardFreq"]["var"].get()) + "\n" +
                "image frequency: " + str(entryDict["imageFreq"]["var"].get()) + "\n" +
                "experiment duration: " + str(entryDict["experimentDuration"]["var"].get()) + "\n" +
                "metadata: " + str(metadataBox.get("1.0", "end"))) #"1.0" means read starting line 1 character 0, END means read to end and add newline (end-1c would remove the added newline) https://stackoverflow.com/questions/14824163/how-to-get-the-input-from-the-tkinter-text-box-widget 
    
    def findUSB():
        nonlocal statusLabel
        nonlocal cageList
        nonlocal cage
        nonlocal driveGroup
        nonlocal driveName

        mountDir = None
        
        post_mount_locations = psutil.disk_partitions()
        pre_mount_locations = post_mount_locations #partition list prior to mounting drive
        error = False
        while True:
            if not killFlag.empty(): #Get kill flag if there is one in the queue - empty is blocking so check if there is a flag before getting
                if killFlag.get() == 0: #If cancel button is pressed, exit thread
                    return None
            post_mount_locations = psutil.disk_partitions()
            time.sleep(0.1)
            #print(str(len(post_mount_locations)) + " " + str(len(pre_mount_locations)))
            if not error and len(post_mount_locations) - len(pre_mount_locations) == 1: #If new partition is found, save file to new partition
                mountDir = list(set(post_mount_locations) - set(pre_mount_locations))[0].mountpoint + '/' #new disk partition is where usb is mounted
                statusLabel.config(text="USB drive found, files will be saved to: " + str(mountDir[:-1]))
                driveName, dummy, dummy, dummy, dummy = win32api.GetVolumeInformation(str(mountDir)) #Get name of mounted drive
                if re.match(r"^CAGE [1-len(cageList)][A-B]$", driveName): #Check that USB has valid name
                    if driveGroup is None:
                        driveGroup = driveName[-1:]
                    else:
                        if driveName[-1:] == driveGroup:
                            if driveName not in cageList: #Check that a protocol has not already been written for this cage
                                cageList[cage] = driveName
                                statusLabel.config(text="Protocol uploaded to: " + driveName + ", insert next drive...")
                                return mountDir
                            else:
                                statusLabel.config(text=driveName + " has already been uploaded.  Please choose a different drive.")
                                error = True
                        else:
                            statusLabel.config(text=driveName + " is not from group " + driveGroup + ".  Please choose a different drive.")
                            error = True 
                else:
                    statusLabel.config(text=driveName + " is not a valid drive.  Please choose a different drive.")
                    error = True
            elif (not error and len(post_mount_locations) - len(pre_mount_locations) == -1) or (error and  len(post_mount_locations) - len(pre_mount_locations) == 0): #If partion was removed, thumb drive was removed so reset partition list
                statusLabel.config(text="USB drive removed, please insert USB drive...")
                pre_mount_locations = post_mount_locations #partition list prior to mounting drive
                error = False
    
    def exportFiles(fileString, mountDir):
        nonlocal imageList
        if mountDir is None: #If cancel button is pressed, exit thread
            return    
        pfileName = mountDir + 'Protocol.txt'
        with open(pfileName, 'w+') as pfile: #write protocol specs to protocol file
            pfile.write(fileString)
        
        imageDir = mountDir + "image/"
        for image in imageList:
            imageFile = drawImage(image, entryDict["imageFreq"]["var"].get(), (0,0,0), (0,255,0))      
            try:
                imageFile.save(imageDir + image, format="PNG")
            except:           
                os.mkdir(imageDir)
                imageFile.save(imageDir + image, format="PNG")
                
    def drawImage(mode, freq, foreground, background):
        global imageWidth
        global imageHeight
        
        if mode.startswith("Solid"):
            br, bg, bb = background
            fr,fg,fb = foreground
            background = (round((fr+br)/2), round((fg+bg)/2), round((fb+bb)/2))
            foreground = background
            
        image = Image.new("RGB", (imageWidth, imageHeight), color=background) #Create and image filled with background color
        drawObject = ImageDraw.Draw(image) #Create drawing context
        
        #Create checkerboard as default starting pattern
        squareWidth = imageWidth/(2*freq)
        squareHeight = squareWidth
        x0 = 0
        y0 = 0
        drawSquare = True
        row = 0
        column = 0
        while y0 < imageHeight:
            y1 = round(squareHeight*(row+1)) #Calculate new position of bottom of square
            x0 = 0 #Reset x0 position
            column = 0
            drawSquare = not drawSquare #Shift phase of draw square to enable checkerboard pattern
            while x0 < imageWidth:  
                x1 = round(squareWidth*(column+1)) #Calculate new position of bottom of square
                #Draw square pattern based on mode
                if mode.startswith("Horizontal_Stripes"): #Draw horizontal lines
                    if(row%2 == 0):
                        drawSquare = False
                    else:
                        drawSquare = True
                elif mode.startswith("Vertical_Stripes"): #Draw vertical lines
                    if(column%2 == 0):
                        drawSquare = False
                    else:
                        drawSquare = True
                elif mode.startswith("Solid"): #Leave image blank - background only
                    drawSquare = False
                else: #By default, draw checkerboard pattern
                    drawSquare = not drawSquare
                if drawSquare:
                    drawObject.rectangle([x0, y0, x1, y1], fill=foreground, outline=None, width=0)
                #print(str([x0, y0, x1, y1]))
                x0 = x1 #Increment x0 position
                column += 1
                
            y0 = y1 #Increment y0 position
            #print(str(row) + " " + str(column) + " " + str(count))
            row += 1
        return image
        
    
    cageList = [None]*nCages
    driveGroup = None #Whether uploading to set A or set B
    driveName = None #Name of current USB drive
    statusLabel.config(text="Please insert USB drive...")
    imageList = None
    
    for cage in range(len(cageList)): #Export once for each cage
        mountDir = findUSB()
        if mountDir is None:
            return
        protocolString = parseProtocol()
        exportFiles(protocolString, mountDir)
    time.sleep(2)
    statusLabel.config(text="Protocol upload complete!")
    uploadButton.config(text="Quit")
if __name__ == '__main__':
    buildGUI()



