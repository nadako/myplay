from setuptools import setup

setup(
    name='MyPlay',
    packages=['myplay'],
    entry_points={'console_scripts': [
                    'myplay = myplay.gui:main',
                    'myplay-service = myplay.service:main'
                 ]}
    )
