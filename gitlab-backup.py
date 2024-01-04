# PREREQ: sudo pip3 install dropbox
# USAGE: sudo python3 <scriptname.py>
import ast # string to dictionary
import dropbox
import os
import subprocess

# gitlab folder that stores config backup (required to decrypt data backup) and data backup
# assumes default locations for linux installation of gitlab community edition
LOCAL_GITLAB_CONFIG_PATH    = "/etc/gitlab/config_backup"
LOCAL_GITLAB_DATA_PATH      = "/var/opt/gitlab/backups"

DROPBOX_APP_KEY     = "<you-have-to-edit-this-field>"
DROPBOX_APP_SECRET  = "<you-have-to-edit-this-field>"
DROPBOX_REFRESH_TOKEN = "<you-have-to-edit-this-field>"
DROPBOX_DESTINATION_CONFIG  = "/Config"
DROPBOX_DESTINATION_DATA    = "/Data"

# access token only valid 4 hours, but refresh token always valid and used to get new access token.
# this function uses refresh token to get new valid access token
# read this to know to get refresh token in the first place: https://www.dropboxforum.com/t5/Dropbox-API-Support-Feedback/Issue-in-generating-access-token/m-p/592921/highlight/true#M27586
def getNewAccessToken():
    refreshCommand = "curl https://api.dropbox.com/oauth2/token -d grant_type=refresh_token -d refresh_token=" + DROPBOX_REFRESH_TOKEN + " -u " + DROPBOX_APP_KEY + ":" + DROPBOX_APP_SECRET
    result = subprocess.run(refreshCommand, shell=True, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    response = result.stdout # this is what you get back, contains the data you want
    response_dict = ast.literal_eval(response)
    return response_dict["access_token"]

# e.g. takes "gitlab_config_1702820194_2023_12_17.tar" and returns 1702820194 as int
# getTimestampFromConfigFilename("gitlab_config_1702820194_2023_12_17.tar")
def getTimestampFromConfigFilename(filename):
    # files that are not gitlab config backups are ignored
    if not "gitlab_config_" in filename:
        return -1
    return int(filename[filename.find("gitlab_config_") + 14:filename.find("_", filename.find("gitlab_config_") + 14)])


# takes path to dir and returns filename of newest config backup
def getNewestConfigBackupFilename():
    # get list of all files in gitlab config backup dir
    configBackupList = [f for f in os.listdir(LOCAL_GITLAB_CONFIG_PATH) if os.path.isfile(os.path.join(LOCAL_GITLAB_CONFIG_PATH, f))]

    # check each filename and remember index of the name with highest timestamp (newest backup)
    newestBackupIndex = -1
    newestBackupHighestTimestamp = -1
    for index, filename in enumerate(configBackupList):
        if getTimestampFromConfigFilename(filename) > newestBackupHighestTimestamp:
            newestBackupHighestTimestamp = getTimestampFromConfigFilename(filename)
            newestBackupIndex = index
    return configBackupList[newestBackupIndex]


# e.g. takes "1702758583_2023_12_16_16.5.1_gitlab_backup.tar" and returns 1702758583 as int
# getTimestampFromDataFilename("1702758583_2023_12_16_16.5.1_gitlab_backup.tar")
def getTimestampFromDataFilename(filename):
    # files that are not gitlab data backups are ignored
    if not "_gitlab_backup" in filename:
        return -1
    return int(filename[:filename.find("_")])


# takes path to dir and returns filename of newest data backup
def getNewestDataBackupFilename():
    # get list of all files in gitlab data backup dir
    dataBackupList = [f for f in os.listdir(LOCAL_GITLAB_DATA_PATH) if os.path.isfile(os.path.join(LOCAL_GITLAB_DATA_PATH, f))]

    # check each filename and remember index of the name with highest timestamp (newest backup)
    newestBackupIndex = -1
    newestBackupHighestTimestamp = -1
    for index, filename in enumerate(dataBackupList):
        if getTimestampFromDataFilename(filename) > newestBackupHighestTimestamp:
            newestBackupHighestTimestamp = getTimestampFromDataFilename(filename)
            newestBackupIndex = index
    return dataBackupList[newestBackupIndex]


def uploadToDropbox(accessToken, localFilePath, remoteFolder):
    print("Will use this access token:", accessToken)
    dbx = dropbox.Dropbox(accessToken)
    with open(localFilePath, "rb") as f:
        dbx.files_upload(f.read(), remoteFolder)
        

def main():
    # get new access token (valid 240 min)
    DROPBOX_ACCESS_TOKEN = getNewAccessToken()    

    # ensure local gitlab paths exist
    if (not os.path.exists(LOCAL_GITLAB_CONFIG_PATH)) or (not os.path.exists(LOCAL_GITLAB_DATA_PATH)):
        print("Local gitlabs paths could not be found. Terminating..")
        return

    # create gitlab backups using subprocess (must be run as sudo or will fail)
    # for this reason you must also automate this in "sudo crontab -e" (sudo is important)
    commandConfigBackup = "sudo gitlab-ctl backup-etc"
    commandDataBackup   = "sudo gitlab-backup create"

    #       make new backups  (might take few minutes but program will wait)
    subprocess.run(commandConfigBackup, shell=True)
    subprocess.run(commandDataBackup, shell=True)


    # get filename of newest gitlab config backup
    newestConfigFilename = getNewestConfigBackupFilename()
    newestConfigFullPath = LOCAL_GITLAB_CONFIG_PATH + "/" + newestConfigFilename
    print("Newest config backup:", newestConfigFullPath)
    
    # get filename of newest gitlab data backup
    newestDataFilename = getNewestDataBackupFilename()
    newestDataFullPath = LOCAL_GITLAB_DATA_PATH + "/" + newestDataFilename
    print("Newest data backup:", newestDataFullPath)

    # upload data (if it already exists nothing happens)
    uploadToDropbox(DROPBOX_ACCESS_TOKEN, newestConfigFullPath , DROPBOX_DESTINATION_CONFIG + "/" + newestConfigFilename)
    uploadToDropbox(DROPBOX_ACCESS_TOKEN, newestDataFullPath   , DROPBOX_DESTINATION_DATA   + "/" + newestDataFilename)
    
    print("Successfully backed up Gitlab Config and Data.")


main()
