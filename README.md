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

Good Luck!

--jm
