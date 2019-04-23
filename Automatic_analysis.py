#Video guide for setting up PyDrive: https://www.youtube.com/watch?v=j31iVbkknzM

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from re import search
from tkinter import Tk, constants
from tkinter.ttk import Treeview
import os

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
                print('title: %s, id: %s' % (file['title'], file['id']))
                subdir_list.append({"Title": file['title'], "mimeType": file['mimeType'], "ID": file['id']})

        return subdir_list

class GUI:
    def __init__(self): #Based on treewalk code here: https://stackoverflow.com/questions/14404982/python-gui-tree-walk, and demo: https://stackoverflow.com/questions/36120426/tkinter-treeview-widget-inserting-data
        self.root = Tk() #Create GUI object
        self.tree = Treeview(columns=("MIME Type", "ID")) #Create Treeview widget - columns - set column names, displaycolumns - specifies which columns are shown
        self.tree.heading('#0', text='Title')
        self.tree.heading('#1', text='MIME Type')
        self.tree.heading('#2', text='ID')
        self.tree.column('#1', stretch=constants.YES)
        self.tree.column('#2', stretch=constants.YES)
        self.tree.column('#0', stretch=constants.YES)
        self.tree.pack(fill='both', expand=True) #Fill - fill given space available, expand - expand - fill whitespace in master tk object
        self.driveDir = driveFile() #Create instance of Google Drive class
        self.createRoot() #Initialize tree with root folder
        self.tree.bind('<<TreeviewOpen>>', self.updateTree) #Update tree upon event
        self.root.mainloop()


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
        print(node_ID)
        child_list = self.driveDir.getDir(node_ID)
        for f in child_list:
            oid = self.tree.insert(node, 'end', text=f["Title"], values=(f["mimeType"], f["ID"]))
            if f["mimeType"] == "application/vnd.google-apps.folder":
                self.tree.insert(oid, 0, text='dummy')


def main():
    #test1 = driveFile("a")
    #test1.getDir()
    treeGUI = GUI()



if __name__ == '__main__':
    main()