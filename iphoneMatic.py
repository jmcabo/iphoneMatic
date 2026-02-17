#!/usr/bin/env python3
#iphoneMatic 0.9 - by JMC - Based on https://github.com/alexisrozhkov/extract_media_from_backup/ and https://github.com/farcaller/bplist-python/
#Created: 2026-02-11
#Updated: 2026-02-13
import os
import shutil
import sqlite3
import argparse
import pathlib
import re
import errno
from enum import Enum
from datetime import datetime
from argparse import RawTextHelpFormatter
from bplist import BPListReader
from sys import stderr, stdout, stdin


USE_COLORS = True
if os.name == "nt" or not stdout.isatty():  #os.name can be: nt, posix or java
    USE_COLORS = False
GREEN_COLOR = '\033[01;32m'    if USE_COLORS else ""
BLUE_COLOR = '\033[01;34m'  if USE_COLORS else ""
RED_COLOR = '\033[01;31m' if USE_COLORS else ""
NO_COLOR = '\033[00m'          if USE_COLORS else ""

class PropertyType(Enum):
    PHONE = 3
    EMAIL = 4
    ADDRESS = 5

def removePrefix(s, prefix):
    if s.startswith(prefix):
        s = s[len(prefix) : ]
    return s

def isFilename_IMG_NNNN(s):
    return re.match(r'IMG_\d+\..*', s) != None

def isFilename_Guid(s):
    return re.match(r'[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}', s) != None

def fixFilename(s):
    #debug: encode filename
    s = s.replace(":", "_")
    s = s.replace("…", "_")
    s = s.replace("+", "_")
    return s

def formatNames(first, middle, last):
    s = ""
    if first != None:
        s += first
    if middle != None:
        if s != "":
           s += " "
        s += middle
    if last != None:
        if s != "":
            s += " "
        s += last
    return s

def writeToFile(filename, content):
    print("Writing to", filename)
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(content)
    except Exception as e:
        print("Error writing note file: ", e)

def ensureDirs(dirs):
    try:
        os.makedirs(dirs)
    except OSError as exc: # Guard against race condition
        if exc.errno != errno.EEXIST:
            raise

