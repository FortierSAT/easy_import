from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = [l.strip() for l in f if l.strip() and not l.startswith("#")]

setup(
    name="easy_import",
    version="0.1.0",
    description="CRL & i3 import pipeline and web interface",
    # so that main.py, run.py, config.py, utils.py are importable
    py_modules=["main", "run", "config", "utils"],
    # everything in src/ under Python packages
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "easy-import-pipeline = main:main",
            "easy-import-web      = run:app",
        ],
    },
)
