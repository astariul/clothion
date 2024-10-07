import setuptools


with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("clothion/__init__.py") as f:
    v = [line for line in f if line.startswith("__version__")][0].split('"')[1]

reqs = [
    "fastapi[all]~=0.110",
    "omegaconf~=2.3",
    "sqlalchemy~=2.0",
    "psycopg2-binary~=2.9",
    "notion-client~=2.1.0",
    "python-dateutil~=2.8",
]

extras_require = {
    "admin": ["alembic~=1.10"],
    "test": ["pytest~=8.0", "pytest-cov~=5.0", "coverage-badge~=1.0"],
    "lint": ["black~=24.2", "ruff~=0.1", "pre-commit>=3.2,<5.0"],
}
extras_require["all"] = sum(extras_require.values(), [])
extras_require["dev"] = extras_require["test"] + extras_require["lint"]

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
    package_data={"clothion": ["templates/*"]},
    install_requires=reqs,
    extras_require=extras_require,
    entry_points={"console_scripts": ["clothion=clothion.app:serve"]},
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
)
