import setuptools


with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("clothion/__init__.py") as f:
    v = [line for line in f if line.startswith("__version__")][0].split('"')[1]

reqs = ["fastapi[all]~=0.95"]

extras_require = {
    "test": ["pytest~=7.0", "pytest-cov~=3.0", "coverage-badge~=1.0"],
    "hook": ["pre-commit~=3.0"],
    "lint": ["isort~=5.9", "black~=23.1", "flake518~=1.2", "darglint~=1.8"],
    "docs": ["mkdocs-material~=9.0", "mkdocstrings[python]~=0.18", "mike~=1.1"],
}
extras_require["all"] = sum(extras_require.values(), [])
extras_require["dev"] = (
    extras_require["test"] + extras_require["hook"] + extras_require["lint"] + extras_require["docs"]
)

setuptools.setup(
    name="clothion",
    version=v,
    author="Nicolas REMOND",
    author_email="remondnicola@gmail.com",
    description="Reserved",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/astariul/clothion",
    packages=setuptools.find_packages(),
    install_requires=reqs,
    extras_require=extras_require,
    entry_points={"console_scripts": ["clothion=clothion.app:serve"]},
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
