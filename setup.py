from dockercli.__init__ import __version__

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    description='Docker-CLI',
    author='Iryna Cherniavska',
    url='http://dockercli.com.',
    download_url='http://github.com/j-bennet/dockercli.',
    author_email='i[dot]chernyavska[at]gmail[dot]com.',
    version=__version__,
    install_requires=[
        'pygments>=2.0.2',
        'prompt-toolkit==0.38',
        'docker-py>=1.2.0',
        'tabulate>=0.7.5',
        'click>=4.0',
        'py-pretty>-0.1',
        'configobj >= 5.0.6',
        'pexpect>=3.3',
        'fuzzyfinder>=1.0.0'
    ],
    extras_require={
        'testing': [
            'pytest>=2.7.0',
            'mock>=1.0.1',
            'tox>=1.9.2'
        ],
    },
    entry_points={
        'console_scripts': 'dockercli = dockercli.main:cli'
    },
    packages=['dockercli'],
    package_data={'dockercli': ['dockerclirc']},
    scripts=[],
    name='dockercli',
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
