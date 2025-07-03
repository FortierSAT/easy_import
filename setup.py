from setuptools import setup, find_packages

# Pull in your requirements automatically
with open("requirements.txt") as f:
    install_requires = [
        line.strip()
        for line in f
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="easy_import",
    version="0.1.0",
    description="CRL & i3 import pipeline and web interface",

    # Make both main.py and run.py importable at top level
    py_modules=["main", "run"],

    # Everything under src/ that has an __init__.py becomes a package
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
