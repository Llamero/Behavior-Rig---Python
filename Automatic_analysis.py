#Video guide for setting up PyDrive: https://www.youtube.com/watch?v=j31iVbkknzM

from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from re import search

#Initialize and authenticate connection to Google Drive
gauth = GoogleAuth()
gauth.LocalWebserverAuth() # Creates local webserver and auto handles authentication.

class driveFile:
    def __init__(self, file_path): #Initializing contructor
        #Authenticate Google Drive connection
        self.file_path = file_path
        self.drive = GoogleDrive(gauth)

        #Get ID of behabior folder
        self.file_list = self.drive.ListFile({'q': 'sharedWithMe'}).GetList() #Get list of all files and folder in shared root directory
        self.behavior_folder = None
        for file in self.file_list:
            if search(r"^BEHAVIOR DATA \(APRIL 2019.*", file['title']) and file['mimeType']=='application/vnd.google-apps.folder': #Search for behavior folder
                print("FOLDER FOUND!")
                self.behavior_folder = file['id']
                break

        #Get ID of results subfolder
        self.results_subfolder = self.getDir(drive_folder = self.behavior_folder, file_pattern = "^results$")


    def getDir(self, drive_folder = None, file_pattern = ".*"):
        #Load behavior folder as default folder - https://stackoverflow.com/questions/1802971/nameerror-name-self-is-not-defined
        if drive_folder is None:
            drive_folder = self.behavior_folder

        # Define a correctly formatted PyDrive query string with placeholder for parent id.
        request_template = "'{parent_id}' in parents and trashed=false" #From https://stackoverflow.com/questions/42027653/use-pydrive-to-list-files-using-a-variable-holding-the-folder-ids-in-a-loop/42039637
        file_list = self.drive.ListFile({'q': request_template.format(parent_id=drive_folder)}).GetList()

        #Search everything in the directory that matches the pattern
        for file in file_list:
            test_name = file['title']
            if search(file_pattern, test_name):
                print('title: %s, id: %s' % (file['title'], file['id']))
                return file['id']






def main():
    test1 = driveFile("a")
    #test1.getDir()



if __name__ == '__main__':
    main()