# -*- coding: utf-8 -*-
"""
Created on Sun Jan 12 13:06:17 2014



"""
#Originally from: https://github.com/plasmon360/python_newport_1918_powermeter
from ctypes import * #Convert variables to C for power meter driver
import time #Sleep for set times
from datetime import datetime, timedelta #Get current date to append to file names
import os, sys
import contextlib #Block pygame spam
import matplotlib.pyplot as plt #plot results
import warnings #Suppress numpy float to int warning
import numpy as np #Create evenly space lists over set interval - linspace
with contextlib.redirect_stdout(None): #Block pygame boot spam - https://stackoverflow.com/questions/51464455/why-when-import-pygame-it-prints-the-version-and-welcome-message-how-delete-it
    import pygame #Show images and log keypress events
from pygame.locals import * #Import pyGame constants locally
from tkinter import Tk, filedialog #Create directory GUI
import random #Shuffle list order
from collections import OrderedDict #Preserve dictionary order

np.warnings.filterwarnings('ignore') #Supress Numpy float to int deprecation warning


class CommandError(Exception):
    '''The function in the usbdll.dll was not sucessfully evaluated'''


class Newport_1918c():
    def __init__(self,**kwargs):
        try:
            self.LIBNAME = kwargs.get('LIBNAME',r"C:\Program Files\Newport\Newport USB Driver\Bin\usbdll.dll")
            #print(self.LIBNAME)
            self.lib = windll.LoadLibrary(self.LIBNAME)
            self.product_id = kwargs.get('product_id',0xCEC7)
        except WindowsError as e:
            print(e.strerror)
            sys.exit(1)
            # raise CommandError('could not open detector library will all the functions in it: %s' % LIBNAME)

        self.open_device_with_product_id()
        self.instrument = self.get_instrument_list()  # here instrument[0] is the device id, [1] is the model number and [2] is the serial number
        [self.device_id, self.model_number, self.serial_number] = self.instrument
        self.clearBuffer() #Clear DLL buffer or else text from previous program run will show up in next run

    def open_device_all_products_all_devices(self):

        status = lib.newp_usb_init_system()  # SHould return a=0 if a device is connected
        if status != 0:
            raise CommandError()
        else:
            print('Success!! your are conneceted to one or more of Newport products')

    def open_device_with_product_id(self):
        """
        opens a device with a certain product id

        """
        cproductid = c_int(self.product_id)
        useusbaddress = c_bool(1)  # We will only use deviceids or addresses
        num_devices = c_int()
        try:
            status = self.lib.newp_usb_open_devices(cproductid, useusbaddress, byref(num_devices))

            if status != 0:
                self.status = 'Not Connected'
                raise CommandError("Make sure the device is properly connected")
            else:
                #print('Number of devices connected: ' + str(num_devices.value) + ' device/devices')
                self.status = 'Connected'
        except CommandError as e:
            print(e)
            sys.exit(1)

    def close_device(self):
        """
        Closes the device


        :raise CommandError:
        """
        status = self.lib.newp_usb_uninit_system()  # closes the units
        if status != 0:
            raise CommandError()
        else:
            print('Closed the newport device connection. Have a nice day!')

    def get_instrument_list(self):
        arInstruments = c_int()
        arInstrumentsModel = c_int()
        arInstrumentsSN = c_int()
        nArraySize = c_int()
        try:
            status = self.lib.GetInstrumentList(byref(arInstruments), byref(arInstrumentsModel), byref(arInstrumentsSN),
                                                byref(nArraySize))
            if status != 0:
                raise CommandError('Cannot get the instrument_list')
            else:
                instrument_list = [arInstruments.value, arInstrumentsModel.value, arInstrumentsSN.value]
                #print('Arrays of Device Id\'s: Model number\'s: Serial Number\'s: ' + str(instrument_list))
                return instrument_list
        except CommandError as e:
            print(e)


    def ask(self, query_string):

        """
        Write a query and read the response from the device
        :rtype : String
        :param query_string: Check Manual for commands, ex '*IDN?'
        :return: :raise CommandError:
        """
        answer = ''
        query = create_string_buffer(bytes(query_string, 'utf-8'))
        leng = c_ulong(sizeof(query))
        cdevice_id = c_long(self.device_id)
        status = self.lib.newp_usb_send_ascii(self.device_id, byref(query), leng)
        if status != 0:
            raise CommandError('Something apperars to be wrong with your query string')
        else:
            pass
        time.sleep(0.1)
        response = create_string_buffer(bytes(('\000' * 1024), 'utf-8'))
        leng = c_ulong(1024)
        read_bytes = c_ulong()
        status = self.lib.newp_usb_get_ascii(cdevice_id, byref(response), leng, byref(read_bytes))
        if status != 0:
            raise CommandError('Connection error or Something apperars to be wrong with your query string')
        else:
            answer = response.value[0:read_bytes.value].rstrip(bytes('\r\n', 'utf-8'))
            answer = str(answer, 'utf-8') #Convert byte string to string
        return answer

    def clearBuffer(self):
        status = 0
        while status is 0:
            cdevice_id = c_long(self.device_id)
            response = create_string_buffer(bytes(('\000' * 1024), 'utf-8'))
            leng = c_ulong(1024)
            read_bytes = c_ulong()
            status = self.lib.newp_usb_get_ascii(cdevice_id, byref(response), leng, byref(read_bytes))

    def write(self, command_string):
        """
        Write a string to the device

        :param command_string: Name of the string to be sent. Check Manual for commands
        :raise CommandError:
        """
        command = create_string_buffer(bytes(command_string, 'utf-8'))
        length = c_ulong(sizeof(command))
        cdevice_id = c_long(self.device_id)
        status = self.lib.newp_usb_send_ascii(cdevice_id, byref(command), length)
        try:
            if status != 0:
                raise CommandError('Connection error or  Something apperars to be wrong with your command string')
            else:
                pass
        except CommandError as e:
            print(e)

    def set_wavelength(self, wavelength):
        """
        Sets the wavelength on the device
        :param wavelength: float
        """
        if isinstance(wavelength, float) == True:
            print('Warning: Wavelength has to be an integer. Converting to integer')
            wavelength = int(wavelength)
        if wavelength >= int(self.ask('PM:MIN:Lambda?')) and wavelength <= int(self.ask('PM:MAX:Lambda?')):
            self.write('PM:Lambda ' + str(wavelength))
        else:
            print('Wavelenth out of range, use the current lambda')

    def set_filtering(self, filter_type=0):
        """
        Set the filtering on the device
        :param filter_type:
        0:No filtering
        1:Analog filter
        2:Digital filter
        3:Analog and Digital filter
        """
        if isinstance(filter_type, int) == True:
            if filter_type == 0:
                self.write('PM:FILT 0')  # no filtering
            elif filter_type == 1:
                self.write('PM:FILT 1')  # Analog filtering
            elif filter_type == 2:
                self.write('PM:FILT 2')  # Digital filtering
            elif filter_type == 1:
                self.write('PM:FILT 3')  # Analog and Digital filtering

        else:  # if the user gives a float or string
            print('Wrong datatype for the filter_type. No filtering being performed')
            self.write('PM:FILT 0')  # no filtering

    def read_buffer(self, wavelength=700, buff_size=1000, interval_ms=1):

        """
        Stores the power values at a certain wavelength.
        :param wavelength: float: Wavelength at which this operation should be done. float.
        :param buff_size: int: nuber of readings that will be taken
        :param interval_ms: float: Time between readings in ms.
        :return: [actualwavelength,mean_power,std_power]
        """
        #Check that the probe status is good
        while True:
            try:
                status = self.ask("PM:PWS?")
                print(status)
                status = int(status.split(", ")[1], 16) #Convert hex string to int
                
                if(status & 1): #If bit(0) is 1 - detector is saturating
                    print("WARNING: Detector is saturating, please turn off light source immediately!")
                    quit()
                elif(status & 4): #If bit(3) is 1 - detector is ranging
                    print("Waiting for detector to finish ranging...")
                else:
                    break
            except:
                pass
            
        #Measure power
        self.set_wavelength(wavelength)
        self.write('PM:DS:Clear')
        self.write('PM:DS:SIZE ' + str(buff_size))
        self.write('PM:DS:INT ' + str(interval_ms * 10))  # to set 1 ms rate we have to give int value of 10. This is strange as manual says the INT should be in ms
        self.write('PM:DS:ENable 1')
        while int(self.ask('PM:DS:COUNT?')) < buff_size:  # Waits for the buffer is full or not.
            time.sleep(0.001 * interval_ms * buff_size / 10)
        min_power = self.ask('PM:STAT:MIN?')
        max_power = self.ask('PM:STAT:MAX?')
        mean_power = self.ask('PM:STAT:MEAN?')
        std_power = self.ask('PM:STAT:SDEV?')
        self.write('PM:DS:Clear')
        return {"Min": min_power, "Max": max_power, "Mean": mean_power, "StDev": std_power}

    def read_instant_power(self, wavelength=700):
        """
        reads the instanenous power
        :param wavelength:
        :return:[actualwavelength,power]
        """
        self.set_wavelength(wavelength)
        actualwavelength = self.ask('PM:Lambda?')
        power = self.ask('PM:Power?')
        return [actualwavelength, power]


    def sweep(self, swave, ewave, interval, buff_size=1000, interval_ms=1):

        """
        Sweeps over wavelength and records the power readings. At each wavelength many readings can be made
        :param swave: int: Start wavelength
        :param ewave: int: End Wavelength
        :param interval: int: interval between wavelength
        :param buff_size: int: nunber of readings
        :param interval_ms: int: Time betweem readings in ms
        :return:[wave,power_mean,power_std]
        """
        self.set_filtering()  # make sure their is no filtering
        data = []
        num_of_points = (ewave - swave) / (1 * interval) + 1

        for i in np.linspace(swave, ewave, num_of_points, dtype='int'):
            data.extend(self.read_buffer(i, buff_size, interval_ms))
        data = [float(x) for x in data]
        wave = data[0::3]
        power_mean = data[1::3]
        power_std = data[2::3]
        return [wave, power_mean, power_std]

    def sweep_instant_power(self, swave, ewave, interval):

        """
        Sweeps over wavelength and records the power readings. only one reading is made
        :param swave: int: Start wavelength
        :param ewave: int: End Wavelength
        :param interval: int: interval between wavelength
        :return:[wave,power]
        :return:
        """
        self.set_filtering(self.device_id)  # make sure there is no filtering
        data = []
        num_of_points = (ewave - swave) / (1 * interval) + 1
        import numpy as np

        for i in np.linspace(swave, ewave, num_of_points).astype(int):
            data.extend(self.read_instant_power(i))
        data = [float(x) for x in data]
        wave = data[0::2]
        power = data[1::2]
        return [wave, power]
    
    def plotter_multisample(self, data):
        plt.close('All')
        sampleOrder = list(range(len(data[0])))
        for a in range(len(data)):
            plt.plot(sampleOrder, data[a], linewidth=1)
            plt.draw()
        plt.show()

    def plotter(self, data):
        plt.close('All')
        print(data["Int"])
        plt.errorbar(data["Int"], data["Mean"], data["StDev"], fmt='ro')
        plt.show()

    def plotter_spectra(self, dark_data, light_data):
        plt.close('All')
        plt.errorbar(dark_data[0], dark_data[1], dark_data[2], fmt='ro')
        plt.errorbar(light_data[0], light_data[1], light_data[2], fmt='go')
        plt.show()

    def console(self):
        """
        opens a console to send commands. See the commands in the user manual.

        """
        #print('You are connected to the first device with deviceid/usb address ' + str(self.serial_number))
        cmd = None
        while cmd != '':
            cmd = input('Newport console, Type command or press <Enter> to leave> ')
            if cmd.find('?') >= 0:
                answer = self.ask(cmd)
                print(answer)
            elif cmd.find('?') < 0 and cmd != '':
                self.write(cmd)
        else:
            print("Exiting the Newport console")