class IPhoneMatic:
    def __init__(self, backup_dir, out_dir, dryRun, preserveNames):
        self.backup_dir = backup_dir
        self.out_dir = out_dir
        self.dryRun = dryRun
        self.preserveNames = preserveNames
        self.existingFilenamesMap = {}
        self.whatsappImagePaths = {}
        self.whatsappThumbnailPath = ""
        self.whatsappStickersPath = ""


    def extractHardlinksWhatsapp(self, subdir, whatsappThumbnailSubdir, whatsappStickersSubdir, domainFilter, pathFilter, typeStr="TypeNormal"):
        self.whatsappThumnailPath = os.path.join(self.out_dir, whatsappThumbnailSubdir)
        self.whatsappStickersPath = os.path.join(self.out_dir, whatsappStickersSubdir)
        self.extractHardlinks(subdir, domainFilter, pathFilter, "TypeWhatsapp")


    def extractHardlinks(self, subdir, domainFilter, pathFilter, typeStr="TypeNormal"):
        conn = sqlite3.connect(os.path.join(self.backup_dir, 'Manifest.db'))

        # simple query to get only media (without thumbnails)
        query = "SELECT fileId, domain, relativePath, flags, file FROM Files " \
                + "WHERE domain LIKE :domainFilter AND relativePath LIKE :pathFilter " \
                + "ORDER BY relativePath"

        MAX = -1
        i = 0
        r = conn.cursor().execute(query, {"domainFilter": domainFilter, "pathFilter": pathFilter})
        for subfile, domain, relpath, _, blob in r:
            # files are stored in subdirectories, that match first 2 characters of their names
            sourceSubdir = subfile[:2]

            originalWhatsappFilename = relpath
            if typeStr == "TypeWhatsapp":
                originalWhatsappFilename = removePrefix(originalWhatsappFilename, "Message/")

            relpath = removePrefix(relpath, "Media/DCIM/")
            relpath = removePrefix(relpath, "100APPLE/")
            relpath = removePrefix(relpath, "Media/PhotoData/Thumbnails/V2/PhotoData/Sync/100SYNCD/")
            relpath = removePrefix(relpath, "Media/PhotoData/Metadata/PhotoData/Sync/100SYNCD/")
            relpath = removePrefix(relpath, "Media/Profile/")
            relpath = removePrefix(relpath, "File Provider Storage/")

            useThumbnailDir = False
            useStickersDir = False
            if typeStr == "TypeWhatsapp":
                #Remove parent dirs:
                p = pathlib.Path(relpath)
                extension = p.suffix
                name = p.stem
                relpath = name + extension
                #Skip thumbnails:
                if extension == ".thumb" or extension == ".favicon" or extension == ".mmsthumb":
                    useThumbnailDir = True
                #Skip stickers:
                if extension == ".webp":
                    useStickersDir = True

            if typeStr == 'TypeAppGroup':
                domain = removePrefix(domain, "AppDomainGroup-")
                relpath = os.path.join(domain, relpath)

            # abspath will normalize path separators (windows uses reverse slashes, but relpath has forward ones)
            # doing it on sourceFile is not really necessary, but won't hurt
            sourceFile = os.path.abspath(os.path.join(self.backup_dir, sourceSubdir, subfile))
            outputDir = self.out_dir
            if useThumbnailDir:
                outputDir = os.path.join(outputDir, self.whatsappThumbnailPath)
            if useStickersDir:
                outputDir = os.path.join(outputDir, self.whatsappStickersPath)
            if subdir != "" and subdir != None:
                outputDir = os.path.join(outputDir, subdir)
            destFile = os.path.abspath(os.path.join(outputDir, relpath))

            if os.path.isfile(sourceFile):
                try:
                    self.processFile(sourceFile, destFile, blob, typeStr, originalWhatsappFilename)
                except Exception as e:
                    print("ERROR processing file", destFile, ": ", e, '\n')
                i += 1

            if MAX != -1 and i == MAX:
                return


    def processFile(self, sourceFile, destFile, blob, typeStr, originalWhatsappFilename):
        lastModified = None
        fileSize = None
        parsed = {}
        try:
            reader = BPListReader(blob)
            parsed = reader.parse()
            #print(parsed)
        except:
            print("Error reading: ", destFile, " with GUID ", os.path.basename(sourceFile))

        if "$objects" in parsed and len(parsed["$objects"]) >= 2:
            if "LastModified" in parsed["$objects"][1]:
                lastModified = parsed["$objects"][1]["LastModified"]
            if "Size" in parsed["$objects"][1]:
                fileSize = parsed["$objects"][1]["Size"]
            #print(lastModified)
            #print(fileSize)
            #print(parsed)

        if lastModified == None or fileSize == None:
            print("Error reading, LastModified or Size attributes not found: ", destFile, " with GUID ", os.path.basename(sourceFile))

        originalFilename = None
        if "$objects" in parsed and len(parsed["$objects"]) >= 4:
            blobInside = parsed["$objects"][3]
            parsedInside = None
            try:
                readerInside = BPListReader(blobInside)
                parsedInside = readerInside.parse()
                #print(parsedInside) #debug
            except Exception as e:
                #print("File '", destFile, "' error in originalFilename attributes: ", e)
                pass
            if parsedInside != None and "com.apple.assetsd.originalFilename" in parsedInside:
                originalFilename = parsedInside["com.apple.assetsd.originalFilename"]
                originalFilename = originalFilename.decode("utf-8")   #It comes as a binary string.

        if originalFilename != None and (isFilename_IMG_NNNN(originalFilename) or isFilename_Guid(originalFilename)):
            originalFilename = None

        #if originalFilename == None:  #debug
        #    return
        #print("ORIGINAL FILENAME: ", originalFilename) #debug

        if not self.preserveNames and typeStr != "TypeApp":
            if originalFilename != None:
                p = pathlib.Path(destFile)
                destDir = str(p.parent)

                #Replace IMG_NNNN with originalFilename
                destFile = os.path.join(destDir, originalFilename)
            else:
                #Rewrite filename using the MTIME date:
                if lastModified != None:
                    suffix = datetime.fromtimestamp(lastModified).strftime("%Y%m%d_%H%M%S")

                    p = pathlib.Path(destFile)
                    extension = p.suffix
                    name = p.stem
                    destDir = str(p.parent)

                    if name.startswith("IMG_") or typeStr == "TypeWhatsapp":
                        name = "IMG_" + suffix

                    #Replace IMG_ with VID_ in videos:
                    extlower = extension.lower()
                    if extlower == ".mov" or extlower == ".mp4":
                        if name.startswith("IMG_"):
                            name = "VID_" + name[4:]

                    destFile = os.path.join(destDir, name + extension)

        #Add _1 or _2 to filenames that have the same lastModified in seconds or the same originalFilename
        if destFile in self.existingFilenamesMap:
            p = pathlib.Path(destFile)
            extension = p.suffix
            name = p.stem
            destDir = str(p.parent)
            #Retry while the destFile already exists:
            n = 1
            while destFile in self.existingFilenamesMap:
                destFile = os.path.join(destDir, name + "_" + str(n) + extension)
                n += 1
        self.existingFilenamesMap[destFile] = sourceFile

        #Add to whatsapp images map:
        if typeStr == "TypeWhatsapp":
            self.whatsappImagePaths[originalWhatsappFilename] = destFile

        if not os.path.isfile(destFile):
            #Show source and dest:
            print(sourceFile, "->", destFile)
            if self.dryRun:
                return

            dirName = os.path.dirname(destFile)
            #Create intermediate dirs:
            if not os.path.exists(dirName):
                ensureDirs(dirName)
            #Hardlink:
            try:
                os.link(sourceFile, destFile)
            except FileExistsError:
                print("File exists")
                pass
            #Set MTIME:
            if lastModified != None:
                os.utime(destFile, (lastModified, lastModified))


    def extractContactsVCF(self, contactsDbFilename, vcfFilename):
        conn = sqlite3.connect(contactsDbFilename)

        query = "SELECT p.ROWID, m.label, m.property, m.value, e.value, p.First, p.Middle, p.Last, " \
                + "     datetime(p.Birthday + 978307200, 'unixepoch', 'localtime'), p.Birthday " \
                + "FROM ABMultiValue m " \
                + "INNER JOIN ABPerson p ON m.record_id = p.ROWID " \
                + "LEFT JOIN ABMultiValueEntry e ON e.parent_id = m.UID " \
                + "WHERE m.property != 76 and m.property != 46 " \
                + "ORDER BY p.ROWID ASC, m.UID ASC"

        personsById = {}
        for personId, label, propertyType, value, \
            addressValue, first, middle, last, birthdayStr, birthday \
            in conn.cursor().execute(query):
            #print(formatNames(first, middle, last))
            person = {}
            if personId in personsById:
                person = personsById[personId]
            else:
                person = {"personId": personId,
                          "name": formatNames(first, middle, last),
                          "first": first, "middle": middle, "last": last,
                          "phones": [], "emails": [], "addresses": [],
                          "birthday": ""}
                if birthday != None and birthday != "":
                    birthdayFormatted = datetime.fromtimestamp(float(birthday) + 978307200).strftime("%Y-%m-%d")
                    person["birthday"] = birthdayFormatted
                personsById[personId] = person
            if propertyType == PropertyType.PHONE.value:
                person["phones"].append(value)
            elif propertyType == PropertyType.EMAIL.value:
                person["emails"].append(value)
            elif propertyType == PropertyType.ADDRESS.value:
                person["addresses"].append(addressValue)

        vcf = ""
        for personId, person in personsById.items():
            vcf += "BEGIN:VCARD\n"
            vcf += "VERSION:2.1\n"
            #debug: escape newlines and others.
            #debug: acentos
            vcf += "FN:" + person["name"] + "\n"
            vcf += "N:" \
                + (person["last"] if person["last"] != None else "") \
                + ";" \
                + (person["first"] if person["first"] != None else "") \
                + ";"  \
                + (person["middle"] if person["middle"] != None else "") \
                + ";" \
                + ";" + "\n"
            for phone in person["phones"]:
                #debug: phone type: CELL, HOME, WORK, etc.
                vcf += "TEL;CELL:" + phone + "\n"
            for email in person["emails"]:
                #debug: email type
                vcf += "EMAIL;HOME:" + email + "\n"
            for address in person["addresses"]:
                #debug: multiline addresses?
                vcf += "ADR;HOME:;;" + address + ";;;;\n"
            if person["birthday"] != "":
                vcf += "BDAY:" + person["birthday"] + "\n"
            vcf += "END:VCARD\n"
        #print(vcf)
        writeToFile(vcfFilename, vcf)


    def extractWhatsappChatsFromDb(self, whatsappDbFilename, whatsappContactsDbFilename, chatsDir, chatsDirHtml):
        WHATSAPP_ADS_ID = "status@broadcast"

        #Parse contacts:
        contactsByLId = {}
        contactsByJId = {}
        if os.path.isfile(whatsappContactsDbFilename):
            conn = sqlite3.connect(whatsappContactsDbFilename)

            query = "SELECT Z_PK, ZFULLNAME, ZBUSINESSNAME, ZPHONENUMBER, ZLID, ZWHATSAPPID " \
                    + "FROM ZWAADDRESSBOOKCONTACT;"

            for contactId, fullname, businessName, phoneNumber, lid, jid in conn.cursor().execute(query):
                contact = {"contactId": contactId,
                           "fullname": fullname,
                           "businessName": businessName,
                           "phoneNumber": phoneNumber,
                           "lid": lid,
                           "jid": jid}
                contactsByLId[lid] = contact
                contactsByJId[jid] = contact


        #Assign filename for chat, don't overwrite if they are called the same. Sort by Id.
        existingChatFilenames = {}

        conn = sqlite3.connect(whatsappDbFilename)

        query = "SELECT c.ZPARTNERNAME, c.ZLASTMESSAGEDATE, c.ZCONTACTIDENTIFIER AS chat_lid, ZCONTACTJID AS chat_jid " \
                + "FROM ZWACHATSESSION c " \
                + "WHERE c.ZLASTMESSAGEDATE NOT NULL " \
                + "ORDER BY c.Z_PK ASC"

        for chatName, lastMessageDate, chatLid, chatJid in conn.cursor().execute(query):

            query = "SELECT c.ZPARTNERNAME, t.ZPARTNERNAME, m.ZTEXT, m.ZMESSAGEDATE, m.ZCHATSESSION, m.ZGROUPMEMBER, " \
                    + "g.ZMEMBERJID, m.ZMESSAGETYPE, " \
                    + "d.ZTHUMBNAILPATH, d.ZTITLE, d.ZSUMMARY, d.ZCONTENT1, d.ZCONTENT2, " \
                    + "i.ZFILESIZE, i.ZMEDIALOCALPATH, i.ZXMPPTHUMBPATH " \
                    + "FROM ZWAMESSAGE m " \
                    + "LEFT JOIN ZWACHATSESSION c ON c.ZCONTACTJID = m.ZFROMJID " \
                    + "LEFT JOIN ZWACHATSESSION t ON t.ZCONTACTJID = m.ZTOJID " \
                    + "LEFT JOIN ZWAGROUPMEMBER g ON g.Z_PK = m.ZGROUPMEMBER " \
                    + "LEFT JOIN ZWAMEDIAITEM i ON i.Z_PK = m.ZMEDIAITEM " \
                    + "LEFT JOIN ZWAMESSAGEDATAITEM d ON d.ZMESSAGE = m.Z_PK " \
                    + "WHERE m.ZFROMJID = :chatJid " \
                    + "      OR m.ZTOJID = :chatJid "

            r = conn.cursor().execute(query, {"chatJid": chatJid})

            chatFilename = os.path.join(chatsDir, chatName + ".txt")
            chatFilenameHtml = os.path.join(chatsDirHtml, chatName + ".html")
            chatFilename = fixFilename(chatFilename)
            chatFilenameHtml = fixFilename(chatFilenameHtml)

            #Add _1 or _2 to filenames that have the same name:
            if chatFilename in existingChatFilenames:
                p = pathlib.Path(chatFilename)
                extension = p.suffix
                name = p.stem
                destDir = str(p.parent)
                #Retry while the chatFilename already exists:
                n = 1
                while chatFilename in existingChatFilenames:
                    chatFilename = os.path.join(chatsDir, name + "_" + str(n) + extension)
                    chatFilenameHtml = os.path.join(chatsDirHtml, name + "_" + str(n) + ".html")
                    n += 1
            existingChatFilenames[chatFilename] = 1

            #debug: ToDo:
            #    @group member names
            #    -links (insta, etc.)
            #        @insta caption
            #        @thumbnail instagram
            #        @a href en links
            #        -escape img src
            #        -escape video src
            #        -escape a href
            #    -skip Whatsapp chat(?)
            #    -empty chat name ".txt"
            #    -escape filenames
            #    -<200e> en filenames
            #    @media items (image filename?)

            #Process messages:
            content = ""
            contentHtml = ""
            contentHtml += "<html><head><meta charset='UTF-8'></head><body><pre style='font-size: 15px;'>"
            for fromName, toName, text, messageDate, chatSession, groupMemberPk, groupMemberJid, messageType, \
                thumbnailPath, dataTitle, dataSummary, dataContent1, dataContent2, mediaFileSize, mediaLocalPath, \
                mediaThumbnailLocalPath \
                in r:
                textHtml = text
                dateStr = datetime.fromtimestamp(float(messageDate) + 978307200).strftime("%Y-%m-%d %H:%M:%S")
                nameStr = "<" + fromName + ">" if fromName != None else "<me>"
                nameStrHtml = "&lt;" + fromName + "&gt;" if fromName != None else "<b>&lt;me&gt;</b>"
                LEADING_SPACE = "                     "
                if groupMemberPk != None and groupMemberJid != None:
                    #Resolve group member name:
                    try:
                        if groupMemberJid.endswith("@lid"):
                            contact = contactsByLId[groupMemberJid]
                        else:
                            contact = contactsByJId[groupMemberJid]
                    except:
                        contact = None
                    if contact != None:
                        nameStr = "<" + contact["fullname"] + ">"
                        nameStrHtml = "&lt;" + contact["fullname"] + "&gt;"
                #Text by messageType
                if text != None:
                    if messageType == MESSAGETYPE_LINK:
                        textHtml = ""
                        if mediaThumbnailLocalPath in self.whatsappImagePaths:
                            imagePath = self.whatsappImagePaths[mediaThumbnailLocalPath]
                            imagePath = os.path.relpath(imagePath, os.path.dirname(chatFilenameHtml))
                            textHtml = "\n" + LEADING_SPACE \
                                + "(Link) <a target='_blank' href='{}'> ".format(text) \
                                + "<img width='200' style='display: inline-block;' src='{}'/></a>".format(str(imagePath))
                        textHtml    += "\n" + LEADING_SPACE + "<a target='_blank' href='{}'>{}</a>".format(text, text)
                if text == None:
                    MESSAGETYPE_IMAGE = 1
                    MESSAGETYPE_VIDEO = 2
                    MESSAGETYPE_LINK = 7
                    MESSAGETYPE_STICKER = 15
                    MESSAGETYPE_VOICECALL = 59
                    if messageType == MESSAGETYPE_VOICECALL:
                        text = "(Voice Call)"
                        textHtml = text
                    if messageType == MESSAGETYPE_IMAGE:
                        imagePath = mediaLocalPath
                        if mediaLocalPath in self.whatsappImagePaths:
                            imagePath = self.whatsappImagePaths[mediaLocalPath]
                            imagePath = os.path.relpath(imagePath, os.path.dirname(chatFilenameHtml))
                        text = "\n" + LEADING_SPACE + "(Image) " + str(imagePath)
                        textHtml = "\n" + LEADING_SPACE + "(Image) <img width='500' style='display: inline-block;' src='{}'/>".format(str(imagePath))
                    if messageType == MESSAGETYPE_VIDEO:
                        imagePath = mediaLocalPath
                        if mediaLocalPath in self.whatsappImagePaths:
                            imagePath = self.whatsappImagePaths[mediaLocalPath]
                            imagePath = os.path.relpath(imagePath, os.path.dirname(chatFilenameHtml))
                        text = "\n" + LEADING_SPACE + "(Video) " + str(imagePath)
                        textHtml = "\n" + LEADING_SPACE + "(Video) <video width='500' controls>" \
                                   + "  <source src='{}' type='video/mp4'> ".format(str(imagePath)) \
                                   + "</video>"
                    if messageType == MESSAGETYPE_STICKER:
                        if mediaLocalPath in self.whatsappImagePaths:
                            imagePath = self.whatsappImagePaths[mediaLocalPath]
                            imagePath = os.path.relpath(imagePath, os.path.dirname(chatFilenameHtml))
                            textHtml = "\n" + LEADING_SPACE + "(Sticker) <img width='200' style='display: inline-block;' src='{}'/>".format(str(imagePath))

                if dataTitle != None:
                    dataDetails = (("\n" + LEADING_SPACE + dataTitle) if dataTitle != text else "") \
                         +  "\n" \
                         +  (("\n" + LEADING_SPACE + dataSummary) if dataSummary != None else "") \
                         +  (("\n" + LEADING_SPACE + dataContent1) if dataContent1 != None and dataContent1 != text else "") \
                         +  (("\n" + LEADING_SPACE + dataContent2) if dataContent2 != None and dataContent2 != text else "")
                    text += dataDetails
                    textHtml += dataDetails
                #Append message:
                content += "{}: {}: {}\n".format(dateStr, nameStr, text)

                #Append to html:
                contentHtml += "{}: {}: {}\n".format(dateStr, nameStrHtml, textHtml)

            contentHtml += "</pre></body></html>"

            #Write chat file:
            writeToFile(chatFilename, content)
            writeToFile(chatFilenameHtml, contentHtml)



    def checkExportNotes(self):
        canUseReadnotes = False
        try:
            import bs4
            import pytz
            import biplist
            canUseReadnotes = True
        except ImportError:
            pass
        return canUseReadnotes


    def exportNotes(self):
        print(BLUE_COLOR + "Exporting notes..." + NO_COLOR)
        if not self.checkExportNotes():
            print(RED_COLOR + "ERROR: You need to run 'pip install --break-system-packages bs4 pytz biplist' to be able to export Notes (or you can comment out exportNotes() at the bottom of this file)" + NO_COLOR)
            return
        notesDbFilename = os.path.join(self.out_dir, "FilesAppGroups/group.com.apple.notes/NoteStore.sqlite")
        if not os.path.isfile(notesDbFilename):
            print("WARNING: NoteStore.sqlite not found. Notes will not be exported")
            return
        destNotesDir = os.path.join(self.out_dir, "Notes")
        ensureDirs(destNotesDir)
        os.system("python3 -B readnotes/readnotes.py  --user all --input \"" \
                + notesDbFilename \
                + "\" --output \"" + destNotesDir + "\"")

    def exportContacts(self):
        print(BLUE_COLOR + "Exporting contacts..." + NO_COLOR)
        contactsDbFilename = os.path.join(self.out_dir, "FilesHome/Library/AddressBook/AddressBook.sqlitedb")
        if not os.path.isfile(contactsDbFilename):
            print(RED_COLOR + "WARNING: AddressBook.sqlite not found. Contacts will not be exported" + NO_COLOR)
            return
        vcfDir = os.path.join(self.out_dir, "Contacts")
        ensureDirs(vcfDir)
        suffixDate = datetime.fromtimestamp(os.path.getmtime(contactsDbFilename)).strftime("%Y-%m-%d")
        vcfFilename = os.path.join(vcfDir, "contacts_" + suffixDate + ".vcf")
        if (os.path.isfile(contactsDbFilename)):
            self.extractContactsVCF(contactsDbFilename, vcfFilename)

    def exportWhatsappChats(self):
        print(BLUE_COLOR + "Exporting whatsapp chats..." + NO_COLOR)
        whatsappContactsDbFilename = os.path.join(self.out_dir, "FilesAppGroups/group.net.whatsapp.WhatsApp.shared/ContactsV2.sqlite")
        whatsappDbFilename = os.path.join(self.out_dir, "FilesAppGroups/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite")
        if not os.path.isfile(whatsappDbFilename):
            print(RED_COLOR + "ERROR: ChatStorage.sqlite not found. Whatsapp chats will not be exported" + NO_COLOR)
            return
        if not os.path.isfile(whatsappContactsDbFilename):
            print(RED_COLOR + "WARNING: ContactsV2.sqlite not found. Group member names will not be written" + NO_COLOR)
        chatsDir = os.path.join(self.out_dir, "WhatsappChats")
        chatsDirHtml = os.path.join(self.out_dir, "WhatsappChatsHtml")
        ensureDirs(chatsDir)
        ensureDirs(chatsDirHtml)
        self.extractWhatsappChatsFromDb(whatsappDbFilename, whatsappContactsDbFilename, chatsDir, chatsDirHtml)


