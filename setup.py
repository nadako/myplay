#
# This file is part of MyPlay.
#
# Copyright 2010 Dan Korostelev <nadako@gmail.com>
#
# MyPlay is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# MyPlay is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with MyPlay.  If not, see <http://www.gnu.org/licenses/>.
#
from setuptools import setup

version = '0.1.0'

setup(
    name='myplay',
    version=version,
    description='Simple music player service',
    author='Dan Korostelev',
    author_email='nadako@gmail.com',
    url='http://code.google.com/p/myplay/', 
    license='GPL',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: No Input/Output',
        'Environment :: Console',
        'Environment :: X11 Applications :: GTK',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2.6',
        'Topic :: Desktop Environment :: Gnome',
        'Topic :: Multimedia :: Sound/Audio :: Players',
    ],

    packages=['myplay'],
    entry_points={
        'console_scripts': [
            'myplay = myplay.gui:main',
            'myplay-service = myplay.service:main'
        ]
    }
)
