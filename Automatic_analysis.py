#Video guide for setting up PyDrive: https://www.youtube.com/watch?v=j31iVbkknzM

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from re import search
from tkinter import Tk, constants, Label, Button, font, Scrollbar, Frame
from tkinter.ttk import Treeview

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

        #Get ID of results subfolder
        self.results_subfolder = self.getDir(drive_folder = self.behavior_folder, file_pattern = "^results$")
        return [self.results_subfolder]


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

class GUI:
    def __init__(self): #Based on treewalk code here: https://stackoverflow.com/questions/14404982/python-gui-tree-walk, and demo: https://stackoverflow.com/questions/36120426/tkinter-treeview-widget-inserting-data
        self.root = Tk() #Create GUI object
        self.frame_list = []

        self.root.title("Google Drive")

        #Create treeview widget for file directory
        self.frame_list.append(Frame(master=self.root)) #Create new frame for status and button
        self.frame_list[len(self.frame_list)-1].pack(fill=constants.BOTH, expand=True, side=constants.TOP)
        self.tree = Treeview(self.frame_list[len(self.frame_list)-1], columns=("MIME Type", "ID"), height=20) #Create Treeview widget - columns - set column names, displaycolumns - specifies which columns are shown
        self.tree["displaycolumns"]=("MIME Type",) #Show only the title and type column, hide the ID column - the trailing column is needed
        self.tree.heading('#0', text='Title')
        self.tree.heading('#1', text='MIME Type')
        #self.tree.heading('#2', text='ID')
        self.tree.column('#1', stretch=constants.NO, width=450)
        #self.tree.column('#2', stretch=constants.YES)
        self.tree.column('#0', stretch=constants.YES, width=450)
        self.tree.pack(fill=constants.BOTH, expand=True, side=constants.LEFT) #Fill frame when window is resized

        #Add scroll bar to tree
        self.tree_scroll = Scrollbar(self.frame_list[len(self.frame_list)-1], command=self.tree.yview)
        self.tree_scroll.pack(side=constants.RIGHT, padx=5, pady=5, fill=constants.Y)
        self.tree.config(yscrollcommand=self.tree_scroll.set) #Scroll bar has to be set to be controlled by treeview

        #Add status widget
        self.frame_list.append(Frame(master=self.root)) #Create new frame for status and button
        self.frame_list[len(self.frame_list)-1].pack(fill=constants.BOTH, expand=False, side=constants.TOP)
        self.title_label = Label(self.frame_list[len(self.frame_list)-1], text = "Please select file:", anchor=constants.W)
        self.title_label.pack(side=constants.LEFT, padx=5, pady=5)
        self.title_font = font.Font(font=self.title_label.cget("font"))
        self.font_size = self.title_font.actual()["size"]
        self.title_font.configure(size=round(self.font_size*1.2))
        self.title_label.configure(font=self.title_font)

        #Create button
        self.gui_button = Button(self.frame_list[len(self.frame_list)-1], text="OK", command=None, font=self.title_font)
        self.gui_button.pack(side=constants.RIGHT, padx=5, pady=5)

        #Populate tree widget and initialize event monitor
        self.driveDir = driveFile() #Create instance of Google Drive class
        self.createRoot() #Initialize tree with root folder
        self.tree.bind('<<TreeviewOpen>>', self.updateTree) #Update tree upon event
        self.root.mainloop()

    #Generate root directory
    def createRoot(self):
        root_data = self.driveDir.getRoot()
        node = self.tree.insert('', 'end', text=root_data[0]["Title"], values=(root_data[0]["mimeType"], root_data[0]["ID"]), open=True) #Parent, index,
        self.fillTree(node)

    def updateTree(self, event):
        self.tree = event.widget
        self.fillTree(self.tree.focus())

    def fillTree(self, node):
        #If node is not folder, then return
        #if self.tree.set(node, "MIME Type") != 'application/vnd.google-apps.folder': #Set with two arguments returns the specified value
         #   return

        node_ID = self.tree.set(node, "ID")
        # Delete the possibly 'dummy' node present.
        self.tree.delete(*self.tree.get_children(node))

        parent = self.tree.parent(node)
        child_list = self.driveDir.getDir(node_ID)
        for f in child_list:
            oid = self.tree.insert(node, 'end', text=f["Title"], values=(f["mimeType"], f["ID"]))
            if f["mimeType"] == "application/vnd.google-apps.folder":
                self.tree.insert(oid, 0, text='dummy')

    def allSubFiles(self, day = 'all'):
        pass

    def singleFile(self):
        pass

def main():
    treeGUI = GUI()



if __name__ == '__main__':
    main()