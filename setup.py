from setuptools import setup, find_packages

setup(
    name="easy_import",
    version="0.1.0",
    description="CRL & i3 import pipeline and web interface",

    # This line makes run.py importable as the module “run”
    py_modules=["run"],

    # Everything under src/ becomes packages
    packages=find_packages(where="src"),
    package_dir={"": "src"},

    install_requires=[],
    entry_points={
        "console_scripts": [
            "easy-import-pipeline = main:main",
            "easy-import-web      = run:app",
        ],
    },
)
