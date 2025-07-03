# setup.py
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = [l.strip() for l in f if l.strip() and not l.startswith("#")]

setup(
    name="easy_import",
    version="0.1.0",
    description="CRL & i3 import pipeline and web interface",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    py_modules=["main", "run", "config", "utils"],
    include_package_data=True,
    package_data={
        # include any .js in the scrapers package
        "scrapers": ["*.js"],
        # if you have other non-Python assets:
        "web": ["static/css/*.css", "static/js/*.js", "static/images/*"],
    },
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "easy-import-pipeline = main:main",
            "easy-import-web      = run:app",
        ],
    },
)
