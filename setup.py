import setuptools
import os


def get_description():
    if os.path.isfile("README.md"):
        with open("README.md", "r") as fh:
            desc = fh.read()
    else:
        desc = ""
    return desc


setuptools.setup(
    name="tr4d3r",
    version="0.1.0",
    description="A rebalancing trade bot library. A good one.",
    long_description=get_description(),
    long_description_content_type="text/markdown",
    author="Pavel",
    author_email="pavelhurwicz@gmail.com",
    url="https://github.com/phurwicz/tr4d3r",
    packages=setuptools.find_packages(),
    install_requires=[
        # trading backend
        "robin_stocks",
        # messaging backend
        "python-telegram-bot",
        # data handling
        "numpy>=1.14",
        "pandas>=1.1.4",
        # utilities
        "deprecated",
        "rich",
        "tqdm",
        "wasabi",
        "wrappy",
    ],
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
