#Video guide for setting up PyDrive: https://www.youtube.com/watch?v=j31iVbkknzM

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from re import search
from tkinter import Tk, constants, Label, Button, font, Scrollbar, Frame, StringVar, Radiobutton
from tkinter.ttk import Treeview
from collections import OrderedDict
from time import sleep

class driveFile:
    def __init__(self): #Initializing contructor
        #Authenticate Google Drive connection
        #Initialize and authenticate connection to Google Drive
        self.gauth = GoogleAuth()
        self.gauth.LocalWebserverAuth() # Creates local webserver and auto handles authentication.
        self.drive = GoogleDrive(self.gauth)

    def getRoot(self):
        #Get ID of behabior folder
        self.file_list = self.drive.ListFile({'q': 'sharedWithMe'}).GetList() #Get list of all files and folder in shared root directory
        self.behavior_folder = None
        for file in self.file_list:
            if search(r"^BEHAVIOR DATA \(APRIL 2019.*", file['title']) and file['mimeType']=='application/vnd.google-apps.folder': #Search for behavior folder
                print("FOLDER FOUND!")
                self.behavior_folder = file['id']
                return [{"Title": file['title'], "mimeType": file['mimeType'], "ID": file['id']}] #Return dictionary as list for consistency

    def getDir(self, drive_folder = None, file_pattern = ".*"):
        #Load behavior folder as default folder - https://stackoverflow.com/questions/1802971/nameerror-name-self-is-not-defined
        if drive_folder is None:
            drive_folder = self.behavior_folder

        # Define a correctly formatted PyDrive query string with placeholder for parent id.
        request_template = "'{parent_id}' in parents and trashed=false" #From https://stackoverflow.com/questions/42027653/use-pydrive-to-list-files-using-a-variable-holding-the-folder-ids-in-a-loop/42039637
        file_list = self.drive.ListFile({'q': request_template.format(parent_id=drive_folder)}).GetList()

        #Search everything in the directory that matches the pattern
        subdir_list = []
        for file in file_list:
            test_name = file['title']
            if search(file_pattern, test_name):
                subdir_list.append({"Title": file['title'], "mimeType": file['mimeType'], "ID": file['id']})

        return subdir_list

    def getFileAsString(self, file_id):
        file = self.drive.CreateFile({'id': file_id})
        file_list = file.GetContentString().split("\r\n")
        return (file_list)



