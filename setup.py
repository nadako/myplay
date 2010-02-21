from setuptools import setup

version = '0.1.0'

setup(
    name='myplay',
    version=version,
    description='Simple music player service',
    author='Dan Korostelev',
    author_email='nadako@gmail.com',
    url='http://code.google.com/p/myplay/', 
    license='GPL v3',
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
