# iphoneMatic
Takes an iphone backup and creates a directory of all the images but using hardlinks so no extra space occupied. Also uses the IMG_DATE_TIME format.
Created: 2026-02-11

The backup can be created with iTunes or the Apple Devices application.

The Apple Devices application is available for free in the Microsoft Store for Windows.

I used a lightning to USB 2.0 cable (data cable), because the charger cables (lightning to USB-Type-C) didn't produce a reaction from Apple Devices.

The source directory must be the one that contains the file Manifest.db, which in windows will be something like:

             C:\Users\YourUser\Apple\MobileSync\Backup\00008110-001A18D40EFB801E\

The Apple Devices app doesn't let you change the destination directory. I was going to run out of space in C:\ and needed to place it in a USB drive. Preferably inside a veracrypt container mounted in F:. No problem, a junction can be created so that the Apple Devices app always backs up to F:\Backup:

             mklink /J "C:\Users\YourUser\Apple\MobileSync\Backup" "F:\Backup"
             
Example command line (Windows):

            python3 iphoneMatic.py F:\\Backup\\00008110-001A18D40EFB801E F:\\DCIM"

Example run (Linux):

    user1@machine1:/media/veracrypt1$ ./iphoneMatic.py Backup/00008110-001A18D40EFB801E/ DCIM/
    /media/veracrypt1/Backup/00008110-001A18D40EFB801E/5c/5cbc273a62c27bf11d657c0b2994c496d4cfdf26 -> /media/veracrypt1/DCIM/VID_20250801_100420.MOV
    /media/veracrypt1/Backup/00008110-001A18D40EFB801E/9e/9ed1c1ae594513c0f9696fb435888c8c6935cf15 -> /media/veracrypt1/DCIM/IMG_20250714_175224.HEIC
    /media/veracrypt1/Backup/00008110-001A18D40EFB801E/f6/f685f2ae9e4c54a5178423aa25b100bebfa6ce34 -> /media/veracrypt1/DCIM/IMG_20250725_144243.HEIC
    [..]


Good Luck!

--jm
