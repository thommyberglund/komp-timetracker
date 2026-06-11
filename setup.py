#!/usr/bin/env python3

"""
Setup script for Komp TimeTracker
"""

from setuptools import setup, find_packages
import os

# Read the requirements file
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

# Filter out comments and empty lines
requirements = [req for req in requirements if req and not req.startswith('#')]

setup(
    name="komp-timetracker",
    version="0.1.0",
    description="Parental Control Application for Bazzite Linux",
    author="Thommy Berglund",
    author_email="",
    url="https://github.com/thommyberglund/komp-timetracker",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "komp-control=komp_timetracker.ui.cli:main",
            "komp-timetracker-service=komp_timetracker.service:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Parents",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Security",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Systems Administration",
    ],
    data_files=[
        ('/etc/komp-timetracker', ['config.yaml']),
        ('/etc/systemd/system', ['packaging/systemd/komp-timetracker.service']),
        ('/usr/local/bin', ['scripts/komp-control']),
    ],
)
