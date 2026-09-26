#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="fomod-simulator",
    version="1.0.0",
    description="Simulateur et installateur visuel de FOMOD Skyrim multi-plateforme (PyQt6)",
    author="Skyrim Tools",
    packages=find_packages(include=["python_app", "python_app.*"]),
    install_requires=[
        "PyQt6>=6.4.0",
        "py7zr>=0.20.0",
    ],
    entry_points={
        "console_scripts": [
            "fomod-simulator=python_app.main:main",
        ],
        "gui_scripts": [
            "fomod-simulator-gui=python_app.main:main",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Games/Entertainment",
    ],
)
