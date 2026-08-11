from setuptools import setup, find_packages

# Define test requirements
test_requirements = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.20.0",
    "pytest-cov>=4.0.0",
]

# Define development requirements
dev_requirements = [
    "black>=23.3.0",
    "isort>=5.12.0",
    "flake8>=6.0.0",
    "flake8-docstrings>=1.7.0",
    "pre-commit>=3.3.0",
] + test_requirements

setup(
    name="telegraphite",
    version="0.1.0",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "telethon>=1.24.0",
        "python-dotenv>=0.19.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "test": test_requirements,
        "dev": dev_requirements,
    },
    entry_points={
        "console_scripts": [
            "telegraphite=telegraphite.cli:main",
        ],
    },
    author="TeleGraphite Developer",
    author_email="example@example.com",
    description="A tool to fetch and save posts from public Telegram channels",
    keywords="telegram, telethon, scraper",
    python_requires=">=3.6",
)