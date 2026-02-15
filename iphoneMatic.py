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

    def extractHardlinks(self, subdir, domainFilter, pathFilter, typeStr="TypeNormal"):
        conn = sqlite3.connect(os.path.join(self.backup_dir, 'Manifest.db'))

        # simple query to get only media (without thumbnails)
        query = "SELECT fileId, domain, relativePath, flags, file FROM Files " \
                + "WHERE domain LIKE '" + domainFilter + "' AND relativePath LIKE '" + pathFilter + "' " \
                + "ORDER BY relativePath"

        MAX = 500000000000
        i = 0
        for subfile, domain, relpath, _, blob in conn.cursor().execute(query):
            # files are stored in subdirectories, that match first 2 characters of their names
            sourceSubdir = subfile[:2]

            relpath = removePrefix(relpath, "Media/DCIM/")
            relpath = removePrefix(relpath, "100APPLE/")
            relpath = removePrefix(relpath, "Media/PhotoData/Thumbnails/V2/PhotoData/Sync/100SYNCD/")
            relpath = removePrefix(relpath, "Media/PhotoData/Metadata/PhotoData/Sync/100SYNCD/")
            relpath = removePrefix(relpath, "Media/Profile/")
            relpath = removePrefix(relpath, "File Provider Storage/")

            if typeStr == "TypeWhatsapp":
                #Remove parent dirs:
                p = pathlib.Path(relpath)
                extension = p.suffix
                name = p.stem
                relpath = name + extension
                #Skip thumbnails:
                if extension == ".thumb" or extension == ".favicon" or extension == ".mmsthumb":
                    continue
                #Skip stickers:
                if extension == ".webp":
                    continue

            if typeStr == 'TypeAppGroup':
                domain = removePrefix(domain, "AppDomainGroup-")
                relpath = os.path.join(domain, relpath)

            # abspath will normalize path separators (windows uses reverse slashes, but relpath has forward ones)
            # doing it on sourceFile is not really necessary, but won't hurt
            sourceFile = os.path.abspath(os.path.join(self.backup_dir, sourceSubdir, subfile))
            outputDir = self.out_dir
            if subdir != "" and subdir != None:
                outputDir = os.path.join(outputDir, subdir)
            destFile = os.path.abspath(os.path.join(outputDir, relpath))

            if os.path.isfile(sourceFile):
                try:
                    self.processFile(sourceFile, destFile, blob, typeStr)
                except Exception as e:
                    print("ERROR processing file", destFile, ": ", e, '\n')
                i += 1

            if i == MAX:
                return


    def processFile(self, sourceFile, destFile, blob, typeStr):
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

    def exportNotes(self):
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
        contactsDbFilename = os.path.join(self.out_dir, "FilesHome/Library/AddressBook/AddressBook.sqlitedb")
        if not os.path.isfile(contactsDbFilename):
            print("WARNING: AddressBook.sqlite not found. Contacts will not be exported")
            return
        vcfDir = os.path.join(self.out_dir, "Contacts")
        ensureDirs(vcfDir)
        suffixDate = datetime.fromtimestamp(os.path.getmtime(contactsDbFilename)).strftime("%Y-%m-%d")
        vcfFilename = os.path.join(vcfDir, "contacts_" + suffixDate + ".vcf")
        if (os.path.isfile(contactsDbFilename)):
            matic.extractContactsVCF(contactsDbFilename, vcfFilename)





def main():
    desc = "Extracts images as hardlinks and sets the correct date \n" \
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
    matic.extractHardlinks("Camera", "CameraRollDomain", "%Media/DCIM%")
    #Some Thumbnails: 
    #    matic.extractHardlinks("FromMac", "CameraRollDomain", "%Media/PhotoData/Thumbnails/V2/PhotoData/Sync/100SYNCD/%")
    #More Thumbnails: 
    #    matic.extractHardlinks("Thumbnails", "CameraRollDomain", "%Media/PhotoData/Metadata/PhotoData/Sync/100SYNCD/%")
    matic.extractHardlinks("WhatsappProfilePictures", "AppDomainGroup-group.net.whatsapp.WhatsApp.shared", "%Media/Profile/%jpg")
    matic.extractHardlinks("Whatsapp", "AppDomainGroup-group.net.whatsapp.WhatsApp.shared", "%Message/Media%", "TypeWhatsapp")
    matic.extractHardlinks("FTPManager", "AppDomainGroup-group.com.skyjos.ftpmanager", "%", "TypeApp")
    matic.extractHardlinks("Files", "AppDomainGroup-group.com.apple.FileProvider.LocalStorage", "%", "TypeApp")
    matic.extractHardlinks("FilesHome", "HomeDomain", "%", "TypeApp")
    matic.extractHardlinks("FilesAppGroups", "AppDomainGroup-%", "%", "TypeAppGroup")
    #Export notes:
    matic.exportNotes()
    #Export contacts
    matic.exportContacts()




#Run program:
if __name__ == "__main__":
    main()