#------------------------------------------------------Generate calibration image set--------------------------------------------------------------------------------
def getDir(): #https://stackoverflow.com/questions/19944712/browse-for-file-path-in-python
    root = Tk()
    root.withdraw()
    currdir = os.getcwd()
    #outDir = filedialog.askdirectory(parent=root, initialdir=currdir, title='Please select an output directory')
    outDir = "C:/Users/User/Desktop/Calibration 1/"
    osPlatform = sys.platform
    if 'win32' in sys.platform:
        outDir += "/"
    print(outDir)
    root.destroy() #Destroy Tk, or else its unclosed mainloop will mess up pyplot
    return outDir

def drawImage(intensity):
    #Display image
    event = pygame.event.poll() #Prevent OS from thinking display is hanging
    screen.fill(intensity)
    pygame.display.flip() #Refresh display

def setup(useDefaults):
    global setupDic
    global nBin
    global nSample
    global readDelay
    global baseColor
    
    def getNum(text):
        num = -1
        while num < 1:
            num = input(text)
            try:
                num=int(num)
            except ValueError:
                print("ERROR: The wavelength must be an integer value.")
                num=-1
        return num

    def getBool(text):
        while True:
            bool = input(text).lower()
            if bool.startswith("y") and "n" not in bool:
                bool = 1
                return bool
            elif bool.startswith("n") and "y" not in bool:
                bool = 0
                return bool
            else:
               print("ERROR: The answer must be \"yes\" or \"no\".")
        
    if useDefaults:
        useDefaults = getBool("Would you like to use the default values (\"yes\" or \"no\")>")
        
        if not useDefaults: #If no, allow user to enter default values
            #Select whether attenuator is present
            setupDic["ATT"] = getBool("Is the attenuator in use (\"yes\" or \"no\")>")
        
            #Get wavelength
            minL = int(nd.ask('PM:MIN:Lambda?'))
            maxL = int(nd.ask('PM:MAX:Lambda?'))
            wl = -1
            while wl < minL or wl > maxL:
                wl = input("Please enter the wavelength (" + str(minL) + "-" + str(maxL) + ")>")
                try:
                    wl=int(wl)
                except ValueError:
                    print("ERROR: The wavelength must be an integer value.")
                    wl=-1
            setupDic["Lambda"] = wl
                
            #Select the desired number of averages
            setupDic["DS:SIZE"] = getNum("Please enter the number of averages>")
            
            #Get protocol parameters
            nBin = getNum("Please enter the number of intensity steps to measure (ex: 256 for monitors)>")
            nSample = getNum("Please enter the number of replicate measurements to perform>")
            readDelay = getNum("Please enter the number of seconds to pause before taking a reading>")
            baseColor[0] = getBool("Do you want to analyze the RED channel (\"yes\" or \"no\")>")
            baseColor[1] = getBool("Do you want to analyze the GREEN channel (\"yes\" or \"no\")>")
            baseColor[2] = getBool("Do you want to analyze the BLUE channel (\"yes\" or \"no\")>")
            

    #Setup current state before zeroing    
    for key, value in setupDic.items():
        nd.write("PM:" + key + " " + str(value))
    
    #Get zero value if not yet set
    if setupDic["ZEROVAL"] <= 0:
        dummy = input("Zeroing: Please turn off the reference monitor and press <Enter>")
        zeroDic = nd.read_buffer(wavelength=setupDic["Lambda"], buff_size=setupDic["DS:SIZE"], interval_ms=setupDic["DS:INT"])
        setupDic["ZEROVAL"] = zeroDic["Mean"]
        nd.write("PM:ZEROVAL " + str(setupDic["ZEROVAL"]))
        input("Setup complete, please turn on monitor and press <Enter>.")

