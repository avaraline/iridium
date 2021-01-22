import os

from setuptools import find_packages, setup

import iridium

BASE_DIR = os.path.dirname(__file__)


def get_description():
    with open(os.path.join(BASE_DIR, "README.md")) as readme:
        return readme.read().strip()


def get_requirements():
    with open(os.path.join(BASE_DIR, "requirements.txt")) as reqs:

        def valid_req(s):
            return s and not s.startswith("#")

        return list(filter(valid_req, map(str.strip, reqs.read().splitlines())))


setup(
    name="iridium",
    version=iridium.version,
    description="Discord IRC bridge.",
    long_description=get_description(),
    long_description_content_type="text/markdown",
    author="Dan Watson",
    author_email="dcwatson@gmail.com",
    url="https://github.com/dcwatson/iridium",
    license="MIT",
    packages=find_packages(),
    install_requires=get_requirements(),
    entry_points={
        "console_scripts": [
            "iridium=iridium.__main__:main",
        ]
    },
    classifiers=[
        "Development Status :: 1 - Planning",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
    ],
)
