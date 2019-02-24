# !/usr/bin/env/python3.6

import os
from random import randint
from shutil import copyfile


mountDir = '/mnt/usb/' #where the usb is mounted
mounted = None
try: 
    os.listdir(mountDir) #check if usb is mounted
except FileNotFoundError:
    mountDir = False 
else:
    mountDir = True

#condition that number is positive
positive_condition = lambda x: int(x) > 0

#get an input number subject to a condition
def inputDigit(message, condition=lambda x: True):
    d = None
    while not d or not d.isdigit() or not condition(d):
        d = input(message)
    d = int(d)
    return d

#ask user if would like to use presets
##presets implemented for 4 nights as per email
def usePresets():
    global images_and_times #list of images and duration of exposure
    global fixed_times      #are times fixed or within a range
    global fixed_order      #order fixed or random
    global off_img          #(optional) image to be shown when screen is 'off', i.e. black image
    global off_time         #duration of off image
    global reward_set       #images that are rewards
    global off_interperse   #use with fixed order. Is Off image interspersed or at the end of the cycle
    global off_spacing      #use without fixed order. After how many images should off image be shown

    preset = 0
    #get which preset use wants or exit upon request
    while preset not in range(1, 5):
        preset = input('Enter preset from nights 1-4 (exit to leave preset menu): ')
        if preset == 'exit':
            return False
        if preset.isdigit():
            preset = int(preset)
        else:
            print('Integers or "exit" only!')
            preset = 0

    if preset == 1:
        images_and_times = {'gray.png': experiment_length}
        fixed_order = True
        reward_set = ['gray.png']
        off_img = None
        fixed_times = True

    elif preset == 2:
        images_and_times = {'gray.png': 60, 'vertical_bw.png': 60, 'horizontal_bw.png': 60}
        fixed_order = True
        reward_set = ['vertical_bw.png']
        off_img = 'black.png'
        off_time = 420
        fixed_times = True
        off_interperse = False


    elif preset == 3:
        images_and_times = {'gray.png': 30, 'vertical_bw.png': 30, 'horizontal_bw.png': 30}
        fixed_order = False
        reward_set = ['vertical_bw.png']
        off_img = 'black.png'
        off_time = 120
        fixed_times = True
        off_spacing = 1

    else:
        min_duration = 12
        max_duration = 120
        images_and_times = {'gray.png': (min_duration, max_duration), 'vertical_bw.png': (min_duration, max_duration), 'horizontal_bw.png': (min_duration, max_duration)}
        fixed_order = False
        reward_set = ['vertical_bw']
        off_img = None
        fixed_times = False

    return preset


def getNewProtocol():
    global images_and_times #list of images and duration of exposure
    global fixed_times      #are times fixed or within a range
    global fixed_order      #order fixed or random
    global off_img          #(optional) image to be shown when screen is 'off', i.e. black image
    global off_time         #duration of off image
    global reward_set       #images that are rewards
    global off_interperse   #use with fixed order. Is Off image interspersed or at the end of the cycle
    global off_spacing      #use without fixed order. After how many images should off image be shown

    directory = input('Enter directory where images are stored: ')
    if not directory.endswith('/'):
        directory += '/'

    fixed_times = input('Fixed times for images? (yes/no): ').lower().startswith('y')

    images_and_times = {}
    reward_set = []
    fixed_order = input('Fixed order? (yes/no): ').lower().startswith('y')

    if fixed_times:

        dir_contents = next(os.walk(directory))[2]
        dir_contents.sort()
        for f in dir_contents: #iterate through directory images, get info for display

            if f.endswith('.png') or f.endswith('.jpg') or f.endswith('.tif'):
                
                img_type = input('What is image {0}? Control (c), Reward (r), Off (o), Remove from list (x), Finish list (f): '.format(f)).lower()
                if img_type.startswith('x'): #removes image from list
                    continue
                if img_type.startswith('f'): #stops iterating through directory
                    break

                duration = inputDigit('Length of display for image {0}: '.format(f), positive_condition)

                if img_type.startswith('o'): #off image
                    off_img = f 
                    off_time = duration 
                elif img_type.startswith('r'): #reward image
                    images_and_times[f] = duration 
                    reward_set.append(f)
                elif img_type.startswith('c'): #control image
                    images_and_times[f] = duration
                else:
                    pass

    else:

        dir_contents = next(os.walk(directory))[2]
        dir_contents.sort()
        for f in dir_contents: #iterate through directory images, get info for display
            if f.endswith('.png') or f.endswith('.jpg') or f.endswith('.tif'):

                def valid(duration):
                    if duration is None or type(duration) != tuple:
                        return False
                    i, j = duration
                    try:
                        i, j = int(i), int(j)
                    except ValueError:
                        return False
                    else:
                        return i <= j

                duration = None

                img_type = input('What is image {0}? Control (c), Reward (r), Off (o), Remove from list (x), Finish list (f): '.format(f)).lower()
                if img_type.startswith('x'): #removes image from list
                    continue
                if img_type.startswith('f'): #stops iterating through directory
                    break

                while not valid(duration):
                    duration = (inputDigit('Minimum length of display for image {0}: '.format(f)), inputDigit('Maximum length of display for image {0}: '.format(f)))

                if img_type.startswith('o'):
                    off_img = f 
                    off_time = duration
                elif img_type.startswith('r'):
                    images_and_times[f] = duration
                    reward_set.append(f)
                elif img_type.startswith('c'):
                    images_and_times[f] = duration
                else:
                    pass

    images = list(images_and_times.keys())
    if mounted:
        if 'images' not in os.listdir(mountDir):
            os.mkdir(mountDir + 'images/')
        for img in images:
            try:
                copyfile(directory + img, mountDir + 'images/' + img)
            except:
                print('could not copy '+ img+ ' to usb')


    if off_img:
        if fixed_order:
            off_interperse = input('Should off image be at the end of cycle (e) or after each image (a)?: ').lower().startswith(a)
        else:
            off_spacing = inputDigit('Off image will be shown after every n (integer) images: ', positive_condition)


