from setuptools import setup, find_packages

setup(
    name="vtrim",
    version="0.1.4",
    author="Chiawei Lee",
    author_email="ljw@live.jp",
    description="Trim detects people in videos and trims segments—without re-encoding—preserving quality and speed.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/ai-libx/vtrim",
    packages=find_packages(),
    package_data={
        "vtrim": ["*.pt", "*.onnx"],
    },
    install_requires=[],
    entry_points={
        "console_scripts": [
            "vtrim=vtrim.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    license="Apache License v2",
)