class GUI:
    def __init__(self): #Based on treewalk code here: https://stackoverflow.com/questions/14404982/python-gui-tree-walk, and demo: https://stackoverflow.com/questions/36120426/tkinter-treeview-widget-inserting-data
        self.file_dic = {} #Dictionary for loading all of the files into  - Hierarchy: Genotype -> List by run -> list by day -> list of cages in order

        self.root = Tk() #Create GUI object
        self.frame_list = {}
        self.active_node = None #Record name of currently selected node in treeview
        self.file_dic = {} #Dictionary for loading all of the files into  - Hierarchy: Genotype -> List by run -> list by day -> list of cages in order
        self.results_node = None

        self.root.title("Google Drive")

        #Create treeview widget for file directory
        self.frame_list["Tree"] = Frame(master=self.root) #Create new frame for status and button
        self.frame_list["Tree"].pack(fill=constants.BOTH, expand=True, side=constants.TOP)
        self.tree = Treeview(self.frame_list["Tree"], columns=("MIME Type", "ID"), height=20) #Create Treeview widget - columns - set column names, displaycolumns - specifies which columns are shown
        self.tree["displaycolumns"]=("MIME Type",) #Show only the title and type column, hide the ID column - the trailing column is needed
        self.tree.heading('#0', text='Title')
        self.tree.heading('#1', text='MIME Type')
        #self.tree.heading('#2', text='ID')
        self.tree.column('#1', stretch=constants.NO, width=450)
        #self.tree.column('#2', stretch=constants.YES)
        self.tree.column('#0', stretch=constants.YES, width=450)
        self.tree.pack(fill=constants.BOTH, expand=True, side=constants.LEFT) #Fill frame when window is resized

        #Add scroll bar to tree
        self.tree_scroll = Scrollbar(self.frame_list["Tree"], command=self.tree.yview)
        self.tree_scroll.pack(side=constants.RIGHT, padx=5, pady=5, fill=constants.Y)
        self.tree.config(yscrollcommand=self.tree_scroll.set) #Scroll bar has to be set to be controlled by treeview

        #Add radio buttons to select day
        self.frame_list["Radio"] = Frame(master=self.root) #Create new frame for radio buttons
        self.frame_list["Radio"].pack(fill=constants.BOTH, expand=False, side=constants.TOP)
        self.radio_label = Label(self.frame_list["Radio"], text = "Please select day:", anchor=constants.W)
        self.radio_label.pack(side=constants.LEFT, padx=5, pady=5)
        self.title_font = font.Font(font=self.radio_label.cget("font"))
        self.font_size = self.title_font.actual()["size"]
        self.title_font.configure(size=round(self.font_size*1.2))
        self.radio_label.configure(font=self.title_font)
        self.day_var = StringVar() #Var to track selected checkbox
        self.day_var.set("Night #1") #Set "All" as default value
        self.radio_list = OrderedDict((("Night #1", None), ("Night #2", None), ("Night #3", None), ("Night #4", None), ("Refresher", None), ("Test", None), ("All", None))) #List to store radio button widgets
        for text in self.radio_list.keys():
            self.b = Radiobutton(self.frame_list["Radio"], text=text, variable=self.day_var, value=text, font=self.title_font, command=None)
            self.b.pack(fill=constants.BOTH, side=constants.LEFT, expand=True)
            self.radio_list[text] = self.b

        #Add status widget
        self.frame_list["Status"] = Frame(master=self.root) #Create new frame for status and button
        self.frame_list["Status"].pack(fill=constants.BOTH, expand=False, side=constants.TOP)
        self.title_label = Label(self.frame_list["Status"], text = "Please select directory or file:", anchor=constants.W, font=self.title_font)
        self.title_label.pack(side=constants.LEFT, padx=5, pady=5)

        #Create button
        self.gui_button = Button(self.frame_list["Status"], text="Analyze", command=self.getTreePosition, font=self.title_font, state="disabled")
        self.gui_button.pack(side=constants.RIGHT, padx=5, pady=5)

        #Populate tree widget and initialize event monitor
        self.driveDir = driveFile() #Create instance of Google Drive class
        self.createRoot() #Initialize tree with root folder
        self.tree.bind('<<TreeviewOpen>>', self.updateTree) #Update tree subdirectory on click of tree expansion icon
        self.tree.bind("<ButtonRelease-1>", self.updateGUI) #Log selected file on release, or else the prior selected file is returned
        self.root.mainloop()

    #Generate root directory
    def createRoot(self):
        root_data = self.driveDir.getRoot()
        node = self.tree.insert('', 'end', text=root_data[0]["Title"], values=(root_data[0]["mimeType"], root_data[0]["ID"]), open=True) #Parent, index,
        self.fillTree(node)

        #Search in root for results folder
        for child in self.tree.get_children(node):
            if self.tree.item(child)["text"] == "results":
                self.results_node = child
                break
        else:
            self.title_label.configure(text="ERROR: Results folder not found.")

    def updateTree(self, event):
        self.tree = event.widget
        self.fillTree(self.tree.focus())

    def fillTree(self, node):
        node_ID = self.tree.set(node, "ID")
        # Delete the possibly 'dummy' node present.
        self.tree.delete(*self.tree.get_children(node))

        parent = self.tree.parent(node)
        child_list = self.driveDir.getDir(node_ID)
        for f in sorted(child_list, key = lambda x: x['Title']): #Sort child files by name - https://stackoverflow.com/questions/47002558/downloading-all-of-the-files-in-a-specific-folder-with-pydrive?rq=1
            oid = self.tree.insert(node, 'end', text=f["Title"], values=(f["mimeType"], f["ID"]))
            if f["mimeType"] == "application/vnd.google-apps.folder":
                self.tree.insert(oid, 0, text='dummy')

    def updateGUI(self, event):
        #Get sleected focus
        self.tree = event.widget
        node = self.tree.focus()

        #If analyzable node is selected, record node
        if self.tree.set(node) and self.tree.set(node, "MIME Type") in ["application/vnd.google-apps.folder", "text/plain"] and self.results_node:
            self.active_node = node
            self.gui_button.config(state="normal")

            #Hide radiobuttons if text file or directory with "Night #" is selected
            title = self.tree.item(node)["text"] #Get name of node
            parent_node = self.tree.parent(node) #Get name of parent node
            parent_title = self.tree.item(parent_node)["text"]
            night_ID = [ID_str for ID_str in self.radio_list.keys() if ID_str in [title, parent_title]] #Check if node or parent node contain Night id
            if night_ID: #If night ID is found, hide radiobuttons and autoselect radio option
                self.day_var.set(night_ID[0])

                for key, value in self.radio_list.items():
                    value.config(state="disabled")
            else:
                for key, value in self.radio_list.items():
                    value.config(state="normal")

        #Otherwise, hide the analyze button
        else:
            self.active_node = None
            self.gui_button.config(state="disabled")

    def getTreePosition(self):
        #Get name of current node to find position in heirarchy
        node_title = self.tree.item(self.active_node)["text"]
        node = self.active_node
        node_list = [node] #List for returning to original selection
        while("BEHAVIOR DATA (APRIL 2019" not in node_title): #Find tree path from selection to root node
            node = self.tree.parent(node) #Get name of parent node
            node_title = self.tree.item(node)["text"]
            node_list = [node] + node_list

        self.getFiles(node_list, 0, None, None, None) #Retrieve all daughter files matching selected day

    def getFiles(self, node_list, node_index, genotype, run_number, day): #Recursive function to get all matching files in all subdirectories
        #Get current node info
        node = node_list[node_index]
        node_title = self.tree.item(node)["text"]

        if node:
            #If node is a text file, check to see it is an experiment data file
            if(self.tree.set(node, "MIME Type") in "text/plain"):
                if(genotype and run_number and day): #This text node is only valid if parent directories contained genotype, run, and day metadata
                    file_string = self.driveDir.getFileAsString(self.tree.set(node, "ID")) #Download the file from Google Drive
                    cage = None
                    test_day = day.replace("Night", "Day")
                    preset_day = None
                    for line in file_string:
                        if not cage:
                            cage = search(r"USB drive ID: CAGE [1-4][A-B]", line) #Search for the cage number in the file
                        if test_day in line:
                            preset_day = day #Verify that day in file metadata matches directory day
                        if(cage and preset_day):
                            cage = cage.group(0)[19:-1]
                            #Build nested dict and store file
                            try:
                                self.file_dic[genotype][run_number]
                                try:
                                    self.file_dic[genotype][run_number][day] = {cage: file_string}
                                except:
                                    self.file_dic[genotype][run_number] = {day: {cage: file_string}}
                            except:
                                self.file_dic[genotype] = {run_number: {day: {cage: file_string}}}
                            print(genotype + " " + run_number + " " + day + " " + preset_day + " " + cage)
                            break

            elif(self.tree.set(node, "MIME Type") in "application/vnd.google-apps.folder"):
                if(", Starting " in node_title):
                    #Extract genotpye metadata
                    genotype = node_title.split(",")[0]
                    genotype, run_number = genotype.split("-")

                elif(self.day_var.get() in node_title):
                    day = node_title

                else:
                    pass

                try:
                    node_list[node_index+1]
                    self.getFiles(node_list, node_index+1, genotype, run_number, day)
                except:
                    self.fillTree(node)
                    for child in self.tree.get_children(node):
                        new_node_list = node_list + [child]
                        self.getFiles(new_node_list, node_index+1, genotype, run_number, day)
            else:
                pass

def main():
    treeGUI = GUI()



if __name__ == '__main__':
    main()