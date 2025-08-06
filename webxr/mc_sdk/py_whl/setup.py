from setuptools import setup, find_packages

setup(
    name="mc_sdk_py",
    version="0.1.5",
    packages=find_packages(),
    package_data={"mc_sdk_py": ["*.so"]},
)