def saturationTest():
    os.system('taskkill /f /im explorer.exe') #Remove taskbar
    num = None
    while num is not '':
        num = input("Input test intensity or press <Enter> to quit>")
        try:
            num=int(num)
        except ValueError:
            break
        drawImage((0,num,0))
        
    pygame.display.quit()
    pygame.quit()
    # Close the device
    nd.close_device()

    #Restore taskbar
    os.system('explorer.exe')
    quit()

def countdown(cycle):
    os.system('taskkill /f /im explorer.exe') #Remove taskbar
    input("Press <Enter> to start countdown>")
    for a in range(cycle):
        i = 255*(a%2)
        drawImage((i, i, i))
        time.sleep(1)
    
if __name__ == '__main__':    
    pygame.init() #Start pygame
        
    # Initialze a instrument object. You might have to change the LIBname or product_id.    
    nd = Newport_1918c(LIBNAME = r"C:\Program Files\Newport\Newport USB Driver\Bin\usbdll.dll",product_id=0xCEC7 )
    # Print the status of the newport detector.
    #print(nd.status)

    if nd.status == 'Connected':
        #print('Serial number is '+ str(nd.serial_number))
        #print('Model name is ' + str(nd.model_number))

        # Print the IDN of the newport detector.
        print('Connected to ' + nd.ask('*IDN?'))
        print("Make sure to use the attenuator if the output is over 4.0 mW!")
        
        #Set constants############################################################################################################################
        nBin = 256
        nSample = 5
        readDelay = 2
        baseColor = [False, True, False] #Which base colors to include in image - red, green, blue
        
        #Get output directory for calibration info
        setupDic = {"MODE": 0, "ANALOGFILTER": 0, "DIGITALFILTER": 0, "AUTO": 1, "UNITS": 2, "DS:INT": 1, "Lambda": 530, "ATT": 0, "DS:SIZE": 2000, "ZEROVAL": 0}
        setup(True)
        
        #Get output directory
        outDir = getDir()
        
        #Initialize pygame window
        displayObj = pygame.display.Info()
        screen = pygame.display.set_mode((displayObj.current_w, displayObj.current_h),  pygame.FULLSCREEN)
        #screen = pygame.display.set_mode((displayObj.current_w, displayObj.current_h))
        pygame.mouse.set_visible(False)
        event = pygame.event.poll() #Keep OS from timing out pygame window
        
        #saturationTest()###############################MANUAL MODE#########################
        
        #Print calibration setup
        with open(outDir + "Calibration Setup - " + str(datetime.now())[:10] + ".txt", "w+") as f:
            setup = str(setupDic)[1:-1].split(", ")
            f.write("Power meter configuration: \n")
            for line in setup:
                f.write(line + "\n")
            f.write("------------------------------------\n")
            f.write("Protocol parameters: \n")
            f.write("Maximum pixel intensity: " + str(nBin) + "\n")
            f.write("Number of samples: " + str(nSample) + "\n")
            f.write("Read delay (s): " + str(readDelay) + "\n")

        countdown(20)
        
        #Measure monitor intensities
        powerArray = OrderedDict()
        plotList = [([None]*nBin) for i in range(nSample)]
        sampleOrder = list(range(nBin)) 
        startTime = time.time()
        for b in range(nSample):
            powerArray = {"Int": [None]*nBin, "Min": [None]*nBin, "Max": [None]*nBin, "Mean": [None]*nBin, "StDev": [None]*nBin} #Initialize measurement matrix
            random.seed(b) #Set seed so random order is identical between monitors
            random.shuffle(sampleOrder)
            with open(outDir + "Calibration " + str(b+1) + " of " + str(nSample) + " - " + str(datetime.now())[:10] + ".xls", "w+") as f: #Create results file
                for key, value in powerArray.items(): #Write header to reults file
                    f.write(key + "\t")
                f.write("\n")
                for a in range(nBin):
                    #Print progress updates
                    percent = round(100*(((b*nBin)+a)/(nSample*nBin)), 1)
                    print("Testing image " + str(a+1) + " of " + str(nBin) + ", Sample " + str(b+1) + " of " + str(nSample) + ", " + str(percent) + "% complete.")
                    if percent > 0:
                        timeLeft = str(timedelta(seconds=((time.time() - startTime)*((100-percent)/percent))))
                        print("Approximate time remaining (minutes): " + timeLeft)
                    
                    index = sampleOrder[a] #Get next index in shuffled list
                    
                    color = (int(baseColor[0]*index), int(baseColor[1]*index), int(baseColor[2]*index)) 
                    drawImage(color) #Create new image
                    time.sleep(readDelay) #Wait for meter to stabilize
                    
                    tempDic = nd.read_buffer(wavelength=setupDic["Lambda"], buff_size=setupDic["DS:SIZE"], interval_ms=setupDic["DS:INT"]) #Gte reading
                    print(str(tempDic)[1:-1] + ", 'Int': " + str(color))
                    for key, value in tempDic.items(): #parse reading
                        powerArray[key][index] = float(tempDic[key])
                    powerArray["Int"][index] = color
                    
                for a in range(nBin):
                    for key, value in powerArray.items(): #send to file
                        f.write(str(value[a]) + "\t")
                    f.write("\n")
                    
                plotList[b] = powerArray["Mean"] #Export mean meansurements to plot list
        
        with open(outDir + "Calibration Setup - " + str(datetime.now())[:10] + ".txt", "a") as f:
            f.write("Total duration of calibration: " + str(timedelta(seconds=(time.time() - startTime))))
        
        #Generate final LUT from average of sample reads
        calibrationLUT = [0]*nBin
        for b in range(nBin):
            for a in range(nSample):
                calibrationLUT[b] += plotList[a][b]
        for a in range(nBin):
            calibrationLUT[a] /= nSample
        
        #Output the calibration LUT
        with open(outDir + "Calibration LUT - " + str(datetime.now())[:10] + ".txt", "w+") as f:
            f.write("Int,Power,\n")
            for a in range(nBin):
                f.write(str(powerArray["Int"][a]) + "," + str(calibrationLUT[a]) + ",\n")
        
        #Close pygame display
        pygame.display.quit()
        pygame.quit()
        
        #Plot results
        nd.plotter_multisample(plotList)
        
        # opens a console
        nd.console()

        # Close the device
        nd.close_device()

        #Restore taskbar
        os.system('explorer.exe')
        # sweep the wavelength of the detector from 500 to 550 with an interval of 10 nm. At each wavelength the buffer size is 10 and the time between samples is 1 ms
        #light_data = nd.sweep(500, 550, 10, buff_size=10, interval_ms=1)
        #nd.plotter_spectra(dark_data, light_data)

        # Give the instant_power
        #data = nd.sweep_instant_power(400, 410, 2)
        #nd.plotter_instantpower(data)



    else:
        nd.status != 'Connected'
        print('Cannot connect.')
        



