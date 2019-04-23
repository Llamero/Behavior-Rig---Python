from tkinter import Tk, filedialog
from re import search
import matplotlib.pyplot as plt #plot results
from statistics import mean, median
from os import listdir
import seaborn as sb #plot swarmplot
from math import inf #Allow for infinity value

testWindow = 25
pumpCutoffs = [0.5, 1, inf] #Maximum duration of each event in seconds for each raster bin
maxPumpInterval = 5 #Maximum time between door events to count as new set
rasterLineWidth = 0.8

#Get input directory
root = Tk()
root.withdraw() #Hide the root window
inDir = filedialog.askdirectory()
root.destroy() #Close Tk window

#Find all results files in directory
fileList = []
for file in listdir(inDir):
    if search(r"^Results - 20[1-2][0-9]-[0-1][0-9]-[0-3][0-9] [0-9a-f]{32}\.txt$",file):
        fileList.append(inDir + "/" + file)

wheelIntervalArray = [None]*4
wheelStatArray = [None]*4

pumpDurationArray = [None]*4
pumpEventsPerInterval = [None]*4
pumpTimeBetweenEvents = [None]*4
pumpIntervalDuration = [None]*4
pumpStatArray = [None]*4
pumpRasterColors = [[1,0,0],[1,1,0],[0,1,0]]*4
pumpRasterArray = [[] for i in range(len(pumpRasterColors))]
staggerRasters = True
pumpRasterOffsets = [int(i/len(pumpCutoffs))+1 for i in range(len(pumpRasterColors))]
pumpRasterLength = [rasterLineWidth]*len(pumpRasterColors)
if staggerRasters:
    newLineWidth = rasterLineWidth/len(pumpCutoffs)
    offset = 0-(rasterLineWidth)/2
    for a in range(len(pumpRasterColors)):
         pumpRasterLength[a] = newLineWidth
         rBin = a%len(pumpCutoffs)
         rCage = int(a/len(pumpCutoffs))+1
         pumpRasterOffsets[a] = rCage + offset + newLineWidth*(rBin+0.5)
         


for file in fileList:
    #Parse file
    wheelArray = []
    pumpArray = {"Time between events": [], "Single pump event duration": [], "Events per Interval": [], "Interval duration": [], "Event start time": []}
    pumpIntervalStart = 0
    pumpEventCount = 0
    pumpEnd = 0
    pumpStart = 0
    cageID = None
    
    with open(file) as f:
        for line in f:
            if line.startswith("Wheel - State: High, Time: "):
                wheelArray.append(float(search(r"\d+\.\d+", line).group(0)))
            elif line.startswith(r"Pump - State: "):
                if line.startswith(r"Pump - State: On, Time: "):
                    pumpStart = float(search(r"\d+\.\d+", line).group(0))
                    pumpArray["Event start time"].append(pumpStart)
                    if pumpStart > (pumpEnd + maxPumpInterval):
                        pumpArray["Events per Interval"].append(pumpEventCount)
                        pumpArray["Time between events"].append(pumpStart-pumpEnd)
                        pumpArray["Interval duration"].append(pumpEnd-pumpIntervalStart)
                        pumpIntervalStart = pumpStart
                        pumpEventCount = 0
                else:
                    pumpEnd = float(search(r"\d+\.\d+", line).group(0))
                    pumpArray["Single pump event duration"].append(pumpEnd-pumpStart)
                    pumpEventCount += 1
            elif not cageID:
                if line.startswith("USB drive ID: CAGE "):
                    cageID = search(r"CAGE [1-4]", line).group(0)       
            else:
                pass
                    

    #Generate a list of interval times
    wheelInterval = []
    cageNum = int(cageID[-1:])
    for a in range(len(wheelArray)-testWindow):
        wheelInterval.append(wheelArray[a+testWindow-1]-wheelArray[a])

    wheelIntervalArray[cageNum-1] = wheelInterval
    wheelStatArray[cageNum-1] = [cageNum, min(wheelInterval),max(wheelInterval),mean(wheelInterval),median(wheelInterval)]  
    
    pumpDurationArray[cageNum-1] = pumpArray["Single pump event duration"]
    pumpStatArray[cageNum-1] = [cageNum, min(pumpArray["Single pump event duration"]),max(pumpArray["Single pump event duration"]),mean(pumpArray["Single pump event duration"]),median(pumpArray["Single pump event duration"]), sum(pumpArray["Single pump event duration"]), len(pumpArray["Single pump event duration"])]  
    pumpEventsPerInterval[cageNum-1] = pumpArray["Events per Interval"]
    pumpTimeBetweenEvents[cageNum-1] = pumpArray["Time between events"]
    pumpIntervalDuration[cageNum-1] = pumpArray["Interval duration"]
    
    #Sort the pump events into the raster array
    nColors = len(pumpRasterColors)/4
    for a in range(len(pumpArray["Single pump event duration"])):
        for b in range(len(pumpCutoffs)):
            if pumpArray["Single pump event duration"][a] < pumpCutoffs[b]:
                pumpRasterArray[((cageNum-1)*len(pumpCutoffs))+b].append(pumpArray["Event start time"][a])
                break
            
