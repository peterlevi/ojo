![Ojo Icon 128x128](http://i.imgur.com/C8RZmp2.png)

# Ojo - a fast and pretty image viewer. [pronounced 'oho']

## Ojo's goals:

1. Ojo's general goal is to become the best image viewer for photography-related work on Linux. To serve as the first step in organizing images.
2. It should start and show a single image as fast as possible - 90% of the time this is all that an image viewer is used for [it does now, need to keep it this way]
3. It should look great and be very unobstrusive when viewing images, so as not to distract from the main content
4. It should support RAW - this is lacking in most other images viewers. [it does now, for viewing, no export options]
5. It should be easy to quickly zoom-in to 100% to a certain part of the image. [we have zooming to 100% now and fit-to-window, but no other-finer grain zooming options]
6. It should provide some simple but convenient Trash, Copy and Move functionality. [nothing of these yet]

## Tech stack
Ojo is based on these technologies: Python, GTK and HTML/JS/CSS with jQuery in an embedded WebKit

## Installation
To install on Ubuntu, Mint or other Ubuntu derivatives:
```
sudo add-apt-repository -y ppa:ojo/daily
sudo apt-get update
sudo apt-get install ojo
```

## Run from code and contribute
1. First install ojo from the PPA above, this would pull all necessary dependencies. Alternatively, manually install the dependencies listed in [debian/control](debian/control).
2. Clone repo
3. Run [bin/ojo](bin/ojo), ojo should start.
4. Hack away, and open a pull-request when ready, or better - immediately once you decide what you want do. For new features, please sync with me before you start - peterlevi AT peterlevi.com. 

## Keyboard shortcuts

#### Browse and image modes
`Enter` - toggles between single image / browse mode  
`F11` - toggles fullscreen  
`Esc` / `Alt-F4` - exit  

#### Image mode:

`Arrows` and `PgUp/PgDown` - move back and forth between images  
`Home` / `End` - go to first/last image  
Press and hold mouse to zoom to specific point at 100%, then hold and move to "look around"  
`Z` - toggles zoom between 100% and Fit-to-window   
(Partial zooming is not supported yet)  

#### Browse mode:

`Arrows` and `PgUp/PgDown` - navigate around  
`Home` / `End` - go to first/last image or folder
`Tab` / `Shift-Tab` - switch focus between files and folders list   
`Enter` - select currently active link  
`Backspace` / `Alt-Up` / `Ctrl-Up` - move one folder up  
`Ctrl-/` - jump to the filesystem root  
`Alt-Left` / `Alt-Right` - go back / go forward in history  
`Ctrl +/=` / `Ctrl -` - increase / decrease size of the thumbnails  
`F5` - reload current folder (file changes are not reflected automatically)  
`Ctrl-F5` - refresh/recreate all thumbnails in the current folder  
  
`Ctrl-F` or `type text directly` - enter search/filter mode.  
Use this to filter images, folders and commands.  
E.g. type `.jpg` to see just JPEG files. Or type `date` to focus the `Sort by date` command.
The filtered view over the images remains if you go into Image mode and start cycling the images.
Press `Esc` to clear the filter and exit search mode (but keep in mind a second `Esc` will exit Ojo).

## Screenshots
Run Ojo with no parameters or by passing a path to a folder with images to start in Browse mode. Or press Enter while viewing a single image to enter Browse mode.
![Ojo - Browse mode](https://user-images.githubusercontent.com/1457048/83980909-f81ebb80-a921-11ea-94a3-8ffeb567bb6f.png)

Run Ojo with a path to an image to open it directly, or press Enter while in browse mode to open the selected image.
![Ojo - Single image view](https://user-images.githubusercontent.com/1457048/83980913-fc4ad900-a921-11ea-96a1-15715572e5ef.png)

The convenient search and filtering is always at your tips - directly start typing words while in Browse mode and Ojo will filter any files, folders, bookmarks, recent files or options that match all the typed words. Use this also to filter by extension, e.g. type ".cr3".
![Search and filtering](https://user-images.githubusercontent.com/1457048/83981136-eccc8f80-a923-11ea-8175-c3a3c3eadd3c.png)

Full EXIF viewing with search is available too, coming directly from the bundled amazing ExifTool by Phil Harvey (https://exiftool.org/).
![EXIF Info using ExifTool](https://user-images.githubusercontent.com/1457048/83981137-ee965300-a923-11ea-8e31-95d8b5d2715f.png)

Ojo in the Launcher.
![Ojo in the Launcher](https://user-images.githubusercontent.com/1457048/83980930-1e445b80-a922-11ea-98c3-92ce08c17a26.png)


