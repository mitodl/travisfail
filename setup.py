from setuptools import setup, find_packages

setup(
    name='travisfail',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Click',
        'requests'
    ],
    entry_points='''
        [console_scripts]
        travisfail=main:cli
    ''',
)