a=0
xWheelLabelArray = [None]*4
xWheelTick = [None]*4
for stats in wheelStatArray:
    wheelStatString = ''
    i = 0
    wheelStatString += "CAGE " + str(stats[i]) + ":\n"
    i+=1
    wheelStatString += "Min Interval: " + str(round(stats[i])) + "   \n"
    i+=1
    wheelStatString += "Max Interval: " + str(round(stats[i])) + "   \n"
    i+=1
    wheelStatString += "Mean Interval: " + str(round(stats[i])) + "   \n"
    i+=1
    wheelStatString += "Median Interval: " + str(round(stats[i])) + "   \n"
    xWheelLabelArray[a] = wheelStatString
    xWheelTick[a] = stats[0]
    a+=1

a=0
xPumpLabelArray = [None]*4
xPumpTick = [None]*4
for stats in pumpStatArray:
    pumpStatString = ''
    i = 0
    pumpStatString += "CAGE " + str(stats[i]) + ":\n"
    i+=1
    pumpStatString += "Min Duration: " + str(round(stats[i], 1)) + "   \n"
    i+=1
    pumpStatString += "Max Duration: " + str(round(stats[i], 1)) + "   \n"
    i+=1
    pumpStatString += "Mean Duration: " + str(round(stats[i], 1)) + "   \n"
    i+=1
    pumpStatString += "Median Duration: " + str(round(stats[i], 1)) + "   \n"
    i+=1
    pumpStatString += "Total Duration: " + str(round(stats[i])) + "   \n"
    i+=1
    pumpStatString += "# of Events: " + str(stats[i]) + "   \n"
    xPumpLabelArray[a] = pumpStatString
    xPumpTick[a] = stats[0]-1 #Subtract 1 since Seaborn box plots start at 0
    a+=1

plt.close('All')

fig, ax = plt.subplots()
ax.boxplot(wheelIntervalArray, 1, '') #1 = notch, '' = no outliers
plt.title('Time to complete ' + str(testWindow) + " wheel rotations.")
plt.ylabel("Interval time (s)")
plt.ylim(bottom=10)
ax.semilogy()
plt.xticks(xWheelTick, xWheelLabelArray)
plt.tight_layout() #Autoscale window to remove overlap

#Rescale window to improve spacing
figWindow = plt.gcf().get_size_inches()
figWindow[0] = figWindow[0]*1.1
figWindow[1] = figWindow[1]*1.2
fig.set_size_inches(figWindow[0], figWindow[1])
plt.savefig(inDir + "/" + "Wheel summary.png")

fig, ax = plt.subplots()
sb.boxplot(data=pumpDurationArray, notch=True, showfliers=False, boxprops={'facecolor':'None'})
plt.title("Pump on duration")
plt.ylabel("On time (s)")
plt.xticks(xPumpTick, xPumpLabelArray)
ax.semilogy()

#Add swarm plot overlay
sb.swarmplot(data=pumpDurationArray, color=".25", size=2)

