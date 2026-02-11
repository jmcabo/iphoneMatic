#!/usr/bin/env python3
#iphoneMatic 0.9 - by JMC - Based on https://github.com/alexisrozhkov/extract_media_from_backup/ and https://github.com/farcaller/bplist-python/
#Created: 2026-02-11
#Updated: 2026-02-11
import os
import shutil
import sqlite3
import argparse
import pathlib
from datetime import datetime
from argparse import RawTextHelpFormatter
from bplist import BPListReader

def removePrefix(s, prefix):
    if s.startswith(prefix):
        s = s[len(prefix) : ]
    return s


def processFile(sourceFile, destFile, blob, dryRun):
    #copy_file_create_subdirs(sourceFile, destFile)
    reader = BPListReader(blob)
    parsed = reader.parse()
    #print(parsed)
    lastModified = parsed["$objects"][1]["LastModified"]
    fileSize = parsed["$objects"][1]["Size"]
    #print(lastModified)
    #print(fileSize)

    suffix = datetime.fromtimestamp(lastModified).strftime("%Y%m%d_%H%M%S")

    p = pathlib.Path(destFile)
    extension = p.suffix
    name = p.stem
    destDir = str(p.parent)

    if name.startswith("IMG_"):
        name = "IMG_" + suffix

    #Replace IMG_ with VID_ in videos:
    if extension.lower() == ".mov":
        if name.startswith("IMG_"):
            name = "VID_" + name[4:]

    destFile = os.path.join(destDir, name + extension)

    #Show source and dest:
    print(sourceFile, "->", destFile)
    if dryRun:
        return

    dirName = os.path.dirname(destFile)
    #Create intermediate dirs:
    if not os.path.exists(dirName):
        try:
            os.makedirs(dirName)
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    #Hardlink:
    try:
        os.link(sourceFile, destFile)
    except FileExistsError:
        print("File exists")
        pass
    #Set MTIME:
    os.utime(destFile, (lastModified, lastModified))



def extractHardlinks(backup_dir, out_dir, dryRun):
    conn = sqlite3.connect(os.path.join(backup_dir, 'Manifest.db'))

    # simple query to get only media (without thumbnails)
    query = "SELECT fileId, domain, relativePath, flags, file FROM Files " \
            + "WHERE domain = 'CameraRollDomain' AND relativePath LIKE '%Media/DCIM%'"

    MAX = 500000000000
    i = 0
    for subfile, _, relpath, _, blob in conn.cursor().execute(query):
        # files are stored in subdirectories, that match first 2 characters of their names
        subdir = subfile[:2]

        relpath = removePrefix(relpath, "Media/DCIM/")
        relpath = removePrefix(relpath, "100APPLE/")

        # abspath will normalize path separators (windows uses reverse slashes, but relpath has forward ones)
        # doing it on sourceFile is not really necessary, but won't hurt
        sourceFile = os.path.abspath(os.path.join(backup_dir, subdir, subfile))
        destFile = os.path.abspath(os.path.join(out_dir, relpath))

        if os.path.isfile(sourceFile):
            try:
                processFile(sourceFile, destFile, blob, dryRun)
            except Exception as e:
                print(e, '\n')
            i += 1

        if i == MAX:
            return



def main():
    desc = "Extracts images as hardlinks and sets the correct date \n" \
            + "\nExample:  python3 iphoneMatic.py F:\\Backup\\00008110-001A18D40EFB801E F:\\DCIM" \
            + "\nNote: output datetimes are in local timezone"

    parser = argparse.ArgumentParser(description=desc, formatter_class=RawTextHelpFormatter)

    parser.add_argument('backup_dir', help='Location of backup directory')
    parser.add_argument('out_dir', help='Destination directory, relative to which ' \
                        'files would be copied, according to original directory structure')
    parser.add_argument('-n', '--pretend', action='store_true', help="Print source and dest but don't create hardlinks")

    args = parser.parse_args()

    extractHardlinks(args.backup_dir, args.out_dir, args.pretend)



#Run program:
if __name__ == "__main__":
    main()





