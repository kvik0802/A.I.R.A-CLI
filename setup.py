from setuptools import setup, find_packages

setup(
    name="aira-cli",
    version="1.0.0",
    description="AIRA CLI — Autonomous Intelligence & Reasoning Agent Terminal",
    long_description=open("README.md", encoding="utf-8").read() if __import__("pathlib").Path("README.md").exists() else "",
    long_description_content_type="text/markdown",
    author="NSS Enterprises / Vicky",
    license="Apache-2.0",
    url="https://github.com/YOUR_USERNAME/AIRA-CLI",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.9",
    install_requires=[
        "anthropic>=0.25.0",
        "rich>=13.0.0",
        "prompt_toolkit>=3.0.0",
        "requests>=2.28.0",
        "psutil>=5.9.0",
        "pyperclip>=1.8.0",
        "python-dotenv>=1.0.0",
        "colorama>=0.4.6",
    ],
    entry_points={
        "console_scripts": [
            "aira=aira.main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
