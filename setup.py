#!/usr/bin/env python
# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
# Copyright (c) 2012, Peter Levi <peterlevi@peterlevi.com>
# This program is free software: you can redistribute it and/or modify it 
# under the terms of the GNU General Public License version 3, as published 
# by the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranties of 
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR 
# PURPOSE.  See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along 
# with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE

###################### DO NOT TOUCH THIS (HEAD TO THE SECOND PART) ######################

import os
import sys
import glob

try:
    import DistUtilsExtra.auto
except ImportError:
    print >> sys.stderr, 'To build ojo you need https://launchpad.net/python-distutils-extra'
    sys.exit(1)
assert DistUtilsExtra.auto.__version__ >= '2.18', 'needs DistUtilsExtra.auto >= 2.18'

def update_desktop_file(datadir):

    try:
        fin = file('ojo.desktop.in', 'r')
        fout = file(fin.name + '.new', 'w')

        for line in fin:            
            if 'Icon=' in line:
                line = "Icon=%s\n" % (datadir + 'media/ojo.svg')
            fout.write(line)
        fout.flush()
        fout.close()
        fin.close()
        os.rename(fout.name, fin.name)
    except (OSError, IOError), e:
        print ("ERROR: Can't find ojo.desktop.in")
        sys.exit(1)


class InstallAndUpdateDataDirectory(DistUtilsExtra.auto.install_auto):
    def run(self):
#        values = {'__ojo_data_directory__': "'%s'" % (self.prefix + '/share/ojo/'),
#                  '__version__': "'%s'" % self.distribution.get_version()}
        update_desktop_file(self.prefix + '/share/ojo/')
        DistUtilsExtra.auto.install_auto.run(self)


        
##################################################################################
###################### YOU SHOULD MODIFY ONLY WHAT IS BELOW ######################
##################################################################################

DistUtilsExtra.auto.setup(
    name='ojo',
    version='0.0.1',
    license='GPL-3',
    author='Peter Levi',
    author_email='peterlevi@peterlevi.com',
    description='A fast image viewer',
    long_description='A fast and pretty image viewer, convenient for photographic work',
    url='https://launchpad.net/ojo',
    cmdclass={'install': InstallAndUpdateDataDirectory},
    packages = ['ojo'],
    package_data = {'ojo': ["ojo/*.*", "media/*.*"]}
    )
