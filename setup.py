"""Setup of Epson projector module."""

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('epson_projector/version.py') as fh:
    exec(fh.read())

setuptools.setup(
    name="epson_projector",
    version=__version__,
    author="Paweł Szafer",
    author_email="pszafer@gmail.com",
    description="Epson projector support for Python",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pszafer/epson_projector",
    install_requires=list(val.strip() for val in open('requirements.txt')),
    packages=['epson_projector'],
    keywords=['epson', 'projector'],
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ),
)
