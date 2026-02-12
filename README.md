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

    F:\> python3 iphoneMatic.py F:\Backup\00008110-001A18D40EFB801E F:\DCIM
    f:\Backup\00008110-001A18D40EFB801E\14\14c9249d327cc25cd03cc7682175dfac56f79268 -> F:\DCIM\Camera\IMG_20250711_220111.PNG
    f:\Backup\00008110-001A18D40EFB801E\2e\2e3db5790e3b8c09ddb470ffa49573fc58eaf764 -> F:\DCIM\Camera\IMG_20250713_181255.HEIC
    f:\Backup\00008110-001A18D40EFB801E\e4\e40948bc14f5da406e0c667721eeac811df1ec3d -> F:\DCIM\Camera\VID_20250713_180244.MOV
    f:\Backup\00008110-001A18D40EFB801E\06\06d624a45988c5177d0cca2902868f24e2d459ad -> F:\DCIM\Camera\IMG_20250714_083054.JPG
    [..]

Example run (Linux):

    user1@machine1:/media/veracrypt1$ ./iphoneMatic.py Backup/00008110-001A18D40EFB801E/ DCIM/
    /media/veracrypt1/Backup/00008110-001A18D40EFB801E/5c/5cbc273a62c27bf11d657c0b2994c496d4cfdf26 -> /media/veracrypt1/DCIM/VID_20250801_100420.MOV
    /media/veracrypt1/Backup/00008110-001A18D40EFB801E/9e/9ed1c1ae594513c0f9696fb435888c8c6935cf15 -> /media/veracrypt1/DCIM/IMG_20250714_175224.HEIC
    /media/veracrypt1/Backup/00008110-001A18D40EFB801E/f6/f685f2ae9e4c54a5178423aa25b100bebfa6ce34 -> /media/veracrypt1/DCIM/IMG_20250725_144243.HEIC
    [..]


Good Luck!

--jm

Appendix 1: To view HEIC files natively in Windows, a codec is necessary. Microsoft charges $1 for the codec at:

      https://apps.microsoft.com/detail/9nmzlz57r3t7

But a free version is available in the .ZIP here:

      https://codecguide.com/media_foundation_codecs.htm

scroll to the middle of the page, click on Download.
A file named Media_Foundation_Codecs.zip will appear.
Uncompress it and double click on Microsoft.HEVCVideoExtension_2.3.8.0_neutral_~_8wekyb3d8bbwe.AppxBundle.
And now the Photos app can display .HEIC images from iPhone.

Cheers!

--jm