def main():
    desc = "Extracts images as hardlinks and sets the correct date - by JMC\n" \
            + "\nExample:  python3 iphoneMatic.py F:\\Backup\\00008110-001A18D40EFB801E F:\\DCIM" \
            + "\nNote: output datetimes are in local timezone"

    parser = argparse.ArgumentParser(description=desc, formatter_class=RawTextHelpFormatter)

    parser.add_argument('backup_dir', help='Location of backup directory')
    parser.add_argument('out_dir', help='Destination directory, relative to which ' \
                        'files would be copied, according to original directory structure')
    parser.add_argument('-n', '--pretend', action='store_true', help="Print source and dest but don't create hardlinks")
    parser.add_argument('-u', '--numeric', action='store_true', help="Use IMG_NNNN.JPG instead of IMG_YYYYmmdd_HHMMSS.JPG")

    args = parser.parse_args()


    matic = IPhoneMatic(args.backup_dir, args.out_dir, args.pretend, args.numeric)
    print(BLUE_COLOR + "Extracting links to camera pictures..." + NO_COLOR)
    matic.extractHardlinks("Camera", "CameraRollDomain", "%Media/DCIM%")
    #Some Thumbnails:
    #    matic.extractHardlinks("FromMac", "CameraRollDomain", "%Media/PhotoData/Thumbnails/V2/PhotoData/Sync/100SYNCD/%")
    #More Thumbnails:
    #    matic.extractHardlinks("Thumbnails", "CameraRollDomain", "%Media/PhotoData/Metadata/PhotoData/Sync/100SYNCD/%")
    print(BLUE_COLOR + "Extracting links to whatsapp pictures..." + NO_COLOR)
    matic.extractHardlinks("WhatsappProfilePictures", "AppDomainGroup-group.net.whatsapp.WhatsApp.shared", "%Media/Profile/%jpg")
    matic.extractHardlinksWhatsapp("Whatsapp", "WhatsappThumbnails", "WhatsappStickers", "AppDomainGroup-group.net.whatsapp.WhatsApp.shared", "%Message/Media%")
    print(BLUE_COLOR + "Extracting links to app files..." + NO_COLOR)
    matic.extractHardlinks("FTPManager", "AppDomainGroup-group.com.skyjos.ftpmanager", "%", "TypeApp")
    matic.extractHardlinks("Files", "AppDomainGroup-group.com.apple.FileProvider.LocalStorage", "%", "TypeApp")
    matic.extractHardlinks("FilesHome", "HomeDomain", "%", "TypeApp")
    matic.extractHardlinks("FilesAppGroups", "AppDomainGroup-%", "%", "TypeAppGroup")
    #Export notes:
    matic.exportNotes()
    #Export contacts
    matic.exportContacts()
    #Export Whatsapp chats
    matic.exportWhatsappChats()




#Run program:
if __name__ == "__main__":
    main()