def generateSequence_fixedOrder():

    sequence_imgs = [] #final sequence of images through entirety of experiment
    sequence_times = [] #final sequence of duration of image displays through entirety of experiment
    total_time = 0
    images = list(images_and_times.keys())
    k = 0

    while total_time < experiment_length:

        img = images[k % len(images)] # % allows for wrapping around the array
        k += 1
        duration = images_and_times[img]
        if type(duration) == tuple:
            duration = randint(duration[0], duration[1]) #duration within specified range if time is not fixed

        sequence_imgs.append(img)
        sequence_times.append(duration)
        total_time += duration

        if total_time > experiment_length:
            break

        if off_img and (off_interperse or k % len(images) == 0):
            sequence_imgs.append(off_img)
            duration = off_time
            if type(duration) == tuple: #if time is variable, get random value within range
                duration = randint(duration[0], duration[1]) #duration within specified range if time not fixed
            sequence_times.append(duration)
            total_time += duration

    return sequence_imgs, sequence_times


def generateSequence_noOrder():

    sequence_imgs = [] #final sequence of images through entirety of experiment
    sequence_times = [] #final sequence of duration of image displays through entirety of experiment
    total_time = 0
    images = list(images_and_times.keys())

    k, previous = -1, -1
    count = 0
    while total_time < experiment_length:
        if off_img:
            k = randint(0, len(images) - 1)
            count += 1
        else: 
            while k != previous:
                k = randint(0, len(images) - 1)
            previous = k

        img = images[k]
        duration = images_and_times[img]
        if type(duration) == tuple:
            duration = randint(duration[0], duration[1]) #duration within specified range if time not fixed

        sequence_imgs.append(img)
        sequence_times.append(duration)
        total_time += duration

        if total_time > experiment_length:
            break

        if off_img and count == off_spacing:
            count = 0
            sequence_imgs.append(off_img)
            duration = off_time
            if type(duration) == tuple: 
                duration = randint(duration[0], duration[1]) #duration within specified range if time not fixed
            sequence_times.append(duration)
            total_time += duration

    return sequence_imgs, sequence_times


def generateFile(wheel_trigger, wheel_interval, reward_duration, metadata):

    if fixed_order:
        sequence_imgs, sequence_times = generateSequence_fixedOrder()

    else:
        sequence_imgs, sequence_times = generateSequence_noOrder()

    if mounted:
        pfileName = mountDir + 'Protocol.txt'
    else:
        pfileName = 'Protocol.txt'

    with open(pfileName, 'w') as pfile: #write protocol specs to protocol file
        pfile.write('image: [%s]' % ', '.join(map(str, sequence_imgs)))
        pfile.write('\n')
        pfile.write('time: [%s]' % ', '.join(map(str, sequence_times)))
        pfile.write('\n')
        pfile.write('reward: [%s]' % ', '.join(map(str, reward_set)))
        pfile.write('\n')
        pfile.write('wheel trigger: {0}'.format(wheel_trigger))
        pfile.write('\n')
        pfile.write('reward duration: {0}'.format(reward_duration))
        pfile.write('\n')
        pfile.write('wheel interval: {0}'.format(wheel_interval))
        pfile.write('\n')
        pfile.write('This is metadata............')
        pfile.write('\n')
        pfile.write(metadata)
    


def main():
    global experiment_length
    global images_and_times
    global fixed_times
    global fixed_order
    global off_img
    off_img = None
    global off_time
    global reward_set
    global off_interperse #for use with fixed order
    global off_spacing #for use with no fixed order
    
    experiment_length = inputDigit("Enter experiment length in HOURS: ", positive_condition)
    experiment_length *= (60**2) #convert hours to seconds

    wheel_trigger = input('Wheel trigger (yes/no): ').lower().startswith('y')
    wheel_interval = inputDigit('Wheel interval (seconds): ', positive_condition)
    reward_duration = inputDigit('Duration of reward (seconds): ', positive_condition)
    metadata = input('Enter any metadata: ')

    presets = input('Use preset protocol? (yes/no): ').lower().startswith('y') #use pre-defined protocols for nights 1-4
    loadedProtocol = False
    if presets:
        loadedProtocol = usePresets()
    if not loadedProtocol:
        getNewProtocol()

    generateFile(wheel_trigger, wheel_interval, reward_duration, metadata)



if __name__ == '__main__':
    main()