#Rescale window to improve spacing
plt.xticks(xPumpTick, xPumpLabelArray)
plt.tight_layout() #Autoscale window to remove overlap
figWindow = plt.gcf().get_size_inches()
figWindow[0] = figWindow[0]*1.2
figWindow[1] = figWindow[1]*1.2
fig.set_size_inches(figWindow[0], figWindow[1])




def make_patch_spines_invisible(axis):
    axis.set_frame_on(True)
    axis.patch.set_visible(False)
    for sp in axis.spines.values():
        sp.set_visible(False)
        
fig, axes = plt.subplots(2, 2) #Create 2x2 plot grid
plt.subplots_adjust(wspace=0.7, hspace=0.5, left=0.05, right=0.88)
i = 0
for a in range(2):
    for b in range(2):
        axes[a,b].set_title("CAGE " + str(pumpStatArray[i][0]))
        par1 = axes[a,b].twinx()
        par2 = axes[a,b].twinx()
        #par3 = axes[a,b].twinx()
        
        # Offset the right spine of par2.  The ticks and label have already been - https://matplotlib.org/gallery/ticks_and_spines/multiple_yaxis_with_spines.html
        # placed on the right by twinx above.
        par2.spines["right"].set_position(("axes", 1.15))
        #par3.spines["left"].set_position(("axes", -0.2))
        # Having been created by twinx, par2 has its frame off, so the line of its
        # detached spine is invisible.  First, activate the frame but make the patch
        # and spines invisible.
        make_patch_spines_invisible(par2)
        #make_patch_spines_invisible(par3)
        # Second, show the right spine.
        par2.spines["right"].set_visible(True)
        #par3.spines["left"].set_visible(True)
        
        #Move tick marks and labels of par3 to the left spine - https://stackoverflow.com/questions/20146652/two-y-axis-on-the-left-side-of-the-figure
        #par3.yaxis.set_label_position('left')
        #par3.yaxis.set_ticks_position('left')
        
        #Set drawing order - way in which lines overlap
        axes[a,b].set_zorder(1)
        par1.set_zorder(2)
        par2.set_zorder(3)
        #par3.set_zorder(4)
        
        #Plot data
        p0, = axes[a,b].plot(pumpIntervalDuration[i], "k-", label="Duration of burst events (s)")
        p1, = par1.plot(pumpEventsPerInterval[i], "g-", label="Events per Interval")
        p2, = par2.plot(pumpTimeBetweenEvents[i], "r-", label="Time between burst events (s)")
        #p3, = par3.plot(pumpDurationArray[i], "b-", label="Individual pump duration(s)")
        
        #Set axis lables
        axes[a,b].set_xlabel("Chronological order")
        axes[a,b].set_ylabel("Duration of burst events (s)")
        par1.set_ylabel("Events per Interval")
        par2.set_ylabel("Time between burst events (s)")
        #par3.set_ylabel("Individual pump duration(s)")
        
        #Make label font color match line color
        axes[a,b].yaxis.label.set_color(p0.get_color())
        par1.yaxis.label.set_color(p1.get_color())
        par2.yaxis.label.set_color(p2.get_color())
        #par3.yaxis.label.set_color(p3.get_color())

        axes[a,b].tick_params(axis='y', colors=p0.get_color())
        par1.tick_params(axis='y', colors=p1.get_color())
        par2.tick_params(axis='y', colors=p2.get_color())
        #par3.tick_params(axis='y', colors=p3.get_color())
        axes[a,b].tick_params(axis='x')
        
        i+=1

fig.suptitle("Pump burst events: Defined as " + str(maxPumpInterval) + " seconds maximum between each pump event")

#Rescale window to improve spacing
#plt.tight_layout() #Autoscale window to remove overlap
figWindow = plt.gcf().get_size_inches()
figWindow[0] = figWindow[0]*1.8
figWindow[1] = figWindow[1]*1.5
fig.set_size_inches(figWindow[0], figWindow[1])     

#Create raster plot of pump events
fig, axs = plt.subplots()
axs.eventplot(pumpRasterArray, colors=pumpRasterColors, lineoffsets=pumpRasterOffsets, linelengths=pumpRasterLength, orientation='vertical')
plt.show()
    
            


